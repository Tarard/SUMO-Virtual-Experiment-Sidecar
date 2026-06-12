from __future__ import annotations

import json
import re
import uuid
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Protocol

from .models import (
    CreateSessionRequest,
    EvidenceArtifact,
    EvidenceResponse,
    OutputInspectionRequest,
    PairOutputInspectionReport,
    ScreenshotEvidence,
    SessionState,
)
from .output_inspection import inspect_output_pair, render_output_inspection_markdown
from .sumo_adapter import TraCISumoRun


class SumoRun(Protocol):
    def step(self, count: int = 1) -> dict[str, Any]: ...

    def run_until(self, target_time: float) -> dict[str, Any]: ...

    def screenshot(self, output_path: Path) -> Path: ...

    def state(self) -> dict[str, Any]: ...

    def close(self) -> None: ...


AdapterFactory = Callable[[str, Path, Path, dict[str, Any]], SumoRun]


@dataclass
class PairedSession:
    id: str
    name: str
    session_dir: Path
    baseline: SumoRun
    variant: SumoRun
    manifest: dict[str, Any]
    evidence: list[ScreenshotEvidence] = field(default_factory=list)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _safe_label(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-.")
    return cleaned or "snapshot"


CHECKPOINT_TEMPLATES = {
    "before-change": "Before controller or parameter change",
    "after-change": "After controller or parameter change",
    "queue-build-up": "Queue build-up observation",
    "final-state": "Final visual state",
}


def _default_adapter_factory(role: str, config_path: Path, session_dir: Path, options: dict[str, Any]) -> SumoRun:
    return TraCISumoRun(role=role, config_path=config_path, session_dir=session_dir, options=options)


class SessionManager:
    def __init__(
        self,
        adapter_factory: AdapterFactory | None = None,
        default_output_root: Path | None = None,
    ) -> None:
        self.adapter_factory = adapter_factory or _default_adapter_factory
        self.default_output_root = default_output_root or Path("runs")
        self.sessions: dict[str, PairedSession] = {}

    def create(self, request: CreateSessionRequest) -> PairedSession:
        baseline_config = request.baseline_config.expanduser().resolve()
        variant_config = request.variant_config.expanduser().resolve()
        if not baseline_config.exists():
            raise FileNotFoundError(f"baseline config not found: {baseline_config}")
        if not variant_config.exists():
            raise FileNotFoundError(f"variant config not found: {variant_config}")

        output_root = (request.output_root or self.default_output_root).expanduser().resolve()
        session_id = f"{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
        session_dir = output_root / session_id
        (session_dir / "baseline" / "screenshots").mkdir(parents=True, exist_ok=True)
        (session_dir / "variant" / "screenshots").mkdir(parents=True, exist_ok=True)

        options = {
            "sumo_gui_binary": request.sumo_gui_binary,
            "start": request.start,
            "quit_on_end": request.quit_on_end,
            "extra_args": request.extra_args,
        }
        manifest = {
            "id": session_id,
            "name": request.name,
            "created_at": _utc_now(),
            "baseline_config": str(baseline_config),
            "variant_config": str(variant_config),
            "session_dir": str(session_dir),
            "options": options,
            "evidence": [],
        }

        baseline: SumoRun | None = None
        try:
            baseline = self.adapter_factory("baseline", baseline_config, session_dir, options)
            variant = self.adapter_factory("variant", variant_config, session_dir, options)
        except Exception:
            if baseline is not None:
                with suppress(Exception):
                    baseline.close()
            raise
        session = PairedSession(
            id=session_id,
            name=request.name,
            session_dir=session_dir,
            baseline=baseline,
            variant=variant,
            manifest=manifest,
        )
        self.sessions[session_id] = session
        self._write_manifest(session)
        self._write_comparison(session, header_only=True)
        return session

    def get(self, session_id: str) -> PairedSession:
        try:
            return self.sessions[session_id]
        except KeyError as exc:
            raise KeyError(f"unknown session: {session_id}") from exc

    def state(self, session_id: str) -> SessionState:
        session = self.get(session_id)
        return SessionState(
            id=session.id,
            name=session.name,
            session_dir=session.session_dir,
            baseline=session.baseline.state(),
            variant=session.variant.state(),
            evidence_count=len(session.evidence),
        )

    def step(self, session_id: str, count: int = 1) -> SessionState:
        session = self.get(session_id)
        session.baseline.step(count)
        session.variant.step(count)
        return self.state(session_id)

    def run_until(self, session_id: str, target_time: float) -> SessionState:
        session = self.get(session_id)
        session.baseline.run_until(target_time)
        session.variant.run_until(target_time)
        return self.state(session_id)

    def screenshot(
        self,
        session_id: str,
        label: str = "snapshot",
        template: str | None = None,
        note: str | None = None,
    ) -> ScreenshotEvidence:
        session = self.get(session_id)
        state = self.state(session_id)
        time_value = float(state.baseline.get("time", 0.0))
        safe_label = _safe_label(label)
        clean_note = note.strip() if note and note.strip() else None
        file_stem = f"t{time_value:g}-{safe_label}"
        baseline_path = session.session_dir / "baseline" / "screenshots" / f"{file_stem}.png"
        variant_path = session.session_dir / "variant" / "screenshots" / f"{file_stem}.png"
        session.baseline.screenshot(baseline_path)
        session.variant.screenshot(variant_path)
        evidence = ScreenshotEvidence(
            session_id=session.id,
            label=safe_label,
            time=time_value,
            baseline_screenshot=baseline_path,
            variant_screenshot=variant_path,
            template=template,
            note=clean_note,
        )
        session.evidence.append(evidence)
        session.manifest["evidence"] = [item.model_dump(mode="json") for item in session.evidence]
        self._write_manifest(session)
        self._write_comparison(session)
        return evidence

    def checkpoint(self, session_id: str, template: str, note: str | None = None) -> ScreenshotEvidence:
        safe_template = _safe_label(template)
        if safe_template not in CHECKPOINT_TEMPLATES:
            allowed = ", ".join(sorted(CHECKPOINT_TEMPLATES))
            raise ValueError(f"unknown checkpoint template: {template}. Allowed templates: {allowed}")
        return self.screenshot(session_id, safe_template, template=safe_template, note=note)

    def evidence(self, session_id: str) -> EvidenceResponse:
        session = self.get(session_id)
        manifest_path = session.session_dir / "manifest.json"
        comparison_path = session.session_dir / "comparison.md"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        comparison = comparison_path.read_text(encoding="utf-8") if comparison_path.exists() else ""
        return EvidenceResponse(
            session_id=session.id,
            session_dir=session.session_dir,
            manifest=manifest,
            comparison_markdown=comparison,
            artifacts=self._list_artifacts(session),
        )

    def inspect_outputs(self, session_id: str, request: OutputInspectionRequest) -> PairOutputInspectionReport:
        session = self.get(session_id)
        report = inspect_output_pair(
            baseline_summary=request.baseline_summary,
            baseline_tripinfo=request.baseline_tripinfo,
            variant_summary=request.variant_summary,
            variant_tripinfo=request.variant_tripinfo,
        )
        json_path = session.session_dir / "output-inspection.json"
        markdown_path = session.session_dir / "output-inspection.md"
        json_path.write_text(json.dumps(report.model_dump(mode="json"), indent=2), encoding="utf-8")
        markdown_path.write_text(render_output_inspection_markdown(report), encoding="utf-8")
        session.manifest["output_inspection"] = {
            "status": report.status,
            "json": str(json_path),
            "markdown": str(markdown_path),
            "updated_at": _utc_now(),
        }
        self._write_manifest(session)
        return report

    def export_packet(self, session_id: str) -> dict[str, Any]:
        session = self.get(session_id)
        evidence = self.evidence(session_id)
        timeline = self._build_timeline(session)
        timeline_markdown = self._render_timeline_markdown(timeline)
        output_inspection_path = session.session_dir / "output-inspection.md"
        output_inspection = (
            output_inspection_path.read_text(encoding="utf-8") if output_inspection_path.exists() else "Not exported yet."
        )
        artifact_lines = [
            f"- `{item.relative_path}` ({item.size_bytes} bytes)" for item in evidence.artifacts
        ] or ["- No artifacts found."]
        packet_lines = [
            f"# Codex Experiment Packet: {session.name}",
            "",
            "This packet is an evidence index for Codex or Claude review. It does not certify experiment validity.",
            "",
            "## Session",
            "",
            f"- Session: `{session.id}`",
            f"- Session folder: `{session.session_dir}`",
            f"- Baseline config: `{session.manifest['baseline_config']}`",
            f"- Variant config: `{session.manifest['variant_config']}`",
            f"- Screenshot checkpoints: `{len(session.evidence)}`",
            "",
            "## Artifacts",
            "",
            *artifact_lines,
            "",
            "## Run Timeline",
            "",
            timeline_markdown,
            "",
            "## Comparison Notes",
            "",
            evidence.comparison_markdown or "No comparison notes exported yet.",
            "",
            "## Output Inspection",
            "",
            output_inspection,
            "",
            "## Claim Boundary",
            "",
            "GUI screenshots are diagnostic visual evidence. Formal claims still require paired outputs, completion status, metric definitions, and reproducibility checks.",
        ]
        packet_markdown = "\n".join(packet_lines)
        packet_path = session.session_dir / "codex-packet.md"
        packet_path.write_text(packet_markdown, encoding="utf-8")
        session.manifest["codex_packet"] = {
            "path": str(packet_path),
            "updated_at": _utc_now(),
        }
        self._write_manifest(session)
        return {
            "packet_path": packet_path,
            "packet_markdown": packet_markdown,
            "evidence": self.evidence(session_id),
        }

    def export_timeline(self, session_id: str) -> dict[str, Any]:
        session = self.get(session_id)
        timeline = self._build_timeline(session)
        timeline_markdown = self._render_timeline_markdown(timeline)
        json_path = session.session_dir / "timeline.json"
        markdown_path = session.session_dir / "timeline.md"
        json_path.write_text(json.dumps(timeline, indent=2), encoding="utf-8")
        markdown_path.write_text(timeline_markdown, encoding="utf-8")
        session.manifest["timeline"] = {
            "json": str(json_path),
            "markdown": str(markdown_path),
            "updated_at": _utc_now(),
        }
        self._write_manifest(session)
        return {
            "timeline": timeline,
            "timeline_json_path": json_path,
            "timeline_markdown_path": markdown_path,
            "timeline_markdown": timeline_markdown,
            "evidence": self.evidence(session_id),
        }

    def close(self, session_id: str) -> None:
        session = self.get(session_id)
        session.baseline.close()
        session.variant.close()
        session.manifest["closed_at"] = _utc_now()
        self._write_manifest(session)

    def _write_manifest(self, session: PairedSession) -> None:
        path = session.session_dir / "manifest.json"
        path.write_text(json.dumps(session.manifest, indent=2), encoding="utf-8")

    def _write_comparison(self, session: PairedSession, header_only: bool = False) -> None:
        path = session.session_dir / "comparison.md"
        lines = [
            f"# SUMO Visual Comparison: {session.name}",
            "",
            f"- Session: `{session.id}`",
            f"- Baseline config: `{session.manifest['baseline_config']}`",
            f"- Variant config: `{session.manifest['variant_config']}`",
            "",
            "GUI screenshots are diagnostic visual evidence. Formal claims still require paired outputs, completion status, and metric checks.",
            "",
        ]
        if not header_only:
            lines.append("## Screenshot Evidence")
            lines.append("")
            for item in session.evidence:
                lines.extend(
                    [
                        f"### {item.label}",
                        "",
                        f"- Time: `{item.time}`",
                        f"- Template: `{item.template or 'manual'}`",
                        f"- Baseline screenshot: `{item.baseline_screenshot}`",
                        f"- Variant screenshot: `{item.variant_screenshot}`",
                        "",
                    ]
                )
                if item.note:
                    lines.extend([f"- Note: {item.note}", ""])
        path.write_text("\n".join(lines), encoding="utf-8")

    def _build_timeline(self, session: PairedSession) -> dict[str, Any]:
        events: list[dict[str, Any]] = [
            {
                "sequence": 1,
                "kind": "session-created",
                "label": "Session created",
                "simulation_time": None,
                "wall_time": session.manifest.get("created_at"),
                "status": "created",
                "template": None,
                "note": None,
                "artifacts": ["manifest.json", "comparison.md"],
            }
        ]
        for item in session.evidence:
            events.append(
                {
                    "sequence": len(events) + 1,
                    "kind": "screenshot-checkpoint",
                    "label": item.label,
                    "simulation_time": item.time,
                    "wall_time": None,
                    "status": "diagnostic",
                    "template": item.template,
                    "note": item.note,
                    "artifacts": [
                        self._relative_artifact(session, item.baseline_screenshot),
                        self._relative_artifact(session, item.variant_screenshot),
                    ],
                }
            )
        if "output_inspection" in session.manifest:
            inspection = session.manifest["output_inspection"]
            events.append(
                {
                    "sequence": len(events) + 1,
                    "kind": "output-inspection",
                    "label": "Output inspection",
                    "simulation_time": None,
                    "wall_time": inspection.get("updated_at"),
                    "status": inspection.get("status", "unknown"),
                    "template": None,
                    "note": None,
                    "artifacts": [
                        self._relative_artifact(session, inspection.get("json", "")),
                        self._relative_artifact(session, inspection.get("markdown", "")),
                    ],
                }
            )
        if "codex_packet" in session.manifest:
            packet = session.manifest["codex_packet"]
            events.append(
                {
                    "sequence": len(events) + 1,
                    "kind": "codex-packet",
                    "label": "Codex packet",
                    "simulation_time": None,
                    "wall_time": packet.get("updated_at"),
                    "status": "exported",
                    "template": None,
                    "note": None,
                    "artifacts": [self._relative_artifact(session, packet.get("path", ""))],
                }
            )
        return {
            "session_id": session.id,
            "session_name": session.name,
            "session_dir": str(session.session_dir),
            "events": events,
        }

    def _render_timeline_markdown(self, timeline: dict[str, Any]) -> str:
        lines = [
            f"# SUMO Run Timeline: {timeline['session_name']}",
            "",
            "This timeline aligns visual checkpoints, output evidence, and exported agent packets. It is an evidence index, not a validity certificate.",
            "",
            "| # | Kind | Label | SUMO time | Status | Note | Artifacts |",
            "|---:|---|---|---:|---|---|---|",
        ]
        for event in timeline["events"]:
            simulation_time = "" if event["simulation_time"] is None else str(event["simulation_time"])
            note = self._markdown_table_cell(event.get("note") or "")
            artifacts = "<br>".join(f"`{artifact}`" for artifact in event["artifacts"] if artifact)
            lines.append(
                f"| {event['sequence']} | {event['kind']} | {event['label']} | {simulation_time} | {event['status']} | {note} | {artifacts} |"
            )
        return "\n".join(lines)

    def _markdown_table_cell(self, value: str) -> str:
        return value.replace("\n", " ").replace("|", "\\|")

    def _relative_artifact(self, session: PairedSession, path_value: str | Path) -> str:
        if not path_value:
            return ""
        path = Path(path_value)
        try:
            return path.resolve().relative_to(session.session_dir.resolve()).as_posix()
        except ValueError:
            return path.as_posix()

    def _list_artifacts(self, session: PairedSession) -> list[EvidenceArtifact]:
        artifacts: list[EvidenceArtifact] = []
        for path in sorted(session.session_dir.rglob("*")):
            if not path.is_file():
                continue
            stat = path.stat()
            artifacts.append(
                EvidenceArtifact(
                    path=path,
                    relative_path=path.relative_to(session.session_dir).as_posix(),
                    size_bytes=stat.st_size,
                    modified_at=datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                )
            )
        return artifacts
