"""
loader.py — Load a scenario JSON into domain objects.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Tuple, List, Dict

from scheduler.models import (
    Route, Segment, Station, Terminal, Physics, Operator,
    Bus, Weights, Direction
)


def _parse_time(t: str) -> float:
    """'19:30' → minutes from midnight."""
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def load_scenario(path: str | Path) -> Tuple[
    str, str, str, Route, List[Station], Physics, List[Operator], List[Bus], Weights
]:
    """
    Returns:
        scenario_id, name, description,
        route, stations, physics, operators, buses, weights
    """
    data = json.loads(Path(path).read_text())

    meta = data["meta"]
    world = data["world"]
    route_raw = world["route"]

    # --- terminals ---
    origin_raw = route_raw["terminals"]["origin"]
    dest_raw   = route_raw["terminals"]["destination"]
    origin = Terminal(origin_raw["id"], origin_raw["name"], origin_raw.get("slow_charger", True))
    dest   = Terminal(dest_raw["id"],   dest_raw["name"],   dest_raw.get("slow_charger", True))

    # --- segments ---
    segments = [
        Segment(s["from"], s["to"], float(s["distance_km"]))
        for s in route_raw["segments"]
    ]
    route = Route(route_raw["id"], route_raw["name"], origin, dest, segments)

    # --- stations ---
    stations = [
        Station(s["id"], s["name"], s.get("num_chargers", 1), s.get("charger_power", "fast"))
        for s in world["stations"]
    ]

    # --- physics ---
    p = world["physics"]
    physics = Physics(
        battery_range_km    = float(p["battery_range_km"]),
        charge_duration_min = float(p["charge_duration_min"]),
        speed_kmph          = float(p["speed_kmph"]),
        initial_charge_km   = float(p["initial_charge_km"]),
    )

    # --- operators ---
    operators = [
        Operator(o["id"], o["name"], o.get("priority_tier", 1))
        for o in world["operators"]
    ]

    # --- weights ---
    w = data["weights"]
    weights = Weights(
        individual = float(w["individual"]),
        operator   = float(w["operator"]),
        overall    = float(w["overall"]),
    )

    # --- buses ---
    buses = [
        Bus(
            id                = b["id"],
            operator_id       = b["operator"],
            direction         = Direction(b["direction"]),
            departure_time_min= _parse_time(b["departure"]),
        )
        for b in data["buses"]
    ]

    return (
        meta["id"], meta["name"], meta["description"],
        route, stations, physics, operators, buses, weights
    )


def list_scenarios(scenarios_dir: str | Path = "scenarios") -> List[Path]:
    d = Path(scenarios_dir)
    return sorted(d.glob("scenario_*.json"))