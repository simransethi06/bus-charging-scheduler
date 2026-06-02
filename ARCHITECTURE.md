# ARCHITECTURE.md — BusGrid Charging Scheduler

---

## 1. Scheduling approach

### What I chose: Weighted event-driven simulation with pluggable soft rules

The scheduler runs in two passes:

**Pass 1 — Feasibility (hard constraints):** For each bus, generate a valid charging plan — a sequence of stations where it must charge to complete the trip without running out of range. The algorithm is greedy: drive as far as possible before charging, always stopping at the last reachable station before range would expire. This guarantees validity in one linear pass.

**Pass 2 — Contention resolution (soft constraints):** At each station, when multiple buses want to charge around the same time, rank them using a weighted composite score. Three built-in soft rules contribute:
- **IndividualWaitRule** — penalises long waits for any single bus
- **OperatorFairnessRule** — penalises operators whose buses are already waiting more than others
- **OverallThroughputRule** — prefers earliest-arriving bus (minimises total delay)

Rules are combined linearly: `score = Σ (rule_i.penalty × weight_i)`. The bus with the lowest score charges first.

### Why this approach — not a pure MILP or CP solver

A mixed-integer program would find a globally optimal schedule but:
- Optimality criterion isn't stable ("what matters operationally only becomes clear once we run real buses")
- Adding a new rule to a MILP requires reformulating constraints — non-trivial
- A rule-engine scales linearly; a MILP's search space grows exponentially

A greedy rule engine with explicit, composable rules matches the real operational lifecycle: tune a weight, add a rule, observe the effect, repeat. Every rule is a Python class with a single `penalty()` method. No solver, no reformulation.

### Why not a pure FIFO queue

Pure FIFO (first-come, first-served at arrival) is too rigid: it ignores operator equity and global throughput. The weight system lets you dial between "every bus is equal" (all weights = 1) and "operator X gets priority" (raise operator weight) without changing any logic.

---

## 2. Data structure design

### Guiding principle: separate *world* from *schedule* from *output*

```
scenario.json
├── meta          # human label, tags
├── world         # everything physical: route, stations, physics, operators
│   ├── route     # segments with distances — not hardcoded BLR/KCH
│   ├── stations  # num_chargers, charger_power — not assumed to be 1
│   └── physics   # battery_range, charge_duration, speed — all tunable
├── weights       # soft-rule weights — one obvious place
└── buses         # the departure schedule
```

The output (`ScheduleResult`) is a separate object: `BusTimeline` per bus, `StationLog` per station. It is never written back into the input files.

### Why JSON with this schema

- Human-readable and VCS-friendly
- Adding a new field (e.g. `"electricity_cost_per_kwh"`) requires zero code changes if the engine doesn't yet consume it — it's just ignored
- The schema is self-describing: a new engineer can read one scenario file and understand the entire world

---

## 3. Changes I anticipated — and how the design handles each

Every item below can be done **through data alone, with no code changes to the engine**, unless noted.

| Anticipated change | How the design handles it |
|---|---|
| **More stations on the route** | Add segments to `route.segments` and entries to `stations`. The engine walks `segments` dynamically — no hardcoded list. |
| **Different segment distances** | Change `distance_km` in the segment. Physics recalculates automatically. |
| **More chargers at a station** | Set `"num_chargers": 2` (or N). `charger_free` is a list of N slots; the engine already picks the best free slot. |
| **Different battery range** | Change `battery_range_km` in `world.physics`. |
| **Different charge duration** | Change `charge_duration_min`. |
| **Different travel speed** | Change `speed_kmph`. |
| **More buses** | Add rows to `buses`. No upper limit. |
| **New operator** | Add to `operators` list. The engine treats operators generically. |
| **New route (different cities)** | Create a new scenario JSON with a new `route.id` and different segments. Nothing in the engine is specific to BLR/KCH. |
| **Multiple routes sharing a station** | Stations are identified by ID only. Two scenarios referencing the same station ID can be merged. (Multi-route scheduling would need a code change to `Scheduler.run` — but the data model is already compatible.) |
| **Priority buses / operators** | Add `"priority_tier"` to the operator (already in schema). Write a `PriorityBusRule` (5 lines) and pass it in. Zero engine changes. |
| **Time-of-day electricity cost** | Add `"electricity_cost_schedule": [{"start": "18:00", "end": "22:00", "cost": 12.5}]` to a station. Write an `ElectricityCostRule`. Zero engine changes. |
| **Driver shift constraints** | Add `"driver_shift_end_min": 1320` to each bus. Write a `DriverShiftRule`. Zero engine changes. |
| **Charger power levels** | `charger_power` is already in the station schema (`"fast"`, `"slow"`, `"ultra"`). Charge duration could be made a function of charger power. |
| **Buses that don't start with full charge** | Add `"initial_charge_km"` override per bus. The engine already reads `physics.initial_charge_km` — making it per-bus is a two-line change in `engine.py`. |
| **Bidirectional route with asymmetric segment distances** | The route is direction-aware. `distance_between()` works in either direction by reversing the segment list. |
| **New soft rule** | Subclass `SoftRule`, override `penalty()`, pass to `Scheduler(extra_rules=[...])`. The engine calls all rules in the list uniformly. |
| **New hard rule** | Add a check in `_generate_charging_plan()` or post-simulation validation. Returns a violation string that surfaces in the UI. |
| **Different weight per bus** | Currently weights are scenario-level. Per-bus weights would require adding a `weights` field to each bus entry — a small schema extension, no engine rewrite. |
| **Scenario with 100+ buses** | The engine is O(B × S) where B = buses, S = stations. For 100 buses and 10 stations that's 1000 events — trivially fast. |
| **Non-fixed charge duration** (e.g. partial charges) | Add `charge_to_pct` per event. The engine would compute duration from kWh delta. Schema-ready; engine needs a small update. |
| **Adding a scenario via UI** | The UI calls `get_all_scenarios()` which glob-scans `scenarios/`. Drop in a new JSON and refresh. |

---

## 4. How to change a weight

**In the UI:** use the sidebar sliders. Takes effect instantly.

**In a scenario file:** edit the `weights` block:
```json
"weights": { "individual": 1.0, "operator": 2.0, "overall": 1.0 }
```

**In code:**
```python
result = run_scenario("scenarios/scenario_1.json",
                      weight_overrides={"operator": 2.0})
```

There is exactly one place weights are stored per scenario. They are never scattered through logic.

---

## 5. How to add a new rule

```python
# In scheduler/engine.py (or any module you import from)

class ElectricityCostRule(SoftRule):
    """
    Prefer charging during off-peak hours.
    Penalty = cost_rate × weight_overall.
    """
    name = "electricity_cost"
    weight_key = "overall"

    # Cost schedule: list of (start_min, end_min, cost_per_kwh)
    PEAK_HOURS = [(18*60, 22*60, 15.0)]
    OFF_PEAK_RATE = 8.0

    def penalty(self, candidate_bus, candidate_arrive, queue_finish_time,
                all_buses, timelines_so_far, operator_stats, weights):
        charge_time = max(candidate_arrive, queue_finish_time)
        # Time of day (mod 24h)
        tod = charge_time % (24 * 60)
        for start, end, rate in self.PEAK_HOURS:
            if start <= tod <= end:
                return weights.overall * rate
        return weights.overall * self.OFF_PEAK_RATE

# Wire it in
from scheduler.runner import run_scenario
result = run_scenario("scenarios/scenario_1.json",
                      extra_rules=[ElectricityCostRule()])
```

The engine doesn't change. The rule is self-contained.

---

## 6. Assumptions made

1. **Speed is uniform** — no traffic, no terrain variation. `speed_kmph` is set in physics.

2. **Charging always fills to 100%** — partial charging is not modelled (would require per-bus state of charge).

3. **Buses depart on time** — no delay at origin. A `departure_delay_min` field could be added trivially.

4. **A bus that arrives at a station must charge there** — once a bus's plan includes a station, it commits. In reality a bus might skip a charging stop if it calculates it doesn't need it (e.g., if a previous wait caused it to "borrow" time). This assumption keeps the simulation deterministic.

5. **Contention resolution is greedy, not globally optimal** — the weighted scorer picks the best next bus at each decision point but does not look ahead. A true optimum would require solving a scheduling problem across all buses simultaneously. For the operational scale described (20–200 buses), greedy with good rules is operationally sufficient and far more interpretable.

6. **All four stations are visited independently** — buses don't share a queue across stations. This is physically correct: each station is geographically separate.

7. **The route is fixed and linear** — no branching routes, no loop segments. The `segments` list is the full description. If the route changes shape, only the JSON changes.

8. **Terminals (BLR, KCH) have infinite slow-charger capacity** — they never queue. Only A, B, C, D are scheduling stations.

---

## 7. What I'd do next

- **Priority buses:** one new rule, one new field (`priority_tier`) already in the operator schema.
- **Multi-route station sharing:** extend `Scheduler.run()` to accept multiple scenarios and merge their station queues.
- **Historical replay:** store `ScheduleResult` as JSON; build a comparison view between weight configurations.
- **Partial charging:** add SOC tracking per bus — requires model changes but the data schema is already extensible.
- **Time-of-day costs:** already shown above — one rule, no engine changes.