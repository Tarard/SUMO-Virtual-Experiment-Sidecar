from pathlib import Path

from sumo_sidecar.output_inspection import inspect_output_pair, inspect_run_outputs


def write_summary(path: Path, *, loaded: int, inserted: int, arrived: int, running: int, waiting: int, teleports: int) -> None:
    path.write_text(
        f"""<summary>
  <step time="0.00" loaded="{loaded}" inserted="0" running="0" waiting="{loaded}" ended="0" arrived="0" teleports="0"/>
  <step time="100.00" loaded="{loaded}" inserted="{inserted}" running="{running}" waiting="{waiting}" ended="{arrived}" arrived="{arrived}" teleports="{teleports}"/>
</summary>
""",
        encoding="utf-8",
    )


def write_tripinfo(path: Path) -> None:
    path.write_text(
        """<tripinfos>
  <tripinfo id="veh0" duration="40.0" waitingTime="5.0" timeLoss="7.5"/>
  <tripinfo id="veh1" duration="60.0" waitingTime="15.0" timeLoss="12.5"/>
</tripinfos>
""",
        encoding="utf-8",
    )


def test_inspect_run_outputs_reports_completion_and_trip_means(tmp_path: Path) -> None:
    summary = tmp_path / "summary.xml"
    tripinfo = tmp_path / "tripinfo.xml"
    write_summary(summary, loaded=2, inserted=2, arrived=2, running=0, waiting=0, teleports=0)
    write_tripinfo(tripinfo)

    report = inspect_run_outputs("baseline", summary_path=summary, tripinfo_path=tripinfo)

    assert report.status == "pass"
    assert report.summary is not None
    assert report.summary.completion_ratio == 1.0
    assert report.summary.arrived == 2
    assert report.tripinfo is not None
    assert report.tripinfo.trip_count == 2
    assert report.tripinfo.mean_duration == 50.0
    assert report.tripinfo.mean_waiting_time == 10.0
    assert report.tripinfo.mean_time_loss == 10.0


def test_inspect_output_pair_warns_when_completion_differs(tmp_path: Path) -> None:
    baseline_summary = tmp_path / "baseline-summary.xml"
    variant_summary = tmp_path / "variant-summary.xml"
    write_summary(baseline_summary, loaded=10, inserted=10, arrived=10, running=0, waiting=0, teleports=0)
    write_summary(variant_summary, loaded=10, inserted=10, arrived=7, running=3, waiting=0, teleports=1)

    report = inspect_output_pair(
        baseline_summary=baseline_summary,
        baseline_tripinfo=None,
        variant_summary=variant_summary,
        variant_tripinfo=None,
    )

    assert report.status == "warn"
    assert any("completion differs" in warning for warning in report.paired_warnings)
    assert report.variant.summary is not None
    assert report.variant.summary.running == 3
    assert report.variant.summary.teleports == 1
