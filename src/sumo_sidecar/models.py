from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    name: str = "untitled"
    baseline_config: Path
    variant_config: Path
    output_root: Path | None = None
    sumo_gui_binary: str | None = None
    start: bool = True
    quit_on_end: bool = False
    extra_args: list[str] = Field(default_factory=list)


class StepRequest(BaseModel):
    count: int = Field(default=1, ge=1)


class RunUntilRequest(BaseModel):
    target_time: float = Field(ge=0)


class ScreenshotRequest(BaseModel):
    label: str = "snapshot"


class SessionState(BaseModel):
    id: str
    name: str
    session_dir: Path
    baseline: dict[str, Any]
    variant: dict[str, Any]
    evidence_count: int


class ScreenshotEvidence(BaseModel):
    session_id: str
    label: str
    time: float
    baseline_screenshot: Path
    variant_screenshot: Path


class EvidenceArtifact(BaseModel):
    path: Path
    relative_path: str
    size_bytes: int
    modified_at: str


class EvidenceResponse(BaseModel):
    session_id: str
    session_dir: Path
    manifest: dict[str, Any]
    comparison_markdown: str
    artifacts: list[EvidenceArtifact]
