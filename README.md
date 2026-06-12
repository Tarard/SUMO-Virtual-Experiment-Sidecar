# SUMO Virtual Experiment Sidecar

Local web sidecar for paired visual feedback in Eclipse SUMO/TraCI experiments.

This project starts two paired `sumo-gui` sessions, controls them through TraCI, captures synchronized screenshots, and writes Codex-readable evidence bundles. It is designed to complement a Codex/Claude workflow: the local app runs and records the visual experiment, while Codex reads the evidence folder and helps interpret what changed.

## Current Scope

MVP focus:

- launch baseline and variant `sumo-gui` sessions;
- keep runs paired by configuration, command, and evidence folder;
- step or run both sessions from a local web page;
- capture paired screenshots from the SUMO GUI view;
- capture a fixed first visual checkpoint into the evidence bundle;
- capture named `before-change`, `after-change`, `queue-build-up`, and `final-state` checkpoints with notes;
- export a before/after visual-diff index for paired template checkpoints;
- write `manifest.json` and `comparison.md` for Codex to inspect.

Not in this release:

- SUMO native GUI plugin;
- VS Code extension;
- cloud service;
- automatic code editing;
- formal proof that an experiment is valid.

GUI screenshots are diagnostic visual evidence. Formal claims still require paired outputs, completion status, metric definitions, and reproducibility checks.

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
```

SUMO must be installed locally. `sumo-gui` should be on `PATH`, or you can provide the full path in the web form.

Creating a paired session launches two `sumo-gui` processes through TraCI. The `Auto-run after launch` option controls SUMO GUI's `--start` behavior; it does not mean "create a session without launching GUI."

## Run

```powershell
.\.venv\Scripts\python -m sumo_sidecar
```

Open:

```text
http://127.0.0.1:8765
```

## Quick Demo

This repository includes a public minimal paired SUMO example:

```text
examples/minimal-paired/
  baseline.sumocfg
  variant.sumocfg
  grid.net.xml
  demand.rou.xml
```

Headless smoke run:

```powershell
sumo -c examples\minimal-paired\baseline.sumocfg
sumo -c examples\minimal-paired\variant.sumocfg
```

Then open the sidecar, run Config Pair Preflight on the two configs, and inspect:

```text
examples\minimal-paired\outputs\baseline\summary.xml
examples\minimal-paired\outputs\baseline\tripinfo.xml
examples\minimal-paired\outputs\variant\summary.xml
examples\minimal-paired\outputs\variant\tripinfo.xml
```

The example is intentionally a workflow demo, not a controller-performance claim.

The web page also has a `Load Minimal Demo` button that fills these paths automatically.

Use `Run Demo Headless` to run the bundled baseline and variant with `sumo` and load their output evidence in one step.

Use `Run Guided Demo` to run config preflight, headless SUMO execution, output inspection, and next-action guidance in one step.

Use `Launch Demo GUI` to open the same bundled baseline and variant as a paired SUMO GUI session. This starts two `sumo-gui` windows.

Use `Launch Guided GUI` to run the guided demo first, then open a paired GUI session with the output inspection report already written into the session evidence bundle.

After a GUI session is active, use `Capture First Checkpoint` to write the first paired visual checkpoint and refresh the Codex evidence panel immediately.

Use `Capture Template Checkpoint` for before/after work. The built-in templates are `before-change`, `after-change`, `queue-build-up`, and `final-state`. The optional note is written into `comparison.md` and `timeline.md`.

Use `Export Visual Diff` after capturing at least one `before-change` and one `after-change` checkpoint. It builds a four-view baseline/variant before/after index for visual inspection.

## Codex Bridge

Codex can interact with the sidecar in two ways:

1. HTTP API on `127.0.0.1:8765`.
2. Evidence folders under `runs/<session_id>/`.
3. Artifact listings returned by `/api/session/{id}/evidence`.
4. Session-scoped artifact files returned by `/api/session/{id}/artifact/{path}`.
5. A single Codex-readable packet written by `/api/session/{id}/packet/export`.
6. A run timeline written by `/api/session/{id}/timeline/export`.

This is intentionally not a VS Code extension. The bridge is designed for the Codex app or any local agent that can call localhost APIs and read files from the same machine.

Typical workflow:

1. Start this sidecar locally.
2. Run environment preflight and config-pair preflight.
3. Create a paired baseline/variant session in the web page.
4. Capture the first paired checkpoint, then capture named before/after checkpoints while watching the SUMO GUI windows.
5. Inspect `summary.xml` and `tripinfo.xml` output evidence before interpreting performance metrics.
6. Export the visual diff index for the paired before/after checkpoints.
7. Export a run timeline to align checkpoints, output inspection, and packet evidence.
8. Export a Codex packet when the session has enough screenshots and output evidence.
9. Ask Codex to inspect the evidence folder, visual diff, packet, timeline, or local API.
10. Use the generated `comparison.md`, `visual-diff.md`, `timeline.md`, and `codex-packet.md` as diagnostic evidence indexes, then pair them with SUMO output files before making formal claims.

See [docs/codex-bridge.md](docs/codex-bridge.md) for exact prompts and API examples.

Useful endpoints:

```text
GET  /api/preflight
GET  /api/examples/minimal-paired
POST /api/examples/minimal-paired/run-headless
POST /api/examples/minimal-paired/run-guided
POST /api/examples/minimal-paired/launch-gui
POST /api/examples/minimal-paired/launch-guided-gui
POST /api/config/preflight
POST /api/outputs/inspect
POST /api/session/{id}/outputs/inspect
POST /api/session/create
POST /api/session/{id}/step
POST /api/session/{id}/run-until
POST /api/session/{id}/screenshot
POST /api/session/{id}/checkpoint/first
POST /api/session/{id}/checkpoint/template
GET  /api/session/{id}/state
GET  /api/session/{id}/evidence
GET  /api/session/{id}/artifact/{path}
POST /api/session/{id}/packet/export
POST /api/session/{id}/timeline/export
POST /api/session/{id}/visual-diff/export
POST /api/session/{id}/close
```

## Evidence Bundle

Each paired session creates:

```text
runs/<session_id>/
  manifest.json
  comparison.md
  codex-packet.md
  timeline.json
  timeline.md
  visual-diff.json
  visual-diff.md
  baseline/
    screenshots/
  variant/
    screenshots/
```

`comparison.md` is intentionally written for agent review. It records the paired screenshot checkpoints and reminds the agent not to treat GUI evidence as a formal performance claim.

The evidence API also returns an artifact list for every file in the session folder. Codex can use that list to decide which screenshots, Markdown notes, manifests, or future SUMO output files need inspection.

The web page renders PNG artifacts as screenshot previews through a session-scoped artifact endpoint. The endpoint serves files only from the active session folder; it is not a general local file browser.

`codex-packet.md` is a single Markdown entrypoint for agent review. It lists the session, artifacts, comparison notes, output inspection when available, and the claim boundary. It is an index over evidence, not an automatic scientific conclusion.

`timeline.md` aligns session creation, screenshot checkpoints, notes, output inspection, and exported Codex packets. This is the quickest way to see what evidence was produced before and after a controller or configuration change.

`visual-diff.md` pairs `before-change` and `after-change` screenshots and lists the four key views: baseline before, baseline after, variant before, and variant after. This is still diagnostic visual evidence; it does not replace output-based performance checks.

## Config Pair Preflight

Before opening SUMO GUI sessions, the sidecar can inspect the two `.sumocfg` files and report:

- missing `net-file`, `route-files`, `additional-files`, or other referenced input files;
- missing parent folders for declared SUMO outputs;
- declared output types such as `summary-output` and `tripinfo-output`;
- baseline/variant route or network mismatches;
- shared output paths that may overwrite one controller's results with another.

This is a construction check, not a scientific validity proof. A passing config preflight means the declared files are locally coherent enough to start visual inspection.

When `summary-output` or `tripinfo-output` paths are declared in the `.sumocfg` files, the web page can carry those paths into the Output Evidence panel so the user does not have to retype them.

## Output Evidence Inspection

The sidecar can inspect paired SUMO outputs:

- `summary.xml`: final loaded, inserted, arrived, running, waiting, teleports, and completion ratio;
- `tripinfo.xml`: arrived-vehicle count and mean duration, waiting time, and time loss.

Completion is reported before performance means. If one controller leaves more vehicles unfinished, the sidecar warns before comparing arrived-only averages.

If a paired session is active, output inspection is also written into the session evidence bundle:

```text
runs/<session_id>/
  output-inspection.json
  output-inspection.md
```

This lets Codex inspect the visual screenshots and completion-first output report from the same session folder.

## Architecture

```text
Browser UI
  -> FastAPI backend
  -> SessionManager
  -> TraCI adapters
  -> baseline sumo-gui / variant sumo-gui
```

Core logic is testable without opening SUMO GUI. The real adapter is isolated in `sumo_adapter.py`.

## Development

Run tests:

```powershell
.\.venv\Scripts\python -m pytest -q
```

The tests use fake SUMO adapters so they can run without launching a GUI.

## Roadmap

The MVP is a local visual sidecar. The next targets are:

- add real pixel-level image difference artifacts when screenshots are valid raster images;
- add user-authored timeline events that do not require screenshots.
