from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .models import ConfigPatchReport


def patch_sumo_config_option(
    source_config: Path,
    option: str,
    value: str,
    output_config: Path | None = None,
) -> ConfigPatchReport:
    resolved_source = source_config.expanduser().resolve()
    if not resolved_source.exists():
        raise FileNotFoundError(f"source config not found: {source_config}")

    clean_option = option.strip()
    clean_value = value.strip()
    if not clean_option:
        raise ValueError("option cannot be empty")
    if not clean_value:
        raise ValueError("value cannot be empty")

    resolved_output = (
        _default_output_path(resolved_source, clean_option)
        if output_config is None
        else output_config.expanduser().resolve()
    )
    if resolved_output == resolved_source:
        raise ValueError("output_config must not overwrite the source config")
    if output_config is not None and resolved_output.exists():
        raise ValueError("output_config already exists; choose a new path")

    try:
        tree = ET.parse(resolved_source)
    except ET.ParseError as exc:
        raise ValueError(f"source config is not valid XML: {exc}") from exc

    matches = [element for element in tree.getroot().iter() if _local_name(element.tag) == clean_option]
    if not matches:
        raise ValueError(f"option not found in source config: {clean_option}")

    target = matches[0]
    attribute = "value" if "value" in target.attrib else "v" if "v" in target.attrib else "value"
    old_value = target.attrib.get(attribute)
    target.set(attribute, clean_value)

    warnings: list[str] = []
    if len(matches) > 1:
        warnings.append(f"found {len(matches)} matching options; updated the first only")
    if old_value is None:
        warnings.append(f"option had no {attribute!r} attribute; created it in the output copy")

    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    tree.write(resolved_output, encoding="utf-8", xml_declaration=True)

    return ConfigPatchReport(
        status="warn" if warnings else "pass",
        source_config=resolved_source,
        output_config=resolved_output,
        option=clean_option,
        old_value=old_value,
        new_value=clean_value,
        attribute=attribute,
        match_count=len(matches),
        warnings=warnings,
        claim_status="config-copy-generated",
    )


def _default_output_path(source_config: Path, option: str) -> Path:
    safe_option = re.sub(r"[^A-Za-z0-9_.-]+", "-", option).strip(".-") or "option"
    candidate = source_config.with_name(f"{source_config.stem}.{safe_option}.patched{source_config.suffix}")
    if not candidate.exists():
        return candidate
    for index in range(1, 1000):
        numbered = source_config.with_name(f"{source_config.stem}.{safe_option}.patched-{index}{source_config.suffix}")
        if not numbered.exists():
            return numbered
    raise ValueError("could not create a unique output_config path")


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag
