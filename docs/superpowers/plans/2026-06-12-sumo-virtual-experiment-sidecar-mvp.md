# SUMO Virtual Experiment Sidecar MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a usable local web sidecar that can launch paired baseline/variant `sumo-gui` sessions, step or run them together, capture screenshots, and write evidence bundles that Codex can inspect.

**Architecture:** A Python FastAPI backend owns session lifecycle, SUMO process launching, TraCI stepping, screenshot capture, and evidence writing. A static local web UI calls the backend through HTTP. Core logic is separated from the TraCI adapter so tests can run without opening SUMO GUI.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Pydantic, TraCI, SUMO/sumo-gui, pytest.

---

## File Structure

- `pyproject.toml`: package metadata, runtime dependencies, pytest config.
- `README.md`: install, run, architecture, API, and SUMO evidence boundary.
- `src/sumo_sidecar/models.py`: request/response models and serializable evidence records.
- `src/sumo_sidecar/sumo_adapter.py`: process and TraCI adapter boundary.
- `src/sumo_sidecar/session_manager.py`: paired session lifecycle, synchronization, screenshots, evidence bundle creation.
- `src/sumo_sidecar/server.py`: FastAPI app and static file mounting.
- `src/sumo_sidecar/__main__.py`: `python -m sumo_sidecar` entrypoint.
- `static/index.html`: local sidecar UI shell.
- `static/styles.css`: restrained local tool styling.
- `static/app.js`: browser API client and UI state handling.
- `tests/test_session_manager.py`: mock-adapter tests for session creation, stepping, screenshot evidence, and teardown.
- `tests/test_api.py`: FastAPI tests for preflight, create, step, run-until, screenshot, state, and evidence endpoints.

## Task 1: Project Scaffolding

- [ ] Create package, static, docs, and tests directories.
- [ ] Add `pyproject.toml`, `.gitignore`, README skeleton, and package entrypoint.
- [ ] Verify `python -m pip install -e ".[dev]"` works in a local virtual environment.

## Task 2: Session Manager TDD

- [ ] Write tests with a fake SUMO adapter proving session creation creates `runs/<session_id>/manifest.json`.
- [ ] Write tests proving paired `step()` advances baseline and variant by the same number of steps.
- [ ] Write tests proving screenshot capture writes baseline/variant screenshot files and updates evidence.
- [ ] Write tests proving `close()` closes both runs.
- [ ] Implement minimal session manager until tests pass.

## Task 3: SUMO Adapter

- [ ] Implement a `SumoRunAdapter` interface.
- [ ] Implement `TraCISumoRun` that launches `sumo-gui` on a unique port with `--remote-port`, `--start`, and optional `--quit-on-end`.
- [ ] Implement `step`, `run_until`, `screenshot`, `state`, and `close`.
- [ ] Add graceful error messages when `traci`, `sumo-gui`, or config files are missing.

## Task 4: FastAPI Backend TDD

- [ ] Write API tests with fake adapter factory.
- [ ] Implement `/api/preflight`.
- [ ] Implement `/api/session/create`.
- [ ] Implement `/api/session/{id}/step`.
- [ ] Implement `/api/session/{id}/run-until`.
- [ ] Implement `/api/session/{id}/screenshot`.
- [ ] Implement `/api/session/{id}/state`.
- [ ] Implement `/api/session/{id}/evidence`.
- [ ] Implement `/api/session/{id}/close`.

## Task 5: Local Web UI

- [ ] Create a single-page local UI with baseline/variant config fields, output folder, session controls, and status cards.
- [ ] Add buttons for create, step, run-until, screenshot, refresh state, evidence, and close.
- [ ] Show Codex-readable evidence path and JSON/Markdown preview.
- [ ] Keep UI dense and tool-like, not a landing page.

## Task 6: Verification and Release Baseline

- [ ] Run `pytest`.
- [ ] Run a preflight command against the local SUMO install if available.
- [ ] Run the app locally and verify `/api/preflight` responds.
- [ ] Commit and push to `Tarard/SUMO-Virtual-Experiment-Sidecar`.

## MVP Completion Criteria

- A user can start the local web app.
- A user can create a paired baseline/variant session from two `.sumocfg` paths.
- The backend can step both simulations synchronously.
- The backend can capture paired GUI screenshots.
- The backend writes a persistent evidence bundle for Codex.
- Tests cover the session manager and API without requiring SUMO GUI.
- README explains that GUI evidence is diagnostic and formal claims still require output/metric/completion checks.
