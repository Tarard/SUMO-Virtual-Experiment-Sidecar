from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from sumo_sidecar.config_patch import patch_sumo_config_option


def test_patch_sumo_config_option_writes_non_destructive_copy(tmp_path: Path) -> None:
    source = tmp_path / "baseline.sumocfg"
    source.write_text(
        '<configuration><time><step-length value="1.0"/></time></configuration>',
        encoding="utf-8",
    )

    report = patch_sumo_config_option(source, "step-length", "0.5")

    assert report.status == "pass"
    assert report.source_config == source.resolve()
    assert report.output_config.exists()
    assert report.output_config != source.resolve()
    assert report.option == "step-length"
    assert report.old_value == "1.0"
    assert report.new_value == "0.5"
    assert report.attribute == "value"
    assert report.match_count == 1
    assert report.claim_status == "config-copy-generated"
    assert 'value="1.0"' in source.read_text(encoding="utf-8")
    patched_root = ET.parse(report.output_config).getroot()
    assert patched_root.find(".//step-length").attrib["value"] == "0.5"


def test_patch_sumo_config_option_rejects_missing_option(tmp_path: Path) -> None:
    source = tmp_path / "baseline.sumocfg"
    source.write_text("<configuration><time/></configuration>", encoding="utf-8")

    with pytest.raises(ValueError, match="option not found"):
        patch_sumo_config_option(source, "step-length", "0.5")


def test_patch_sumo_config_option_rejects_overwriting_source(tmp_path: Path) -> None:
    source = tmp_path / "baseline.sumocfg"
    source.write_text(
        '<configuration><time><step-length value="1.0"/></time></configuration>',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must not overwrite the source"):
        patch_sumo_config_option(source, "step-length", "0.5", output_config=source)


def test_patch_sumo_config_option_rejects_overwriting_existing_output(tmp_path: Path) -> None:
    source = tmp_path / "baseline.sumocfg"
    output = tmp_path / "variant.sumocfg"
    source.write_text(
        '<configuration><time><step-length value="1.0"/></time></configuration>',
        encoding="utf-8",
    )
    output.write_text("<configuration/>", encoding="utf-8")

    with pytest.raises(ValueError, match="output_config already exists"):
        patch_sumo_config_option(source, "step-length", "0.5", output_config=output)
