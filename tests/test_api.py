from pathlib import Path

from fastapi.testclient import TestClient

from sumo_sidecar.server import create_app
from tests.test_session_manager import FakeAdapterFactory


def test_preflight_reports_available_fields(tmp_path: Path) -> None:
    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    response = client.get("/api/preflight")

    assert response.status_code == 200
    body = response.json()
    assert "python_version" in body
    assert "sumo_gui_binary" in body
    assert "traci_available" in body


def test_minimal_demo_metadata_api_returns_usable_paths(tmp_path: Path) -> None:
    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    response = client.get("/api/examples/minimal-paired")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "minimal-paired"
    assert Path(body["baseline_config"]).exists()
    assert Path(body["variant_config"]).exists()
    assert Path(body["root"]).exists()
    assert Path(body["baseline_summary"]).parent.exists()
    assert Path(body["baseline_tripinfo"]).parent.exists()
    assert Path(body["variant_summary"]).parent.exists()
    assert Path(body["variant_tripinfo"]).parent.exists()


def test_config_preflight_api_reports_pair_risks(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.sumocfg"
    variant = tmp_path / "variant.sumocfg"
    baseline.write_text(
        """<configuration>
  <input>
    <net-file value="network.net.xml"/>
    <route-files value="routes.rou.xml"/>
  </input>
  <output>
    <tripinfo-output value="shared/tripinfo.xml"/>
  </output>
</configuration>
""",
        encoding="utf-8",
    )
    variant.write_text(
        """<configuration>
  <input>
    <net-file value="network.net.xml"/>
    <route-files value="routes.rou.xml"/>
  </input>
  <output>
    <tripinfo-output value="shared/tripinfo.xml"/>
  </output>
</configuration>
""",
        encoding="utf-8",
    )
    (tmp_path / "network.net.xml").write_text("<net/>", encoding="utf-8")
    (tmp_path / "routes.rou.xml").write_text("<routes/>", encoding="utf-8")
    (tmp_path / "shared").mkdir()

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    response = client.post(
        "/api/config/preflight",
        json={
            "baseline_config": str(baseline),
            "variant_config": str(variant),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "warn"
    assert body["baseline"]["status"] == "pass"
    assert any("shared output path" in warning for warning in body["paired_warnings"])


def test_output_inspection_api_reports_completion_difference(tmp_path: Path) -> None:
    baseline_summary = tmp_path / "baseline-summary.xml"
    variant_summary = tmp_path / "variant-summary.xml"
    baseline_summary.write_text(
        """<summary>
  <step time="100" loaded="4" inserted="4" running="0" waiting="0" arrived="4" teleports="0"/>
</summary>
""",
        encoding="utf-8",
    )
    variant_summary.write_text(
        """<summary>
  <step time="100" loaded="4" inserted="4" running="1" waiting="0" arrived="3" teleports="1"/>
</summary>
""",
        encoding="utf-8",
    )

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    response = client.post(
        "/api/outputs/inspect",
        json={
            "baseline_summary": str(baseline_summary),
            "variant_summary": str(variant_summary),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "warn"
    assert body["baseline"]["summary"]["completion_ratio"] == 1.0
    assert body["variant"]["summary"]["completion_ratio"] == 0.75
    assert any("completion differs" in warning for warning in body["paired_warnings"])


def test_session_api_lifecycle(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.sumocfg"
    variant = tmp_path / "variant.sumocfg"
    baseline.write_text("<configuration/>", encoding="utf-8")
    variant.write_text("<configuration/>", encoding="utf-8")

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    create_response = client.post(
        "/api/session/create",
        json={
            "name": "api-demo",
            "baseline_config": str(baseline),
            "variant_config": str(variant),
        },
    )
    assert create_response.status_code == 200
    session_id = create_response.json()["id"]

    step_response = client.post(f"/api/session/{session_id}/step", json={"count": 2})
    assert step_response.status_code == 200
    assert step_response.json()["baseline"]["time"] == 2
    assert step_response.json()["variant"]["time"] == 2

    run_response = client.post(f"/api/session/{session_id}/run-until", json={"target_time": 7})
    assert run_response.status_code == 200
    assert run_response.json()["baseline"]["time"] == 7

    screenshot_response = client.post(
        f"/api/session/{session_id}/screenshot",
        json={"label": "phase-change"},
    )
    assert screenshot_response.status_code == 200
    assert Path(screenshot_response.json()["baseline_screenshot"]).exists()

    evidence_response = client.get(f"/api/session/{session_id}/evidence")
    assert evidence_response.status_code == 200
    evidence_body = evidence_response.json()
    assert "phase-change" in evidence_body["comparison_markdown"]
    assert any(item["relative_path"] == "comparison.md" for item in evidence_body["artifacts"])
    assert any(item["relative_path"].endswith(".png") for item in evidence_body["artifacts"])

    baseline_summary = tmp_path / "baseline-summary.xml"
    variant_summary = tmp_path / "variant-summary.xml"
    baseline_summary.write_text(
        '<summary><step time="10" loaded="2" inserted="2" running="0" waiting="0" arrived="2" teleports="0"/></summary>',
        encoding="utf-8",
    )
    variant_summary.write_text(
        '<summary><step time="10" loaded="2" inserted="2" running="1" waiting="0" arrived="1" teleports="0"/></summary>',
        encoding="utf-8",
    )
    output_response = client.post(
        f"/api/session/{session_id}/outputs/inspect",
        json={
            "baseline_summary": str(baseline_summary),
            "variant_summary": str(variant_summary),
        },
    )
    assert output_response.status_code == 200
    assert output_response.json()["status"] == "warn"

    evidence_response = client.get(f"/api/session/{session_id}/evidence")
    evidence_body = evidence_response.json()
    assert any(item["relative_path"] == "output-inspection.json" for item in evidence_body["artifacts"])
    assert any(item["relative_path"] == "output-inspection.md" for item in evidence_body["artifacts"])

    close_response = client.post(f"/api/session/{session_id}/close")
    assert close_response.status_code == 200
    assert close_response.json()["status"] == "closed"
