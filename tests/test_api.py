from pathlib import Path
from shutil import which
import struct
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
    assert Path(body["packet"]["packet_path"]).name == "codex-packet.md"
    assert Path(body["metric_chart"]["metric_chart_svg_path"]).name == "metric-delta-chart.svg"
    assert Path(body["review_summary"]["review_summary_markdown_path"]).name == "review-summary.md"
    assert "Output Inspection" in body["packet"]["packet_markdown"]
    assert "Metric Delta Chart" in body["packet"]["packet_markdown"]
    assert "Review Summary" in body["packet"]["packet_markdown"]
    assert "Claim boundary" in body["review_summary"]["review_summary_markdown"]
    assert "metric-delta-chart.md" in body["review_summary"]["review_summary_markdown"]
    assert body["workflow"]["status"] == "review-ready"
    assert body["workflow"]["claim_status"] == "evidence-index-ready"

    artifact_paths = {item["relative_path"] for item in body["evidence"]["artifacts"]}
    assert "output-inspection.json" in artifact_paths
    assert "output-inspection.md" in artifact_paths
    assert "visual-diff.json" in artifact_paths
    assert "visual-diff.md" in artifact_paths
    assert "metric-comparison.json" in artifact_paths
    assert "metric-comparison.md" in artifact_paths
    assert "metric-delta-chart.svg" in artifact_paths
    assert "metric-delta-chart.md" in artifact_paths
    assert "review-summary.json" in artifact_paths
    assert "review-summary.md" in artifact_paths
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
    assert Path(tmp_path / "runs" / session_id / pair["baseline_pixel_diff"]).exists()
    assert Path(tmp_path / "runs" / session_id / pair["variant_pixel_diff"]).exists()
    assert "baseline_pixel_diff" in body["visual_diff_markdown"]
    assert "variant_pixel_diff" in body["visual_diff_markdown"]


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
