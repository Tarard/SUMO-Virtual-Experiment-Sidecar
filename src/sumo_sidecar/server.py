from __future__ import annotations

from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config_preflight import preflight_pair
from .demo_runner import minimal_paired_metadata, run_minimal_paired_guided, run_minimal_paired_headless
from .models import (
    ConfigPreflightRequest,
    CreateSessionRequest,
    OutputInspectionRequest,
    RunUntilRequest,
    ScreenshotRequest,
    StepRequest,
)
from .output_inspection import inspect_output_pair
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

    @app.post("/api/config/preflight")
    def api_config_preflight(request: ConfigPreflightRequest) -> dict[str, Any]:
        try:
            return preflight_pair(request.baseline_config, request.variant_config).model_dump(mode="json")
        except OSError as exc:
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

    @app.get("/api/session/{session_id}/state")
    def get_state(session_id: str) -> dict[str, Any]:
        try:
            return manager.state(session_id).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/session/{session_id}/evidence")
    def get_evidence(session_id: str) -> dict[str, Any]:
        try:
            return manager.evidence(session_id).model_dump(mode="json")
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
