from pathlib import Path

from sumo_sidecar.config_preflight import preflight_config, preflight_pair


def write_config(
    path: Path,
    *,
    net_file: str = "network.net.xml",
    route_files: str = "demand.rou.xml",
    additional_files: str = "detectors.add.xml",
    summary_output: str = "outputs/summary.xml",
    tripinfo_output: str = "outputs/tripinfo.xml",
) -> None:
    path.write_text(
        f"""<configuration>
  <input>
    <net-file value="{net_file}"/>
    <route-files value="{route_files}"/>
    <additional-files value="{additional_files}"/>
  </input>
  <output>
    <summary-output value="{summary_output}"/>
    <tripinfo-output value="{tripinfo_output}"/>
  </output>
</configuration>
""",
        encoding="utf-8",
    )


def test_preflight_config_reports_missing_inputs_and_declared_outputs(tmp_path: Path) -> None:
    config = tmp_path / "scenario.sumocfg"
    write_config(config)
    (tmp_path / "network.net.xml").write_text("<net/>", encoding="utf-8")
    (tmp_path / "demand.rou.xml").write_text("<routes/>", encoding="utf-8")
    (tmp_path / "outputs").mkdir()

    report = preflight_config(config, role="baseline")

    assert report.status == "fail"
    assert report.valid_xml
    assert report.missing_inputs == ["detectors.add.xml"]
    assert "summary-output" in report.declared_outputs
    assert "tripinfo-output" in report.declared_outputs
    assert not report.missing_output_parents


def test_preflight_config_reports_missing_output_parent(tmp_path: Path) -> None:
    config = tmp_path / "scenario.sumocfg"
    write_config(config)
    (tmp_path / "network.net.xml").write_text("<net/>", encoding="utf-8")
    (tmp_path / "demand.rou.xml").write_text("<routes/>", encoding="utf-8")
    (tmp_path / "detectors.add.xml").write_text("<additional/>", encoding="utf-8")

    report = preflight_config(config, role="baseline")

    assert report.status == "fail"
    assert report.missing_inputs == []
    assert report.missing_output_parents == ["outputs"]


def test_pair_preflight_detects_shared_output_paths(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.sumocfg"
    variant = tmp_path / "variant.sumocfg"
    write_config(baseline, summary_output="shared/summary.xml")
    write_config(variant, summary_output="shared/summary.xml")
    for name in ["network.net.xml", "demand.rou.xml", "detectors.add.xml"]:
        (tmp_path / name).write_text("<xml/>", encoding="utf-8")
    (tmp_path / "shared").mkdir()
    (tmp_path / "outputs").mkdir()

    report = preflight_pair(baseline, variant)

    assert report.status == "warn"
    assert any("shared output path" in warning for warning in report.paired_warnings)


def test_pair_preflight_detects_mismatched_demand_files(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.sumocfg"
    variant = tmp_path / "variant.sumocfg"
    write_config(baseline, route_files="baseline.rou.xml")
    write_config(variant, route_files="variant.rou.xml")
    for name in ["network.net.xml", "baseline.rou.xml", "variant.rou.xml", "detectors.add.xml"]:
        (tmp_path / name).write_text("<xml/>", encoding="utf-8")
    (tmp_path / "outputs").mkdir()

    report = preflight_pair(baseline, variant)

    assert report.status == "warn"
    assert any("route-files differ" in warning for warning in report.paired_warnings)
