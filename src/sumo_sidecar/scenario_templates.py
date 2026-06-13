from __future__ import annotations

from copy import deepcopy
from typing import Any


SCENARIO_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "signal-timing",
        "label": "signal-timing-change",
        "parameter": "max_green",
        "before_value": "30",
        "after_value": "45",
        "hypothesis": (
            "Changing the green-time parameter should affect queue discharge while completion remains comparable."
        ),
        "expected_metrics": ["completion_ratio", "mean_duration", "mean_waiting_time"],
        "note": "Use before-change and after-change checkpoints around the timing edit.",
    },
    {
        "id": "detector-mapping",
        "label": "detector-mapping-check",
        "parameter": "detector_map",
        "before_value": "current mapping",
        "after_value": "candidate mapping",
        "hypothesis": (
            "Changing detector mapping should affect the controller response if the detector-to-movement mapping is active."
        ),
        "expected_metrics": ["completion_ratio", "mean_waiting_time", "mean_time_loss"],
        "note": "Verify detector IDs, lanes, and controlled movements before interpreting controller behavior.",
    },
    {
        "id": "demand-stress",
        "label": "demand-stress-check",
        "parameter": "route_demand_scale",
        "before_value": "1.0",
        "after_value": "1.2",
        "hypothesis": (
            "Increasing demand should expose queue growth or backlog only if route, seed, horizon, and outputs remain paired."
        ),
        "expected_metrics": ["completion_ratio", "arrived", "running", "teleports"],
        "note": "Treat this as a stress diagnostic unless paired completion and demand evidence are preserved.",
    },
    {
        "id": "controller-weight",
        "label": "controller-weight-change",
        "parameter": "controller_weight",
        "before_value": "current value",
        "after_value": "candidate value",
        "hypothesis": (
            "Changing a controller weight should alter phase selection only if the intended controller path is active."
        ),
        "expected_metrics": ["completion_ratio", "mean_duration", "mean_time_loss"],
        "note": "Pair this with controller logs or change records before reading metric deltas.",
    },
    {
        "id": "output-audit",
        "label": "output-alignment-check",
        "parameter": "output_interval",
        "before_value": "current interval",
        "after_value": "aligned interval",
        "hypothesis": "Aligning output settings should make baseline and variant metrics comparable without changing demand.",
        "expected_metrics": ["completion_ratio", "trip_count"],
        "note": "Use this when the main risk is overwritten, missing, or mismatched SUMO outputs.",
    },
]


def list_scenario_templates() -> list[dict[str, Any]]:
    return deepcopy(SCENARIO_TEMPLATES)
