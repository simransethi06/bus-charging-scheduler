"""
engine.py — The scheduling engine.

Design:
  - ChargingPlanGenerator: decides WHICH stations each bus uses (feasibility pass)
  - RuleEngine: scores candidate orderings using pluggable soft rules + weights
  - Scheduler: orchestrates the full run and resolves charger contention

Extending:
  - Add a new soft rule → subclass SoftRule, return a penalty, register it.
  - Add a hard rule → add a check in _validate_plan().
  - More buses/stations/routes → no code changes needed.
  - Different weights → pass a different Weights object in.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Callable

from scheduler.models import (
    Bus, Direction, Route, Station, Physics, Operator,
    Weights, ChargeEvent, BusTimeline, StationLog, ScheduleResult
)


# ─────────────────────────────────────────────
#  Soft-rule interface (open for extension)
# ─────────────────────────────────────────────

class SoftRule:
    """
    Base class for soft scheduling rules.
    Each rule computes a penalty for placing `candidate_bus` next in a queue.

    To add a new rule:
      1. Subclass SoftRule.
      2. Override penalty().
      3. Pass an instance to Scheduler(extra_rules=[...]).

    The RuleEngine multiplies each penalty by its weight and sums them.
    """
    name: str = "unnamed_rule"
    weight_key: str = "overall"   # which Weights field to multiply by

    def penalty(
        self,
        candidate_bus: Bus,
        candidate_arrive: float,
        queue_finish_time: float,         # when charger becomes free
        all_buses: List[Bus],
        timelines_so_far: Dict[str, BusTimeline],
        operator_stats: Dict[str, Dict],  # pre-computed per-operator stats
        weights: Weights,
    ) -> float:
        raise NotImplementedError


class IndividualWaitRule(SoftRule):
    """Penalise long wait for this specific bus."""
    name = "individual_wait"
    weight_key = "individual"

    def penalty(self, candidate_bus, candidate_arrive, queue_finish_time,
                all_buses, timelines_so_far, operator_stats, weights):
        wait = max(0.0, queue_finish_time - candidate_arrive)
        return weights.individual * wait


class OperatorFairnessRule(SoftRule):
    """
    Penalise if this operator's buses are already waiting more than others.
    High operator weight → scheduler tries harder to spread load across operators.
    """
    name = "operator_fairness"
    weight_key = "operator"

    def penalty(self, candidate_bus, candidate_arrive, queue_finish_time,
                all_buses, timelines_so_far, operator_stats, weights):
        op_id = candidate_bus.operator_id
        op_avg = operator_stats.get(op_id, {}).get("avg_wait", 0.0)
        # If this operator already has a high average wait, reduce its penalty
        # (i.e., prefer to let it charge sooner). We return a negative offset.
        return weights.operator * (-op_avg)


class OverallThroughputRule(SoftRule):
    """Minimise total network delay — prefer earliest-arriving bus."""
    name = "overall_throughput"
    weight_key = "overall"

    def penalty(self, candidate_bus, candidate_arrive, queue_finish_time,
                all_buses, timelines_so_far, operator_stats, weights):
        # Earlier arrival → lower penalty → gets priority
        return weights.overall * candidate_arrive


# ─────────────────────────────────────────────
#  Plan generator: which stations does each bus charge at?
# ─────────────────────────────────────────────

def _generate_charging_plan(
    bus: Bus,
    route: Route,
    station_ids: List[str],
    physics: Physics,
) -> List[str]:
    """
    Greedy: drive as far as possible before charging.
    Always charges at the last feasible station before range runs out.

    Returns ordered list of station IDs the bus will charge at.
    """
    stops_in_order = route.stops_for_direction(bus.direction)
    stations_in_order = [s for s in stops_in_order if s in station_ids]

    origin = stops_in_order[0]
    destination = stops_in_order[-1]

    plan: List[str] = []
    current_stop = origin
    remaining_range = physics.initial_charge_km

    while current_stop != destination:
        # Find next stop
        idx = stops_in_order.index(current_stop)
        if idx + 1 >= len(stops_in_order):
            break
        next_stop = stops_in_order[idx + 1]
        dist = route.distance_between(current_stop, next_stop)

        if dist > remaining_range:
            # Must charge at current stop if it's a station
            if current_stop in station_ids and current_stop not in plan:
                plan.append(current_stop)
                remaining_range = physics.battery_range_km
            else:
                # Should not happen with valid route geometry — flag it
                raise ValueError(
                    f"Bus {bus.id} cannot reach {next_stop} from {current_stop} "
                    f"(range={remaining_range:.0f}km, dist={dist:.0f}km)"
                )
        else:
            # Can we skip all remaining stations and still reach destination?
            dist_to_dest = route.distance_between(current_stop, destination)
            if dist_to_dest <= remaining_range:
                break   # no more charging needed

            # Greedy: look ahead — charge at last possible station
            # Find farthest station we can reach
            furthest_reachable = None
            dist_so_far = 0.0
            for future_stop in stops_in_order[idx + 1:]:
                d = route.distance_between(current_stop, future_stop)
                if d <= remaining_range:
                    if future_stop in station_ids:
                        furthest_reachable = future_stop
                else:
                    break

            if furthest_reachable:
                dist_to_furthest = route.distance_between(current_stop, furthest_reachable)
                remaining_range -= dist_to_furthest
                current_stop = furthest_reachable

                # Check if we can make it from here without another charge
                dist_from_here_to_dest = route.distance_between(current_stop, destination)
                if dist_from_here_to_dest > physics.battery_range_km:
                    plan.append(current_stop)
                    remaining_range = physics.battery_range_km
                else:
                    plan.append(current_stop)
                    remaining_range = physics.battery_range_km
            else:
                remaining_range -= dist
                current_stop = next_stop

    return plan


# ─────────────────────────────────────────────
#  Charger queue: per-station priority queue
# ─────────────────────────────────────────────

@dataclass(order=True)
class QueueEntry:
    score: float
    arrive_time: float
    bus_id: str = field(compare=False)


# ─────────────────────────────────────────────
#  Main Scheduler
# ─────────────────────────────────────────────

class Scheduler:
    """
    Event-driven scheduler.

    Algorithm:
      1. For each bus, compute charging plan (which stations).
      2. For each station, collect all buses that want to charge there.
      3. Resolve ordering using weighted soft-rule scoring.
      4. Propagate wait times forward through each bus's journey.
    """

    def __init__(self, extra_rules: Optional[List[SoftRule]] = None):
        self.rules: List[SoftRule] = [
            IndividualWaitRule(),
            OperatorFairnessRule(),
            OverallThroughputRule(),
        ]
        if extra_rules:
            self.rules.extend(extra_rules)

    def run(
        self,
        scenario_id: str,
        route: Route,
        stations: List[Station],
        physics: Physics,
        operators: List[Operator],
        buses: List[Bus],
        weights: Weights,
    ) -> ScheduleResult:
        station_ids = {s.id for s in stations}
        station_map = {s.id: s for s in stations}
        operator_map = {o.id: o for o in operators}

        # ── Step 1: charging plans ──────────────────────────────────────────
        plans: Dict[str, List[str]] = {}
        for bus in buses:
            plans[bus.id] = _generate_charging_plan(bus, route, station_ids, physics)

        # ── Step 2: compute raw arrival times (no waiting) ─────────────────
        #    arrival_at[bus_id][stop_id] = earliest possible arrival ignoring queues
        raw_arrivals: Dict[str, Dict[str, float]] = {}
        for bus in buses:
            stops = route.stops_for_direction(bus.direction)
            t = bus.departure_time_min
            arrivals = {stops[0]: t}
            for i in range(len(stops) - 1):
                d = route.distance_between(stops[i], stops[i+1])
                t += (d / physics.speed_kmph) * 60
                arrivals[stops[i+1]] = t
            raw_arrivals[bus.id] = arrivals

        # ── Step 3: event-driven simulation ────────────────────────────────
        #    charger_free_at[station_id][charger_slot] = time charger is free
        charger_free: Dict[str, List[float]] = {
            s.id: [0.0] * s.num_chargers for s in stations
        }
        # actual_time[bus_id] = current time (accounting for accumulated waits)
        actual_time: Dict[str, float] = {
            b.id: b.departure_time_min for b in buses
        }
        # accumulated delay per bus
        accumulated_delay: Dict[str, float] = {b.id: 0.0 for b in buses}

        charge_events: Dict[str, List[ChargeEvent]] = {b.id: [] for b in buses}
        timelines_built: Dict[str, BusTimeline] = {}

        # Process each station in route order (using forward order as canonical)
        # For bidirectional routes, buses visit stations in their own order.
        # We process events chronologically across all buses and stations.

        # Build a flat event list: (arrive_time, bus_id, station_id)
        # Then process station by station, resolving queues.

        # For each station, collect all (arrive_time, bus_id) sorted by arrival
        station_events: Dict[str, List[Tuple[float, str]]] = {s.id: [] for s in stations}

        for bus in buses:
            plan = plans[bus.id]
            stops = route.stops_for_direction(bus.direction)
            for station_id in plan:
                # raw arrival at this station (no delays yet — we'll add them)
                arr = raw_arrivals[bus.id][station_id]
                station_events[station_id].append((arr, bus.id))

        # Sort each station's queue by raw arrival
        for sid in station_events:
            station_events[sid].sort(key=lambda x: x[0])

        # ── Step 4: simulate each station with delay propagation ────────────
        # We need a topological approach: process stations in the order buses visit them.
        # Since buses travel in one direction, we process forward stations in route order,
        # but buses from KCH visit them in reverse. We handle both by tracking actual_time.

        # Collect all stations that any bus visits, in chronological order of first visit
        all_charge_events_flat: List[Tuple[float, str, str]] = []  # (arrive, bus_id, station_id)
        for bus in buses:
            plan = plans[bus.id]
            t = bus.departure_time_min
            stops = route.stops_for_direction(bus.direction)
            for i in range(len(stops) - 1):
                seg_dist = route.distance_between(stops[i], stops[i+1])
                t += (seg_dist / physics.speed_kmph) * 60
                if stops[i+1] in station_ids and stops[i+1] in plan:
                    all_charge_events_flat.append((t, bus.id, stops[i+1]))

        # Sort globally by raw arrival time
        all_charge_events_flat.sort()

        # Simulate: for each charge event in arrival order, account for actual delays
        # We track per-bus "current time" which accumulates waits
        bus_current_time: Dict[str, float] = {b.id: b.departure_time_min for b in buses}
        bus_stops_visited: Dict[str, int] = {b.id: 0 for b in buses}  # index into stops list
        bus_stops: Dict[str, List[str]] = {
            b.id: route.stops_for_direction(b.direction) for b in buses
        }
        bus_plans: Dict[str, List[str]] = plans  # alias

        # Build per-bus stop-distance lookup
        def travel_time_to_next_stop(bus_id: str, from_stop: str, to_stop: str) -> float:
            d = route.distance_between(from_stop, to_stop)
            return (d / physics.speed_kmph) * 60

        # Re-simulate with actual times
        # For each bus, track which stops have been visited and current clock
        bus_position: Dict[str, str] = {b.id: bus_stops[b.id][0] for b in buses}

        # We process charge events per bus in their route order
        station_logs: Dict[str, StationLog] = {s.id: StationLog(s.id) for s in stations}

        # For each bus, simulate its journey stop by stop
        bus_timelines_list: List[BusTimeline] = []
        violations: List[str] = []

        for bus in buses:
            stops = bus_stops[bus.id]
            plan = bus_plans[bus.id]
            t = bus.departure_time_min
            prev_stop = stops[0]
            events: List[ChargeEvent] = []
            range_left = physics.initial_charge_km

            for i in range(1, len(stops)):
                cur_stop = stops[i]
                d = route.distance_between(prev_stop, cur_stop)
                travel = (d / physics.speed_kmph) * 60

                # Hard check: range constraint
                if d > range_left + 0.01:
                    violations.append(
                        f"Bus {bus.id}: range exceeded between {prev_stop}→{cur_stop} "
                        f"(need {d:.0f}km, have {range_left:.0f}km)"
                    )

                t += travel
                range_left -= d

                if cur_stop in station_ids and cur_stop in plan:
                    # Find earliest free charger slot at this station
                    s_obj = station_map[cur_stop]
                    charger_slots = charger_free[cur_stop]

                    # Pick the slot that minimises wait
                    best_slot = min(range(len(charger_slots)), key=lambda i: charger_slots[i])
                    free_at = charger_slots[best_slot]
                    charge_start = max(t, free_at)

                    # Compute score for this bus to decide ordering
                    # (In the multi-bus queue case, we use the weighted score)
                    wait = charge_start - t
                    charge_end = charge_start + physics.charge_duration_min

                    ev = ChargeEvent(
                        bus_id         = bus.id,
                        station_id     = cur_stop,
                        arrive_time_min= t,
                        queue_start_min= t,
                        charge_start_min=charge_start,
                        charge_end_min = charge_end,
                    )
                    events.append(ev)
                    station_logs[cur_stop].events.append(ev)

                    # Update charger availability
                    charger_slots[best_slot] = charge_end
                    t = charge_end
                    range_left = physics.battery_range_km  # recharged to full

                prev_stop = cur_stop

            # Final arrival
            arrival = t
            tl = BusTimeline(
                bus              = bus,
                charge_events    = events,
                departure_time_min=bus.departure_time_min,
                arrival_time_min = arrival,
            )
            bus_timelines_list.append(tl)

        # Sort station logs chronologically
        for sl in station_logs.values():
            sl.events.sort(key=lambda e: e.charge_start_min)

        # ── Step 5: weighted re-ordering at contested stations ──────────────
        # If multiple buses want the same charger near the same time,
        # re-order them using the soft-rule scoring.
        bus_timeline_map = {tl.bus.id: tl for tl in bus_timelines_list}
        self._apply_weighted_ordering(
            buses, bus_plans, bus_stops, station_map, physics,
            station_logs, charger_free, weights, route
        )

        return ScheduleResult(
            scenario_id   = scenario_id,
            weights       = weights,
            bus_timelines = bus_timelines_list,
            station_logs  = station_logs,
            is_valid      = len(violations) == 0,
            violations    = violations,
        )

    def _score(
        self,
        bus: Bus,
        arrive: float,
        queue_free: float,
        all_buses: List[Bus],
        timelines_so_far: Dict[str, BusTimeline],
        operator_stats: Dict[str, Dict],
        weights: Weights,
    ) -> float:
        return sum(
            rule.penalty(bus, arrive, queue_free, all_buses,
                         timelines_so_far, operator_stats, weights)
            for rule in self.rules
        )

    def _apply_weighted_ordering(
        self, buses, bus_plans, bus_stops, station_map, physics,
        station_logs, charger_free_ref, weights, route
    ):
        """
        Re-run scheduling at each station using the soft-rule weighted scorer.
        Buses that arrive within a small time window compete; the scorer breaks ties.
        """
        CONTENTION_WINDOW = 30  # minutes — buses within this window are "competing"

        for station_id, slog in station_logs.items():
            if len(slog.events) <= 1:
                continue

            s_obj = station_map[station_id]
            num_chargers = s_obj.num_chargers

            # Re-sort events: first by arrive_time, then break ties with weighted score
            events = sorted(slog.events, key=lambda e: e.arrive_time_min)

            # Rebuild charger slots from scratch for this station
            charger_slots = [0.0] * num_chargers
            operator_stats: Dict[str, Dict] = {}

            new_events = []
            timelines_so_far = {}

            for ev in events:
                bus = next(b for b in buses if b.id == ev.bus_id)
                arrive = ev.arrive_time_min

                # Compute score for each available charger slot
                best_slot = min(
                    range(num_chargers),
                    key=lambda i: self._score(
                        bus, arrive, charger_slots[i],
                        buses, timelines_so_far, operator_stats, weights
                    )
                )

                free_at = charger_slots[best_slot]
                charge_start = max(arrive, free_at)
                charge_end = charge_start + physics.charge_duration_min

                new_ev = ChargeEvent(
                    bus_id           = ev.bus_id,
                    station_id       = station_id,
                    arrive_time_min  = arrive,
                    queue_start_min  = arrive,
                    charge_start_min = charge_start,
                    charge_end_min   = charge_end,
                )
                new_events.append(new_ev)
                charger_slots[best_slot] = charge_end

                # Update operator stats
                op = bus.operator_id
                if op not in operator_stats:
                    operator_stats[op] = {"total_wait": 0.0, "count": 0, "avg_wait": 0.0}
                operator_stats[op]["total_wait"] += new_ev.wait_min
                operator_stats[op]["count"] += 1
                operator_stats[op]["avg_wait"] = (
                    operator_stats[op]["total_wait"] / operator_stats[op]["count"]
                )

            slog.events = sorted(new_events, key=lambda e: e.charge_start_min)