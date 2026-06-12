from pathlib import Path
from shutil import copytree, which
import subprocess

import pytest

from sumo_sidecar.config_preflight import preflight_pair
from sumo_sidecar.output_inspection import inspect_output_pair


REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_DIR = REPO_ROOT / "examples" / "minimal-paired"


def test_minimal_paired_example_config_preflight_passes() -> None:
    report = preflight_pair(EXAMPLE_DIR / "baseline.sumocfg", EXAMPLE_DIR / "variant.sumocfg")

    assert report.status == "pass"
    assert report.baseline.declared_outputs == ["summary-output", "tripinfo-output"]
    assert report.variant.declared_outputs == ["summary-output", "tripinfo-output"]


def test_minimal_paired_example_runs_headless_and_outputs_are_inspectable(tmp_path: Path) -> None:
    if which("sumo") is None:
        pytest.skip("sumo binary is not available on PATH")

    workdir = tmp_path / "minimal-paired"
    copytree(EXAMPLE_DIR, workdir)

    subprocess.run(["sumo", "-c", "baseline.sumocfg"], cwd=workdir, check=True)
    subprocess.run(["sumo", "-c", "variant.sumocfg"], cwd=workdir, check=True)

    report = inspect_output_pair(
        baseline_summary=workdir / "outputs" / "baseline" / "summary.xml",
        baseline_tripinfo=workdir / "outputs" / "baseline" / "tripinfo.xml",
        variant_summary=workdir / "outputs" / "variant" / "summary.xml",
        variant_tripinfo=workdir / "outputs" / "variant" / "tripinfo.xml",
    )

    assert report.status == "pass"
    assert report.baseline.summary is not None
    assert report.baseline.summary.completion_ratio == 1.0
    assert report.variant.summary is not None
    assert report.variant.summary.completion_ratio == 1.0
    assert report.baseline.tripinfo is not None
    assert report.baseline.tripinfo.trip_count == 6
    assert report.variant.tripinfo is not None
    assert report.variant.tripinfo.trip_count == 6
