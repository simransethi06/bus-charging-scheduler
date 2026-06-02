"""
runner.py — Thin glue between loader, engine, and UI.
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional, List

from scheduler.loader import load_scenario, list_scenarios
from scheduler.engine import Scheduler, SoftRule
from scheduler.models import ScheduleResult, Weights


def run_scenario(
    path: str | Path,
    weight_overrides: Optional[dict] = None,
    extra_rules: Optional[List[SoftRule]] = None,
) -> ScheduleResult:
    """
    Load and schedule a scenario.

    Args:
        path:             path to scenario JSON
        weight_overrides: optional dict to override weights, e.g.
                          {"individual": 2.0, "operator": 0.5}
        extra_rules:      optional extra soft rules to inject

    Returns:
        ScheduleResult — full output ready for display
    """
    (
        scenario_id, name, description,
        route, stations, physics, operators, buses, weights
    ) = load_scenario(path)

    # Allow weight overrides (for live UI sliders or testing)
    if weight_overrides:
        weights = Weights(
            individual = weight_overrides.get("individual", weights.individual),
            operator   = weight_overrides.get("operator",   weights.operator),
            overall    = weight_overrides.get("overall",    weights.overall),
        )

    scheduler = Scheduler(extra_rules=extra_rules)
    result = scheduler.run(
        scenario_id = scenario_id,
        route       = route,
        stations    = stations,
        physics     = physics,
        operators   = operators,
        buses       = buses,
        weights     = weights,
    )
    # Attach human-readable name/description for UI
    result.scenario_name = name
    result.scenario_description = description
    return result


def get_all_scenarios(scenarios_dir: str | Path = "scenarios"):
    """Return list of (path, scenario_id, name, description) for all scenarios."""
    results = []
    for path in list_scenarios(scenarios_dir):
        import json
        data = json.loads(Path(path).read_text())
        results.append((
            path,
            data["meta"]["id"],
            data["meta"]["name"],
            data["meta"]["description"],
        ))
    return results