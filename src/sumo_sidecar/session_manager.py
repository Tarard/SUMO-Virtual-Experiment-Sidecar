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

    def screenshot(self, session_id: str, label: str = "snapshot") -> ScreenshotEvidence:
        session = self.get(session_id)
        state = self.state(session_id)
        time_value = float(state.baseline.get("time", 0.0))
        safe_label = _safe_label(label)
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
        )
        session.evidence.append(evidence)
        session.manifest["evidence"] = [item.model_dump(mode="json") for item in session.evidence]
        self._write_manifest(session)
        self._write_comparison(session)
        return evidence

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
                        f"- Baseline screenshot: `{item.baseline_screenshot}`",
                        f"- Variant screenshot: `{item.variant_screenshot}`",
                        "",
                    ]
                )
        path.write_text("\n".join(lines), encoding="utf-8")

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
