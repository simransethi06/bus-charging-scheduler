# BusGrid · Electric Bus Charging Scheduler

A scheduling system for electric buses running the **Bengaluru ↔ Kochi** route, built with Python + Streamlit.

---

## Quick start

```bash
git clone <repo-url>
cd bus-charging-scheduler
pip install -r requirements.txt
streamlit run app.py
```

Open `http://localhost:8501`.

---

## How to change a weight

Open the **sidebar sliders** in the UI — weights update the schedule live.

To change a scenario's *default* weight, edit the `weights` block in its JSON:

```json
// scenarios/scenario_4.json
"weights": {
  "individual": 1.0,
  "operator":   2.0,   // ← change this
  "overall":    1.0
}
```

To override weights in code:

```python
from scheduler.runner import run_scenario

result = run_scenario(
    "scenarios/scenario_1.json",
    weight_overrides={"individual": 2.0, "operator": 0.5, "overall": 1.0}
)
```

---

## How to add a new rule

1. Subclass `SoftRule` in `scheduler/engine.py` (or any file):

```python
class PriorityBusRule(SoftRule):
    """Give priority buses (e.g. emergency coaches) a lower penalty."""
    name = "priority_bus"
    weight_key = "individual"

    def penalty(self, candidate_bus, candidate_arrive, queue_finish_time,
                all_buses, timelines_so_far, operator_stats, weights):
        # Priority buses get negative penalty → they jump the queue
        if candidate_bus.operator_id == "priority":
            return -9999.0
        return 0.0
```

2. Pass it in:

```python
from scheduler.runner import run_scenario
from scheduler.engine import PriorityBusRule

result = run_scenario("scenarios/scenario_1.json", extra_rules=[PriorityBusRule()])
```

That's it. The engine doesn't change.

---

## Project layout

```
.
├── app.py                    # Streamlit UI (one file)
├── requirements.txt
├── scenarios/
│   ├── scenario_1.json       # Even spacing (baseline)
│   ├── scenario_2.json       # Bunched start
│   ├── scenario_3.json       # Asymmetric load
│   ├── scenario_4.json       # Operator-heavy (KPN dominant, w_op=2.0)
│   └── scenario_5.json       # Worst-case convergence
└── scheduler/
    ├── models.py             # Pure data structures
    ├── loader.py             # JSON → domain objects
    ├── engine.py             # Scheduling engine + soft rules
    └── runner.py             # Glue: load + run → result
```

---

## Adding a new scenario

Create `scenarios/scenario_6.json` following the existing schema — the UI picks it up automatically, no code changes.

---

## Architecture

See `ARCHITECTURE.md` for design decisions, anticipated changes, and extension guide.