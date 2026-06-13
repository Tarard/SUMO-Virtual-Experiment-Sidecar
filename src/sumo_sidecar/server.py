from __future__ import annotations

from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config_preflight import preflight_pair
from .config_patch import patch_sumo_config_option
from .demo_runner import minimal_paired_metadata, run_minimal_paired_guided, run_minimal_paired_headless
from .models import (
    ChangeRecordRequest,
    ConfigPatchRequest,
    ConfigPreflightRequest,
    CreateSessionRequest,
    OutputInspectionRequest,
    RunUntilRequest,
    ScreenshotRequest,
    ScenarioPlanRequest,
    StepRequest,
    TemplateCheckpointRequest,
    TimelineNoteRequest,
    VisualObservationRequest,
)
from .output_inspection import inspect_output_pair
from .scenario_templates import list_scenario_templates
from .session_manager import AdapterFactory, SessionManager
from .sumo_adapter import preflight


def create_app(
    adapter_factory: AdapterFactory | None = None,
    default_output_root: Path | None = None,
) -> FastAPI:
    app = FastAPI(title="SUMO Virtual Experiment Sidecar", version="0.1.0")
    manager = SessionManager(adapter_factory=adapter_factory, default_output_root=default_output_root)
    repo_root = Path(__file__).resolve().parents[2]
    static_dir = repo_root / "static"

    @app.get("/api/preflight")
    def api_preflight() -> dict[str, Any]:
        return preflight()

    @app.get("/api/scenario/templates")
    def api_scenario_templates() -> dict[str, Any]:
        return {"templates": list_scenario_templates()}

    @app.get("/api/examples/minimal-paired")
    def api_minimal_paired_example() -> dict[str, Any]:
        metadata = minimal_paired_metadata(repo_root)
        if not Path(metadata["root"]).exists():
            raise HTTPException(status_code=404, detail="minimal paired example is not available")
        return metadata

    @app.post("/api/examples/minimal-paired/run-headless")
    def api_run_minimal_paired_headless() -> dict[str, Any]:
        try:
            return run_minimal_paired_headless(repo_root)
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/examples/minimal-paired/run-guided")
    def api_run_minimal_paired_guided() -> dict[str, Any]:
        try:
            return run_minimal_paired_guided(repo_root)
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/examples/minimal-paired/launch-gui")
    def api_launch_minimal_paired_gui() -> dict[str, Any]:
        metadata = minimal_paired_metadata(repo_root)
        try:
            session = manager.create(
                CreateSessionRequest(
                    name=metadata["gui_session_name"],
                    baseline_config=Path(metadata["baseline_config"]),
                    variant_config=Path(metadata["variant_config"]),
                    start=False,
                    quit_on_end=False,
                )
            )
            return manager.state(session.id).model_dump(mode="json")
        except (FileNotFoundError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/examples/minimal-paired/launch-guided-gui")
    def api_launch_minimal_paired_guided_gui() -> dict[str, Any]:
        metadata = minimal_paired_metadata(repo_root)
        try:
            guided_demo = run_minimal_paired_guided(repo_root)
            session = manager.create(
                CreateSessionRequest(
                    name=metadata["gui_session_name"],
                    baseline_config=Path(metadata["baseline_config"]),
                    variant_config=Path(metadata["variant_config"]),
                    start=False,
                    quit_on_end=False,
                )
            )
            output_inspection = manager.inspect_outputs(
                session.id,
                OutputInspectionRequest(
                    baseline_summary=Path(metadata["baseline_summary"]),
                    baseline_tripinfo=Path(metadata["baseline_tripinfo"]),
                    variant_summary=Path(metadata["variant_summary"]),
                    variant_tripinfo=Path(metadata["variant_tripinfo"]),
                ),
            )
            evidence = manager.evidence(session.id)
            status = "fail" if "fail" in {guided_demo["status"], output_inspection.status} else (
                "warn" if "warn" in {guided_demo["status"], output_inspection.status} else "pass"
            )
            return {
                "status": status,
                "guided_demo": guided_demo,
                "session": manager.state(session.id).model_dump(mode="json"),
                "output_inspection": output_inspection.model_dump(mode="json"),
                "evidence": evidence.model_dump(mode="json"),
            }
        except (FileNotFoundError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/examples/minimal-paired/launch-full-workflow-gui")
    def api_launch_minimal_paired_full_workflow_gui() -> dict[str, Any]:
        metadata = minimal_paired_metadata(repo_root)
        try:
            guided_demo = run_minimal_paired_guided(repo_root)
            session = manager.create(
                CreateSessionRequest(
                    name=metadata["gui_session_name"],
                    baseline_config=Path(metadata["baseline_config"]),
                    variant_config=Path(metadata["variant_config"]),
                    start=False,
                    quit_on_end=False,
                )
            )
            output_inspection = manager.inspect_outputs(
                session.id,
                OutputInspectionRequest(
                    baseline_summary=Path(metadata["baseline_summary"]),
                    baseline_tripinfo=Path(metadata["baseline_tripinfo"]),
                    variant_summary=Path(metadata["variant_summary"]),
                    variant_tripinfo=Path(metadata["variant_tripinfo"]),
                ),
            )
            scenario_plan = manager.plan_scenario(
                session.id,
                ScenarioPlanRequest(
                    label="demo-step-scenario",
                    parameter="paired_demo_step_count",
                    before_value="0",
                    after_value="2",
                    hypothesis="A short paired step interval should create visible diagnostic progress while completion evidence remains unchanged.",
                    expected_metrics=["completion_ratio", "mean_duration"],
                    note="This scenario demonstrates the evidence workflow, not controller performance.",
                ),
            )
            first_checkpoint = manager.screenshot(session.id, "first-checkpoint")
            timeline_note = manager.add_timeline_note(
                session.id,
                "demo-workflow",
                "Bundled minimal demo full workflow: guided config/output evidence plus paired GUI checkpoints.",
            )
            change_record = manager.record_change(
                session.id,
                ChangeRecordRequest(
                    label="demo-step-change",
                    parameter="paired_demo_step_count",
                    before_value="0",
                    after_value="2",
                    rationale="Create a small before/after visual interval for the bundled public demo.",
                    note="This records the demonstration action, not a controller-performance change.",
                ),
            )
            before_checkpoint = manager.checkpoint(
                session.id,
                "before-change",
                "Before stepping the paired demo GUI sessions.",
            )
            manager.step(session.id, 2)
            after_checkpoint = manager.checkpoint(
                session.id,
                "after-change",
                "After stepping both paired demo GUI sessions by 2 simulation steps.",
            )
            visual_diff = manager.export_visual_diff(session.id)
            metric_comparison = manager.export_metric_comparison(session.id)
            metric_chart = manager.export_metric_chart(session.id)
            packet = manager.export_packet(session.id)
            timeline = manager.export_timeline(session.id, preset="full")
            review_timeline = manager.export_timeline(session.id, preset="review")
            review_summary = manager.export_review_summary(session.id)
            packet = manager.export_packet(session.id)
            timeline = manager.export_timeline(session.id, preset="full")
            review_timeline = manager.export_timeline(session.id, preset="review")
            agent_prompt = manager.export_agent_review_prompt(session.id)
            workflow = manager.workflow_status(session.id)
            evidence = manager.evidence(session.id)

            if "fail" in {guided_demo["status"], output_inspection.status}:
                status = "fail"
            elif workflow["status"] == "review-ready-with-warnings":
                status = "warn"
            else:
                status = "pass"

            return {
                "status": status,
                "guided_demo": guided_demo,
                "session": manager.state(session.id).model_dump(mode="json"),
                "output_inspection": output_inspection.model_dump(mode="json"),
                "checkpoints": {
                    "first": first_checkpoint.model_dump(mode="json"),
                    "before": before_checkpoint.model_dump(mode="json"),
                    "after": after_checkpoint.model_dump(mode="json"),
                },
                "scenario_plan": {
                    "scenario_plan": scenario_plan["scenario_plan"],
                    "scenario_plan_json_path": str(scenario_plan["scenario_plan_json_path"]),
                    "scenario_plan_markdown_path": str(scenario_plan["scenario_plan_markdown_path"]),
                    "scenario_plan_markdown": scenario_plan["scenario_plan_markdown"],
                },
                "timeline_note": timeline_note,
                "change_record": change_record,
                "visual_diff": {
                    "visual_diff": visual_diff["visual_diff"],
                    "visual_diff_json_path": str(visual_diff["visual_diff_json_path"]),
                    "visual_diff_markdown_path": str(visual_diff["visual_diff_markdown_path"]),
                    "visual_diff_markdown": visual_diff["visual_diff_markdown"],
                },
                "metric_comparison": {
                    "metric_comparison": metric_comparison["metric_comparison"],
                    "metric_comparison_json_path": str(metric_comparison["metric_comparison_json_path"]),
                    "metric_comparison_markdown_path": str(metric_comparison["metric_comparison_markdown_path"]),
                    "metric_comparison_markdown": metric_comparison["metric_comparison_markdown"],
                },
                "metric_chart": {
                    "metric_chart": metric_chart["metric_chart"],
                    "metric_chart_svg_path": str(metric_chart["metric_chart_svg_path"]),
                    "metric_chart_markdown_path": str(metric_chart["metric_chart_markdown_path"]),
                    "metric_chart_svg": metric_chart["metric_chart_svg"],
                    "metric_chart_markdown": metric_chart["metric_chart_markdown"],
                },
                "packet": {
                    "packet_path": str(packet["packet_path"]),
                    "packet_markdown": packet["packet_markdown"],
                },
                "agent_prompt": {
                    "agent_prompt_json_path": str(agent_prompt["agent_prompt_json_path"]),
                    "agent_prompt_markdown_path": str(agent_prompt["agent_prompt_markdown_path"]),
                    "agent_prompt_markdown": agent_prompt["agent_prompt_markdown"],
                    "agent_prompt": agent_prompt["agent_prompt"],
                },
                "timeline": {
                    "timeline": timeline["timeline"],
                    "timeline_json_path": str(timeline["timeline_json_path"]),
                    "timeline_markdown_path": str(timeline["timeline_markdown_path"]),
                    "timeline_markdown": timeline["timeline_markdown"],
                },
                "review_timeline": {
                    "timeline": review_timeline["timeline"],
                    "timeline_json_path": str(review_timeline["timeline_json_path"]),
                    "timeline_markdown_path": str(review_timeline["timeline_markdown_path"]),
                    "timeline_markdown": review_timeline["timeline_markdown"],
                },
                "review_summary": {
                    "review_summary": review_summary["review_summary"],
                    "review_summary_json_path": str(review_summary["review_summary_json_path"]),
                    "review_summary_markdown_path": str(review_summary["review_summary_markdown_path"]),
                    "review_summary_markdown": review_summary["review_summary_markdown"],
                },
                "workflow": workflow,
                "evidence": evidence.model_dump(mode="json"),
            }
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/config/preflight")
    def api_config_preflight(request: ConfigPreflightRequest) -> dict[str, Any]:
        try:
            return preflight_pair(request.baseline_config, request.variant_config).model_dump(mode="json")
        except OSError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/config/patch")
    def api_config_patch(request: ConfigPatchRequest) -> dict[str, Any]:
        try:
            return patch_sumo_config_option(
                request.source_config,
                request.option,
                request.value,
                output_config=request.output_config,
            ).model_dump(mode="json")
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/outputs/inspect")
    def api_outputs_inspect(request: OutputInspectionRequest) -> dict[str, Any]:
        try:
            return inspect_output_pair(
                baseline_summary=request.baseline_summary,
                baseline_tripinfo=request.baseline_tripinfo,
                variant_summary=request.variant_summary,
                variant_tripinfo=request.variant_tripinfo,
            ).model_dump(mode="json")
        except OSError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/session/{session_id}/outputs/inspect")
    def api_session_outputs_inspect(session_id: str, request: OutputInspectionRequest) -> dict[str, Any]:
        try:
            return manager.inspect_outputs(session_id, request).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except OSError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/session/create")
    def create_session(request: CreateSessionRequest) -> dict[str, Any]:
        try:
            session = manager.create(request)
            return manager.state(session.id).model_dump(mode="json")
        except (FileNotFoundError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/session/{session_id}/step")
    def step_session(session_id: str, request: StepRequest) -> dict[str, Any]:
        try:
            return manager.step(session_id, request.count).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/session/{session_id}/run-until")
    def run_until(session_id: str, request: RunUntilRequest) -> dict[str, Any]:
        try:
            return manager.run_until(session_id, request.target_time).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/session/{session_id}/screenshot")
    def screenshot(session_id: str, request: ScreenshotRequest) -> dict[str, Any]:
        try:
            return manager.screenshot(session_id, request.label).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/session/{session_id}/checkpoint/first")
    def first_checkpoint(session_id: str) -> dict[str, Any]:
        try:
            screenshot_evidence = manager.screenshot(session_id, "first-checkpoint")
            evidence = manager.evidence(session_id)
            return {
                "screenshot": screenshot_evidence.model_dump(mode="json"),
                "evidence": evidence.model_dump(mode="json"),
            }
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/session/{session_id}/checkpoint/template")
    def template_checkpoint(session_id: str, request: TemplateCheckpointRequest) -> dict[str, Any]:
        try:
            screenshot_evidence = manager.checkpoint(session_id, request.template, request.note)
            evidence = manager.evidence(session_id)
            return {
                "screenshot": screenshot_evidence.model_dump(mode="json"),
                "evidence": evidence.model_dump(mode="json"),
            }
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/session/{session_id}/state")
    def get_state(session_id: str) -> dict[str, Any]:
        try:
            return manager.state(session_id).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/session/{session_id}/workflow/status")
    def get_workflow_status(session_id: str) -> dict[str, Any]:
        try:
            return manager.workflow_status(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/session/{session_id}/comparison/readiness")
    def get_comparison_readiness(session_id: str) -> dict[str, Any]:
        try:
            return manager.comparison_readiness(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/session/{session_id}/evidence")
    def get_evidence(session_id: str) -> dict[str, Any]:
        try:
            return manager.evidence(session_id).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/session/{session_id}/artifact/{artifact_path:path}")
    def get_artifact(session_id: str, artifact_path: str) -> FileResponse:
        try:
            session = manager.get(session_id)
            session_dir = session.session_dir.resolve()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        requested_path = (session_dir / artifact_path).resolve()
        if not requested_path.is_file() or not requested_path.is_relative_to(session_dir):
            raise HTTPException(status_code=404, detail="artifact not found")
        return FileResponse(requested_path)

    @app.post("/api/session/{session_id}/packet/export")
    def export_packet(session_id: str) -> dict[str, Any]:
        try:
            packet = manager.export_packet(session_id)
            return {
                "packet_path": str(packet["packet_path"]),
                "packet_markdown": packet["packet_markdown"],
                "evidence": packet["evidence"].model_dump(mode="json"),
            }
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/session/{session_id}/agent-review-prompt/export")
    def export_agent_review_prompt(session_id: str) -> dict[str, Any]:
        try:
            prompt = manager.export_agent_review_prompt(session_id)
            return {
                "agent_prompt": prompt["agent_prompt"],
                "agent_prompt_json_path": str(prompt["agent_prompt_json_path"]),
                "agent_prompt_markdown_path": str(prompt["agent_prompt_markdown_path"]),
                "agent_prompt_markdown": prompt["agent_prompt_markdown"],
                "evidence": prompt["evidence"].model_dump(mode="json"),
            }
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/session/{session_id}/timeline/export")
    def export_timeline(session_id: str, preset: str = "full") -> dict[str, Any]:
        try:
            timeline = manager.export_timeline(session_id, preset=preset)
            return {
                "timeline": timeline["timeline"],
                "timeline_json_path": str(timeline["timeline_json_path"]),
                "timeline_markdown_path": str(timeline["timeline_markdown_path"]),
                "timeline_markdown": timeline["timeline_markdown"],
                "evidence": timeline["evidence"].model_dump(mode="json"),
            }
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/session/{session_id}/timeline/note")
    def add_timeline_note(session_id: str, request: TimelineNoteRequest) -> dict[str, Any]:
        try:
            note = manager.add_timeline_note(session_id, request.label, request.note)
            return {
                "note": note,
                "evidence": manager.evidence(session_id).model_dump(mode="json"),
            }
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/session/{session_id}/scenario/plan")
    def plan_scenario(session_id: str, request: ScenarioPlanRequest) -> dict[str, Any]:
        try:
            plan = manager.plan_scenario(session_id, request)
            return {
                "scenario_plan": plan["scenario_plan"],
                "scenario_plan_json_path": str(plan["scenario_plan_json_path"]),
                "scenario_plan_markdown_path": str(plan["scenario_plan_markdown_path"]),
                "scenario_plan_markdown": plan["scenario_plan_markdown"],
                "scenario_status": plan["scenario_status"],
                "evidence": plan["evidence"].model_dump(mode="json"),
            }
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/session/{session_id}/scenario/status")
    def get_scenario_status(session_id: str) -> dict[str, Any]:
        try:
            return manager.scenario_status(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/session/{session_id}/change/record")
    def record_change(session_id: str, request: ChangeRecordRequest) -> dict[str, Any]:
        try:
            change = manager.record_change(session_id, request)
            return {
                "change": change,
                "evidence": manager.evidence(session_id).model_dump(mode="json"),
            }
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/session/{session_id}/visual-observation/record")
    def record_visual_observation(session_id: str, request: VisualObservationRequest) -> dict[str, Any]:
        try:
            observation = manager.record_visual_observation(session_id, request)
            return {
                "observation": observation,
                "evidence": manager.evidence(session_id).model_dump(mode="json"),
            }
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/session/{session_id}/metrics/compare")
    def compare_metrics(session_id: str) -> dict[str, Any]:
        try:
            comparison = manager.export_metric_comparison(session_id)
            return {
                "metric_comparison": comparison["metric_comparison"],
                "metric_comparison_json_path": str(comparison["metric_comparison_json_path"]),
                "metric_comparison_markdown_path": str(comparison["metric_comparison_markdown_path"]),
                "metric_comparison_markdown": comparison["metric_comparison_markdown"],
                "evidence": comparison["evidence"].model_dump(mode="json"),
            }
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/session/{session_id}/metrics/chart")
    def export_metric_chart(session_id: str) -> dict[str, Any]:
        try:
            chart = manager.export_metric_chart(session_id)
            return {
                "metric_chart": chart["metric_chart"],
                "metric_chart_svg_path": str(chart["metric_chart_svg_path"]),
                "metric_chart_markdown_path": str(chart["metric_chart_markdown_path"]),
                "metric_chart_svg": chart["metric_chart_svg"],
                "metric_chart_markdown": chart["metric_chart_markdown"],
                "evidence": chart["evidence"].model_dump(mode="json"),
            }
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/session/{session_id}/review/summary")
    def export_review_summary(session_id: str) -> dict[str, Any]:
        try:
            summary = manager.export_review_summary(session_id)
            return {
                "review_summary": summary["review_summary"],
                "review_summary_json_path": str(summary["review_summary_json_path"]),
                "review_summary_markdown_path": str(summary["review_summary_markdown_path"]),
                "review_summary_markdown": summary["review_summary_markdown"],
                "evidence": summary["evidence"].model_dump(mode="json"),
            }
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/session/{session_id}/visual-diff/export")
    def export_visual_diff(session_id: str) -> dict[str, Any]:
        try:
            visual_diff = manager.export_visual_diff(session_id)
            return {
                "visual_diff": visual_diff["visual_diff"],
                "visual_diff_json_path": str(visual_diff["visual_diff_json_path"]),
                "visual_diff_markdown_path": str(visual_diff["visual_diff_markdown_path"]),
                "visual_diff_markdown": visual_diff["visual_diff_markdown"],
                "evidence": visual_diff["evidence"].model_dump(mode="json"),
            }
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/session/{session_id}/close")
    def close_session(session_id: str) -> dict[str, str]:
        try:
            manager.close(session_id)
            return {"status": "closed"}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(static_dir / "index.html")

    return app


def main() -> None:
    uvicorn.run(create_app(), host="127.0.0.1", port=8765)
