from __future__ import annotations

from copy import deepcopy
from typing import Any


VISUAL_OBSERVATION_TAXONOMY: list[dict[str, Any]] = [
    {
        "id": "queue-growth",
        "label": "Queue growth",
        "description": "A queue appears longer after a change, or the queue dissipates more slowly than in the paired baseline.",
        "evidence_targets": ["visual-diff.md", "visual-observations.md", "output-inspection.md", "metric-comparison.md"],
        "evidence_checks": [
            "Check completion ratio, arrived vehicles, running vehicles, waiting vehicles, and teleports before interpreting queue growth.",
            "Check that the before/after screenshots use comparable time points and camera framing.",
            "Check whether the changed parameter or controller action can plausibly affect the queued movement.",
        ],
        "next_actions": ["Inspect Outputs", "Compare Metrics", "Export Review Summary"],
        "note_prompt": "Which approach or movement has a visibly longer queue, and at what time/checkpoint?",
        "claim_boundary": "A queue-growth observation is visual diagnosis only; it does not prove causality, performance improvement, or publishable validity without paired output evidence.",
    },
    {
        "id": "spillback",
        "label": "Spillback",
        "description": "A queue appears to block an upstream link, intersection entry, detector area, or turn pocket.",
        "evidence_targets": ["visual-diff.md", "visual-observations.md", "output-inspection.md", "timeline.md"],
        "evidence_checks": [
            "Check whether the suspected blockage is present at the same simulation time in both baseline and variant.",
            "Check completion, running vehicles, waiting vehicles, insertion backlog, and teleports before treating spillback as a controller effect.",
            "Check route demand and lane connectivity if spillback appears only in one run.",
        ],
        "next_actions": ["Inspect Outputs", "Add Timeline Note", "Compare Metrics"],
        "note_prompt": "Which downstream queue blocks which upstream movement or link?",
        "claim_boundary": "A spillback observation is visual diagnosis only; it does not prove causality or controller failure without paired completion and route/demand evidence.",
    },
    {
        "id": "phase-mismatch",
        "label": "Phase mismatch",
        "description": "Observed vehicle service, stopping, or release pattern appears inconsistent with the intended TLS, NEMA, or TraCI phase logic.",
        "evidence_targets": ["visual-diff.md", "change-records.md", "scenario-plan.md", "comparison.md"],
        "evidence_checks": [
            "Check whether the visual movement being served matches the intended phase index and allowed movements.",
            "Check change records and controller logs before attributing mismatch to the controller.",
            "Check yellow/all-red and transition handling before comparing green-service time.",
        ],
        "next_actions": ["Record Change", "Export Visual Diff", "Export Agent Prompt"],
        "note_prompt": "Which movement appears served or blocked contrary to the intended TLS/NEMA phase?",
        "claim_boundary": "A phase-mismatch observation is a debugging clue; it does not prove causality, correctness, or invalidity without controller and TLS mapping evidence.",
    },
    {
        "id": "insertion-teleport",
        "label": "Insertion or teleport symptom",
        "description": "Vehicles appear missing, suddenly relocated, unable to enter, or removed in a way that could distort visual and metric comparisons.",
        "evidence_targets": ["output-inspection.md", "visual-diff.md", "metric-comparison.md"],
        "evidence_checks": [
            "Check inserted, waiting, running, arrived, and teleport counts before using tripinfo means.",
            "Check SUMO warnings and route loading if the visual scene looks unexpectedly sparse.",
            "Check whether one variant ends with unfinished vehicles while the other completes.",
        ],
        "next_actions": ["Inspect Outputs", "Compare Metrics", "Check Compare Readiness"],
        "note_prompt": "What looks missing, teleported, or unable to enter, and in which run?",
        "claim_boundary": "An insertion or teleport symptom can invalidate a comparison; it does not prove controller performance and must be checked in SUMO outputs.",
    },
    {
        "id": "density-change",
        "label": "Vehicle density change",
        "description": "A region appears more or less crowded after a change, without a clear queue or spillback pattern yet.",
        "evidence_targets": ["visual-diff.md", "visual-observations.md", "metric-comparison.md"],
        "evidence_checks": [
            "Check whether density changes coincide with completion differences, route changes, or demand differences.",
            "Check whether the same viewport and simulation time were used.",
            "Check whether the difference is local visual evidence or reflected in output metrics.",
        ],
        "next_actions": ["Record Visual Observation", "Inspect Outputs", "Compare Metrics"],
        "note_prompt": "Which area looks denser or sparser, and how does it differ from the paired baseline?",
        "claim_boundary": "A density-change observation is a screening cue; it does not prove performance or mechanism without paired outputs and scenario metadata.",
    },
    {
        "id": "deadlock-gridlock",
        "label": "Deadlock or gridlock",
        "description": "Vehicles appear mutually blocked or the network stops progressing despite visible demand.",
        "evidence_targets": ["visual-diff.md", "output-inspection.md", "timeline.md", "next-action-review.md"],
        "evidence_checks": [
            "Check whether simulation completion stalled or ended with running/waiting vehicles.",
            "Check teleports and insertion backlog before interpreting mean travel time.",
            "Check whether the visual blockage is caused by demand, lane connectivity, TLS logic, or controller action.",
        ],
        "next_actions": ["Inspect Outputs", "Export Next Action Review", "Export Agent Prompt"],
        "note_prompt": "Where does traffic stop progressing, and which vehicles or movements block each other?",
        "claim_boundary": "A deadlock/gridlock observation is diagnostic; it does not prove root cause until route, TLS, output, and controller evidence are checked.",
    },
    {
        "id": "route-demand-mismatch",
        "label": "Route or demand mismatch suspicion",
        "description": "The two paired runs appear to load different vehicle patterns, routes, or demand volumes.",
        "evidence_targets": ["comparison.md", "output-inspection.md", "scenario-plan.md"],
        "evidence_checks": [
            "Check loaded and inserted vehicle counts before comparing performance metrics.",
            "Check that route files, demand generation, seed, and horizon are paired across baseline and variant.",
            "Check whether changed outputs overwrite each other or come from different runs.",
        ],
        "next_actions": ["Check Config Pair", "Inspect Outputs", "Check Compare Readiness"],
        "note_prompt": "What visual pattern suggests the two runs may not share the same demand or route setup?",
        "claim_boundary": "A route or demand mismatch suspicion can make a comparison invalid; it must be resolved before any controller claim.",
    },
]


def list_visual_observation_taxonomy() -> list[dict[str, Any]]:
    return deepcopy(VISUAL_OBSERVATION_TAXONOMY)


def find_visual_observation_type(observation_type: str) -> dict[str, Any] | None:
    normalized = observation_type.strip().lower()
    for item in VISUAL_OBSERVATION_TAXONOMY:
        if item["id"] == normalized:
            return deepcopy(item)
    return None
