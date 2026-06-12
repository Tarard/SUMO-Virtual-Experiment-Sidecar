from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable

from .models import ConfigPreflightReport, ConfigReference, PairConfigPreflightReport


INPUT_OPTIONS = {
    "net-file",
    "route-files",
    "additional-files",
    "weight-files",
    "lane-weight-files",
    "state-files",
}

SPECIAL_OUTPUT_VALUES = {"", "-", "stdout", "stderr", "NUL", "nul"}


def preflight_config(config_path: Path, role: str) -> ConfigPreflightReport:
    resolved_config = config_path.expanduser().resolve()
    if not resolved_config.exists():
        return ConfigPreflightReport(
            role=role,
            config_path=resolved_config,
            config_exists=False,
            valid_xml=False,
            status="fail",
            references=[],
            missing_inputs=[str(config_path)],
            missing_output_parents=[],
            declared_outputs=[],
            warnings=[f"{role} config not found"],
        )

    try:
        root = ET.parse(resolved_config).getroot()
    except ET.ParseError as exc:
        return ConfigPreflightReport(
            role=role,
            config_path=resolved_config,
            config_exists=True,
            valid_xml=False,
            status="fail",
            references=[],
            missing_inputs=[],
            missing_output_parents=[],
            declared_outputs=[],
            warnings=[f"{role} config is not valid XML: {exc}"],
        )

    references = _extract_references(root, resolved_config.parent, role)
    missing_inputs = [
        _display_path(item.resolved_path, resolved_config.parent)
        for item in references
        if item.kind == "input" and not item.exists
    ]
    missing_output_parents = sorted(
        {
            _display_path(item.resolved_path.parent, resolved_config.parent)
            for item in references
            if item.kind == "output" and not item.parent_exists
        }
    )
    declared_outputs = sorted({item.option for item in references if item.kind == "output"})
    warnings: list[str] = []
    if not declared_outputs:
        warnings.append(f"{role} declares no SUMO output files in the .sumocfg")

    if missing_inputs or missing_output_parents:
        status = "fail"
    elif warnings:
        status = "warn"
    else:
        status = "pass"

    return ConfigPreflightReport(
        role=role,
        config_path=resolved_config,
        config_exists=True,
        valid_xml=True,
        status=status,
        references=references,
        missing_inputs=missing_inputs,
        missing_output_parents=missing_output_parents,
        declared_outputs=declared_outputs,
        warnings=warnings,
    )


def preflight_pair(baseline_config: Path, variant_config: Path) -> PairConfigPreflightReport:
    baseline = preflight_config(baseline_config, role="baseline")
    variant = preflight_config(variant_config, role="variant")
    paired_warnings = _paired_warnings(baseline, variant)

    if baseline.status == "fail" or variant.status == "fail":
        status = "fail"
    elif baseline.status == "warn" or variant.status == "warn" or paired_warnings:
        status = "warn"
    else:
        status = "pass"

    return PairConfigPreflightReport(
        status=status,
        baseline=baseline,
        variant=variant,
        paired_warnings=paired_warnings,
    )


def _extract_references(root: ET.Element, base_dir: Path, role: str) -> list[ConfigReference]:
    references: list[ConfigReference] = []
    for element in root.iter():
        option = _local_name(element.tag)
        value = element.attrib.get("value") or element.attrib.get("v")
        if value is None:
            continue

        if _is_input_option(option):
            for item in _split_values(value):
                path = _resolve(base_dir, item)
                references.append(
                    ConfigReference(
                        role=role,
                        kind="input",
                        option=option,
                        value=item,
                        resolved_path=path,
                        exists=path.exists(),
                        parent_exists=path.parent.exists(),
                    )
                )
        elif _is_output_option(option):
            for item in _split_values(value):
                if item in SPECIAL_OUTPUT_VALUES:
                    continue
                path = _resolve(base_dir, item)
                references.append(
                    ConfigReference(
                        role=role,
                        kind="output",
                        option=option,
                        value=item,
                        resolved_path=path,
                        exists=path.exists(),
                        parent_exists=path.parent.exists(),
                    )
                )
    return references


def _paired_warnings(
    baseline: ConfigPreflightReport,
    variant: ConfigPreflightReport,
) -> list[str]:
    warnings: list[str] = []

    for option in ("net-file", "route-files", "additional-files"):
        baseline_values = _reference_paths(baseline.references, option, kind="input")
        variant_values = _reference_paths(variant.references, option, kind="input")
        if baseline_values and variant_values and baseline_values != variant_values:
            warnings.append(f"{option} differ between baseline and variant")

    baseline_outputs = _reference_paths(baseline.references, None, kind="output")
    variant_outputs = _reference_paths(variant.references, None, kind="output")
    for shared in sorted(baseline_outputs & variant_outputs):
        warnings.append(f"shared output path may be overwritten: {shared}")

    return warnings


def _reference_paths(
    references: Iterable[ConfigReference],
    option: str | None,
    *,
    kind: str,
) -> set[str]:
    return {
        str(reference.resolved_path)
        for reference in references
        if reference.kind == kind and (option is None or reference.option == option)
    }


def _is_input_option(option: str) -> bool:
    return option in INPUT_OPTIONS or option.endswith("-files")


def _is_output_option(option: str) -> bool:
    return option.endswith("-output") or "output" in option


def _split_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _resolve(base_dir: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


def _display_path(path: Path, base_dir: Path) -> str:
    try:
        return path.relative_to(base_dir).as_posix()
    except ValueError:
        return str(path)


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag
