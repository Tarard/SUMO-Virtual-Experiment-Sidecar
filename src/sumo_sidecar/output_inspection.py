from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from statistics import mean

from .models import PairOutputInspectionReport, RunOutputInspection, SummaryMetrics, TripinfoMetrics


def inspect_run_outputs(
    role: str,
    *,
    summary_path: Path | None,
    tripinfo_path: Path | None,
) -> RunOutputInspection:
    warnings: list[str] = []
    summary = inspect_summary(summary_path) if summary_path is not None else None
    tripinfo = inspect_tripinfo(tripinfo_path) if tripinfo_path is not None else None

    if summary is None:
        warnings.append(f"{role} summary output not provided")
    elif summary.warnings:
        warnings.extend(summary.warnings)

    if tripinfo is None:
        warnings.append(f"{role} tripinfo output not provided")
    elif tripinfo.warnings:
        warnings.extend(tripinfo.warnings)

    if _has_invalid_file(summary) or _has_invalid_file(tripinfo):
        status = "fail"
    elif warnings:
        status = "warn"
    else:
        status = "pass"

    return RunOutputInspection(
        role=role,
        status=status,
        summary=summary,
        tripinfo=tripinfo,
        warnings=warnings,
    )


def inspect_output_pair(
    *,
    baseline_summary: Path | None,
    baseline_tripinfo: Path | None,
    variant_summary: Path | None,
    variant_tripinfo: Path | None,
) -> PairOutputInspectionReport:
    baseline = inspect_run_outputs(
        "baseline",
        summary_path=baseline_summary,
        tripinfo_path=baseline_tripinfo,
    )
    variant = inspect_run_outputs(
        "variant",
        summary_path=variant_summary,
        tripinfo_path=variant_tripinfo,
    )
    paired_warnings = _paired_warnings(baseline, variant)

    if baseline.status == "fail" or variant.status == "fail":
        status = "fail"
    elif baseline.status == "warn" or variant.status == "warn" or paired_warnings:
        status = "warn"
    else:
        status = "pass"

    return PairOutputInspectionReport(
        status=status,
        baseline=baseline,
        variant=variant,
        paired_warnings=paired_warnings,
    )


def inspect_summary(path: Path) -> SummaryMetrics:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        return SummaryMetrics(
            path=resolved,
            exists=False,
            valid_xml=False,
            last_time=None,
            loaded=None,
            inserted=None,
            arrived=None,
            running=None,
            waiting=None,
            teleports=None,
            completion_ratio=None,
            warnings=[f"summary output not found: {resolved}"],
        )

    try:
        root = ET.parse(resolved).getroot()
    except ET.ParseError as exc:
        return SummaryMetrics(
            path=resolved,
            exists=True,
            valid_xml=False,
            last_time=None,
            loaded=None,
            inserted=None,
            arrived=None,
            running=None,
            waiting=None,
            teleports=None,
            completion_ratio=None,
            warnings=[f"summary output is not valid XML: {exc}"],
        )

    steps = [element for element in root.iter() if _local_name(element.tag) == "step"]
    if not steps:
        return SummaryMetrics(
            path=resolved,
            exists=True,
            valid_xml=True,
            last_time=None,
            loaded=None,
            inserted=None,
            arrived=None,
            running=None,
            waiting=None,
            teleports=None,
            completion_ratio=None,
            warnings=["summary output contains no step records"],
        )

    last = steps[-1]
    loaded = _int_attr(last, "loaded")
    inserted = _int_attr(last, "inserted")
    arrived = _int_attr(last, "arrived")
    if arrived is None:
        arrived = _int_attr(last, "ended")
    running = _int_attr(last, "running")
    waiting = _int_attr(last, "waiting")
    teleports = _int_attr(last, "teleports")
    completion_ratio = None if not loaded else (arrived or 0) / loaded
    warnings: list[str] = []
    if running:
        warnings.append(f"vehicles still running at final summary step: {running}")
    if waiting:
        warnings.append(f"vehicles waiting for insertion at final summary step: {waiting}")
    if teleports:
        warnings.append(f"teleports reported in summary output: {teleports}")
    if completion_ratio is not None and completion_ratio < 1.0:
        warnings.append(f"completion ratio below 1.0: {completion_ratio:.3f}")

    return SummaryMetrics(
        path=resolved,
        exists=True,
        valid_xml=True,
        last_time=_float_attr(last, "time"),
        loaded=loaded,
        inserted=inserted,
        arrived=arrived,
        running=running,
        waiting=waiting,
        teleports=teleports,
        completion_ratio=completion_ratio,
        warnings=warnings,
    )


def inspect_tripinfo(path: Path) -> TripinfoMetrics:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        return TripinfoMetrics(
            path=resolved,
            exists=False,
            valid_xml=False,
            trip_count=0,
            mean_duration=None,
            mean_waiting_time=None,
            mean_time_loss=None,
            warnings=[f"tripinfo output not found: {resolved}"],
        )

    try:
        root = ET.parse(resolved).getroot()
    except ET.ParseError as exc:
        return TripinfoMetrics(
            path=resolved,
            exists=True,
            valid_xml=False,
            trip_count=0,
            mean_duration=None,
            mean_waiting_time=None,
            mean_time_loss=None,
            warnings=[f"tripinfo output is not valid XML: {exc}"],
        )

    trips = [element for element in root.iter() if _local_name(element.tag) == "tripinfo"]
    durations = [_float_attr(item, "duration") for item in trips]
    waiting_times = [_float_attr(item, "waitingTime") for item in trips]
    time_losses = [_float_attr(item, "timeLoss") for item in trips]
    warnings: list[str] = []
    if not trips:
        warnings.append("tripinfo output contains no tripinfo records")

    return TripinfoMetrics(
        path=resolved,
        exists=True,
        valid_xml=True,
        trip_count=len(trips),
        mean_duration=_mean_present(durations),
        mean_waiting_time=_mean_present(waiting_times),
        mean_time_loss=_mean_present(time_losses),
        warnings=warnings,
    )


def _paired_warnings(
    baseline: RunOutputInspection,
    variant: RunOutputInspection,
) -> list[str]:
    warnings: list[str] = []
    if baseline.summary and variant.summary:
        b_completion = baseline.summary.completion_ratio
        v_completion = variant.summary.completion_ratio
        if b_completion is not None and v_completion is not None and abs(b_completion - v_completion) > 1e-9:
            warnings.append(f"completion differs between baseline and variant: {b_completion:.3f} vs {v_completion:.3f}")

    if baseline.tripinfo and variant.tripinfo and baseline.tripinfo.trip_count != variant.tripinfo.trip_count:
        warnings.append(
            f"tripinfo record count differs between baseline and variant: "
            f"{baseline.tripinfo.trip_count} vs {variant.tripinfo.trip_count}"
        )

    return warnings


def _has_invalid_file(metrics: SummaryMetrics | TripinfoMetrics | None) -> bool:
    return metrics is not None and (not metrics.exists or not metrics.valid_xml)


def _mean_present(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return mean(present) if present else None


def _int_attr(element: ET.Element, name: str) -> int | None:
    value = element.attrib.get(name)
    if value is None:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _float_attr(element: ET.Element, name: str) -> float | None:
    value = element.attrib.get(name)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag
