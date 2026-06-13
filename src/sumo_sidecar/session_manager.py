from __future__ import annotations

import json
import re
import uuid
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html import escape as html_escape
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
    ScenarioPlanRequest,
    SessionState,
    VisualObservationRequest,
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
    "review": {"session-created", "scenario-plan", "user-note", "change-record", "visual-observation", "screenshot-checkpoint", "output-inspection", "metric-comparison", "metric-chart", "visual-diff", "codex-packet", "review-summary", "next-action-review"},
    "visual": {"session-created", "screenshot-checkpoint", "visual-observation", "visual-diff"},
    "outputs": {"session-created", "output-inspection", "metric-comparison", "metric-chart"},
    "notes": {"session-created", "scenario-plan", "user-note", "change-record"},
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
            "visual_observations": [],
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
            "## Scenario Plan",
            "",
            self._read_optional_text(session.session_dir / "scenario-plan.md", "No guided scenario plan exported yet."),
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
            "## Metric Comparison",
            "",
            self._read_optional_text(session.session_dir / "metric-comparison.md", "No metric comparison exported yet."),
            "",
            "## Metric Delta Chart",
            "",
            self._read_optional_text(session.session_dir / "metric-delta-chart.md", "No metric delta chart exported yet."),
            "",
            "## Review Summary",
            "",
            self._read_optional_text(session.session_dir / "review-summary.md", "No review summary exported yet."),
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

    def export_agent_review_prompt(self, session_id: str) -> dict[str, Any]:
        session = self.get(session_id)
        readiness = self.comparison_readiness(session_id)
        workflow = self.workflow_status(session_id)
        prompt = self._build_agent_review_prompt(session, readiness, workflow)
        prompt_markdown = self._render_agent_review_prompt_markdown(prompt)
        json_path = session.session_dir / "agent-review-prompt.json"
        markdown_path = session.session_dir / "agent-review-prompt.md"
        json_path.write_text(json.dumps(prompt, indent=2), encoding="utf-8")
        markdown_path.write_text(prompt_markdown, encoding="utf-8")
        session.manifest["agent_review_prompt"] = {
            "status": prompt["readiness_status"],
            "json": str(json_path),
            "markdown": str(markdown_path),
            "updated_at": _utc_now(),
        }
        self._write_manifest(session)
        return {
            "agent_prompt": prompt,
            "agent_prompt_json_path": json_path,
            "agent_prompt_markdown_path": markdown_path,
            "agent_prompt_markdown": prompt_markdown,
            "evidence": self.evidence(session_id),
        }

    def export_next_action_review(self, session_id: str) -> dict[str, Any]:
        session = self.get(session_id)
        readiness = self.comparison_readiness(session_id)
        workflow = self.workflow_status(session_id)
        review = self._build_next_action_review(session, readiness, workflow)
        review_markdown = self._render_next_action_review_markdown(review)
        json_path = session.session_dir / "next-action-review.json"
        markdown_path = session.session_dir / "next-action-review.md"
        json_path.write_text(json.dumps(review, indent=2), encoding="utf-8")
        markdown_path.write_text(review_markdown, encoding="utf-8")
        session.manifest["next_action_review"] = {
            "status": review["status"],
            "json": str(json_path),
            "markdown": str(markdown_path),
            "updated_at": _utc_now(),
        }
        self._write_manifest(session)
        return {
            "next_action_review": review,
            "next_action_review_json_path": json_path,
            "next_action_review_markdown_path": markdown_path,
            "next_action_review_markdown": review_markdown,
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

    def plan_scenario(self, session_id: str, request: ScenarioPlanRequest) -> dict[str, Any]:
        session = self.get(session_id)
        parameter = request.parameter.strip()
        before_value = request.before_value.strip()
        after_value = request.after_value.strip()
        hypothesis = request.hypothesis.strip()
        note = request.note.strip() if request.note and request.note.strip() else None
        expected_metrics = [item.strip() for item in request.expected_metrics if item.strip()]
        if not parameter:
            raise ValueError("scenario parameter cannot be empty")
        if not before_value:
            raise ValueError("scenario before_value cannot be empty")
        if not after_value:
            raise ValueError("scenario after_value cannot be empty")
        if not hypothesis:
            raise ValueError("scenario hypothesis cannot be empty")
        plan = {
            "label": _safe_label(request.label),
            "parameter": parameter,
            "before_value": before_value,
            "after_value": after_value,
            "hypothesis": hypothesis,
            "expected_metrics": expected_metrics,
            "note": note,
            "created_at": _utc_now(),
        }
        json_path = session.session_dir / "scenario-plan.json"
        markdown_path = session.session_dir / "scenario-plan.md"
        json_path.write_text(
            json.dumps(
                {
                    "session_id": session.id,
                    "session_name": session.name,
                    "scenario_plan": plan,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        markdown = self._render_scenario_plan_markdown(session, plan)
        markdown_path.write_text(markdown, encoding="utf-8")
        session.manifest["scenario_plan"] = {
            **plan,
            "json": str(json_path),
            "markdown": str(markdown_path),
            "updated_at": _utc_now(),
        }
        self._write_manifest(session)
        return {
            "scenario_plan": plan,
            "scenario_plan_json_path": json_path,
            "scenario_plan_markdown_path": markdown_path,
            "scenario_plan_markdown": markdown,
            "scenario_status": self.scenario_status(session_id),
            "evidence": self.evidence(session_id),
        }

    def scenario_status(self, session_id: str) -> dict[str, Any]:
        session = self.get(session_id)
        relative_paths = {item.relative_path for item in self._list_artifacts(session)}
        templates = {item.template for item in session.evidence if item.template}
        has_scenario = "scenario_plan" in session.manifest and "scenario-plan.md" in relative_paths
        has_first_checkpoint = any(item.label == "first-checkpoint" for item in session.evidence)
        has_before = "before-change" in templates
        has_after = "after-change" in templates
        has_change = bool(session.manifest.get("change_records"))
        checks = [
            self._scenario_item("scenario_plan", "Create Scenario Plan", has_scenario, "scenario-plan.md" if has_scenario else "missing"),
            self._scenario_item("first_checkpoint", "Capture First Checkpoint", has_first_checkpoint, "first-checkpoint screenshot evidence"),
            self._scenario_item("before_checkpoint", "Capture before-change checkpoint", has_before, "before-change checkpoint"),
            self._scenario_item("change_record", "Record planned change", has_change, f"{len(session.manifest.get('change_records', []))} change record(s)"),
            self._scenario_item("after_checkpoint", "Capture after-change checkpoint", has_after, "after-change checkpoint"),
            self._scenario_manifest_item(session, "output_inspection", "Inspect Outputs", session.manifest.get("output_inspection")),
            self._scenario_manifest_item(session, "metric_comparison", "Compare Metrics", session.manifest.get("metric_comparison")),
            self._scenario_manifest_item(session, "metric_chart", "Export Metric Chart", session.manifest.get("metric_chart")),
            self._scenario_manifest_item(session, "visual_diff", "Export Visual Diff", session.manifest.get("visual_diff")),
            self._scenario_manifest_item(session, "timeline", "Export Timeline", session.manifest.get("timeline")),
            self._scenario_manifest_item(session, "review_summary", "Export Review Summary", session.manifest.get("review_summary")),
            self._scenario_manifest_item(session, "codex_packet", "Export Codex Packet", session.manifest.get("codex_packet")),
        ]
        next_actions = self._scenario_next_actions(checks)
        return {
            "session_id": session.id,
            "session_name": session.name,
            "status": "ready-for-review" if not next_actions else "needs-evidence",
            "current_step": next_actions[0] if next_actions else "Ask Codex to inspect scenario-plan.md, review-summary.md, metric-delta-chart.md, visual-diff.md, and codex-packet.md.",
            "checklist": checks,
            "next_actions": next_actions or ["Ask Codex to inspect scenario-plan.md, review-summary.md, metric-delta-chart.md, visual-diff.md, and codex-packet.md."],
        }

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

    def record_visual_observation(self, session_id: str, request: VisualObservationRequest) -> dict[str, Any]:
        session = self.get(session_id)
        observation_type = request.observation_type.strip()
        note = request.note.strip()
        confidence = request.confidence.strip() if request.confidence.strip() else "diagnostic"
        evidence_artifact = request.evidence_artifact.strip() if request.evidence_artifact and request.evidence_artifact.strip() else None
        if not observation_type:
            raise ValueError("visual observation type cannot be empty")
        if not note:
            raise ValueError("visual observation note cannot be empty")
        state = self.state(session_id)
        entry = {
            "label": _safe_label(request.label),
            "observation_type": observation_type,
            "evidence_artifact": evidence_artifact,
            "confidence": confidence,
            "note": note,
            "simulation_time": float(state.baseline.get("time", 0.0)),
            "created_at": _utc_now(),
        }
        session.manifest.setdefault("visual_observations", []).append(entry)
        self._write_visual_observations(session)
        self._write_manifest(session)
        return entry

    def export_metric_comparison(self, session_id: str) -> dict[str, Any]:
        session = self.get(session_id)
        output_inspection = session.manifest.get("output_inspection")
        if not output_inspection:
            raise ValueError("output inspection must be persisted before metric comparison")
        output_json_path = Path(output_inspection.get("json", ""))
        if not output_json_path.exists():
            raise ValueError(f"output inspection json not found: {output_json_path}")
        report_data = json.loads(output_json_path.read_text(encoding="utf-8"))
        metric_comparison = self._build_metric_comparison(session, report_data)
        metric_markdown = self._render_metric_comparison_markdown(metric_comparison)
        json_path = session.session_dir / "metric-comparison.json"
        markdown_path = session.session_dir / "metric-comparison.md"
        json_path.write_text(json.dumps(metric_comparison, indent=2), encoding="utf-8")
        markdown_path.write_text(metric_markdown, encoding="utf-8")
        session.manifest["metric_comparison"] = {
            "status": metric_comparison["status"],
            "json": str(json_path),
            "markdown": str(markdown_path),
            "updated_at": _utc_now(),
        }
        self._write_manifest(session)
        return {
            "metric_comparison": metric_comparison,
            "metric_comparison_json_path": json_path,
            "metric_comparison_markdown_path": markdown_path,
            "metric_comparison_markdown": metric_markdown,
            "evidence": self.evidence(session_id),
        }

    def export_metric_chart(self, session_id: str) -> dict[str, Any]:
        session = self.get(session_id)
        metric_comparison = session.manifest.get("metric_comparison")
        if not metric_comparison:
            raise ValueError("metric comparison must be exported before metric chart")
        metric_json_path = Path(metric_comparison.get("json", ""))
        if not metric_json_path.exists():
            raise ValueError(f"metric comparison json not found: {metric_json_path}")
        comparison = json.loads(metric_json_path.read_text(encoding="utf-8"))
        metric_chart = self._build_metric_chart(session, comparison)
        metric_chart_svg = self._render_metric_chart_svg(metric_chart)
        metric_chart_markdown = self._render_metric_chart_markdown(metric_chart)
        svg_path = session.session_dir / "metric-delta-chart.svg"
        markdown_path = session.session_dir / "metric-delta-chart.md"
        svg_path.write_text(metric_chart_svg, encoding="utf-8")
        markdown_path.write_text(metric_chart_markdown, encoding="utf-8")
        session.manifest["metric_chart"] = {
            "status": metric_chart["status"],
            "svg": str(svg_path),
            "markdown": str(markdown_path),
            "updated_at": _utc_now(),
        }
        self._write_manifest(session)
        return {
            "metric_chart": metric_chart,
            "metric_chart_svg_path": svg_path,
            "metric_chart_markdown_path": markdown_path,
            "metric_chart_svg": metric_chart_svg,
            "metric_chart_markdown": metric_chart_markdown,
            "evidence": self.evidence(session_id),
        }

    def workflow_status(self, session_id: str) -> dict[str, Any]:
        session = self.get(session_id)
        relative_paths = {item.relative_path for item in self._list_artifacts(session)}
        templates = {item.template for item in session.evidence if item.template}
        has_first_checkpoint = any(item.label == "first-checkpoint" for item in session.evidence)
        has_before_after = {"before-change", "after-change"}.issubset(templates)
        has_timeline_note = bool(session.manifest.get("timeline_notes"))
        has_change_record = bool(session.manifest.get("change_records"))
        output_inspection = session.manifest.get("output_inspection")
        metric_comparison = session.manifest.get("metric_comparison")
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
                "metric_comparison",
                "Export completion-first metric comparison",
                bool(metric_comparison),
                metric_comparison.get("status", "missing") if metric_comparison else "missing",
                missing_status="warn",
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

    def comparison_readiness(self, session_id: str) -> dict[str, Any]:
        session = self.get(session_id)
        relative_paths = {item.relative_path for item in self._list_artifacts(session)}
        templates = {item.template for item in session.evidence if item.template}
        has_scenario = "scenario_plan" in session.manifest and "scenario-plan.md" in relative_paths
        has_first_checkpoint = any(item.label == "first-checkpoint" for item in session.evidence)
        has_before_after = {"before-change", "after-change"}.issubset(templates)
        output_inspection = session.manifest.get("output_inspection")
        metric_comparison = session.manifest.get("metric_comparison")
        visual_diff = session.manifest.get("visual_diff")

        checklist = [
            self._workflow_item("scenario_plan", "Create Scenario Plan", has_scenario, "scenario-plan.md" if has_scenario else "missing"),
            self._workflow_item("first_checkpoint", "Capture First Checkpoint", has_first_checkpoint, "first-checkpoint screenshot evidence"),
            self._workflow_item(
                "before_after_checkpoints",
                "Capture before-change and after-change checkpoints",
                has_before_after,
                ", ".join(sorted(template for template in templates if template)) or "missing",
            ),
            self._workflow_item(
                "change_record",
                "Record structured change",
                bool(session.manifest.get("change_records")),
                f"{len(session.manifest.get('change_records', []))} change record(s)",
            ),
            self._workflow_item(
                "output_inspection",
                "Inspect paired SUMO outputs",
                bool(output_inspection),
                output_inspection.get("status", "missing") if output_inspection else "missing",
            ),
            self._workflow_item(
                "metric_comparison",
                "Export completion-first metric comparison",
                bool(metric_comparison),
                metric_comparison.get("status", "missing") if metric_comparison else "missing",
            ),
            self._workflow_item(
                "visual_diff",
                "Export before/after visual diff",
                bool(visual_diff),
                visual_diff.get("status", "missing") if visual_diff else "missing",
            ),
            self._workflow_item(
                "metric_chart",
                "Export metric delta chart",
                bool(session.manifest.get("metric_chart")),
                session.manifest.get("metric_chart", {}).get("status", "missing") if session.manifest.get("metric_chart") else "missing",
                missing_status="recommended",
            ),
            self._workflow_item(
                "timeline",
                "Export run timeline",
                "timeline" in session.manifest and "timeline.md" in relative_paths,
                "timeline.md" if "timeline.md" in relative_paths else "missing",
                missing_status="recommended",
            ),
            self._workflow_item(
                "review_summary",
                "Export review summary",
                bool(session.manifest.get("review_summary")),
                session.manifest.get("review_summary", {}).get("status", "missing") if session.manifest.get("review_summary") else "missing",
                missing_status="recommended",
            ),
            self._workflow_item(
                "codex_packet",
                "Export Codex packet",
                "codex_packet" in session.manifest and "codex-packet.md" in relative_paths,
                "codex-packet.md" if "codex-packet.md" in relative_paths else "missing",
                missing_status="recommended",
            ),
        ]
        required_ids = {
            "scenario_plan",
            "first_checkpoint",
            "before_after_checkpoints",
            "change_record",
            "output_inspection",
            "metric_comparison",
            "visual_diff",
        }
        missing_required = [item for item in checklist if item["id"] in required_ids and item["status"] != "pass"]
        has_recommended_gap = any(item["status"] == "recommended" for item in checklist)
        if missing_required:
            status = "needs-evidence"
            claim_status = "diagnostic-incomplete"
        elif has_recommended_gap:
            status = "ready-to-compare"
            claim_status = "diagnostic-comparison-ready"
        else:
            status = "ready-for-agent-review"
            claim_status = "review-package-ready"
        return {
            "session_id": session.id,
            "session_name": session.name,
            "status": status,
            "claim_status": claim_status,
            "checklist": checklist,
            "next_actions": self._comparison_readiness_actions(checklist),
            "claim_boundary": "Readiness means the sidecar has enough diagnostic evidence for before/after review. It does not certify causality, controller performance, or publishable validity.",
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

    def export_review_summary(self, session_id: str) -> dict[str, Any]:
        session = self.get(session_id)
        workflow = self.workflow_status(session_id)
        review_summary = self._build_review_summary(session, workflow)
        review_summary_markdown = self._render_review_summary_markdown(review_summary)
        json_path = session.session_dir / "review-summary.json"
        markdown_path = session.session_dir / "review-summary.md"
        json_path.write_text(json.dumps(review_summary, indent=2), encoding="utf-8")
        markdown_path.write_text(review_summary_markdown, encoding="utf-8")
        session.manifest["review_summary"] = {
            "status": review_summary["status"],
            "json": str(json_path),
            "markdown": str(markdown_path),
            "updated_at": _utc_now(),
        }
        self._write_manifest(session)
        return {
            "review_summary": review_summary,
            "review_summary_json_path": json_path,
            "review_summary_markdown_path": markdown_path,
            "review_summary_markdown": review_summary_markdown,
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
        if status_by_id["metric_comparison"] == "warn":
            actions.append("Compare Metrics after output inspection is persisted.")
        if status_by_id["visual_diff"] == "warn":
            actions.append("Export Visual Diff after before/after checkpoints exist.")
        if status_by_id["timeline"] == "missing":
            actions.append("Export Timeline.")
        if status_by_id["codex_packet"] == "missing":
            actions.append("Export Codex Packet.")
        if not actions:
            actions.append("Ask Codex to inspect codex-packet.md, timeline.md, metric-comparison.md, visual-diff.md, and output-inspection.md.")
        return actions

    def _comparison_readiness_actions(self, checklist: list[dict[str, str]]) -> list[str]:
        status_by_id = {item["id"]: item["status"] for item in checklist}
        required_actions = [
            ("scenario_plan", "Create Scenario Plan."),
            ("first_checkpoint", "Capture First Checkpoint."),
            ("before_after_checkpoints", "Capture before-change and after-change checkpoints."),
            ("change_record", "Record Scenario Change or Record Change."),
            ("output_inspection", "Inspect Outputs with paired summary.xml and tripinfo.xml."),
            ("metric_comparison", "Compare Metrics."),
            ("visual_diff", "Export Visual Diff."),
        ]
        actions = [action for item_id, action in required_actions if status_by_id.get(item_id) != "pass"]
        if actions:
            return actions
        recommended_actions = [
            ("metric_chart", "Export Metric Chart."),
            ("timeline", "Export Timeline."),
            ("review_summary", "Export Review Summary."),
            ("codex_packet", "Export Codex Packet."),
        ]
        actions = [action for item_id, action in recommended_actions if status_by_id.get(item_id) == "recommended"]
        if actions:
            return actions
        return ["Ask Codex to inspect review-summary.md, codex-packet.md, metric-delta-chart.md, visual-diff.md, and output-inspection.md."]

    def _scenario_item(self, item_id: str, label: str, passed: bool, evidence: str) -> dict[str, str]:
        return {
            "id": item_id,
            "label": label,
            "status": "pass" if passed else "missing",
            "evidence": evidence,
        }

    def _scenario_manifest_item(
        self,
        session: PairedSession,
        item_id: str,
        label: str,
        manifest_entry: dict[str, Any] | None,
    ) -> dict[str, str]:
        if not manifest_entry:
            return self._scenario_item(item_id, label, False, "missing")
        artifacts = [
            self._relative_artifact(session, manifest_entry.get(key, ""))
            for key in ("markdown", "json", "svg", "path")
            if manifest_entry.get(key)
        ]
        return self._scenario_item(
            item_id,
            label,
            True,
            ", ".join(path for path in artifacts if path) or manifest_entry.get("status", "exported"),
        )

    def _scenario_next_actions(self, checklist: list[dict[str, str]]) -> list[str]:
        status_by_id = {item["id"]: item["status"] for item in checklist}
        ordered_actions = [
            ("scenario_plan", "Create Scenario Plan."),
            ("first_checkpoint", "Capture First Checkpoint."),
            ("before_checkpoint", "Capture before-change checkpoint."),
            ("change_record", "Record Change with the planned parameter, before value, after value, and rationale."),
            ("after_checkpoint", "Capture after-change checkpoint."),
            ("visual_diff", "Export Visual Diff."),
            ("output_inspection", "Inspect Outputs with summary.xml and tripinfo.xml."),
            ("metric_comparison", "Compare Metrics."),
            ("metric_chart", "Export Metric Chart."),
            ("timeline", "Export Timeline."),
            ("review_summary", "Export Review Summary."),
            ("codex_packet", "Export Codex Packet."),
        ]
        return [action for item_id, action in ordered_actions if status_by_id.get(item_id) == "missing"]

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
        if "scenario_plan" in session.manifest:
            plan = session.manifest["scenario_plan"]
            events.append(
                {
                    "sequence": len(events) + 1,
                    "kind": "scenario-plan",
                    "label": plan.get("label", "scenario-plan"),
                    "simulation_time": None,
                    "wall_time": plan.get("updated_at") or plan.get("created_at"),
                    "status": "planned",
                    "template": None,
                    "note": f"{plan.get('parameter')}: {plan.get('before_value')} -> {plan.get('after_value')}",
                    "artifacts": [
                        self._relative_artifact(session, plan.get("json", "")),
                        self._relative_artifact(session, plan.get("markdown", "")),
                    ],
                }
            )
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
        for observation in session.manifest.get("visual_observations", []):
            events.append(
                {
                    "sequence": len(events) + 1,
                    "kind": "visual-observation",
                    "label": observation.get("label", "visual-observation"),
                    "simulation_time": observation.get("simulation_time"),
                    "wall_time": observation.get("created_at"),
                    "status": observation.get("confidence", "diagnostic"),
                    "template": None,
                    "note": f"{observation.get('observation_type')}: {observation.get('note')}",
                    "artifacts": ["visual-observations.json", "visual-observations.md"],
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
        if "metric_comparison" in session.manifest:
            comparison = session.manifest["metric_comparison"]
            events.append(
                {
                    "sequence": len(events) + 1,
                    "kind": "metric-comparison",
                    "label": "Metric comparison",
                    "simulation_time": None,
                    "wall_time": comparison.get("updated_at"),
                    "status": comparison.get("status", "unknown"),
                    "template": None,
                    "note": "completion-first baseline-vs-variant metric deltas",
                    "artifacts": [
                        self._relative_artifact(session, comparison.get("json", "")),
                        self._relative_artifact(session, comparison.get("markdown", "")),
                    ],
                }
            )
        if "metric_chart" in session.manifest:
            chart = session.manifest["metric_chart"]
            events.append(
                {
                    "sequence": len(events) + 1,
                    "kind": "metric-chart",
                    "label": "Metric delta chart",
                    "simulation_time": None,
                    "wall_time": chart.get("updated_at"),
                    "status": chart.get("status", "unknown"),
                    "template": None,
                    "note": "visual index of metric deltas; bars are not a validity claim",
                    "artifacts": [
                        self._relative_artifact(session, chart.get("svg", "")),
                        self._relative_artifact(session, chart.get("markdown", "")),
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
        if "review_summary" in session.manifest:
            summary = session.manifest["review_summary"]
            events.append(
                {
                    "sequence": len(events) + 1,
                    "kind": "review-summary",
                    "label": "Review summary",
                    "simulation_time": None,
                    "wall_time": summary.get("updated_at"),
                    "status": summary.get("status", "unknown"),
                    "template": None,
                    "note": "compact evidence and claim-boundary dashboard",
                    "artifacts": [
                        self._relative_artifact(session, summary.get("json", "")),
                        self._relative_artifact(session, summary.get("markdown", "")),
                    ],
                }
            )
        if "next_action_review" in session.manifest:
            review = session.manifest["next_action_review"]
            events.append(
                {
                    "sequence": len(events) + 1,
                    "kind": "next-action-review",
                    "label": "Next action review",
                    "simulation_time": None,
                    "wall_time": review.get("updated_at"),
                    "status": review.get("status", "unknown"),
                    "template": None,
                    "note": "diagnostic control screen for the next Sidecar action",
                    "artifacts": [
                        self._relative_artifact(session, review.get("json", "")),
                        self._relative_artifact(session, review.get("markdown", "")),
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
            baseline_before = self._relative_artifact(session, before.baseline_screenshot)
            baseline_after = self._relative_artifact(session, after.baseline_screenshot)
            variant_before = self._relative_artifact(session, before.variant_screenshot)
            variant_after = self._relative_artifact(session, after.variant_screenshot)
            baseline_pixel_diff = pixel_diff.get("baseline_diff")
            variant_pixel_diff = pixel_diff.get("variant_diff")
            pairs.append(
                {
                    "index": index,
                    "status": "paired",
                    "before": self._visual_diff_checkpoint(session, before),
                    "after": self._visual_diff_checkpoint(session, after),
                    "baseline_before": baseline_before,
                    "baseline_after": baseline_after,
                    "variant_before": variant_before,
                    "variant_after": variant_after,
                    "pixel_diff": pixel_diff,
                    "baseline_pixel_diff": baseline_pixel_diff,
                    "variant_pixel_diff": variant_pixel_diff,
                    "matrix": [
                        {
                            "role": "baseline",
                            "label": "Baseline",
                            "before": baseline_before,
                            "after": baseline_after,
                            "pixel_diff": baseline_pixel_diff,
                            "changed_pixels": pixel_diff["baseline_changed_pixels"],
                            "total_pixels": pixel_diff["baseline_total_pixels"],
                            "changed_pixel_ratio": self._pixel_ratio(
                                pixel_diff["baseline_changed_pixels"],
                                pixel_diff["baseline_total_pixels"],
                            ),
                        },
                        {
                            "role": "variant",
                            "label": "Variant",
                            "before": variant_before,
                            "after": variant_after,
                            "pixel_diff": variant_pixel_diff,
                            "changed_pixels": pixel_diff["variant_changed_pixels"],
                            "total_pixels": pixel_diff["variant_total_pixels"],
                            "changed_pixel_ratio": self._pixel_ratio(
                                pixel_diff["variant_changed_pixels"],
                                pixel_diff["variant_total_pixels"],
                            ),
                        },
                    ],
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

    def _pixel_ratio(self, changed_pixels: Any, total_pixels: Any) -> float | None:
        if not isinstance(changed_pixels, (int, float)) or not isinstance(total_pixels, (int, float)):
            return None
        if total_pixels <= 0:
            return None
        return changed_pixels / total_pixels

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
            lines.extend(
                [
                    "#### Visual comparison matrix",
                    "",
                    "| Role | Before | After | Pixel diff | Changed pixels | Changed ratio |",
                    "|---|---|---|---|---:|---:|",
                ]
            )
            for row in pair.get("matrix", []):
                changed_pixels = row["changed_pixels"] if row["changed_pixels"] is not None else "n/a"
                total_pixels = row["total_pixels"] if row["total_pixels"] is not None else "n/a"
                ratio = row["changed_pixel_ratio"]
                ratio_text = "n/a" if ratio is None else f"{ratio:.2%}"
                lines.append(
                    f"| {row['label']} | `{row['before']}` | `{row['after']}` | `{row['pixel_diff']}` | {changed_pixels} / {total_pixels} | {ratio_text} |"
                )
            lines.append("")
            if pixel_diff["warnings"]:
                lines.extend(f"- Pixel warning: {warning}" for warning in pixel_diff["warnings"])
                lines.append("")
        return "\n".join(lines)

    def _build_metric_comparison(self, session: PairedSession, report_data: dict[str, Any]) -> dict[str, Any]:
        baseline = report_data.get("baseline", {})
        variant = report_data.get("variant", {})
        return {
            "session_id": session.id,
            "session_name": session.name,
            "status": report_data.get("status", "unknown"),
            "change_records": session.manifest.get("change_records", []),
            "paired_warnings": report_data.get("paired_warnings", []),
            "completion_metrics": self._metric_rows(
                baseline.get("summary") or {},
                variant.get("summary") or {},
                [
                    ("loaded", "Loaded vehicles"),
                    ("inserted", "Inserted vehicles"),
                    ("arrived", "Arrived vehicles"),
                    ("running", "Vehicles still running"),
                    ("waiting", "Vehicles waiting for insertion"),
                    ("teleports", "Teleports"),
                    ("completion_ratio", "Completion ratio"),
                ],
            ),
            "tripinfo_metrics": self._metric_rows(
                baseline.get("tripinfo") or {},
                variant.get("tripinfo") or {},
                [
                    ("trip_count", "Tripinfo records"),
                    ("mean_duration", "Mean duration"),
                    ("mean_waiting_time", "Mean waiting time"),
                    ("mean_time_loss", "Mean time loss"),
                ],
            ),
            "claim_boundary": "This is a diagnostic metric comparison. It compares persisted paired output evidence, but formal claims still require matched demand, seeds, horizon, controller logs, and reproducible runs.",
        }

    def _metric_rows(
        self,
        baseline_metrics: dict[str, Any],
        variant_metrics: dict[str, Any],
        metrics: list[tuple[str, str]],
    ) -> list[dict[str, Any]]:
        rows = []
        for metric, label in metrics:
            baseline_value = baseline_metrics.get(metric)
            variant_value = variant_metrics.get(metric)
            rows.append(
                {
                    "metric": metric,
                    "label": label,
                    "baseline": baseline_value,
                    "variant": variant_value,
                    "delta": self._metric_delta(baseline_value, variant_value),
                    "delta_definition": "variant - baseline",
                }
            )
        return rows

    def _metric_delta(self, baseline_value: Any, variant_value: Any) -> float | int | None:
        if isinstance(baseline_value, (int, float)) and isinstance(variant_value, (int, float)):
            delta = variant_value - baseline_value
            return round(delta, 10) if isinstance(delta, float) else delta
        return None

    def _render_metric_comparison_markdown(self, comparison: dict[str, Any]) -> str:
        lines = [
            f"# SUMO Metric Comparison: {comparison['session_name']}",
            "",
            "This diagnostic metric comparison is built from persisted `output-inspection.json`; it does not re-run SUMO and it does not certify a performance claim.",
            "",
            f"- Status: `{comparison['status']}`",
            f"- Claim boundary: {comparison['claim_boundary']}",
            "",
            "## Change records",
            "",
        ]
        if comparison["change_records"]:
            lines.extend(
                f"- `{record['parameter']}`: `{record['before_value']}` -> `{record['after_value']}` ({record['rationale']})"
                for record in comparison["change_records"]
            )
        else:
            lines.append("- none")
        lines.extend(["", "## Paired warnings", ""])
        if comparison["paired_warnings"]:
            lines.extend(f"- {warning}" for warning in comparison["paired_warnings"])
        else:
            lines.append("- none")
        lines.extend(["", "## Completion-first metrics", ""])
        lines.extend(self._render_metric_table(comparison["completion_metrics"]))
        lines.extend(["", "## Tripinfo metrics", ""])
        lines.extend(self._render_metric_table(comparison["tripinfo_metrics"]))
        return "\n".join(lines)

    def _render_metric_table(self, rows: list[dict[str, Any]]) -> list[str]:
        lines = [
            "| Metric | Baseline | Variant | Delta |",
            "|---|---:|---:|---:|",
        ]
        for row in rows:
            lines.append(
                f"| {row['label']} (`{row['metric']}`) | {self._format_metric_value(row['baseline'])} | {self._format_metric_value(row['variant'])} | {self._format_metric_value(row['delta'])} |"
            )
        return lines

    def _format_metric_value(self, value: Any) -> str:
        return "" if value is None else f"`{value}`"

    def _build_review_summary(self, session: PairedSession, workflow: dict[str, Any]) -> dict[str, Any]:
        cards = [
            self._review_manifest_card(
                session,
                "scenario_plan",
                "Scenario plan",
                session.manifest.get("scenario_plan"),
            ),
            self._review_card(
                "change_records",
                "Structured change records",
                "pass" if session.manifest.get("change_records") else "warn",
                f"{len(session.manifest.get('change_records', []))} change record(s)",
                ["change-records.md", "change-records.json"] if session.manifest.get("change_records_artifact") else [],
            ),
            self._review_card(
                "visual_observations",
                "Visual observations",
                "pass" if session.manifest.get("visual_observations") else "warn",
                f"{len(session.manifest.get('visual_observations', []))} observation(s)",
                ["visual-observations.md", "visual-observations.json"] if session.manifest.get("visual_observations_artifact") else [],
            ),
            self._review_manifest_card(
                session,
                "output_inspection",
                "Output inspection",
                session.manifest.get("output_inspection"),
            ),
            self._review_manifest_card(
                session,
                "metric_comparison",
                "Completion-first metric comparison",
                session.manifest.get("metric_comparison"),
            ),
            self._review_manifest_card(
                session,
                "metric_chart",
                "Metric delta chart",
                session.manifest.get("metric_chart"),
            ),
            self._review_manifest_card(
                session,
                "visual_diff",
                "Before/after visual diff",
                session.manifest.get("visual_diff"),
            ),
            self._review_manifest_card(
                session,
                "timeline",
                "Run timeline",
                session.manifest.get("timeline"),
            ),
            self._review_manifest_card(
                session,
                "codex_packet",
                "Codex packet",
                session.manifest.get("codex_packet"),
            ),
            self._review_card(
                "workflow",
                "Workflow control screen",
                workflow["status"],
                workflow["claim_status"],
                [],
            ),
        ]
        return {
            "session_id": session.id,
            "session_name": session.name,
            "session_dir": str(session.session_dir),
            "status": workflow["status"],
            "claim_status": workflow["claim_status"],
            "cards": cards,
            "metric_highlights": self._metric_highlights(session),
            "change_records": session.manifest.get("change_records", []),
            "visual_observations": session.manifest.get("visual_observations", []),
            "artifacts_to_review": self._review_artifacts_to_review(session),
            "next_actions": workflow["next_actions"],
            "claim_boundary": "This summary is a review dashboard for existing Sidecar evidence. It does not re-run SUMO, prove causality, or certify controller performance.",
        }

    def _review_manifest_card(
        self,
        session: PairedSession,
        card_id: str,
        label: str,
        manifest_entry: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not manifest_entry:
            return self._review_card(card_id, label, "missing", "not exported", [])
        artifacts = [
            self._relative_artifact(session, manifest_entry.get(key, ""))
            for key in ("markdown", "json", "svg", "path")
            if manifest_entry.get(key)
        ]
        return self._review_card(
            card_id,
            label,
            manifest_entry.get("status", "exported"),
            ", ".join(path for path in artifacts if path) or "exported",
            [path for path in artifacts if path],
        )

    def _review_card(
        self,
        card_id: str,
        label: str,
        status: str,
        summary: str,
        artifacts: list[str],
    ) -> dict[str, Any]:
        return {
            "id": card_id,
            "label": label,
            "status": status,
            "summary": summary,
            "artifacts": artifacts,
        }

    def _metric_highlights(self, session: PairedSession) -> list[dict[str, Any]]:
        metric_path = session.session_dir / "metric-comparison.json"
        if not metric_path.exists():
            return []
        comparison = json.loads(metric_path.read_text(encoding="utf-8"))
        preferred = {
            "completion_ratio",
            "arrived",
            "running",
            "teleports",
            "mean_duration",
            "mean_waiting_time",
            "mean_time_loss",
        }
        rows = comparison.get("completion_metrics", []) + comparison.get("tripinfo_metrics", [])
        return [row for row in rows if row.get("metric") in preferred]

    def _review_artifacts_to_review(self, session: PairedSession) -> list[str]:
        candidates = [
            "next-action-review.md",
            "agent-review-prompt.md",
            "codex-packet.md",
            "review-summary.md",
            "scenario-plan.md",
            "timeline.md",
            "timeline-review.md",
            "metric-delta-chart.md",
            "metric-delta-chart.svg",
            "metric-comparison.md",
            "visual-observations.md",
            "visual-diff.md",
            "output-inspection.md",
            "change-records.md",
            "comparison.md",
        ]
        return [path for path in candidates if (session.session_dir / path).exists()]

    def _build_agent_review_prompt(
        self,
        session: PairedSession,
        readiness: dict[str, Any],
        workflow: dict[str, Any],
    ) -> dict[str, Any]:
        artifacts_to_open = self._agent_prompt_artifacts_to_open(session)
        next_actions = []
        for action in readiness.get("next_actions", []) + workflow.get("next_actions", []):
            if action not in next_actions:
                next_actions.append(action)
        return {
            "session_id": session.id,
            "session_name": session.name,
            "session_dir": str(session.session_dir),
            "baseline_config": session.manifest["baseline_config"],
            "variant_config": session.manifest["variant_config"],
            "readiness_status": readiness["status"],
            "workflow_status": workflow["status"],
            "claim_status": readiness["claim_status"],
            "artifacts_to_open": artifacts_to_open,
            "next_actions": next_actions,
            "readiness_checklist": readiness["checklist"],
            "claim_boundary": readiness["claim_boundary"],
            "copyable_prompt": self._copyable_agent_prompt(session, readiness, workflow, artifacts_to_open, next_actions),
        }

    def _agent_prompt_artifacts_to_open(self, session: PairedSession) -> list[str]:
        candidates = [
            "next-action-review.md",
            "review-summary.md",
            "codex-packet.md",
            "scenario-plan.md",
            "change-records.md",
            "visual-observations.md",
            "visual-diff.md",
            "metric-comparison.md",
            "metric-delta-chart.md",
            "metric-delta-chart.svg",
            "output-inspection.md",
            "timeline.md",
            "timeline-review.md",
            "comparison.md",
            "manifest.json",
        ]
        return [path for path in candidates if (session.session_dir / path).exists()]

    def _build_next_action_review(
        self,
        session: PairedSession,
        readiness: dict[str, Any],
        workflow: dict[str, Any],
    ) -> dict[str, Any]:
        relative_paths = {item.relative_path for item in self._list_artifacts(session)}
        visual_observations = session.manifest.get("visual_observations", [])
        has_visual_diff = "visual-diff.md" in relative_paths
        has_visual_observations = bool(visual_observations)
        has_output_inspection = "output-inspection.md" in relative_paths
        has_metric_comparison = "metric-comparison.md" in relative_paths
        has_metric_chart = "metric-delta-chart.md" in relative_paths
        has_review_summary = "review-summary.md" in relative_paths
        has_codex_packet = "codex-packet.md" in relative_paths
        has_agent_prompt = "agent-review-prompt.md" in relative_paths

        recommended_actions: list[dict[str, str]] = []
        if not has_visual_diff:
            recommended_actions.append(
                self._next_action(
                    1,
                    "Export Visual Diff",
                    "Before/after visual evidence has not been indexed yet.",
                    "visual-diff.md",
                )
            )
        elif not has_visual_observations:
            recommended_actions.append(
                self._next_action(
                    1,
                    "Record Visual Observation",
                    "The visual diff exists, but the human-visible queue, phase, or density pattern has not been described.",
                    "visual-observations.md",
                )
            )
        elif not has_output_inspection:
            recommended_actions.append(
                self._next_action(
                    1,
                    "Inspect Outputs",
                    "Visual observations need completion, unfinished-vehicle, teleport, and output-warning evidence before interpretation.",
                    "output-inspection.md",
                )
            )
        elif not has_metric_comparison:
            recommended_actions.append(
                self._next_action(
                    1,
                    "Compare Metrics",
                    "Output inspection exists, but completion-first baseline/variant deltas have not been exported.",
                    "metric-comparison.md",
                )
            )
        elif not has_metric_chart:
            recommended_actions.append(
                self._next_action(
                    1,
                    "Export Metric Chart",
                    "Metric deltas exist, but there is no visual metric artifact for quick paired inspection.",
                    "metric-delta-chart.md",
                )
            )
        elif not has_review_summary:
            recommended_actions.append(
                self._next_action(
                    1,
                    "Export Review Summary",
                    "Core visual and metric artifacts exist, but the compact claim-boundary dashboard has not been exported.",
                    "review-summary.md",
                )
            )
        elif not has_codex_packet:
            recommended_actions.append(
                self._next_action(
                    1,
                    "Export Codex Packet",
                    "The review summary exists, but Codex still needs a single evidence bundle index.",
                    "codex-packet.md",
                )
            )
        elif not has_agent_prompt:
            recommended_actions.append(
                self._next_action(
                    1,
                    "Export Agent Prompt",
                    "The evidence bundle is ready, but the copyable Codex/Claude prompt has not been exported.",
                    "agent-review-prompt.md",
                )
            )
        else:
            recommended_actions.append(
                self._next_action(
                    1,
                    "Ask Codex or Claude to review agent-review-prompt.md",
                    "Core diagnostic review artifacts exist; the next step is agent-assisted review of supported claims and gaps.",
                    "agent-review-prompt.md",
                )
            )

        known_actions = {item["action"] for item in recommended_actions}
        for action in readiness.get("next_actions", []) + workflow.get("next_actions", []):
            clean_action = action.rstrip(".")
            if clean_action not in known_actions:
                recommended_actions.append(
                    self._next_action(
                        len(recommended_actions) + 1,
                        clean_action,
                        "Sidecar status check still reports this as a remaining workflow gap.",
                        "workflow-status",
                    )
                )
                known_actions.add(clean_action)

        missing_or_warn_checks = [
            {
                "source": source,
                "id": item["id"],
                "label": item["label"],
                "status": item["status"],
                "evidence": item["evidence"],
            }
            for source, checklist in (("comparison_readiness", readiness.get("checklist", [])), ("workflow_status", workflow.get("checklist", [])))
            for item in checklist
            if item.get("status") != "pass"
        ]
        status = "ready-for-agent-review" if recommended_actions[0]["action"].startswith("Ask Codex") else "needs-action"
        return {
            "session_id": session.id,
            "session_name": session.name,
            "session_dir": str(session.session_dir),
            "status": status,
            "readiness_status": readiness["status"],
            "workflow_status": workflow["status"],
            "claim_status": "diagnostic-control-screen",
            "visual_observations": visual_observations,
            "missing_or_warn_checks": missing_or_warn_checks,
            "recommended_actions": recommended_actions,
            "artifacts_to_open": self._agent_prompt_artifacts_to_open(session),
            "claim_boundary": "Next-action review is a diagnostic control screen. It does not prove causality, performance improvement, or publishable validity.",
        }

    def _next_action(self, priority: int, action: str, reason: str, evidence: str) -> dict[str, str]:
        return {
            "priority": str(priority),
            "action": action,
            "reason": reason,
            "evidence": evidence,
        }

    def _copyable_agent_prompt(
        self,
        session: PairedSession,
        readiness: dict[str, Any],
        workflow: dict[str, Any],
        artifacts_to_open: list[str],
        next_actions: list[str],
    ) -> str:
        artifact_lines = "\n".join(f"- {artifact}" for artifact in artifacts_to_open) or "- No review artifacts exported yet."
        action_lines = "\n".join(f"- {action}" for action in next_actions) or "- Inspect the listed artifacts and propose the next evidence step."
        return "\n".join(
            [
                "Use Simulation Helper Skill for Eclipse SUMO (`simulation-helper-skill-for-eclipse-sumo`) or an equivalent SUMO/TraCI audit workflow to review this Sidecar evidence bundle.",
                "",
                f"Session folder: {session.session_dir}",
                f"Session id: {session.id}",
                f"Baseline config: {session.manifest['baseline_config']}",
                f"Variant config: {session.manifest['variant_config']}",
                f"Comparison readiness: {readiness['status']}",
                f"Workflow status: {workflow['status']}",
                f"Claim status: {readiness['claim_status']}",
                "",
                "Open these artifacts first:",
                artifact_lines,
                "",
                "Task:",
                "1. Report only supported visual and metric differences from the listed artifacts.",
                "2. Start with completion, unfinished vehicles, teleports, and output warnings before interpreting tripinfo means.",
                "3. Connect visual changes to change records only when the evidence supports the connection.",
                "4. Identify missing evidence, unpaired assumptions, or claim overreach.",
                "5. Give the next concrete Sidecar action to run.",
                "",
                "Next actions currently suggested by the Sidecar:",
                action_lines,
                "",
                "Do not claim causality, performance improvement, or publishable validity from this prompt alone.",
            ]
        )

    def _render_agent_review_prompt_markdown(self, prompt: dict[str, Any]) -> str:
        artifact_lines = [f"- `{artifact}`" for artifact in prompt["artifacts_to_open"]] or ["- none"]
        action_lines = [f"- {action}" for action in prompt["next_actions"]] or ["- none"]
        return "\n".join(
            [
                f"# Agent Review Prompt: {prompt['session_name']}",
                "",
                "Use this prompt in Codex or Claude. It is a bridge from the local Sidecar evidence bundle to an agent review turn.",
                "",
                "## Status",
                "",
                f"- Comparison readiness: `{prompt['readiness_status']}`",
                f"- Workflow status: `{prompt['workflow_status']}`",
                f"- Claim status: `{prompt['claim_status']}`",
                f"- Session folder: `{prompt['session_dir']}`",
                "",
                "## Artifacts to open",
                "",
                *artifact_lines,
                "",
                "## Current next actions",
                "",
                *action_lines,
                "",
                "## Copyable prompt",
                "",
                "```text",
                prompt["copyable_prompt"],
                "```",
                "",
                "## Claim boundary",
                "",
                prompt["claim_boundary"],
            ]
        )

    def _render_next_action_review_markdown(self, review: dict[str, Any]) -> str:
        action_lines = [
            f"| {action['priority']} | {self._markdown_table_cell(action['action'])} | {self._markdown_table_cell(action['reason'])} | `{action['evidence']}` |"
            for action in review["recommended_actions"]
        ]
        observation_lines = [
            f"- `{item.get('label', 'visual-observation')}` / `{item.get('observation_type', 'unknown')}` / `{item.get('confidence', 'diagnostic')}`: {item.get('note', '')} (artifact: `{item.get('evidence_artifact') or 'not specified'}`)"
            for item in review["visual_observations"]
        ] or ["- none"]
        gap_lines = [
            f"- `{item['source']}` `{item['id']}`: `{item['status']}` - {item['evidence']}"
            for item in review["missing_or_warn_checks"]
        ] or ["- none"]
        artifact_lines = [f"- `{artifact}`" for artifact in review["artifacts_to_open"]] or ["- none"]
        return "\n".join(
            [
                f"# Next Action Review: {review['session_name']}",
                "",
                "A diagnostic control screen for choosing the next Sidecar action from current visual, output, and review artifacts.",
                "",
                "## Status",
                "",
                f"- Next-action status: `{review['status']}`",
                f"- Comparison readiness: `{review['readiness_status']}`",
                f"- Workflow status: `{review['workflow_status']}`",
                f"- Claim status: `{review['claim_status']}`",
                f"- Session folder: `{review['session_dir']}`",
                "",
                "## Recommended actions",
                "",
                "| Priority | Action | Reason | Evidence target |",
                "|---|---|---|---|",
                *action_lines,
                "",
                "## Visual observations",
                "",
                *observation_lines,
                "",
                "Primary observation artifact: `visual-observations.md`.",
                "",
                "## Remaining gaps",
                "",
                *gap_lines,
                "",
                "## Artifacts to open",
                "",
                *artifact_lines,
                "",
                "## Claim boundary",
                "",
                review["claim_boundary"],
            ]
        )

    def _render_review_summary_markdown(self, summary: dict[str, Any]) -> str:
        lines = [
            f"# SUMO Review Summary: {summary['session_name']}",
            "",
            "A compact dashboard for Codex or Claude to inspect the current Sidecar evidence bundle before interpreting an experiment change.",
            "",
            "## Status",
            "",
            f"- Workflow status: `{summary['status']}`",
            f"- Claim status: `{summary['claim_status']}`",
            "",
            "## Claim boundary",
            "",
            summary["claim_boundary"],
            "",
            "## Review cards",
            "",
            "| Area | Status | Summary | Artifacts |",
            "|---|---|---|---|",
        ]
        for card in summary["cards"]:
            artifacts = ", ".join(f"`{artifact}`" for artifact in card["artifacts"]) or ""
            lines.append(
                f"| {self._markdown_table_cell(card['label'])} | `{card['status']}` | {self._markdown_table_cell(card['summary'])} | {artifacts} |"
            )
        lines.extend(["", "## Metric highlights", ""])
        if summary["metric_highlights"]:
            lines.extend(self._render_metric_table(summary["metric_highlights"]))
        else:
            lines.append("No metric comparison has been exported yet.")
        lines.extend(["", "## Change records", ""])
        if summary["change_records"]:
            lines.extend(
                f"- `{record['parameter']}`: `{record['before_value']}` -> `{record['after_value']}` ({record['rationale']})"
                for record in summary["change_records"]
            )
        else:
            lines.append("- none")
        lines.extend(["", "## Visual observations", ""])
        if summary["visual_observations"]:
            lines.extend(
                f"- `{observation['observation_type']}` ({observation['confidence']}): {observation['note']}"
                for observation in summary["visual_observations"]
            )
        else:
            lines.append("- none")
        lines.extend(["", "## Artifacts to review", ""])
        if summary["artifacts_to_review"]:
            lines.extend(f"- `{artifact}`" for artifact in summary["artifacts_to_review"])
        else:
            lines.append("- none")
        lines.extend(["", "## Next actions", ""])
        lines.extend(f"- {action}" for action in summary["next_actions"])
        return "\n".join(lines)

    def _build_metric_chart(self, session: PairedSession, comparison: dict[str, Any]) -> dict[str, Any]:
        rows = []
        for category, source_rows in (
            ("completion", comparison.get("completion_metrics", [])),
            ("tripinfo", comparison.get("tripinfo_metrics", [])),
        ):
            for row in source_rows:
                if isinstance(row.get("delta"), (int, float)):
                    rows.append({**row, "category": category})
        return {
            "session_id": session.id,
            "session_name": session.name,
            "status": comparison.get("status", "unknown"),
            "delta_definition": "variant - baseline",
            "rows": rows,
            "claim_boundary": "This is a diagnostic visualization of already-exported metric deltas. Bar length is scaled within this artifact and does not define improvement, causality, or statistical validity.",
        }

    def _render_metric_chart_svg(self, chart: dict[str, Any]) -> str:
        rows = chart["rows"]
        row_height = 46
        top = 92
        bottom = 70
        width = 980
        height = top + max(1, len(rows)) * row_height + bottom
        label_x = 32
        center_x = 560
        max_bar_width = 220
        max_abs_delta = max((abs(row["delta"]) for row in rows), default=1) or 1
        svg_lines = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="SUMO metric delta chart">',
            '<rect width="100%" height="100%" fill="#fbfcfb"/>',
            f'<text x="{label_x}" y="34" font-family="Segoe UI, Arial, sans-serif" font-size="22" font-weight="700" fill="#17212b">SUMO Metric Delta Chart: {html_escape(chart["session_name"])}</text>',
            f'<text x="{label_x}" y="61" font-family="Segoe UI, Arial, sans-serif" font-size="13" fill="#62717d">Delta definition: {html_escape(chart["delta_definition"])}. Bars are a diagnostic visualization, not a performance claim.</text>',
            f'<line x1="{center_x}" y1="{top - 26}" x2="{center_x}" y2="{height - bottom + 18}" stroke="#83909a" stroke-width="1"/>',
            f'<text x="{center_x - 34}" y="{top - 34}" font-family="Segoe UI, Arial, sans-serif" font-size="12" fill="#62717d">0 delta</text>',
        ]
        if not rows:
            svg_lines.append(
                f'<text x="{label_x}" y="{top}" font-family="Segoe UI, Arial, sans-serif" font-size="14" fill="#62717d">No numeric metric deltas available.</text>'
            )
        for index, row in enumerate(rows):
            y = top + index * row_height
            delta = row["delta"]
            bar_width = round((abs(delta) / max_abs_delta) * max_bar_width, 2)
            x = center_x if delta >= 0 else center_x - bar_width
            fill = "#0d4f7a" if delta > 0 else ("#b85c38" if delta < 0 else "#83909a")
            value_text_x = center_x + bar_width + 12 if delta >= 0 else center_x - bar_width - 160
            svg_lines.extend(
                [
                    f'<text x="{label_x}" y="{y + 14}" font-family="Segoe UI, Arial, sans-serif" font-size="13" font-weight="700" fill="#17212b">{html_escape(row["label"])}</text>',
                    f'<text x="{label_x}" y="{y + 32}" font-family="Segoe UI, Arial, sans-serif" font-size="11" fill="#62717d">{html_escape(row["category"])} / {html_escape(row["metric"])}</text>',
                    f'<rect x="{x}" y="{y}" width="{bar_width}" height="22" rx="3" fill="{fill}"/>',
                    f'<text x="{value_text_x}" y="{y + 16}" font-family="Segoe UI, Arial, sans-serif" font-size="12" fill="#17212b">delta {html_escape(str(delta))}</text>',
                ]
            )
        svg_lines.extend(
            [
                f'<text x="{label_x}" y="{height - 28}" font-family="Segoe UI, Arial, sans-serif" font-size="12" fill="#62717d">Diagnostic visualization only; compare numeric units and completion evidence before interpreting bars.</text>',
                "</svg>",
            ]
        )
        return "\n".join(svg_lines)

    def _render_metric_chart_markdown(self, chart: dict[str, Any]) -> str:
        lines = [
            f"# SUMO Metric Delta Chart: {chart['session_name']}",
            "",
            "This diagnostic visualization is built from persisted `metric-comparison.json`; it does not re-run SUMO and it does not certify a performance claim.",
            "",
            f"- Status: `{chart['status']}`",
            f"- Delta definition: `{chart['delta_definition']}`",
            f"- Claim boundary: {chart['claim_boundary']}",
            "",
            "![Metric delta chart](metric-delta-chart.svg)",
            "",
            "## Delta rows",
            "",
        ]
        if chart["rows"]:
            lines.extend(self._render_metric_table(chart["rows"]))
        else:
            lines.append("No numeric metric deltas available.")
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

    def _write_visual_observations(self, session: PairedSession) -> None:
        observations = session.manifest.get("visual_observations", [])
        json_path = session.session_dir / "visual-observations.json"
        markdown_path = session.session_dir / "visual-observations.md"
        json_path.write_text(
            json.dumps(
                {
                    "session_id": session.id,
                    "session_name": session.name,
                    "observations": observations,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        markdown_path.write_text(self._render_visual_observations_markdown(session, observations), encoding="utf-8")
        session.manifest["visual_observations_artifact"] = {
            "json": str(json_path),
            "markdown": str(markdown_path),
            "updated_at": _utc_now(),
        }

    def _render_scenario_plan_markdown(self, session: PairedSession, plan: dict[str, Any]) -> str:
        metrics = ", ".join(f"`{metric}`" for metric in plan["expected_metrics"]) or "`not specified`"
        return "\n".join(
            [
                f"# SUMO Scenario Plan: {session.name}",
                "",
                "This guided scenario plan records the intended before/after comparison. It is not evidence that the change was applied or that the result is valid.",
                "",
                f"- Scenario: `{plan['label']}`",
                f"- Parameter: `{plan['parameter']}`",
                f"- Planned change: `{plan['before_value']}` -> `{plan['after_value']}`",
                f"- Hypothesis: {plan['hypothesis']}",
                f"- Expected metrics: {metrics}",
                f"- Note: {plan.get('note') or 'none'}",
                f"- Created at: `{plan['created_at']}`",
                "",
                "## Required evidence sequence",
                "",
                "1. Capture `first-checkpoint`.",
                "2. Capture `before-change` before applying or activating the planned change.",
                "3. Record the actual change with parameter, before value, after value, and rationale.",
                "4. Capture `after-change` after the change is active.",
                "5. Inspect SUMO outputs, compare metrics, export metric chart, export visual diff, timeline, review summary, and Codex packet.",
                "",
                "## Claim boundary",
                "",
                "This plan can guide evidence collection, but claims still require paired demand, seed, horizon, completion status, metric definitions, and reproducible outputs.",
            ]
        )

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

    def _render_visual_observations_markdown(self, session: PairedSession, observations: list[dict[str, Any]]) -> str:
        lines = [
            f"# SUMO Visual Observations: {session.name}",
            "",
            "Visual observations record what a human noticed in the SUMO GUI or visual-diff matrix. They are diagnostic annotations, not proof of causality or performance.",
            "",
        ]
        if not observations:
            lines.append("No visual observations have been recorded yet.")
            return "\n".join(lines)
        for index, observation in enumerate(observations, start=1):
            lines.extend(
                [
                    f"## {index}. {observation['label']}",
                    "",
                    f"- Type: `{observation['observation_type']}`",
                    f"- Confidence: `{observation['confidence']}`",
                    f"- SUMO time: `{observation['simulation_time']}`",
                    f"- Evidence artifact: `{observation.get('evidence_artifact') or 'not specified'}`",
                    f"- Note: {observation['note']}",
                    f"- Recorded at: `{observation['created_at']}`",
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
