from __future__ import annotations

import importlib.util
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any


def find_binary(name: str) -> str | None:
    return shutil.which(name) or shutil.which(f"{name}.exe")


def preflight() -> dict[str, Any]:
    traci_spec = importlib.util.find_spec("traci")
    sumo_gui = find_binary("sumo-gui")
    sumo = find_binary("sumo")
    return {
        "python_version": sys.version,
        "sumo_gui_binary": sumo_gui,
        "sumo_binary": sumo,
        "traci_available": traci_spec is not None,
        "traci_location": traci_spec.origin if traci_spec else None,
    }


class TraCISumoRun:
    def __init__(self, role: str, config_path: Path, session_dir: Path, options: dict[str, Any]) -> None:
        try:
            import traci  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError("Python package 'traci' is required. Install this project with .[dev] or install traci.") from exc

        self.traci = traci
        self.role = role
        self.config_path = config_path
        self.session_dir = session_dir
        self.label = f"{role}-{uuid.uuid4().hex[:8]}"
        binary = options.get("sumo_gui_binary") or find_binary("sumo-gui")
        if not binary:
            raise FileNotFoundError("sumo-gui binary not found on PATH. Set sumo_gui_binary in the create-session request.")

        cmd = [binary, "-c", str(config_path)]
        if options.get("start", True):
            cmd.append("--start")
        if options.get("quit_on_end", False):
            cmd.append("--quit-on-end")
        cmd.extend(options.get("extra_args") or [])

        self.traci.start(cmd, label=self.label)
        self.connection = self.traci.getConnection(self.label)

    def step(self, count: int = 1) -> dict[str, Any]:
        for _ in range(count):
            self.connection.simulationStep()
        return self.state()

    def run_until(self, target_time: float) -> dict[str, Any]:
        while float(self.connection.simulation.getTime()) < target_time:
            self.connection.simulationStep()
            if self.connection.simulation.getMinExpectedNumber() == 0:
                break
        return self.state()

    def screenshot(self, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection.gui.screenshot("View #0", str(output_path))
        return output_path

    def state(self) -> dict[str, Any]:
        simulation = self.connection.simulation
        return {
            "role": self.role,
            "config_path": str(self.config_path),
            "time": float(simulation.getTime()),
            "min_expected": int(simulation.getMinExpectedNumber()),
            "departed_last_step": int(simulation.getDepartedNumber()),
            "arrived_last_step": int(simulation.getArrivedNumber()),
        }

    def close(self) -> None:
        self.connection.close(False)
