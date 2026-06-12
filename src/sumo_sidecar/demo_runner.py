from __future__ import annotations

import subprocess
from pathlib import Path
from shutil import which
from typing import Any

from .config_preflight import preflight_pair
from .output_inspection import inspect_output_pair


def minimal_paired_metadata(repo_root: Path) -> dict[str, Any]:
    example_root = repo_root / "examples" / "minimal-paired"
    return {
        "name": "minimal-paired",
        "root": str(example_root),
        "baseline_config": str(example_root / "baseline.sumocfg"),
        "variant_config": str(example_root / "variant.sumocfg"),
        "baseline_summary": str(example_root / "outputs" / "baseline" / "summary.xml"),
        "baseline_tripinfo": str(example_root / "outputs" / "baseline" / "tripinfo.xml"),
        "variant_summary": str(example_root / "outputs" / "variant" / "summary.xml"),
        "variant_tripinfo": str(example_root / "outputs" / "variant" / "tripinfo.xml"),
        "headless_commands": [
            "sumo -c examples\\minimal-paired\\baseline.sumocfg",
            "sumo -c examples\\minimal-paired\\variant.sumocfg",
        ],
    }


def run_minimal_paired_headless(repo_root: Path, timeout_seconds: int = 60) -> dict[str, Any]:
    metadata = minimal_paired_metadata(repo_root)
    example_root = Path(metadata["root"])
    if not example_root.exists():
        raise RuntimeError("minimal paired example is not available")

    sumo_binary = which("sumo")
    if sumo_binary is None:
        raise RuntimeError("sumo binary is not available on PATH")

    _remove_outputs(metadata)
    commands = [
        [sumo_binary, "-c", "baseline.sumocfg"],
        [sumo_binary, "-c", "variant.sumocfg"],
    ]
    results = [_run_command(command, example_root, timeout_seconds) for command in commands]
    output_inspection = inspect_output_pair(
        baseline_summary=Path(metadata["baseline_summary"]),
        baseline_tripinfo=Path(metadata["baseline_tripinfo"]),
        variant_summary=Path(metadata["variant_summary"]),
        variant_tripinfo=Path(metadata["variant_tripinfo"]),
    )
    command_failed = any(result["returncode"] != 0 for result in results)
    status = "fail" if command_failed else output_inspection.status

    return {
        **metadata,
        "status": status,
        "commands": results,
        "output_inspection": output_inspection.model_dump(mode="json"),
    }


def run_minimal_paired_guided(repo_root: Path, timeout_seconds: int = 60) -> dict[str, Any]:
    metadata = minimal_paired_metadata(repo_root)
    config_preflight = preflight_pair(
        Path(metadata["baseline_config"]),
        Path(metadata["variant_config"]),
    )
    headless_run = run_minimal_paired_headless(repo_root, timeout_seconds=timeout_seconds)
    output_inspection = headless_run["output_inspection"]
    status = _combine_statuses(config_preflight.status, headless_run["status"], output_inspection["status"])

    return {
        **metadata,
        "status": status,
        "claim_status": "diagnostic-demo",
        "config_preflight": config_preflight.model_dump(mode="json"),
        "headless_run": {
            "status": headless_run["status"],
            "commands": headless_run["commands"],
        },
        "output_inspection": output_inspection,
        "next_actions": [
            "Review config preflight warnings before changing claims.",
            "Review completion-first output evidence before comparing performance metrics.",
            "Click Create Paired Session to open paired SUMO GUI windows for visual inspection.",
            "Treat GUI screenshots as diagnostic evidence unless paired outputs support the claim.",
        ],
    }


def _remove_outputs(metadata: dict[str, Any]) -> None:
    for key in ("baseline_summary", "baseline_tripinfo", "variant_summary", "variant_tripinfo"):
        Path(metadata[key]).unlink(missing_ok=True)


def _run_command(command: list[str], cwd: Path, timeout_seconds: int) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return {
            "command": command,
            "cwd": str(cwd),
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "cwd": str(cwd),
            "returncode": -1,
            "stdout": exc.stdout or "",
            "stderr": f"command timed out after {timeout_seconds} seconds",
        }


def _combine_statuses(*statuses: str) -> str:
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses:
        return "warn"
    return "pass"
