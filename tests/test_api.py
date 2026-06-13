from pathlib import Path
from shutil import which
import struct
import xml.etree.ElementTree as ET
import zlib

import pytest
from fastapi.testclient import TestClient

from sumo_sidecar.server import create_app
from tests.test_session_manager import FakeAdapterFactory


def write_rgb_png(path: Path, rgb: tuple[int, int, int]) -> None:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00" + bytes(rgb)))
        + chunk(b"IEND", b"")
    )


def test_preflight_reports_available_fields(tmp_path: Path) -> None:
    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    response = client.get("/api/preflight")

    assert response.status_code == 200
    body = response.json()
    assert "python_version" in body
    assert "sumo_gui_binary" in body
    assert "traci_available" in body


def test_homepage_exposes_full_workflow_demo_action(tmp_path: Path) -> None:
    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    index_response = client.get("/")
    script_response = client.get("/static/app.js")

    assert index_response.status_code == 200
    assert script_response.status_code == 200
    assert "launchFullWorkflowGuiBtn" in index_response.text
    assert "Launch Full Workflow" in index_response.text
    assert "/api/examples/minimal-paired/launch-full-workflow-gui" in script_response.text


def test_homepage_exposes_structured_change_record_action(tmp_path: Path) -> None:
    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    index_response = client.get("/")
    script_response = client.get("/static/app.js")

    assert index_response.status_code == 200
    assert script_response.status_code == 200
    assert "recordChangeBtn" in index_response.text
    assert "Record Change" in index_response.text
    assert "/change/record" in script_response.text


def test_homepage_exposes_metric_comparison_action(tmp_path: Path) -> None:
    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    index_response = client.get("/")
    script_response = client.get("/static/app.js")

    assert index_response.status_code == 200
    assert script_response.status_code == 200
    assert "compareMetricsBtn" in index_response.text
    assert "Compare Metrics" in index_response.text
    assert "/metrics/compare" in script_response.text


def test_homepage_exposes_metric_chart_action(tmp_path: Path) -> None:
    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    index_response = client.get("/")
    script_response = client.get("/static/app.js")

    assert index_response.status_code == 200
    assert script_response.status_code == 200
    assert "exportMetricChartBtn" in index_response.text
    assert "Export Metric Chart" in index_response.text
    assert "metricChartPreview" in index_response.text
    assert "/metrics/chart" in script_response.text


def test_homepage_exposes_review_summary_action(tmp_path: Path) -> None:
    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    index_response = client.get("/")
    script_response = client.get("/static/app.js")

    assert index_response.status_code == 200
    assert script_response.status_code == 200
    assert "exportReviewSummaryBtn" in index_response.text
    assert "Export Review Summary" in index_response.text
    assert "reviewSummaryPreview" in index_response.text
    assert "/review/summary" in script_response.text


def test_homepage_exposes_comparison_readiness_action(tmp_path: Path) -> None:
    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    index_response = client.get("/")
    script_response = client.get("/static/app.js")

    assert index_response.status_code == 200
    assert script_response.status_code == 200
    assert "compareReadinessBtn" in index_response.text
    assert "Check Compare Readiness" in index_response.text
    assert "compareReadinessOutput" in index_response.text
    assert "/comparison/readiness" in script_response.text
    assert "renderComparisonReadiness" in script_response.text


def test_homepage_exposes_agent_review_prompt_action(tmp_path: Path) -> None:
    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    index_response = client.get("/")
    script_response = client.get("/static/app.js")

    assert index_response.status_code == 200
    assert script_response.status_code == 200
    assert "exportAgentPromptBtn" in index_response.text
    assert "Export Agent Prompt" in index_response.text
    assert "agentPromptPreview" in index_response.text
    assert "/agent-review-prompt/export" in script_response.text
    assert "renderAgentReviewPrompt" in script_response.text


def test_homepage_exposes_next_action_review_action(tmp_path: Path) -> None:
    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    index_response = client.get("/")
    script_response = client.get("/static/app.js")

    assert index_response.status_code == 200
    assert script_response.status_code == 200
    assert "exportNextActionReviewBtn" in index_response.text
    assert "Export Next Action Review" in index_response.text
    assert "nextActionReviewPreview" in index_response.text
    assert "/next-action-review/export" in script_response.text
    assert "renderNextActionReview" in script_response.text


def test_homepage_exposes_visual_observation_controls(tmp_path: Path) -> None:
    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    index_response = client.get("/")
    script_response = client.get("/static/app.js")

    assert index_response.status_code == 200
    assert script_response.status_code == 200
    assert "visualObservationType" in index_response.text
    assert "visualObservationArtifact" in index_response.text
    assert "visualObservationNote" in index_response.text
    assert "recordVisualObservationBtn" in index_response.text
    assert "Record Visual Observation" in index_response.text
    assert "visualObservationPreview" in index_response.text
    assert "/visual-observation/record" in script_response.text
    assert "visualObservationPayload" in script_response.text
    assert "renderVisualObservation" in script_response.text


def test_visual_observation_taxonomy_api_returns_claim_bounded_entries(tmp_path: Path) -> None:
    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    response = client.get("/api/visual-observation/taxonomy")

    assert response.status_code == 200
    body = response.json()
    taxonomy = {item["id"]: item for item in body["taxonomy"]}
    assert {"queue-growth", "spillback", "phase-mismatch", "insertion-teleport"}.issubset(taxonomy)
    assert "visual-diff.md" in taxonomy["spillback"]["evidence_targets"]
    assert "output-inspection.md" in taxonomy["spillback"]["evidence_targets"]
    assert any("completion" in item for item in taxonomy["queue-growth"]["evidence_checks"])
    assert "does not prove causality" in taxonomy["phase-mismatch"]["claim_boundary"]


def test_homepage_exposes_visual_observation_taxonomy_controls(tmp_path: Path) -> None:
    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    index_response = client.get("/")
    script_response = client.get("/static/app.js")

    assert index_response.status_code == 200
    assert script_response.status_code == 200
    assert "visualObservationTaxonomy" in index_response.text
    assert "Load Observation Types" in index_response.text
    assert "visualObservationGuidePreview" in index_response.text
    assert "/api/visual-observation/taxonomy" in script_response.text
    assert "applyVisualObservationTaxonomy" in script_response.text


def test_homepage_exposes_visual_diff_matrix_renderer(tmp_path: Path) -> None:
    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    index_response = client.get("/")
    script_response = client.get("/static/app.js")

    assert index_response.status_code == 200
    assert script_response.status_code == 200
    assert "visualDiffPreview" in index_response.text
    assert "renderVisualDiffMatrix" in script_response.text
    assert "visual-diff-matrix" in script_response.text
    assert "changed_pixel_ratio" in script_response.text


def test_homepage_exposes_scenario_guide_controls(tmp_path: Path) -> None:
    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    index_response = client.get("/")
    script_response = client.get("/static/app.js")

    assert index_response.status_code == 200
    assert script_response.status_code == 200
    assert "scenarioLabel" in index_response.text
    assert "scenarioParameter" in index_response.text
    assert "startScenarioBtn" in index_response.text
    assert "Refresh Scenario" in index_response.text
    assert "scenarioOutput" in index_response.text
    assert "/scenario/plan" in script_response.text
    assert "/scenario/status" in script_response.text


def test_scenario_templates_api_returns_safe_prefill_records(tmp_path: Path) -> None:
    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    response = client.get("/api/scenario/templates")

    assert response.status_code == 200
    body = response.json()
    templates = body["templates"]
    template_ids = {template["id"] for template in templates}

    assert {"signal-timing", "detector-mapping", "demand-stress"}.issubset(template_ids)
    for template in templates:
        assert template["label"]
        assert template["parameter"]
        assert template["before_value"]
        assert template["after_value"]
        assert template["hypothesis"]
        assert template["expected_metrics"]
        assert template["note"]

    public_text = "\n".join(str(template) for template in templates).lower()
    assert "track b" not in public_text
    assert "heart" not in public_text
    assert "agimo" not in public_text


def test_homepage_exposes_scenario_template_controls(tmp_path: Path) -> None:
    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    index_response = client.get("/")
    script_response = client.get("/static/app.js")

    assert index_response.status_code == 200
    assert script_response.status_code == 200
    assert "scenarioTemplate" in index_response.text
    assert "loadScenarioTemplateBtn" in index_response.text
    assert "Load Template" in index_response.text
    assert "/api/scenario/templates" in script_response.text
    assert "applyScenarioTemplate" in script_response.text


def test_homepage_exposes_config_patch_controls(tmp_path: Path) -> None:
    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    index_response = client.get("/")
    script_response = client.get("/static/app.js")

    assert index_response.status_code == 200
    assert script_response.status_code == 200
    assert "sourcePatchConfig" in index_response.text
    assert "createConfigPatchBtn" in index_response.text
    assert "Create Config Patch" in index_response.text
    assert "configPatchOutput" in index_response.text
    assert "/api/config/patch" in script_response.text
    assert "configPatchPayload" in script_response.text


def test_homepage_exposes_patch_from_scenario_action(tmp_path: Path) -> None:
    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    index_response = client.get("/")
    script_response = client.get("/static/app.js")

    assert index_response.status_code == 200
    assert script_response.status_code == 200
    assert "patchFromScenarioBtn" in index_response.text
    assert "Patch Config From Scenario" in index_response.text
    assert "scenarioPatchPayload" in script_response.text
    assert "syncConfigPatchFieldsFromScenario" in script_response.text
    assert "patchConfigFromScenario" in script_response.text
    assert "preflightPatchedScenarioConfig" in script_response.text
    assert "recordScenarioChangeBtn" in index_response.text
    assert "Record Scenario Change" in index_response.text
    assert "scenarioChangeRecordPayload" in script_response.text
    assert "recordScenarioChange" in script_response.text
    assert "/api/config/patch" in script_response.text
    assert "/api/config/preflight" in script_response.text
    assert "/change/record" in script_response.text


def test_config_patch_api_writes_variant_config_copy(tmp_path: Path) -> None:
    source = tmp_path / "baseline.sumocfg"
    output = tmp_path / "variant.sumocfg"
    source.write_text(
        '<configuration><time><step-length value="1.0"/></time></configuration>',
        encoding="utf-8",
    )

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    response = client.post(
        "/api/config/patch",
        json={
            "source_config": str(source),
            "option": "step-length",
            "value": "0.5",
            "output_config": str(output),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pass"
    assert body["source_config"] == str(source.resolve())
    assert body["output_config"] == str(output.resolve())
    assert body["old_value"] == "1.0"
    assert body["new_value"] == "0.5"
    assert body["claim_status"] == "config-copy-generated"
    assert output.exists()
    assert 'value="1.0"' in source.read_text(encoding="utf-8")
    assert ET.parse(output).getroot().find(".//step-length").attrib["value"] == "0.5"


def test_scenario_template_payload_can_start_scenario_plan(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.sumocfg"
    variant = tmp_path / "variant.sumocfg"
    baseline.write_text("<configuration/>", encoding="utf-8")
    variant.write_text("<configuration/>", encoding="utf-8")

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    create_response = client.post(
        "/api/session/create",
        json={
            "name": "template-prefill-demo",
            "baseline_config": str(baseline),
            "variant_config": str(variant),
        },
    )
    session_id = create_response.json()["id"]
    template = client.get("/api/scenario/templates").json()["templates"][0]

    response = client.post(
        f"/api/session/{session_id}/scenario/plan",
        json={
            "label": template["label"],
            "parameter": template["parameter"],
            "before_value": template["before_value"],
            "after_value": template["after_value"],
            "hypothesis": template["hypothesis"],
            "expected_metrics": template["expected_metrics"],
            "note": template["note"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["scenario_plan"]["label"] == template["label"]
    assert body["scenario_plan"]["parameter"] == template["parameter"]
    assert "Scenario Plan" in body["scenario_plan_markdown"]


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


def test_minimal_demo_headless_api_runs_and_returns_output_inspection(tmp_path: Path) -> None:
    if which("sumo") is None:
        pytest.skip("sumo binary is not available on PATH")

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    response = client.post("/api/examples/minimal-paired/run-headless")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "minimal-paired"
    assert body["status"] == "pass"
    assert all(command["returncode"] == 0 for command in body["commands"])
    assert body["output_inspection"]["status"] == "pass"
    assert body["output_inspection"]["baseline"]["summary"]["completion_ratio"] == 1.0
    assert body["output_inspection"]["variant"]["summary"]["completion_ratio"] == 1.0
    assert body["output_inspection"]["baseline"]["tripinfo"]["trip_count"] == 6
    assert body["output_inspection"]["variant"]["tripinfo"]["trip_count"] == 6


def test_minimal_demo_guided_api_runs_preflight_headless_and_returns_next_actions(tmp_path: Path) -> None:
    if which("sumo") is None:
        pytest.skip("sumo binary is not available on PATH")

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    response = client.post("/api/examples/minimal-paired/run-guided")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "minimal-paired"
    assert body["status"] == "pass"
    assert body["claim_status"] == "diagnostic-demo"
    assert body["config_preflight"]["status"] == "pass"
    assert body["headless_run"]["status"] == "pass"
    assert body["output_inspection"]["status"] == "pass"
    assert any("Create Paired Session" in action for action in body["next_actions"])


def test_minimal_demo_launch_gui_api_creates_paired_session_with_demo_configs(tmp_path: Path) -> None:
    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    response = client.post("/api/examples/minimal-paired/launch-gui")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "minimal-paired-gui"
    assert body["evidence_count"] == 0
    assert body["session_dir"].startswith(str(tmp_path / "runs"))
    assert Path(body["baseline"]["config_path"]).name == "baseline.sumocfg"
    assert Path(body["variant"]["config_path"]).name == "variant.sumocfg"


def test_minimal_demo_launch_guided_gui_api_persists_output_evidence(tmp_path: Path) -> None:
    if which("sumo") is None:
        pytest.skip("sumo binary is not available on PATH")

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    response = client.post("/api/examples/minimal-paired/launch-guided-gui")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pass"
    assert body["guided_demo"]["status"] == "pass"
    assert body["session"]["name"] == "minimal-paired-gui"
    assert body["output_inspection"]["status"] == "pass"
    assert body["evidence"]["manifest"]["output_inspection"]["status"] == "pass"
    artifact_paths = {item["relative_path"] for item in body["evidence"]["artifacts"]}
    assert "output-inspection.json" in artifact_paths
    assert "output-inspection.md" in artifact_paths


def test_minimal_demo_full_workflow_gui_api_exports_review_ready_bundle(tmp_path: Path) -> None:
    if which("sumo") is None:
        pytest.skip("sumo binary is not available on PATH")

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    response = client.post("/api/examples/minimal-paired/launch-full-workflow-gui")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pass"
    assert body["guided_demo"]["status"] == "pass"
    assert body["session"]["name"] == "minimal-paired-gui"
    assert body["output_inspection"]["status"] == "pass"
    assert body["visual_diff"]["visual_diff"]["status"] == "ready"
    assert body["timeline"]["timeline"]["preset"] == "full"
    assert body["review_timeline"]["timeline"]["preset"] == "review"
    assert Path(body["scenario_plan"]["scenario_plan_markdown_path"]).name == "scenario-plan.md"
    assert Path(body["packet"]["packet_path"]).name == "codex-packet.md"
    assert Path(body["agent_prompt"]["agent_prompt_markdown_path"]).name == "agent-review-prompt.md"
    assert Path(body["next_action_review"]["next_action_review_markdown_path"]).name == "next-action-review.md"
    assert Path(body["metric_chart"]["metric_chart_svg_path"]).name == "metric-delta-chart.svg"
    assert Path(body["review_summary"]["review_summary_markdown_path"]).name == "review-summary.md"
    assert "Output Inspection" in body["packet"]["packet_markdown"]
    assert "Scenario Plan" in body["packet"]["packet_markdown"]
    assert "Metric Delta Chart" in body["packet"]["packet_markdown"]
    assert "Review Summary" in body["packet"]["packet_markdown"]
    assert "Record Visual Observation" in body["next_action_review"]["next_action_review_markdown"]
    assert "next-action-review.md" in body["agent_prompt"]["agent_prompt"]["artifacts_to_open"]
    assert "next-action-review" in {event["kind"] for event in body["review_timeline"]["timeline"]["events"]}
    assert "Claim boundary" in body["review_summary"]["review_summary_markdown"]
    assert "metric-delta-chart.md" in body["review_summary"]["review_summary_markdown"]
    assert body["workflow"]["status"] == "review-ready"
    assert body["workflow"]["claim_status"] == "evidence-index-ready"

    artifact_paths = {item["relative_path"] for item in body["evidence"]["artifacts"]}
    assert "output-inspection.json" in artifact_paths
    assert "output-inspection.md" in artifact_paths
    assert "scenario-plan.json" in artifact_paths
    assert "scenario-plan.md" in artifact_paths
    assert "visual-diff.json" in artifact_paths
    assert "visual-diff.md" in artifact_paths
    assert "metric-comparison.json" in artifact_paths
    assert "metric-comparison.md" in artifact_paths
    assert "metric-delta-chart.svg" in artifact_paths
    assert "metric-delta-chart.md" in artifact_paths
    assert "review-summary.json" in artifact_paths
    assert "review-summary.md" in artifact_paths
    assert "next-action-review.json" in artifact_paths
    assert "next-action-review.md" in artifact_paths
    assert "agent-review-prompt.json" in artifact_paths
    assert "agent-review-prompt.md" in artifact_paths
    assert "timeline.json" in artifact_paths
    assert "timeline-review.json" in artifact_paths
    assert "codex-packet.md" in artifact_paths
    assert any(path.endswith("first-checkpoint.png") for path in artifact_paths)
    assert any(path.endswith("before-change.png") for path in artifact_paths)
    assert any(path.endswith("after-change.png") for path in artifact_paths)
    assert "change-records.json" in artifact_paths
    assert "change-records.md" in artifact_paths


def test_first_checkpoint_api_captures_pair_and_returns_refreshed_evidence(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.sumocfg"
    variant = tmp_path / "variant.sumocfg"
    baseline.write_text("<configuration/>", encoding="utf-8")
    variant.write_text("<configuration/>", encoding="utf-8")

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    create_response = client.post(
        "/api/session/create",
        json={
            "name": "checkpoint-demo",
            "baseline_config": str(baseline),
            "variant_config": str(variant),
        },
    )
    session_id = create_response.json()["id"]

    response = client.post(f"/api/session/{session_id}/checkpoint/first")

    assert response.status_code == 200
    body = response.json()
    assert body["screenshot"]["label"] == "first-checkpoint"
    assert Path(body["screenshot"]["baseline_screenshot"]).exists()
    assert Path(body["screenshot"]["variant_screenshot"]).exists()
    assert "first-checkpoint" in body["evidence"]["comparison_markdown"]
    artifact_paths = {item["relative_path"] for item in body["evidence"]["artifacts"]}
    assert any(
        path.startswith("baseline/screenshots/") and path.endswith("first-checkpoint.png")
        for path in artifact_paths
    )
    assert any(
        path.startswith("variant/screenshots/") and path.endswith("first-checkpoint.png")
        for path in artifact_paths
    )


def test_session_artifact_api_serves_only_files_inside_session(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.sumocfg"
    variant = tmp_path / "variant.sumocfg"
    baseline.write_text("<configuration/>", encoding="utf-8")
    variant.write_text("<configuration/>", encoding="utf-8")

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    create_response = client.post(
        "/api/session/create",
        json={
            "name": "artifact-demo",
            "baseline_config": str(baseline),
            "variant_config": str(variant),
        },
    )
    session_id = create_response.json()["id"]
    screenshot_response = client.post(
        f"/api/session/{session_id}/screenshot",
        json={"label": "visual-preview"},
    )
    screenshot_path = Path(screenshot_response.json()["baseline_screenshot"])
    relative_path = screenshot_path.relative_to(tmp_path / "runs" / session_id).as_posix()

    artifact_response = client.get(f"/api/session/{session_id}/artifact/{relative_path}")
    blocked_response = client.get(f"/api/session/{session_id}/artifact/../baseline.sumocfg")

    assert artifact_response.status_code == 200
    assert artifact_response.text
    assert blocked_response.status_code == 404


def test_codex_packet_export_writes_single_markdown_entrypoint(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.sumocfg"
    variant = tmp_path / "variant.sumocfg"
    baseline.write_text("<configuration/>", encoding="utf-8")
    variant.write_text("<configuration/>", encoding="utf-8")

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    create_response = client.post(
        "/api/session/create",
        json={
            "name": "packet-demo",
            "baseline_config": str(baseline),
            "variant_config": str(variant),
        },
    )
    session_id = create_response.json()["id"]
    client.post(f"/api/session/{session_id}/checkpoint/first")

    response = client.post(f"/api/session/{session_id}/packet/export")

    assert response.status_code == 200
    body = response.json()
    packet_path = Path(body["packet_path"])
    assert packet_path.exists()
    assert packet_path.name == "codex-packet.md"
    assert "packet-demo" in body["packet_markdown"]
    assert "first-checkpoint" in body["packet_markdown"]
    assert "comparison.md" in body["packet_markdown"]


def test_timeline_export_aligns_checkpoints_outputs_and_packet(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.sumocfg"
    variant = tmp_path / "variant.sumocfg"
    baseline.write_text("<configuration/>", encoding="utf-8")
    variant.write_text("<configuration/>", encoding="utf-8")

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    create_response = client.post(
        "/api/session/create",
        json={
            "name": "timeline-demo",
            "baseline_config": str(baseline),
            "variant_config": str(variant),
        },
    )
    session_id = create_response.json()["id"]
    client.post(f"/api/session/{session_id}/checkpoint/first")

    baseline_summary = tmp_path / "baseline-summary.xml"
    variant_summary = tmp_path / "variant-summary.xml"
    baseline_summary.write_text(
        '<summary><step time="10" loaded="2" inserted="2" running="0" waiting="0" arrived="2" teleports="0"/></summary>',
        encoding="utf-8",
    )
    variant_summary.write_text(
        '<summary><step time="10" loaded="2" inserted="2" running="0" waiting="0" arrived="2" teleports="0"/></summary>',
        encoding="utf-8",
    )
    client.post(
        f"/api/session/{session_id}/outputs/inspect",
        json={
            "baseline_summary": str(baseline_summary),
            "variant_summary": str(variant_summary),
        },
    )
    client.post(f"/api/session/{session_id}/packet/export")

    response = client.post(f"/api/session/{session_id}/timeline/export")

    assert response.status_code == 200
    body = response.json()
    assert Path(body["timeline_json_path"]).exists()
    assert Path(body["timeline_markdown_path"]).exists()
    event_kinds = [event["kind"] for event in body["timeline"]["events"]]
    assert event_kinds[:2] == ["session-created", "screenshot-checkpoint"]
    assert "output-inspection" in event_kinds
    assert "codex-packet" in event_kinds
    assert "first-checkpoint" in body["timeline_markdown"]
    assert "output-inspection.md" in body["timeline_markdown"]
    assert "codex-packet.md" in body["timeline_markdown"]


def test_timeline_export_visual_preset_filters_to_visual_events(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.sumocfg"
    variant = tmp_path / "variant.sumocfg"
    baseline.write_text("<configuration/>", encoding="utf-8")
    variant.write_text("<configuration/>", encoding="utf-8")

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    create_response = client.post(
        "/api/session/create",
        json={
            "name": "timeline-visual-demo",
            "baseline_config": str(baseline),
            "variant_config": str(variant),
        },
    )
    session_id = create_response.json()["id"]
    client.post(f"/api/session/{session_id}/checkpoint/first")
    client.post(
        f"/api/session/{session_id}/checkpoint/template",
        json={"template": "before-change", "note": "Before tuning."},
    )
    client.post(f"/api/session/{session_id}/step", json={"count": 2})
    client.post(
        f"/api/session/{session_id}/checkpoint/template",
        json={"template": "after-change", "note": "After tuning."},
    )
    client.post(
        f"/api/session/{session_id}/timeline/note",
        json={"label": "parameter-change", "note": "Changed max green."},
    )
    client.post(f"/api/session/{session_id}/visual-diff/export")

    response = client.post(f"/api/session/{session_id}/timeline/export?preset=visual")

    assert response.status_code == 200
    body = response.json()
    assert body["timeline"]["preset"] == "visual"
    assert Path(body["timeline_json_path"]).name == "timeline-visual.json"
    assert Path(body["timeline_markdown_path"]).name == "timeline-visual.md"
    event_kinds = [event["kind"] for event in body["timeline"]["events"]]
    assert "session-created" in event_kinds
    assert "screenshot-checkpoint" in event_kinds
    assert "visual-diff" in event_kinds
    assert "user-note" not in event_kinds
    assert "output-inspection" not in event_kinds
    assert "Visual diff index" in body["timeline_markdown"]


def test_timeline_export_outputs_preset_filters_to_output_events(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.sumocfg"
    variant = tmp_path / "variant.sumocfg"
    baseline.write_text("<configuration/>", encoding="utf-8")
    variant.write_text("<configuration/>", encoding="utf-8")

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    create_response = client.post(
        "/api/session/create",
        json={
            "name": "timeline-outputs-demo",
            "baseline_config": str(baseline),
            "variant_config": str(variant),
        },
    )
    session_id = create_response.json()["id"]
    client.post(f"/api/session/{session_id}/checkpoint/first")
    baseline_summary = tmp_path / "baseline-summary.xml"
    variant_summary = tmp_path / "variant-summary.xml"
    baseline_summary.write_text(
        '<summary><step time="10" loaded="2" inserted="2" running="0" waiting="0" arrived="2" teleports="0"/></summary>',
        encoding="utf-8",
    )
    variant_summary.write_text(
        '<summary><step time="10" loaded="2" inserted="2" running="0" waiting="0" arrived="2" teleports="0"/></summary>',
        encoding="utf-8",
    )
    client.post(
        f"/api/session/{session_id}/outputs/inspect",
        json={
            "baseline_summary": str(baseline_summary),
            "variant_summary": str(variant_summary),
        },
    )

    response = client.post(f"/api/session/{session_id}/timeline/export?preset=outputs")

    assert response.status_code == 200
    body = response.json()
    assert body["timeline"]["preset"] == "outputs"
    assert Path(body["timeline_markdown_path"]).name == "timeline-outputs.md"
    event_kinds = [event["kind"] for event in body["timeline"]["events"]]
    assert event_kinds == ["session-created", "output-inspection"]
    assert "output-inspection.md" in body["timeline_markdown"]
    assert "first-checkpoint" not in body["timeline_markdown"]


def test_template_checkpoint_records_note_in_evidence_and_timeline(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.sumocfg"
    variant = tmp_path / "variant.sumocfg"
    baseline.write_text("<configuration/>", encoding="utf-8")
    variant.write_text("<configuration/>", encoding="utf-8")

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    create_response = client.post(
        "/api/session/create",
        json={
            "name": "template-demo",
            "baseline_config": str(baseline),
            "variant_config": str(variant),
        },
    )
    session_id = create_response.json()["id"]

    response = client.post(
        f"/api/session/{session_id}/checkpoint/template",
        json={
            "template": "before-change",
            "note": "Before changing the signal controller parameters.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["screenshot"]["label"] == "before-change"
    assert body["screenshot"]["template"] == "before-change"
    assert body["screenshot"]["note"] == "Before changing the signal controller parameters."
    assert "Before changing the signal controller parameters." in body["evidence"]["comparison_markdown"]

    timeline_response = client.post(f"/api/session/{session_id}/timeline/export")

    assert timeline_response.status_code == 200
    timeline_body = timeline_response.json()
    checkpoint_events = [
        event for event in timeline_body["timeline"]["events"] if event["kind"] == "screenshot-checkpoint"
    ]
    assert checkpoint_events[0]["template"] == "before-change"
    assert checkpoint_events[0]["note"] == "Before changing the signal controller parameters."
    assert "Before changing the signal controller parameters." in timeline_body["timeline_markdown"]


def test_visual_diff_export_pairs_before_after_template_checkpoints(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.sumocfg"
    variant = tmp_path / "variant.sumocfg"
    baseline.write_text("<configuration/>", encoding="utf-8")
    variant.write_text("<configuration/>", encoding="utf-8")

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    create_response = client.post(
        "/api/session/create",
        json={
            "name": "diff-demo",
            "baseline_config": str(baseline),
            "variant_config": str(variant),
        },
    )
    session_id = create_response.json()["id"]
    client.post(
        f"/api/session/{session_id}/checkpoint/template",
        json={"template": "before-change", "note": "Before tuning."},
    )
    client.post(f"/api/session/{session_id}/step", json={"count": 3})
    client.post(
        f"/api/session/{session_id}/checkpoint/template",
        json={"template": "after-change", "note": "After tuning."},
    )

    response = client.post(f"/api/session/{session_id}/visual-diff/export")

    assert response.status_code == 200
    body = response.json()
    assert Path(body["visual_diff_json_path"]).exists()
    assert Path(body["visual_diff_markdown_path"]).exists()
    assert body["visual_diff"]["status"] == "ready"
    assert body["visual_diff"]["pairs"][0]["before"]["template"] == "before-change"
    assert body["visual_diff"]["pairs"][0]["after"]["template"] == "after-change"
    assert "Before tuning." in body["visual_diff_markdown"]
    assert "After tuning." in body["visual_diff_markdown"]
    assert "baseline_before" in body["visual_diff_markdown"]
    assert "variant_after" in body["visual_diff_markdown"]


def test_visual_diff_export_creates_pixel_diff_artifacts_for_valid_pngs(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.sumocfg"
    variant = tmp_path / "variant.sumocfg"
    baseline.write_text("<configuration/>", encoding="utf-8")
    variant.write_text("<configuration/>", encoding="utf-8")

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    create_response = client.post(
        "/api/session/create",
        json={
            "name": "pixel-diff-demo",
            "baseline_config": str(baseline),
            "variant_config": str(variant),
        },
    )
    session_id = create_response.json()["id"]
    before_response = client.post(
        f"/api/session/{session_id}/checkpoint/template",
        json={"template": "before-change", "note": "Before tuning."},
    )
    write_rgb_png(Path(before_response.json()["screenshot"]["baseline_screenshot"]), (0, 0, 0))
    write_rgb_png(Path(before_response.json()["screenshot"]["variant_screenshot"]), (20, 20, 20))

    client.post(f"/api/session/{session_id}/step", json={"count": 3})
    after_response = client.post(
        f"/api/session/{session_id}/checkpoint/template",
        json={"template": "after-change", "note": "After tuning."},
    )
    write_rgb_png(Path(after_response.json()["screenshot"]["baseline_screenshot"]), (255, 255, 255))
    write_rgb_png(Path(after_response.json()["screenshot"]["variant_screenshot"]), (20, 20, 20))

    response = client.post(f"/api/session/{session_id}/visual-diff/export")

    assert response.status_code == 200
    body = response.json()
    pair = body["visual_diff"]["pairs"][0]
    assert pair["pixel_diff"]["status"] == "ready"
    assert pair["pixel_diff"]["baseline_changed_pixels"] == 1
    assert pair["pixel_diff"]["variant_changed_pixels"] == 0
    assert [row["role"] for row in pair["matrix"]] == ["baseline", "variant"]
    assert pair["matrix"][0] == {
        "role": "baseline",
        "label": "Baseline",
        "before": pair["baseline_before"],
        "after": pair["baseline_after"],
        "pixel_diff": pair["baseline_pixel_diff"],
        "changed_pixels": 1,
        "total_pixels": 1,
        "changed_pixel_ratio": 1.0,
    }
    assert pair["matrix"][1] == {
        "role": "variant",
        "label": "Variant",
        "before": pair["variant_before"],
        "after": pair["variant_after"],
        "pixel_diff": pair["variant_pixel_diff"],
        "changed_pixels": 0,
        "total_pixels": 1,
        "changed_pixel_ratio": 0.0,
    }
    assert Path(tmp_path / "runs" / session_id / pair["baseline_pixel_diff"]).exists()
    assert Path(tmp_path / "runs" / session_id / pair["variant_pixel_diff"]).exists()
    assert "Visual comparison matrix" in body["visual_diff_markdown"]
    assert "baseline_pixel_diff" in body["visual_diff_markdown"]
    assert "variant_pixel_diff" in body["visual_diff_markdown"]


def test_visual_observation_record_enters_evidence_review_and_prompt(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.sumocfg"
    variant = tmp_path / "variant.sumocfg"
    baseline.write_text("<configuration/>", encoding="utf-8")
    variant.write_text("<configuration/>", encoding="utf-8")

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)
    create_response = client.post(
        "/api/session/create",
        json={
            "name": "visual-observation-demo",
            "baseline_config": str(baseline),
            "variant_config": str(variant),
        },
    )
    session_id = create_response.json()["id"]
    client.post(f"/api/session/{session_id}/checkpoint/template", json={"template": "before-change"})
    client.post(f"/api/session/{session_id}/step", json={"count": 4})
    client.post(f"/api/session/{session_id}/checkpoint/template", json={"template": "after-change"})
    client.post(f"/api/session/{session_id}/visual-diff/export")

    response = client.post(
        f"/api/session/{session_id}/visual-observation/record",
        json={
            "label": "queue-growth-eastbound",
            "observation_type": "queue-growth",
            "evidence_artifact": "visual-diff.md",
            "confidence": "diagnostic",
            "note": "Variant appears to keep a longer eastbound queue after the change.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    observation = body["observation"]
    assert observation["label"] == "queue-growth-eastbound"
    assert observation["observation_type"] == "queue-growth"
    assert observation["evidence_artifact"] == "visual-diff.md"
    assert observation["confidence"] == "diagnostic"
    assert observation["simulation_time"] == 4
    assert "longer eastbound queue" in observation["note"]
    artifact_paths = {item["relative_path"] for item in body["evidence"]["artifacts"]}
    assert "visual-observations.json" in artifact_paths
    assert "visual-observations.md" in artifact_paths
    assert body["evidence"]["manifest"]["visual_observations"][0]["observation_type"] == "queue-growth"

    timeline_response = client.post(f"/api/session/{session_id}/timeline/export")
    assert timeline_response.status_code == 200
    timeline = timeline_response.json()
    assert "visual-observation" in {event["kind"] for event in timeline["timeline"]["events"]}
    assert "visual-observations.md" in timeline["timeline_markdown"]

    summary_response = client.post(f"/api/session/{session_id}/review/summary")
    assert summary_response.status_code == 200
    summary = summary_response.json()
    card_ids = {card["id"] for card in summary["review_summary"]["cards"]}
    assert "visual_observations" in card_ids
    assert "queue-growth" in summary["review_summary_markdown"]

    prompt_response = client.post(f"/api/session/{session_id}/agent-review-prompt/export")
    assert prompt_response.status_code == 200
    prompt = prompt_response.json()
    assert "visual-observations.md" in prompt["agent_prompt"]["artifacts_to_open"]
    assert "visual-observations.md" in prompt["agent_prompt_markdown"]


def test_visual_observation_record_includes_taxonomy_guidance(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.sumocfg"
    variant = tmp_path / "variant.sumocfg"
    baseline.write_text("<configuration/>", encoding="utf-8")
    variant.write_text("<configuration/>", encoding="utf-8")

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)
    create_response = client.post(
        "/api/session/create",
        json={
            "name": "taxonomy-observation-demo",
            "baseline_config": str(baseline),
            "variant_config": str(variant),
        },
    )
    session_id = create_response.json()["id"]

    response = client.post(
        f"/api/session/{session_id}/visual-observation/record",
        json={
            "label": "possible-spillback",
            "observation_type": "spillback",
            "evidence_artifact": "visual-diff.md",
            "confidence": "diagnostic",
            "note": "The downstream queue appears to block the upstream approach.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    observation = body["observation"]
    assert observation["taxonomy"]["label"] == "Spillback"
    assert "output-inspection.md" in observation["taxonomy"]["evidence_targets"]
    assert "does not prove causality" in observation["taxonomy"]["claim_boundary"]
    markdown_path = tmp_path / "runs" / session_id / "visual-observations.md"
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Evidence to check" in markdown
    assert "output-inspection.md" in markdown
    assert "does not prove causality" in markdown


def test_next_action_review_turns_visual_observations_into_next_actions(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.sumocfg"
    variant = tmp_path / "variant.sumocfg"
    baseline.write_text("<configuration/>", encoding="utf-8")
    variant.write_text("<configuration/>", encoding="utf-8")

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)
    create_response = client.post(
        "/api/session/create",
        json={
            "name": "next-action-review-demo",
            "baseline_config": str(baseline),
            "variant_config": str(variant),
        },
    )
    session_id = create_response.json()["id"]
    client.post(
        f"/api/session/{session_id}/scenario/plan",
        json={
            "label": "max-green-scenario",
            "parameter": "max_green",
            "before_value": "30",
            "after_value": "45",
            "hypothesis": "Longer green may reduce queues if completion remains paired.",
            "expected_metrics": ["completion_ratio", "mean_duration"],
        },
    )
    client.post(f"/api/session/{session_id}/checkpoint/first")
    client.post(f"/api/session/{session_id}/checkpoint/template", json={"template": "before-change"})
    client.post(
        f"/api/session/{session_id}/change/record",
        json={
            "label": "max-green-change",
            "parameter": "max_green",
            "before_value": "30",
            "after_value": "45",
            "rationale": "Check the queue response before claiming improvement.",
        },
    )
    client.post(f"/api/session/{session_id}/step", json={"count": 4})
    client.post(f"/api/session/{session_id}/checkpoint/template", json={"template": "after-change"})
    client.post(f"/api/session/{session_id}/visual-diff/export")
    client.post(
        f"/api/session/{session_id}/visual-observation/record",
        json={
            "label": "queue-growth-eastbound",
            "observation_type": "queue-growth",
            "evidence_artifact": "visual-diff.md",
            "confidence": "diagnostic",
            "note": "Variant appears to keep a longer eastbound queue after the change.",
        },
    )

    response = client.post(f"/api/session/{session_id}/next-action-review/export")

    assert response.status_code == 200
    body = response.json()
    review = body["next_action_review"]
    assert review["status"] == "needs-action"
    assert review["claim_status"] == "diagnostic-control-screen"
    assert review["visual_observations"][0]["observation_type"] == "queue-growth"
    assert review["recommended_actions"][0]["action"] == "Inspect Outputs"
    assert "completion" in review["recommended_actions"][0]["reason"]
    assert review["recommended_actions"][0]["evidence"] == "output-inspection.md"
    assert "does not prove causality" in review["claim_boundary"]
    assert Path(body["next_action_review_json_path"]).exists()
    assert Path(body["next_action_review_markdown_path"]).exists()
    assert "Inspect Outputs" in body["next_action_review_markdown"]
    assert "visual-observations.md" in body["next_action_review_markdown"]

    artifact_paths = {item["relative_path"] for item in body["evidence"]["artifacts"]}
    assert "next-action-review.json" in artifact_paths
    assert "next-action-review.md" in artifact_paths


def test_next_action_review_includes_taxonomy_missing_evidence_guidance(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.sumocfg"
    variant = tmp_path / "variant.sumocfg"
    baseline.write_text("<configuration/>", encoding="utf-8")
    variant.write_text("<configuration/>", encoding="utf-8")

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)
    create_response = client.post(
        "/api/session/create",
        json={
            "name": "taxonomy-next-action-demo",
            "baseline_config": str(baseline),
            "variant_config": str(variant),
        },
    )
    session_id = create_response.json()["id"]
    client.post(f"/api/session/{session_id}/checkpoint/template", json={"template": "before-change"})
    client.post(f"/api/session/{session_id}/step", json={"count": 2})
    client.post(f"/api/session/{session_id}/checkpoint/template", json={"template": "after-change"})
    client.post(f"/api/session/{session_id}/visual-diff/export")
    client.post(
        f"/api/session/{session_id}/visual-observation/record",
        json={
            "label": "possible-spillback",
            "observation_type": "spillback",
            "evidence_artifact": "visual-diff.md",
            "confidence": "diagnostic",
            "note": "The downstream queue appears to block the upstream approach.",
        },
    )

    response = client.post(f"/api/session/{session_id}/next-action-review/export")

    assert response.status_code == 200
    body = response.json()
    guidance = body["next_action_review"]["observation_guidance"]
    assert guidance[0]["label"] == "possible-spillback"
    assert guidance[0]["taxonomy_label"] == "Spillback"
    assert "output-inspection.md" in guidance[0]["missing_evidence_targets"]
    assert "timeline.md" in guidance[0]["missing_evidence_targets"]
    assert any("completion" in check for check in guidance[0]["evidence_checks"])
    assert "Inspect Outputs" in guidance[0]["suggested_next_actions"]
    assert "does not prove causality" in guidance[0]["claim_boundary"]
    assert "Observation guidance" in body["next_action_review_markdown"]
    assert "possible-spillback" in body["next_action_review_markdown"]
    assert "output-inspection.md" in body["next_action_review_markdown"]
    assert "does not prove causality" in body["next_action_review_markdown"]


def test_timeline_note_api_records_user_event_without_screenshot(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.sumocfg"
    variant = tmp_path / "variant.sumocfg"
    baseline.write_text("<configuration/>", encoding="utf-8")
    variant.write_text("<configuration/>", encoding="utf-8")

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    create_response = client.post(
        "/api/session/create",
        json={
            "name": "note-demo",
            "baseline_config": str(baseline),
            "variant_config": str(variant),
        },
    )
    session_id = create_response.json()["id"]

    response = client.post(
        f"/api/session/{session_id}/timeline/note",
        json={
            "label": "parameter-change",
            "note": "Changed max green from 30 to 45 seconds.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["note"]["label"] == "parameter-change"
    assert body["note"]["note"] == "Changed max green from 30 to 45 seconds."
    assert body["evidence"]["manifest"]["timeline_notes"][0]["label"] == "parameter-change"

    timeline_response = client.post(f"/api/session/{session_id}/timeline/export")

    assert timeline_response.status_code == 200
    timeline_body = timeline_response.json()
    event_kinds = [event["kind"] for event in timeline_body["timeline"]["events"]]
    assert "user-note" in event_kinds
    assert "Changed max green from 30 to 45 seconds." in timeline_body["timeline_markdown"]


def test_change_record_api_writes_structured_evidence_and_timeline_event(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.sumocfg"
    variant = tmp_path / "variant.sumocfg"
    baseline.write_text("<configuration/>", encoding="utf-8")
    variant.write_text("<configuration/>", encoding="utf-8")

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    create_response = client.post(
        "/api/session/create",
        json={
            "name": "change-record-demo",
            "baseline_config": str(baseline),
            "variant_config": str(variant),
        },
    )
    session_id = create_response.json()["id"]

    response = client.post(
        f"/api/session/{session_id}/change/record",
        json={
            "label": "max green tuning",
            "parameter": "max_green",
            "before_value": "30",
            "after_value": "45",
            "rationale": "Allow longer discharge after queue build-up.",
            "note": "Use before/after checkpoints to inspect the visual effect.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["change"]["label"] == "max-green-tuning"
    assert body["change"]["parameter"] == "max_green"
    assert body["change"]["before_value"] == "30"
    assert body["change"]["after_value"] == "45"
    assert body["evidence"]["manifest"]["change_records"][0]["parameter"] == "max_green"
    artifact_paths = {item["relative_path"] for item in body["evidence"]["artifacts"]}
    assert "change-records.json" in artifact_paths
    assert "change-records.md" in artifact_paths
    change_markdown = Path(tmp_path / "runs" / session_id / "change-records.md").read_text(encoding="utf-8")
    assert "max_green" in change_markdown
    assert "`30` -> `45`" in change_markdown

    timeline_response = client.post(f"/api/session/{session_id}/timeline/export")

    assert timeline_response.status_code == 200
    timeline_body = timeline_response.json()
    event_kinds = [event["kind"] for event in timeline_body["timeline"]["events"]]
    assert "change-record" in event_kinds
    assert "max_green: 30 -> 45" in timeline_body["timeline_markdown"]


def test_metric_comparison_api_writes_completion_first_delta_report(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.sumocfg"
    variant = tmp_path / "variant.sumocfg"
    baseline.write_text("<configuration/>", encoding="utf-8")
    variant.write_text("<configuration/>", encoding="utf-8")

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    create_response = client.post(
        "/api/session/create",
        json={
            "name": "metric-demo",
            "baseline_config": str(baseline),
            "variant_config": str(variant),
        },
    )
    session_id = create_response.json()["id"]
    client.post(
        f"/api/session/{session_id}/change/record",
        json={
            "label": "max-green-change",
            "parameter": "max_green",
            "before_value": "30",
            "after_value": "45",
            "rationale": "Test whether extra green reduces delay without reducing completion.",
        },
    )
    baseline_summary = tmp_path / "baseline-summary.xml"
    variant_summary = tmp_path / "variant-summary.xml"
    baseline_tripinfo = tmp_path / "baseline-tripinfo.xml"
    variant_tripinfo = tmp_path / "variant-tripinfo.xml"
    baseline_summary.write_text(
        '<summary><step time="10" loaded="2" inserted="2" running="0" waiting="0" arrived="2" teleports="0"/></summary>',
        encoding="utf-8",
    )
    variant_summary.write_text(
        '<summary><step time="10" loaded="2" inserted="2" running="0" waiting="0" arrived="2" teleports="0"/></summary>',
        encoding="utf-8",
    )
    baseline_tripinfo.write_text(
        '<tripinfos><tripinfo id="b0" duration="10" waitingTime="1" timeLoss="2"/><tripinfo id="b1" duration="20" waitingTime="3" timeLoss="4"/></tripinfos>',
        encoding="utf-8",
    )
    variant_tripinfo.write_text(
        '<tripinfos><tripinfo id="v0" duration="8" waitingTime="0" timeLoss="1"/><tripinfo id="v1" duration="18" waitingTime="2" timeLoss="3"/></tripinfos>',
        encoding="utf-8",
    )
    client.post(
        f"/api/session/{session_id}/outputs/inspect",
        json={
            "baseline_summary": str(baseline_summary),
            "baseline_tripinfo": str(baseline_tripinfo),
            "variant_summary": str(variant_summary),
            "variant_tripinfo": str(variant_tripinfo),
        },
    )

    response = client.post(f"/api/session/{session_id}/metrics/compare")

    assert response.status_code == 200
    body = response.json()
    report = body["metric_comparison"]
    assert report["status"] == "pass"
    assert report["change_records"][0]["parameter"] == "max_green"
    summary_by_metric = {item["metric"]: item for item in report["completion_metrics"]}
    tripinfo_by_metric = {item["metric"]: item for item in report["tripinfo_metrics"]}
    assert summary_by_metric["completion_ratio"]["baseline"] == 1.0
    assert summary_by_metric["completion_ratio"]["variant"] == 1.0
    assert summary_by_metric["completion_ratio"]["delta"] == 0.0
    assert tripinfo_by_metric["mean_duration"]["baseline"] == 15.0
    assert tripinfo_by_metric["mean_duration"]["variant"] == 13.0
    assert tripinfo_by_metric["mean_duration"]["delta"] == -2.0
    assert Path(body["metric_comparison_json_path"]).exists()
    assert Path(body["metric_comparison_markdown_path"]).exists()
    assert "Completion-first metrics" in body["metric_comparison_markdown"]
    assert "max_green" in body["metric_comparison_markdown"]
    assert "diagnostic metric comparison" in body["metric_comparison_markdown"]
    artifact_paths = {item["relative_path"] for item in body["evidence"]["artifacts"]}
    assert "metric-comparison.json" in artifact_paths
    assert "metric-comparison.md" in artifact_paths

    timeline_response = client.post(f"/api/session/{session_id}/timeline/export")

    assert timeline_response.status_code == 200
    timeline_body = timeline_response.json()
    event_kinds = [event["kind"] for event in timeline_body["timeline"]["events"]]
    assert "metric-comparison" in event_kinds
    assert "metric-comparison.md" in timeline_body["timeline_markdown"]


def test_metric_chart_api_writes_visual_delta_artifacts(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.sumocfg"
    variant = tmp_path / "variant.sumocfg"
    baseline.write_text("<configuration/>", encoding="utf-8")
    variant.write_text("<configuration/>", encoding="utf-8")

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    create_response = client.post(
        "/api/session/create",
        json={
            "name": "metric-chart-demo",
            "baseline_config": str(baseline),
            "variant_config": str(variant),
        },
    )
    session_id = create_response.json()["id"]
    baseline_summary = tmp_path / "baseline-summary.xml"
    variant_summary = tmp_path / "variant-summary.xml"
    baseline_tripinfo = tmp_path / "baseline-tripinfo.xml"
    variant_tripinfo = tmp_path / "variant-tripinfo.xml"
    baseline_summary.write_text(
        '<summary><step time="10" loaded="2" inserted="2" running="0" waiting="0" arrived="2" teleports="0"/></summary>',
        encoding="utf-8",
    )
    variant_summary.write_text(
        '<summary><step time="10" loaded="2" inserted="2" running="0" waiting="0" arrived="2" teleports="0"/></summary>',
        encoding="utf-8",
    )
    baseline_tripinfo.write_text(
        '<tripinfos><tripinfo id="b0" duration="10" waitingTime="1" timeLoss="2"/><tripinfo id="b1" duration="20" waitingTime="3" timeLoss="4"/></tripinfos>',
        encoding="utf-8",
    )
    variant_tripinfo.write_text(
        '<tripinfos><tripinfo id="v0" duration="8" waitingTime="0" timeLoss="1"/><tripinfo id="v1" duration="18" waitingTime="2" timeLoss="3"/></tripinfos>',
        encoding="utf-8",
    )
    client.post(
        f"/api/session/{session_id}/outputs/inspect",
        json={
            "baseline_summary": str(baseline_summary),
            "baseline_tripinfo": str(baseline_tripinfo),
            "variant_summary": str(variant_summary),
            "variant_tripinfo": str(variant_tripinfo),
        },
    )
    client.post(f"/api/session/{session_id}/metrics/compare")

    response = client.post(f"/api/session/{session_id}/metrics/chart")

    assert response.status_code == 200
    body = response.json()
    chart = body["metric_chart"]
    assert chart["status"] == "pass"
    chart_metrics = {row["metric"] for row in chart["rows"]}
    assert {"completion_ratio", "mean_duration", "mean_waiting_time", "mean_time_loss"}.issubset(chart_metrics)
    assert '<svg xmlns="http://www.w3.org/2000/svg"' in body["metric_chart_svg"]
    assert "variant - baseline" in body["metric_chart_svg"]
    assert "Mean duration" in body["metric_chart_svg"]
    assert "metric-delta-chart.svg" in body["metric_chart_markdown"]
    assert "diagnostic visualization" in body["metric_chart_markdown"]
    assert Path(body["metric_chart_svg_path"]).exists()
    assert Path(body["metric_chart_markdown_path"]).exists()

    artifact_paths = {item["relative_path"] for item in body["evidence"]["artifacts"]}
    assert "metric-delta-chart.svg" in artifact_paths
    assert "metric-delta-chart.md" in artifact_paths

    client.post(f"/api/session/{session_id}/packet/export")
    packet = client.post(f"/api/session/{session_id}/packet/export").json()
    assert "Metric Delta Chart" in packet["packet_markdown"]
    assert "metric-delta-chart.md" in packet["packet_markdown"]

    timeline_response = client.post(f"/api/session/{session_id}/timeline/export?preset=outputs")
    timeline_body = timeline_response.json()
    event_kinds = [event["kind"] for event in timeline_body["timeline"]["events"]]
    assert "metric-chart" in event_kinds
    assert "metric-delta-chart.svg" in timeline_body["timeline_markdown"]

    client.post(f"/api/session/{session_id}/checkpoint/first")
    client.post(
        f"/api/session/{session_id}/checkpoint/template",
        json={"template": "before-change", "note": "Before tuning."},
    )
    client.post(
        f"/api/session/{session_id}/checkpoint/template",
        json={"template": "after-change", "note": "After tuning."},
    )
    client.post(f"/api/session/{session_id}/visual-diff/export")
    client.post(f"/api/session/{session_id}/timeline/export")
    client.post(f"/api/session/{session_id}/packet/export")
    summary_response = client.post(f"/api/session/{session_id}/review/summary")
    card_ids = {card["id"] for card in summary_response.json()["review_summary"]["cards"]}
    assert "metric_chart" in card_ids
    assert "metric-delta-chart.md" in summary_response.json()["review_summary_markdown"]


def test_review_summary_api_writes_compact_claim_dashboard(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.sumocfg"
    variant = tmp_path / "variant.sumocfg"
    baseline.write_text("<configuration/>", encoding="utf-8")
    variant.write_text("<configuration/>", encoding="utf-8")

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    create_response = client.post(
        "/api/session/create",
        json={
            "name": "review-summary-demo",
            "baseline_config": str(baseline),
            "variant_config": str(variant),
        },
    )
    session_id = create_response.json()["id"]
    client.post(f"/api/session/{session_id}/checkpoint/first")
    client.post(
        f"/api/session/{session_id}/checkpoint/template",
        json={"template": "before-change", "note": "Before tuning."},
    )
    client.post(f"/api/session/{session_id}/step", json={"count": 2})
    client.post(
        f"/api/session/{session_id}/checkpoint/template",
        json={"template": "after-change", "note": "After tuning."},
    )
    client.post(
        f"/api/session/{session_id}/timeline/note",
        json={"label": "parameter-change", "note": "Changed max green after inspecting the first checkpoint."},
    )
    client.post(
        f"/api/session/{session_id}/change/record",
        json={
            "label": "max-green-change",
            "parameter": "max_green",
            "before_value": "30",
            "after_value": "45",
            "rationale": "Check whether extra green improves duration without reducing completion.",
        },
    )
    baseline_summary = tmp_path / "baseline-summary.xml"
    variant_summary = tmp_path / "variant-summary.xml"
    baseline_tripinfo = tmp_path / "baseline-tripinfo.xml"
    variant_tripinfo = tmp_path / "variant-tripinfo.xml"
    baseline_summary.write_text(
        '<summary><step time="10" loaded="2" inserted="2" running="0" waiting="0" arrived="2" teleports="0"/></summary>',
        encoding="utf-8",
    )
    variant_summary.write_text(
        '<summary><step time="10" loaded="2" inserted="2" running="0" waiting="0" arrived="2" teleports="0"/></summary>',
        encoding="utf-8",
    )
    baseline_tripinfo.write_text(
        '<tripinfos><tripinfo id="b0" duration="10" waitingTime="1" timeLoss="2"/><tripinfo id="b1" duration="20" waitingTime="3" timeLoss="4"/></tripinfos>',
        encoding="utf-8",
    )
    variant_tripinfo.write_text(
        '<tripinfos><tripinfo id="v0" duration="8" waitingTime="0" timeLoss="1"/><tripinfo id="v1" duration="18" waitingTime="2" timeLoss="3"/></tripinfos>',
        encoding="utf-8",
    )
    client.post(
        f"/api/session/{session_id}/outputs/inspect",
        json={
            "baseline_summary": str(baseline_summary),
            "baseline_tripinfo": str(baseline_tripinfo),
            "variant_summary": str(variant_summary),
            "variant_tripinfo": str(variant_tripinfo),
        },
    )
    client.post(f"/api/session/{session_id}/metrics/compare")
    client.post(f"/api/session/{session_id}/visual-diff/export")
    client.post(f"/api/session/{session_id}/timeline/export")
    client.post(f"/api/session/{session_id}/packet/export")

    response = client.post(f"/api/session/{session_id}/review/summary")

    assert response.status_code == 200
    body = response.json()
    summary = body["review_summary"]
    assert summary["status"] == "review-ready"
    assert summary["claim_status"] == "evidence-index-ready"
    card_ids = {card["id"] for card in summary["cards"]}
    assert {"change_records", "metric_comparison", "visual_diff", "workflow"}.issubset(card_ids)
    highlights = {item["metric"]: item for item in summary["metric_highlights"]}
    assert highlights["completion_ratio"]["delta"] == 0.0
    assert highlights["mean_duration"]["delta"] == -2.0
    assert "Claim boundary" in body["review_summary_markdown"]
    assert "metric-comparison.md" in body["review_summary_markdown"]
    assert "visual-diff.md" in body["review_summary_markdown"]
    assert "change-records.md" in body["review_summary_markdown"]
    assert Path(body["review_summary_json_path"]).exists()
    assert Path(body["review_summary_markdown_path"]).exists()

    artifact_paths = {item["relative_path"] for item in body["evidence"]["artifacts"]}
    assert "review-summary.json" in artifact_paths
    assert "review-summary.md" in artifact_paths

    timeline_response = client.post(f"/api/session/{session_id}/timeline/export")
    event_kinds = [event["kind"] for event in timeline_response.json()["timeline"]["events"]]
    assert "review-summary" in event_kinds


def test_scenario_guide_tracks_before_after_evidence_sequence(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.sumocfg"
    variant = tmp_path / "variant.sumocfg"
    baseline.write_text("<configuration/>", encoding="utf-8")
    variant.write_text("<configuration/>", encoding="utf-8")

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    create_response = client.post(
        "/api/session/create",
        json={
            "name": "scenario-guide-demo",
            "baseline_config": str(baseline),
            "variant_config": str(variant),
        },
    )
    session_id = create_response.json()["id"]

    plan_response = client.post(
        f"/api/session/{session_id}/scenario/plan",
        json={
            "label": "max-green-scenario",
            "parameter": "max_green",
            "before_value": "30",
            "after_value": "45",
            "hypothesis": "Longer green should reduce duration if completion remains unchanged.",
            "expected_metrics": ["completion_ratio", "mean_duration"],
            "note": "Use before/after checkpoints around the parameter change.",
        },
    )

    assert plan_response.status_code == 200
    body = plan_response.json()
    assert body["scenario_plan"]["parameter"] == "max_green"
    assert body["scenario_status"]["status"] == "needs-evidence"
    assert body["scenario_status"]["current_step"] == "Capture First Checkpoint."
    assert Path(body["scenario_plan_json_path"]).exists()
    assert Path(body["scenario_plan_markdown_path"]).exists()
    assert "max_green" in body["scenario_plan_markdown"]
    artifact_paths = {item["relative_path"] for item in body["evidence"]["artifacts"]}
    assert "scenario-plan.json" in artifact_paths
    assert "scenario-plan.md" in artifact_paths

    client.post(f"/api/session/{session_id}/checkpoint/first")
    client.post(
        f"/api/session/{session_id}/checkpoint/template",
        json={"template": "before-change", "note": "Before changing max green."},
    )
    status_after_before = client.get(f"/api/session/{session_id}/scenario/status").json()
    assert status_after_before["current_step"] == "Record Change with the planned parameter, before value, after value, and rationale."

    client.post(
        f"/api/session/{session_id}/change/record",
        json={
            "label": "max-green-change",
            "parameter": "max_green",
            "before_value": "30",
            "after_value": "45",
            "rationale": "Use the scenario plan hypothesis as the change rationale.",
        },
    )
    client.post(
        f"/api/session/{session_id}/checkpoint/template",
        json={"template": "after-change", "note": "After changing max green."},
    )
    client.post(f"/api/session/{session_id}/visual-diff/export")

    baseline_summary = tmp_path / "baseline-summary.xml"
    variant_summary = tmp_path / "variant-summary.xml"
    baseline_tripinfo = tmp_path / "baseline-tripinfo.xml"
    variant_tripinfo = tmp_path / "variant-tripinfo.xml"
    baseline_summary.write_text(
        '<summary><step time="10" loaded="2" inserted="2" running="0" waiting="0" arrived="2" teleports="0"/></summary>',
        encoding="utf-8",
    )
    variant_summary.write_text(
        '<summary><step time="10" loaded="2" inserted="2" running="0" waiting="0" arrived="2" teleports="0"/></summary>',
        encoding="utf-8",
    )
    baseline_tripinfo.write_text(
        '<tripinfos><tripinfo id="b0" duration="10" waitingTime="1" timeLoss="2"/><tripinfo id="b1" duration="20" waitingTime="3" timeLoss="4"/></tripinfos>',
        encoding="utf-8",
    )
    variant_tripinfo.write_text(
        '<tripinfos><tripinfo id="v0" duration="8" waitingTime="0" timeLoss="1"/><tripinfo id="v1" duration="18" waitingTime="2" timeLoss="3"/></tripinfos>',
        encoding="utf-8",
    )
    client.post(
        f"/api/session/{session_id}/outputs/inspect",
        json={
            "baseline_summary": str(baseline_summary),
            "baseline_tripinfo": str(baseline_tripinfo),
            "variant_summary": str(variant_summary),
            "variant_tripinfo": str(variant_tripinfo),
        },
    )
    client.post(f"/api/session/{session_id}/metrics/compare")
    client.post(f"/api/session/{session_id}/metrics/chart")
    client.post(f"/api/session/{session_id}/timeline/export")
    client.post(f"/api/session/{session_id}/review/summary")
    client.post(f"/api/session/{session_id}/packet/export")

    final_status_response = client.get(f"/api/session/{session_id}/scenario/status")

    assert final_status_response.status_code == 200
    final_status = final_status_response.json()
    assert final_status["status"] == "ready-for-review"
    assert final_status["current_step"] == "Ask Codex to inspect scenario-plan.md, review-summary.md, metric-delta-chart.md, visual-diff.md, and codex-packet.md."
    checklist = {item["id"]: item for item in final_status["checklist"]}
    assert checklist["scenario_plan"]["status"] == "pass"
    assert checklist["first_checkpoint"]["status"] == "pass"
    assert checklist["before_checkpoint"]["status"] == "pass"
    assert checklist["change_record"]["status"] == "pass"
    assert checklist["after_checkpoint"]["status"] == "pass"
    assert checklist["output_inspection"]["status"] == "pass"
    assert checklist["metric_comparison"]["status"] == "pass"
    assert checklist["metric_chart"]["status"] == "pass"
    assert checklist["visual_diff"]["status"] == "pass"
    assert checklist["timeline"]["status"] == "pass"
    assert checklist["review_summary"]["status"] == "pass"
    assert checklist["codex_packet"]["status"] == "pass"

    timeline = client.post(f"/api/session/{session_id}/timeline/export?preset=review").json()
    event_kinds = [event["kind"] for event in timeline["timeline"]["events"]]
    assert "scenario-plan" in event_kinds
    assert "scenario-plan.md" in timeline["timeline_markdown"]

    packet = client.post(f"/api/session/{session_id}/packet/export").json()
    assert "Scenario Plan" in packet["packet_markdown"]
    assert "scenario-plan.md" in packet["packet_markdown"]

    summary = client.post(f"/api/session/{session_id}/review/summary").json()
    card_ids = {card["id"] for card in summary["review_summary"]["cards"]}
    assert "scenario_plan" in card_ids
    assert "scenario-plan.md" in summary["review_summary_markdown"]


def test_comparison_readiness_reports_core_before_after_gate(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.sumocfg"
    variant = tmp_path / "variant.sumocfg"
    baseline.write_text("<configuration/>", encoding="utf-8")
    variant.write_text("<configuration/>", encoding="utf-8")

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    create_response = client.post(
        "/api/session/create",
        json={
            "name": "comparison-readiness-demo",
            "baseline_config": str(baseline),
            "variant_config": str(variant),
        },
    )
    session_id = create_response.json()["id"]

    initial_response = client.get(f"/api/session/{session_id}/comparison/readiness")

    assert initial_response.status_code == 200
    initial = initial_response.json()
    assert initial["status"] == "needs-evidence"
    assert initial["claim_status"] == "diagnostic-incomplete"
    initial_checks = {item["id"]: item for item in initial["checklist"]}
    assert initial_checks["scenario_plan"]["status"] == "missing"
    assert any("Create Scenario Plan" in action for action in initial["next_actions"])

    client.post(
        f"/api/session/{session_id}/scenario/plan",
        json={
            "label": "step-length-scenario",
            "parameter": "step-length",
            "before_value": "1.0",
            "after_value": "0.5",
            "hypothesis": "Shorter step length should alter simulation resolution, not certify performance.",
            "expected_metrics": ["completion_ratio", "mean_duration"],
        },
    )
    client.post(f"/api/session/{session_id}/checkpoint/first")
    client.post(
        f"/api/session/{session_id}/checkpoint/template",
        json={"template": "before-change", "note": "Before config patch."},
    )
    client.post(
        f"/api/session/{session_id}/change/record",
        json={
            "label": "step-length-change",
            "parameter": "step-length",
            "before_value": "1.0",
            "after_value": "0.5",
            "rationale": "Record the config copy generated from the scenario guide.",
        },
    )
    client.post(
        f"/api/session/{session_id}/checkpoint/template",
        json={"template": "after-change", "note": "After config patch."},
    )
    baseline_summary = tmp_path / "baseline-summary.xml"
    variant_summary = tmp_path / "variant-summary.xml"
    baseline_summary.write_text(
        '<summary><step time="10" loaded="2" inserted="2" running="0" waiting="0" arrived="2" teleports="0"/></summary>',
        encoding="utf-8",
    )
    variant_summary.write_text(
        '<summary><step time="10" loaded="2" inserted="2" running="0" waiting="0" arrived="2" teleports="0"/></summary>',
        encoding="utf-8",
    )
    client.post(
        f"/api/session/{session_id}/outputs/inspect",
        json={
            "baseline_summary": str(baseline_summary),
            "variant_summary": str(variant_summary),
        },
    )
    client.post(f"/api/session/{session_id}/metrics/compare")
    client.post(f"/api/session/{session_id}/visual-diff/export")

    ready_response = client.get(f"/api/session/{session_id}/comparison/readiness")

    assert ready_response.status_code == 200
    ready = ready_response.json()
    assert ready["status"] == "ready-to-compare"
    assert ready["claim_status"] == "diagnostic-comparison-ready"
    checks = {item["id"]: item for item in ready["checklist"]}
    assert checks["scenario_plan"]["status"] == "pass"
    assert checks["first_checkpoint"]["status"] == "pass"
    assert checks["before_after_checkpoints"]["status"] == "pass"
    assert checks["change_record"]["status"] == "pass"
    assert checks["output_inspection"]["status"] == "pass"
    assert checks["metric_comparison"]["status"] == "pass"
    assert checks["visual_diff"]["status"] == "pass"
    assert checks["review_summary"]["status"] == "recommended"
    assert any("Export Review Summary" in action for action in ready["next_actions"])


def test_agent_review_prompt_export_writes_copyable_codex_prompt(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.sumocfg"
    variant = tmp_path / "variant.sumocfg"
    baseline.write_text("<configuration/>", encoding="utf-8")
    variant.write_text("<configuration/>", encoding="utf-8")
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

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)
    create_response = client.post(
        "/api/session/create",
        json={
            "name": "agent-prompt-demo",
            "baseline_config": str(baseline),
            "variant_config": str(variant),
        },
    )
    session_id = create_response.json()["id"]
    client.post(
        f"/api/session/{session_id}/scenario/plan",
        json={
            "label": "agent-prompt-scenario",
            "parameter": "max_green",
            "before_value": "30",
            "after_value": "45",
            "hypothesis": "A longer max_green may change queues.",
            "expected_metrics": ["completion_ratio", "mean_duration"],
            "note": "Prompt bridge test.",
        },
    )
    client.post(f"/api/session/{session_id}/checkpoint/first")
    client.post(f"/api/session/{session_id}/checkpoint/template", json={"template": "before-change"})
    client.post(
        f"/api/session/{session_id}/change/record",
        json={
            "label": "max-green-change",
            "parameter": "max_green",
            "before_value": "30",
            "after_value": "45",
            "rationale": "Expose the planned before/after change to Codex.",
        },
    )
    client.post(f"/api/session/{session_id}/step", json={"count": 2})
    client.post(f"/api/session/{session_id}/checkpoint/template", json={"template": "after-change"})
    client.post(
        f"/api/session/{session_id}/outputs/inspect",
        json={
            "baseline_summary": str(baseline_summary),
            "variant_summary": str(variant_summary),
        },
    )
    client.post(f"/api/session/{session_id}/metrics/compare")
    client.post(f"/api/session/{session_id}/visual-diff/export")
    client.post(f"/api/session/{session_id}/review/summary")
    client.post(f"/api/session/{session_id}/packet/export")

    response = client.post(f"/api/session/{session_id}/agent-review-prompt/export")

    assert response.status_code == 200
    body = response.json()
    assert Path(body["agent_prompt_json_path"]).exists()
    assert Path(body["agent_prompt_markdown_path"]).exists()
    prompt = body["agent_prompt"]
    assert prompt["readiness_status"] == "ready-to-compare"
    assert prompt["claim_status"] == "diagnostic-comparison-ready"
    assert "review-summary.md" in prompt["artifacts_to_open"]
    assert "codex-packet.md" in prompt["artifacts_to_open"]
    assert "metric-comparison.md" in prompt["artifacts_to_open"]
    assert "visual-diff.md" in prompt["artifacts_to_open"]
    assert "Use this prompt in Codex or Claude" in body["agent_prompt_markdown"]
    assert "Report only supported visual and metric differences" in body["agent_prompt_markdown"]
    assert "Do not claim causality, performance improvement, or publishable validity" in body["agent_prompt_markdown"]
    artifact_paths = {item["relative_path"] for item in body["evidence"]["artifacts"]}
    assert "agent-review-prompt.json" in artifact_paths
    assert "agent-review-prompt.md" in artifact_paths


def test_workflow_status_guides_incomplete_session_next_actions(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.sumocfg"
    variant = tmp_path / "variant.sumocfg"
    baseline.write_text("<configuration/>", encoding="utf-8")
    variant.write_text("<configuration/>", encoding="utf-8")

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    create_response = client.post(
        "/api/session/create",
        json={
            "name": "workflow-demo",
            "baseline_config": str(baseline),
            "variant_config": str(variant),
        },
    )
    session_id = create_response.json()["id"]

    response = client.get(f"/api/session/{session_id}/workflow/status")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs-evidence"
    assert body["claim_status"] == "diagnostic-incomplete"
    checklist = {item["id"]: item for item in body["checklist"]}
    assert checklist["first_checkpoint"]["status"] == "missing"
    assert checklist["output_inspection"]["status"] == "missing"
    assert any("Capture First Checkpoint" in action for action in body["next_actions"])


def test_workflow_status_reports_review_ready_session(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.sumocfg"
    variant = tmp_path / "variant.sumocfg"
    baseline.write_text("<configuration/>", encoding="utf-8")
    variant.write_text("<configuration/>", encoding="utf-8")

    app = create_app(adapter_factory=FakeAdapterFactory(), default_output_root=tmp_path / "runs")
    client = TestClient(app)

    create_response = client.post(
        "/api/session/create",
        json={
            "name": "workflow-ready-demo",
            "baseline_config": str(baseline),
            "variant_config": str(variant),
        },
    )
    session_id = create_response.json()["id"]
    client.post(f"/api/session/{session_id}/checkpoint/first")
    client.post(
        f"/api/session/{session_id}/checkpoint/template",
        json={"template": "before-change", "note": "Before tuning."},
    )
    client.post(f"/api/session/{session_id}/step", json={"count": 2})
    client.post(
        f"/api/session/{session_id}/checkpoint/template",
        json={"template": "after-change", "note": "After tuning."},
    )
    client.post(
        f"/api/session/{session_id}/timeline/note",
        json={"label": "parameter-change", "note": "Changed max green."},
    )
    client.post(
        f"/api/session/{session_id}/change/record",
        json={
            "label": "max-green-change",
            "parameter": "max_green",
            "before_value": "30",
            "after_value": "45",
            "rationale": "Record the controller parameter changed between before/after checkpoints.",
        },
    )
    baseline_summary = tmp_path / "baseline-summary.xml"
    variant_summary = tmp_path / "variant-summary.xml"
    baseline_summary.write_text(
        '<summary><step time="10" loaded="2" inserted="2" running="0" waiting="0" arrived="2" teleports="0"/></summary>',
        encoding="utf-8",
    )
    variant_summary.write_text(
        '<summary><step time="10" loaded="2" inserted="2" running="0" waiting="0" arrived="2" teleports="0"/></summary>',
        encoding="utf-8",
    )
    client.post(
        f"/api/session/{session_id}/outputs/inspect",
        json={
            "baseline_summary": str(baseline_summary),
            "variant_summary": str(variant_summary),
        },
    )
    client.post(f"/api/session/{session_id}/metrics/compare")
    client.post(f"/api/session/{session_id}/visual-diff/export")
    client.post(f"/api/session/{session_id}/timeline/export")
    client.post(f"/api/session/{session_id}/packet/export")

    response = client.get(f"/api/session/{session_id}/workflow/status")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "review-ready"
    assert body["claim_status"] == "evidence-index-ready"
    checklist = {item["id"]: item for item in body["checklist"]}
    assert checklist["first_checkpoint"]["status"] == "pass"
    assert checklist["template_pair"]["status"] == "pass"
    assert checklist["output_inspection"]["status"] == "pass"
    assert checklist["metric_comparison"]["status"] == "pass"
    assert checklist["visual_diff"]["status"] in {"pass", "warn"}
    assert checklist["timeline"]["status"] == "pass"
    assert checklist["codex_packet"]["status"] == "pass"
    assert body["next_actions"] == ["Ask Codex to inspect codex-packet.md, timeline.md, metric-comparison.md, visual-diff.md, and output-inspection.md."]


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
