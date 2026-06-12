from __future__ import annotations

from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config_preflight import preflight_pair
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
        example_root = repo_root / "examples" / "minimal-paired"
        if not example_root.exists():
            raise HTTPException(status_code=404, detail="minimal paired example is not available")
        return {
            "name": "minimal-paired",
            "root": str(example_root),
            "baseline_config": str(example_root / "baseline.sumocfg"),
            "variant_config": str(example_root / "variant.sumocfg"),
            "baseline_summary": str(example_root / "outputs" / "baseline" / "summary.xml"),
            "baseline_tripinfo": str(example_root / "outputs" / "baseline" / "tripinfo.xml"),
            "variant_summary": str(example_root / "outputs" / "variant" / "summary.xml"),
            "variant_tripinfo": str(example_root / "outputs" / "variant" / "tripinfo.xml"),
            "headless_commands": [
                "sumo -c examples\\minimal-paired\\baseline.sumocfg",
                "sumo -c examples\\minimal-paired\\variant.sumocfg",
            ],
        }

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
