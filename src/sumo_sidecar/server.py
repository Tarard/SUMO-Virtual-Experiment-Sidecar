from __future__ import annotations

from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config_preflight import preflight_pair
from .models import ConfigPreflightRequest, CreateSessionRequest, RunUntilRequest, ScreenshotRequest, StepRequest
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

    @app.post("/api/config/preflight")
    def api_config_preflight(request: ConfigPreflightRequest) -> dict[str, Any]:
        try:
            return preflight_pair(request.baseline_config, request.variant_config).model_dump(mode="json")
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
