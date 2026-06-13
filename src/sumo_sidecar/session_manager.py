from __future__ import annotations

import json
import re
import uuid
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Protocol

from PIL import Image

from .models import (
    ChangeRecordRequest,
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

TIMELINE_PRESETS = {
    "full": None,
    "review": {"session-created", "user-note", "change-record", "screenshot-checkpoint", "output-inspection", "visual-diff", "codex-packet"},
    "visual": {"session-created", "screenshot-checkpoint", "visual-diff"},
    "outputs": {"session-created", "output-inspection"},
    "notes": {"session-created", "user-note", "change-record"},
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
            "timeline_notes": [],
            "change_records": [],
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
            "## Change Records",
            "",
            self._read_optional_text(session.session_dir / "change-records.md", "No structured change records exported yet."),
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

    def export_timeline(self, session_id: str, preset: str = "full") -> dict[str, Any]:
        session = self.get(session_id)
        clean_preset = _safe_label(preset)
        timeline = self._filter_timeline(self._build_timeline(session), clean_preset)
        timeline_markdown = self._render_timeline_markdown(timeline)
        suffix = "" if clean_preset == "full" else f"-{clean_preset}"
        json_path = session.session_dir / f"timeline{suffix}.json"
        markdown_path = session.session_dir / f"timeline{suffix}.md"
        json_path.write_text(json.dumps(timeline, indent=2), encoding="utf-8")
        markdown_path.write_text(timeline_markdown, encoding="utf-8")
        timeline_manifest_key = "timeline" if clean_preset == "full" else f"timeline_{clean_preset}"
        session.manifest[timeline_manifest_key] = {
            "preset": clean_preset,
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

    def add_timeline_note(self, session_id: str, label: str, note: str) -> dict[str, Any]:
        session = self.get(session_id)
        clean_label = _safe_label(label)
        clean_note = note.strip()
        if not clean_note:
            raise ValueError("timeline note cannot be empty")
        entry = {
            "label": clean_label,
            "note": clean_note,
            "created_at": _utc_now(),
        }
        session.manifest.setdefault("timeline_notes", []).append(entry)
        self._write_manifest(session)
        return entry

    def record_change(self, session_id: str, request: ChangeRecordRequest) -> dict[str, Any]:
        session = self.get(session_id)
        parameter = request.parameter.strip()
        before_value = request.before_value.strip()
        after_value = request.after_value.strip()
        rationale = request.rationale.strip()
        note = request.note.strip() if request.note and request.note.strip() else None
        if not parameter:
            raise ValueError("change parameter cannot be empty")
        if not before_value:
            raise ValueError("change before_value cannot be empty")
        if not after_value:
            raise ValueError("change after_value cannot be empty")
        if not rationale:
            raise ValueError("change rationale cannot be empty")
        entry = {
            "label": _safe_label(request.label),
            "parameter": parameter,
            "before_value": before_value,
            "after_value": after_value,
            "rationale": rationale,
            "note": note,
            "created_at": _utc_now(),
        }
        session.manifest.setdefault("change_records", []).append(entry)
        self._write_change_records(session)
        self._write_manifest(session)
        return entry

    def workflow_status(self, session_id: str) -> dict[str, Any]:
        session = self.get(session_id)
        relative_paths = {item.relative_path for item in self._list_artifacts(session)}
        templates = {item.template for item in session.evidence if item.template}
        has_first_checkpoint = any(item.label == "first-checkpoint" for item in session.evidence)
        has_before_after = {"before-change", "after-change"}.issubset(templates)
        has_timeline_note = bool(session.manifest.get("timeline_notes"))
        has_change_record = bool(session.manifest.get("change_records"))
        output_inspection = session.manifest.get("output_inspection")
        visual_diff = session.manifest.get("visual_diff")
        has_timeline = "timeline" in session.manifest and "timeline.md" in relative_paths
        has_packet = "codex_packet" in session.manifest and "codex-packet.md" in relative_paths

        checklist = [
            self._workflow_item(
                "first_checkpoint",
                "Capture the first paired visual checkpoint",
                has_first_checkpoint,
                "first-checkpoint screenshot evidence",
            ),
            self._workflow_item(
                "template_pair",
                "Capture before-change and after-change checkpoints",
                has_before_after,
                ", ".join(sorted(template for template in templates if template)) or "no template checkpoints",
            ),
            self._workflow_item(
                "timeline_note",
                "Record at least one timeline note",
                has_timeline_note,
                f"{len(session.manifest.get('timeline_notes', []))} timeline note(s)",
                missing_status="warn",
            ),
            self._workflow_item(
                "change_record",
                "Record the structured parameter or controller change",
                has_change_record,
                f"{len(session.manifest.get('change_records', []))} change record(s)",
                missing_status="warn",
            ),
            self._workflow_item(
                "output_inspection",
                "Persist completion-first SUMO output inspection",
                bool(output_inspection),
                output_inspection.get("status", "missing") if output_inspection else "missing",
            ),
            self._workflow_item(
                "visual_diff",
                "Export before/after visual diff",
                bool(visual_diff),
                visual_diff.get("status", "missing") if visual_diff else "missing",
                missing_status="warn",
            ),
            self._workflow_item(
                "timeline",
                "Export run timeline",
                has_timeline,
                "timeline.md" if has_timeline else "missing",
            ),
            self._workflow_item(
                "codex_packet",
                "Export Codex evidence packet",
                has_packet,
                "codex-packet.md" if has_packet else "missing",
            ),
        ]
        missing_required = [
            item for item in checklist
            if item["status"] == "missing" and item["id"] in {"first_checkpoint", "template_pair", "output_inspection", "timeline", "codex_packet"}
        ]
        warnings = [item for item in checklist if item["status"] == "warn"]
        if missing_required:
            status = "needs-evidence"
            claim_status = "diagnostic-incomplete"
        elif warnings:
            status = "review-ready-with-warnings"
            claim_status = "evidence-index-ready"
        else:
            status = "review-ready"
            claim_status = "evidence-index-ready"
        return {
            "session_id": session.id,
            "session_name": session.name,
            "session_dir": str(session.session_dir),
            "status": status,
            "claim_status": claim_status,
            "checklist": checklist,
            "next_actions": self._workflow_next_actions(checklist),
        }

    def export_visual_diff(self, session_id: str) -> dict[str, Any]:
        session = self.get(session_id)
        visual_diff = self._build_visual_diff(session)
        visual_diff_markdown = self._render_visual_diff_markdown(visual_diff)
        json_path = session.session_dir / "visual-diff.json"
        markdown_path = session.session_dir / "visual-diff.md"
        json_path.write_text(json.dumps(visual_diff, indent=2), encoding="utf-8")
        markdown_path.write_text(visual_diff_markdown, encoding="utf-8")
        session.manifest["visual_diff"] = {
            "status": visual_diff["status"],
            "json": str(json_path),
            "markdown": str(markdown_path),
            "updated_at": _utc_now(),
        }
        self._write_manifest(session)
        return {
            "visual_diff": visual_diff,
            "visual_diff_json_path": json_path,
            "visual_diff_markdown_path": markdown_path,
            "visual_diff_markdown": visual_diff_markdown,
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

    def _workflow_item(
        self,
        item_id: str,
        label: str,
        passed: bool,
        evidence: str,
        missing_status: str = "missing",
    ) -> dict[str, str]:
        return {
            "id": item_id,
            "label": label,
            "status": "pass" if passed else missing_status,
            "evidence": evidence,
        }

    def _workflow_next_actions(self, checklist: list[dict[str, str]]) -> list[str]:
        status_by_id = {item["id"]: item["status"] for item in checklist}
        actions: list[str] = []
        if status_by_id["first_checkpoint"] == "missing":
            actions.append("Capture First Checkpoint.")
        if status_by_id["template_pair"] == "missing":
            actions.append("Capture Template Checkpoint for before-change and after-change.")
        if status_by_id["timeline_note"] == "warn":
            actions.append("Add Timeline Note for the parameter change or observation.")
        if status_by_id["change_record"] == "warn":
            actions.append("Record Change with the parameter, before value, after value, and rationale.")
        if status_by_id["output_inspection"] == "missing":
            actions.append("Inspect Outputs with summary.xml and tripinfo.xml.")
        if status_by_id["visual_diff"] == "warn":
            actions.append("Export Visual Diff after before/after checkpoints exist.")
        if status_by_id["timeline"] == "missing":
            actions.append("Export Timeline.")
        if status_by_id["codex_packet"] == "missing":
            actions.append("Export Codex Packet.")
        if not actions:
            actions.append("Ask Codex to inspect codex-packet.md, timeline.md, visual-diff.md, and output-inspection.md.")
        return actions

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
        for note in session.manifest.get("timeline_notes", []):
            events.append(
                {
                    "sequence": len(events) + 1,
                    "kind": "user-note",
                    "label": note.get("label", "note"),
                    "simulation_time": None,
                    "wall_time": note.get("created_at"),
                    "status": "recorded",
                    "template": None,
                    "note": note.get("note"),
                    "artifacts": ["manifest.json"],
                }
            )
        for change in session.manifest.get("change_records", []):
            events.append(
                {
                    "sequence": len(events) + 1,
                    "kind": "change-record",
                    "label": change.get("label", "change"),
                    "simulation_time": None,
                    "wall_time": change.get("created_at"),
                    "status": "recorded",
                    "template": None,
                    "note": f"{change.get('parameter')}: {change.get('before_value')} -> {change.get('after_value')}",
                    "artifacts": ["change-records.json", "change-records.md"],
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
        if "visual_diff" in session.manifest:
            visual_diff = session.manifest["visual_diff"]
            events.append(
                {
                    "sequence": len(events) + 1,
                    "kind": "visual-diff",
                    "label": "Visual diff index",
                    "simulation_time": None,
                    "wall_time": visual_diff.get("updated_at"),
                    "status": visual_diff.get("status", "unknown"),
                    "template": None,
                    "note": None,
                    "artifacts": [
                        self._relative_artifact(session, visual_diff.get("json", "")),
                        self._relative_artifact(session, visual_diff.get("markdown", "")),
                    ],
                }
            )
        return {
            "session_id": session.id,
            "session_name": session.name,
            "session_dir": str(session.session_dir),
            "preset": "full",
            "events": events,
        }

    def _filter_timeline(self, timeline: dict[str, Any], preset: str) -> dict[str, Any]:
        if preset not in TIMELINE_PRESETS:
            allowed = ", ".join(sorted(TIMELINE_PRESETS))
            raise ValueError(f"unknown timeline preset: {preset}. Allowed presets: {allowed}")
        allowed_kinds = TIMELINE_PRESETS[preset]
        if allowed_kinds is None:
            timeline["preset"] = preset
            return timeline
        filtered_events = [
            event for event in timeline["events"]
            if event["kind"] in allowed_kinds
        ]
        for sequence, event in enumerate(filtered_events, start=1):
            event["sequence"] = sequence
        return {
            **timeline,
            "preset": preset,
            "events": filtered_events,
        }

    def _build_visual_diff(self, session: PairedSession) -> dict[str, Any]:
        before_items = [item for item in session.evidence if item.template == "before-change"]
        after_items = [item for item in session.evidence if item.template == "after-change"]
        pairs = []
        for index, (before, after) in enumerate(zip(before_items, after_items), start=1):
            pixel_diff = self._build_pixel_diff(session, index, before, after)
            pairs.append(
                {
                    "index": index,
                    "status": "paired",
                    "before": self._visual_diff_checkpoint(session, before),
                    "after": self._visual_diff_checkpoint(session, after),
                    "baseline_before": self._relative_artifact(session, before.baseline_screenshot),
                    "baseline_after": self._relative_artifact(session, after.baseline_screenshot),
                    "variant_before": self._relative_artifact(session, before.variant_screenshot),
                    "variant_after": self._relative_artifact(session, after.variant_screenshot),
                    "pixel_diff": pixel_diff,
                    "baseline_pixel_diff": pixel_diff.get("baseline_diff"),
                    "variant_pixel_diff": pixel_diff.get("variant_diff"),
                    "claim_boundary": "Visual differences are diagnostic only; pair them with SUMO output evidence before making performance claims.",
                }
            )
        warnings = []
        if len(before_items) != len(after_items):
            warnings.append(
                f"unpaired checkpoints: before-change={len(before_items)}, after-change={len(after_items)}"
            )
        status = "ready" if pairs and not warnings else ("warn" if pairs else "incomplete")
        return {
            "session_id": session.id,
            "session_name": session.name,
            "status": status,
            "pairs": pairs,
            "warnings": warnings,
        }

    def _visual_diff_checkpoint(self, session: PairedSession, item: ScreenshotEvidence) -> dict[str, Any]:
        return {
            "label": item.label,
            "template": item.template,
            "note": item.note,
            "simulation_time": item.time,
            "baseline_screenshot": self._relative_artifact(session, item.baseline_screenshot),
            "variant_screenshot": self._relative_artifact(session, item.variant_screenshot),
        }

    def _build_pixel_diff(
        self,
        session: PairedSession,
        pair_index: int,
        before: ScreenshotEvidence,
        after: ScreenshotEvidence,
    ) -> dict[str, Any]:
        diff_dir = session.session_dir / "visual-diff"
        baseline_diff = diff_dir / f"pair-{pair_index}-baseline-pixel-diff.png"
        variant_diff = diff_dir / f"pair-{pair_index}-variant-pixel-diff.png"
        baseline_result = self._write_pixel_diff(before.baseline_screenshot, after.baseline_screenshot, baseline_diff)
        variant_result = self._write_pixel_diff(before.variant_screenshot, after.variant_screenshot, variant_diff)
        warnings = [
            warning
            for warning in [baseline_result.get("warning"), variant_result.get("warning")]
            if warning
        ]
        status = "ready" if baseline_result["status"] == "ready" and variant_result["status"] == "ready" else "unavailable"
        return {
            "status": status,
            "baseline_changed_pixels": baseline_result["changed_pixels"],
            "variant_changed_pixels": variant_result["changed_pixels"],
            "baseline_total_pixels": baseline_result["total_pixels"],
            "variant_total_pixels": variant_result["total_pixels"],
            "baseline_diff": self._relative_artifact(session, baseline_diff) if baseline_result["status"] == "ready" else None,
            "variant_diff": self._relative_artifact(session, variant_diff) if variant_result["status"] == "ready" else None,
            "warnings": warnings,
        }

    def _write_pixel_diff(self, before_path: Path, after_path: Path, output_path: Path) -> dict[str, Any]:
        try:
            with Image.open(before_path) as before_image, Image.open(after_path) as after_image:
                before_rgb = before_image.convert("RGB")
                after_rgb = after_image.convert("RGB")
                if before_rgb.size != after_rgb.size:
                    return {
                        "status": "unavailable",
                        "changed_pixels": None,
                        "total_pixels": None,
                        "warning": f"image size mismatch: {before_path.name} {before_rgb.size} vs {after_path.name} {after_rgb.size}",
                    }
                changed_pixels = 0
                diff = Image.new("RGB", before_rgb.size, "black")
                diff_pixels = diff.load()
                before_pixels = before_rgb.load()
                after_pixels = after_rgb.load()
                width, height = before_rgb.size
                for y in range(height):
                    for x in range(width):
                        if before_pixels[x, y] != after_pixels[x, y]:
                            changed_pixels += 1
                            diff_pixels[x, y] = (255, 255, 255)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                diff.save(output_path)
                return {
                    "status": "ready",
                    "changed_pixels": changed_pixels,
                    "total_pixels": width * height,
                    "warning": None,
                }
        except OSError as exc:
            return {
                "status": "unavailable",
                "changed_pixels": None,
                "total_pixels": None,
                "warning": f"pixel diff unavailable for {before_path.name} / {after_path.name}: {exc}",
            }

    def _render_visual_diff_markdown(self, visual_diff: dict[str, Any]) -> str:
        lines = [
            f"# SUMO Visual Diff Index: {visual_diff['session_name']}",
            "",
            "This file pairs `before-change` and `after-change` screenshots. It is a visual diagnostic index, not a performance claim.",
            "",
            f"- Status: `{visual_diff['status']}`",
            "",
        ]
        if visual_diff["warnings"]:
            lines.extend(["## Warnings", ""])
            lines.extend(f"- {warning}" for warning in visual_diff["warnings"])
            lines.append("")
        if not visual_diff["pairs"]:
            lines.extend(
                [
                    "## Missing Pair",
                    "",
                    "Capture at least one `before-change` and one `after-change` checkpoint, then export the visual diff again.",
                ]
            )
            return "\n".join(lines)
        lines.extend(["## Pairs", ""])
        for pair in visual_diff["pairs"]:
            before = pair["before"]
            after = pair["after"]
            pixel_diff = pair["pixel_diff"]
            lines.extend(
                [
                    f"### Pair {pair['index']}",
                    "",
                    f"- Before note: {before.get('note') or 'none'}",
                    f"- After note: {after.get('note') or 'none'}",
                    f"- Before SUMO time: `{before['simulation_time']}`",
                    f"- After SUMO time: `{after['simulation_time']}`",
                    f"- baseline_before: `{pair['baseline_before']}`",
                    f"- baseline_after: `{pair['baseline_after']}`",
                    f"- variant_before: `{pair['variant_before']}`",
                    f"- variant_after: `{pair['variant_after']}`",
                    f"- Pixel diff status: `{pixel_diff['status']}`",
                    f"- Baseline changed pixels: `{pixel_diff['baseline_changed_pixels']}` / `{pixel_diff['baseline_total_pixels']}`",
                    f"- Variant changed pixels: `{pixel_diff['variant_changed_pixels']}` / `{pixel_diff['variant_total_pixels']}`",
                    f"- baseline_pixel_diff: `{pair['baseline_pixel_diff']}`",
                    f"- variant_pixel_diff: `{pair['variant_pixel_diff']}`",
                    f"- Claim boundary: {pair['claim_boundary']}",
                    "",
                ]
            )
            if pixel_diff["warnings"]:
                lines.extend(f"- Pixel warning: {warning}" for warning in pixel_diff["warnings"])
                lines.append("")
        return "\n".join(lines)

    def _write_change_records(self, session: PairedSession) -> None:
        records = session.manifest.get("change_records", [])
        json_path = session.session_dir / "change-records.json"
        markdown_path = session.session_dir / "change-records.md"
        json_path.write_text(
            json.dumps(
                {
                    "session_id": session.id,
                    "session_name": session.name,
                    "records": records,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        markdown_path.write_text(self._render_change_records_markdown(session, records), encoding="utf-8")
        session.manifest["change_records_artifact"] = {
            "json": str(json_path),
            "markdown": str(markdown_path),
            "updated_at": _utc_now(),
        }

    def _render_change_records_markdown(self, session: PairedSession, records: list[dict[str, Any]]) -> str:
        lines = [
            f"# SUMO Change Records: {session.name}",
            "",
            "Structured change records connect parameter edits to before/after screenshots and output evidence. They do not prove causality by themselves.",
            "",
        ]
        if not records:
            lines.append("No structured change records have been recorded yet.")
            return "\n".join(lines)
        for index, record in enumerate(records, start=1):
            lines.extend(
                [
                    f"## {index}. {record['label']}",
                    "",
                    f"- Parameter: `{record['parameter']}`",
                    f"- Change: `{record['before_value']}` -> `{record['after_value']}`",
                    f"- Rationale: {record['rationale']}",
                    f"- Note: {record.get('note') or 'none'}",
                    f"- Recorded at: `{record['created_at']}`",
                    "",
                ]
            )
        return "\n".join(lines)

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

    def _read_optional_text(self, path: Path, default: str) -> str:
        return path.read_text(encoding="utf-8") if path.exists() else default

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
