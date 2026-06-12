from pathlib import Path

from sumo_sidecar.models import CreateSessionRequest, OutputInspectionRequest
from sumo_sidecar.session_manager import SessionManager


class FakeRun:
    def __init__(self, role: str, config_path: Path) -> None:
        self.role = role
        self.config_path = config_path
        self.time = 0.0
        self.closed = False
        self.screenshots: list[Path] = []

    def step(self, count: int = 1) -> dict:
        self.time += count
        return self.state()

    def run_until(self, target_time: float) -> dict:
        self.time = target_time
        return self.state()

    def screenshot(self, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(f"{self.role}:{self.time}", encoding="utf-8")
        self.screenshots.append(output_path)
        return output_path

    def state(self) -> dict:
        return {
            "role": self.role,
            "config_path": str(self.config_path),
            "time": self.time,
            "closed": self.closed,
        }

    def close(self) -> None:
        self.closed = True


class FakeAdapterFactory:
    def __init__(self, fail_on_role: str | None = None) -> None:
        self.created: list[FakeRun] = []
        self.fail_on_role = fail_on_role

    def __call__(self, role: str, config_path: Path, session_dir: Path, options: dict) -> FakeRun:
        if role == self.fail_on_role:
            raise RuntimeError(f"failed to start {role}")
        run = FakeRun(role, config_path)
        self.created.append(run)
        return run


def make_request(tmp_path: Path) -> CreateSessionRequest:
    baseline = tmp_path / "baseline.sumocfg"
    variant = tmp_path / "variant.sumocfg"
    baseline.write_text("<configuration/>", encoding="utf-8")
    variant.write_text("<configuration/>", encoding="utf-8")
    return CreateSessionRequest(
        name="demo",
        baseline_config=baseline,
        variant_config=variant,
        output_root=tmp_path / "runs",
    )


def test_create_session_writes_manifest(tmp_path: Path) -> None:
    factory = FakeAdapterFactory()
    manager = SessionManager(adapter_factory=factory)

    session = manager.create(make_request(tmp_path))

    assert session.id
    assert session.session_dir.exists()
    manifest = session.session_dir / "manifest.json"
    assert manifest.exists()
    assert len(factory.created) == 2


def test_step_advances_baseline_and_variant_together(tmp_path: Path) -> None:
    manager = SessionManager(adapter_factory=FakeAdapterFactory())
    session = manager.create(make_request(tmp_path))

    state = manager.step(session.id, count=5)

    assert state.baseline["time"] == 5
    assert state.variant["time"] == 5


def test_screenshot_writes_paired_evidence(tmp_path: Path) -> None:
    manager = SessionManager(adapter_factory=FakeAdapterFactory())
    session = manager.create(make_request(tmp_path))
    manager.step(session.id, count=3)

    evidence = manager.screenshot(session.id, label="queue-check")

    assert evidence.baseline_screenshot.exists()
    assert evidence.variant_screenshot.exists()
    assert "queue-check" in evidence.baseline_screenshot.name
    comparison = session.session_dir / "comparison.md"
    assert comparison.exists()
    assert "queue-check" in comparison.read_text(encoding="utf-8")


def test_evidence_lists_session_artifacts(tmp_path: Path) -> None:
    manager = SessionManager(adapter_factory=FakeAdapterFactory())
    session = manager.create(make_request(tmp_path))
    manager.screenshot(session.id, label="queue-check")

    evidence = manager.evidence(session.id)
    relative_paths = {item.relative_path.replace("\\", "/") for item in evidence.artifacts}

    assert "manifest.json" in relative_paths
    assert "comparison.md" in relative_paths
    assert any(path.startswith("baseline/screenshots/") for path in relative_paths)
    assert any(path.startswith("variant/screenshots/") for path in relative_paths)


def test_output_inspection_is_written_to_session_evidence(tmp_path: Path) -> None:
    manager = SessionManager(adapter_factory=FakeAdapterFactory())
    session = manager.create(make_request(tmp_path))
    baseline_summary = tmp_path / "baseline-summary.xml"
    variant_summary = tmp_path / "variant-summary.xml"
    baseline_summary.write_text(
        '<summary><step time="10" loaded="2" inserted="2" running="0" waiting="0" arrived="2" teleports="0"/></summary>',
        encoding="utf-8",
    )
    variant_summary.write_text(
        '<summary><step time="10" loaded="2" inserted="2" running="1" waiting="0" arrived="1" teleports="0"/></summary>',
        encoding="utf-8",
    )

    report = manager.inspect_outputs(
        session.id,
        OutputInspectionRequest(
            baseline_summary=baseline_summary,
            variant_summary=variant_summary,
        ),
    )
    evidence = manager.evidence(session.id)
    relative_paths = {item.relative_path for item in evidence.artifacts}

    assert report.status == "warn"
    assert "output-inspection.json" in relative_paths
    assert "output-inspection.md" in relative_paths
    assert "completion differs" in (session.session_dir / "output-inspection.md").read_text(encoding="utf-8")
    assert evidence.manifest["output_inspection"]["status"] == "warn"


def test_screenshot_sanitizes_label_for_file_paths(tmp_path: Path) -> None:
    manager = SessionManager(adapter_factory=FakeAdapterFactory())
    session = manager.create(make_request(tmp_path))

    evidence = manager.screenshot(session.id, label="../unsafe label")

    assert evidence.label == "unsafe-label"
    assert evidence.baseline_screenshot.parent.name == "screenshots"
    assert evidence.baseline_screenshot.name.endswith("unsafe-label.png")


def test_create_closes_started_run_when_second_adapter_fails(tmp_path: Path) -> None:
    factory = FakeAdapterFactory(fail_on_role="variant")
    manager = SessionManager(adapter_factory=factory)

    try:
        manager.create(make_request(tmp_path))
    except RuntimeError:
        pass

    assert len(factory.created) == 1
    assert factory.created[0].role == "baseline"
    assert factory.created[0].closed


def test_close_closes_both_runs(tmp_path: Path) -> None:
    factory = FakeAdapterFactory()
    manager = SessionManager(adapter_factory=factory)
    session = manager.create(make_request(tmp_path))

    manager.close(session.id)

    assert all(run.closed for run in factory.created)
