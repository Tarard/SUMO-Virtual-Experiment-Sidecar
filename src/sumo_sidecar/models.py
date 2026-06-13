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


class ConfigPreflightRequest(BaseModel):
    baseline_config: Path
    variant_config: Path


class ConfigPatchRequest(BaseModel):
    source_config: Path
    option: str
    value: str
    output_config: Path | None = None


class OutputInspectionRequest(BaseModel):
    baseline_summary: Path | None = None
    baseline_tripinfo: Path | None = None
    variant_summary: Path | None = None
    variant_tripinfo: Path | None = None


class StepRequest(BaseModel):
    count: int = Field(default=1, ge=1)


class RunUntilRequest(BaseModel):
    target_time: float = Field(ge=0)


class ScreenshotRequest(BaseModel):
    label: str = "snapshot"


class TemplateCheckpointRequest(BaseModel):
    template: str = "before-change"
    note: str | None = None


class TimelineNoteRequest(BaseModel):
    label: str = "note"
    note: str


class ChangeRecordRequest(BaseModel):
    label: str = "parameter-change"
    parameter: str
    before_value: str
    after_value: str
    rationale: str
    note: str | None = None


class ScenarioPlanRequest(BaseModel):
    label: str = "parameter-change-scenario"
    parameter: str
    before_value: str
    after_value: str
    hypothesis: str
    expected_metrics: list[str] = Field(default_factory=list)
    note: str | None = None


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
    template: str | None = None
    note: str | None = None


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


class ConfigReference(BaseModel):
    role: str
    kind: str
    option: str
    value: str
    resolved_path: Path
    exists: bool
    parent_exists: bool


class ConfigPreflightReport(BaseModel):
    role: str
    config_path: Path
    config_exists: bool
    valid_xml: bool
    status: str
    references: list[ConfigReference]
    missing_inputs: list[str]
    missing_output_parents: list[str]
    declared_outputs: list[str]
    warnings: list[str]


class PairConfigPreflightReport(BaseModel):
    status: str
    baseline: ConfigPreflightReport
    variant: ConfigPreflightReport
    paired_warnings: list[str]


class ConfigPatchReport(BaseModel):
    status: str
    source_config: Path
    output_config: Path
    option: str
    old_value: str | None
    new_value: str
    attribute: str
    match_count: int
    warnings: list[str]
    claim_status: str


class SummaryMetrics(BaseModel):
    path: Path
    exists: bool
    valid_xml: bool
    last_time: float | None
    loaded: int | None
    inserted: int | None
    arrived: int | None
    running: int | None
    waiting: int | None
    teleports: int | None
    completion_ratio: float | None
    warnings: list[str]


class TripinfoMetrics(BaseModel):
    path: Path
    exists: bool
    valid_xml: bool
    trip_count: int
    mean_duration: float | None
    mean_waiting_time: float | None
    mean_time_loss: float | None
    warnings: list[str]


class RunOutputInspection(BaseModel):
    role: str
    status: str
    summary: SummaryMetrics | None
    tripinfo: TripinfoMetrics | None
    warnings: list[str]


class PairOutputInspectionReport(BaseModel):
    status: str
    baseline: RunOutputInspection
    variant: RunOutputInspection
    paired_warnings: list[str]
