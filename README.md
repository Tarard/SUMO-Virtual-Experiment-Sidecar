# SUMO Virtual Experiment Sidecar

Local web sidecar for paired visual feedback in Eclipse SUMO/TraCI experiments.

This project starts two paired `sumo-gui` sessions, controls them through TraCI, captures synchronized screenshots, and writes Codex-readable evidence bundles. It is designed to complement a Codex/Claude workflow: the local app runs and records the visual experiment, while Codex reads the evidence folder and helps interpret what changed.

## Current Scope

MVP focus:

- launch baseline and variant `sumo-gui` sessions;
- keep runs paired by configuration, command, and evidence folder;
- generate non-destructive `.sumocfg` copies for simple SUMO option changes;
- bridge Scenario Guide fields into safe config-copy requests;
- step or run both sessions from a local web page;
- capture paired screenshots from the SUMO GUI view;
- capture a fixed first visual checkpoint into the evidence bundle;
- capture named `before-change`, `after-change`, `queue-build-up`, and `final-state` checkpoints with notes;
- load reusable scenario templates for common SUMO/TraCI before/after checks;
- guide before/after parameter-change scenarios with `scenario-plan.md` and next-step status;
- record user-authored timeline notes without taking screenshots;
- record structured parameter/controller changes with before value, after value, and rationale;
- record human visual observations from the SUMO GUI or visual-diff matrix;
- load a visual-observation taxonomy for queue growth, spillback, phase mismatch, insertion/teleport symptoms, density change, deadlock/gridlock, and route/demand mismatch clues;
- export completion-first metric comparisons from persisted paired SUMO outputs;
- export metric-delta SVG charts from completion-first comparisons;
- export a before/after visual-diff matrix for paired template checkpoints;
- generate pixel-level visual-diff PNGs when before/after screenshots are valid raster images;
- report workflow status and next actions for the active evidence bundle;
- report comparison readiness for before/after Codex review;
- export timeline presets for full, review, visual, output, or note-focused evidence review;
- export a compact review summary that links changes, metric deltas, visual diff status, and claim boundaries;
- export a copyable Codex/Claude review prompt for the active evidence bundle;
- export a next-action review that turns current evidence gaps into the next Sidecar operation;
- run a bundled full workflow demo that produces a review-ready evidence bundle;
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

Use `Create Config Patch` when you need a quick variant `.sumocfg` from a baseline config. It updates one existing SUMO option in an output copy and refuses to overwrite the source config or an explicitly named existing output file. Run config-pair preflight before launching the paired GUI session.

Use `Launch Demo GUI` to open the same bundled baseline and variant as a paired SUMO GUI session. This starts two `sumo-gui` windows.

Use `Launch Guided GUI` to run the guided demo first, then open a paired GUI session with the output inspection report already written into the session evidence bundle.

Use `Launch Full Workflow` to run the guided demo, open the paired GUI session, start a demo scenario plan, capture first and before/after checkpoints, add a timeline note, export visual diff, export metric comparison, export a metric chart, export full and review timelines, export a review summary, export a Codex packet, export a next-action review, export an agent review prompt, and return a review-ready workflow status. This is the shortest public demonstration of the full evidence loop.

Use `Load Template` in the Scenario Guide to prefill a common scenario such as signal timing, detector mapping, demand stress, controller weight, or output alignment. Templates only fill the scenario form. They do not edit SUMO files, launch runs, or prove that the planned change was applied.

Use `Patch Config From Scenario` to turn the current scenario parameter and after-value into a safe config-copy request. It uses the source config from the Construction Preflight panel, or the baseline config if no source patch config is set, then runs config-pair preflight on the baseline/generated variant pair.

Use `Record Scenario Change` after a paired session exists to write the Scenario Guide parameter, before value, after value, and hypothesis into `change-records.md`.

Use `Start Scenario` before a manual before/after comparison. It writes `scenario-plan.json` and `scenario-plan.md`, records the planned parameter, before value, after value, hypothesis, expected metrics, and then tells you the next evidence step.

Use `Refresh Scenario` during the run to see the current guided step. The scenario guide advances as first checkpoint, before-change checkpoint, change record, after-change checkpoint, output inspection, metric comparison, metric chart, visual diff, timeline, review summary, and Codex packet become available.

After a GUI session is active, use `Capture First Checkpoint` to write the first paired visual checkpoint and refresh the Codex evidence panel immediately.

Use `Capture Template Checkpoint` for before/after work. The built-in templates are `before-change`, `after-change`, `queue-build-up`, and `final-state`. The optional note is written into `comparison.md` and `timeline.md`.

Use `Add Timeline Note` to record parameter changes, observations, or assumptions without taking another screenshot.

Use `Record Change` when you want Codex to know exactly what changed between two checkpoints. Record the parameter or controller element, before value, after value, and rationale before interpreting visual or metric differences.

Use `Record Visual Observation` after looking at the SUMO GUI or the visual-diff matrix. Record what you saw, which artifact supports it, and how confident you are. This helps Codex connect human visual inspection to the evidence bundle without treating the observation as proof.

Use `Load Observation Types` before recording a visual observation when you want guided labels and evidence checks. The taxonomy helps classify observations such as queue growth, spillback, phase mismatch, insertion/teleport symptoms, density change, deadlock/gridlock, or route/demand mismatch suspicion. It is not automatic image understanding.

Use `Compare Metrics` after output inspection. It exports a completion-first baseline/variant/delta table from `output-inspection.json`, with completion and unfinished-vehicle evidence placed before tripinfo means.

Use `Export Metric Chart` after metric comparison. It writes `metric-delta-chart.svg` and `metric-delta-chart.md`, making signs and relative magnitudes easier to inspect while keeping the actual delta values visible.

Use `Export Review Summary` when the evidence bundle is ready for agent review. It creates a compact dashboard over structured changes, output inspection, metric comparison, visual diff, timeline, packet status, and the current claim boundary.

Use `Export Agent Prompt` when you want a copyable Codex/Claude instruction that points the agent to the session folder, readiness status, review artifacts, next actions, and claim boundary. This is the bridge for using the Sidecar from the standalone Codex app.

Use `Export Next Action Review` when you want the Sidecar to convert the current evidence gaps into a concrete next operation. It writes `next-action-review.json` and `next-action-review.md`. If visual observations use a known taxonomy type, the review also lists missing evidence targets, suggested checks, and claim boundaries for those observations. It is a diagnostic control screen, not a claim generator.

Use `Export Visual Diff` after capturing at least one `before-change` and one `after-change` checkpoint. It builds a Baseline/Variant by Before/After/Diff matrix for direct visual inspection. When screenshots are valid raster images with matching dimensions, it also writes pixel-level diff PNGs and reports changed-pixel ratios for each row.

Use `Refresh Workflow` to see which evidence steps are complete, which are missing, and what should happen next before asking Codex to review the session.

Use `Check Compare Readiness` to see whether the active session has the core before/after evidence needed for diagnostic comparison: scenario plan, first checkpoint, before/after checkpoints, change record, output inspection, metric comparison, and visual diff. It will still recommend metric chart, timeline, review summary, and Codex packet before final agent review.

Use the `Timeline preset` selector before `Export Timeline` when a session is long. Presets include `full`, `review`, `visual`, `outputs`, and `notes`.

## Codex Bridge

Codex can interact with the sidecar in two ways:

1. HTTP API on `127.0.0.1:8765`.
2. Evidence folders under `runs/<session_id>/`.
3. Artifact listings returned by `/api/session/{id}/evidence`.
4. Session-scoped artifact files returned by `/api/session/{id}/artifact/{path}`.
5. A single Codex-readable packet written by `/api/session/{id}/packet/export`.
6. A run timeline written by `/api/session/{id}/timeline/export`.
7. A compact review dashboard written by `/api/session/{id}/review/summary`.
8. A copyable agent prompt written by `/api/session/{id}/agent-review-prompt/export`.
9. A next-action control screen written by `/api/session/{id}/next-action-review/export`.

This is intentionally not a VS Code extension. The bridge is designed for the Codex app or any local agent that can call localhost APIs and read files from the same machine.

Typical workflow:

1. Start this sidecar locally.
2. Run environment preflight and config-pair preflight.
3. Optionally generate a variant `.sumocfg` with Create Config Patch or Patch Config From Scenario, then review config-pair preflight.
4. Create a paired baseline/variant session in the web page.
5. Optionally load a scenario template, then start a scenario plan before the manual before/after comparison.
6. Capture the first paired checkpoint, then capture named before/after checkpoints while watching the SUMO GUI windows.
7. Add timeline notes when you change parameters, observe a behavior, or record an assumption.
8. Record structured changes, or use Record Scenario Change, so Codex can connect what changed to visual checkpoints and output metrics.
9. Record visual observations when you notice queue growth, spillback, phase mismatch, deadlock, or other GUI-visible behavior.
10. Inspect `summary.xml` and `tripinfo.xml` output evidence before interpreting performance metrics.
11. Export metric comparison so completion status and tripinfo deltas are visible together.
12. Export a metric chart so the metric deltas are visible as an artifact.
13. Export the visual diff index for the paired before/after checkpoints.
14. Export a run timeline, optionally with a preset, to align scenario plan, checkpoints, change records, visual observations, metric comparison, chart, notes, output inspection, and packet evidence.
15. Export a review summary to create the compact review dashboard.
16. Export a Codex packet when the session has enough screenshots and output evidence.
17. Export an agent review prompt and paste it into Codex or Claude.
18. Refresh scenario/workflow status, check comparison readiness, and follow remaining next actions.
19. Ask Codex to inspect the evidence folder, scenario plan, review summary, metric chart, metric comparison, visual observations, visual diff, packet, timeline, workflow status, agent prompt, or local API.
20. Use the generated `scenario-plan.md`, `comparison.md`, `change-records.md`, `visual-observations.md`, `metric-comparison.md`, `metric-delta-chart.md`, `visual-diff.md`, `timeline.md`, `review-summary.md`, `codex-packet.md`, and `agent-review-prompt.md` as diagnostic evidence indexes, then pair them with SUMO output files before making formal claims.

See [docs/codex-bridge.md](docs/codex-bridge.md) for exact prompts and API examples.

Useful endpoints:

```text
GET  /api/preflight
GET  /api/scenario/templates
GET  /api/examples/minimal-paired
POST /api/examples/minimal-paired/run-headless
POST /api/examples/minimal-paired/run-guided
POST /api/examples/minimal-paired/launch-gui
POST /api/examples/minimal-paired/launch-guided-gui
POST /api/examples/minimal-paired/launch-full-workflow-gui
POST /api/config/patch
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
GET  /api/session/{id}/workflow/status
GET  /api/session/{id}/comparison/readiness
GET  /api/session/{id}/evidence
GET  /api/session/{id}/artifact/{path}
POST /api/session/{id}/packet/export
POST /api/session/{id}/timeline/export?preset=full
POST /api/session/{id}/timeline/note
POST /api/session/{id}/scenario/plan
GET  /api/session/{id}/scenario/status
POST /api/session/{id}/change/record
GET  /api/visual-observation/taxonomy
POST /api/session/{id}/visual-observation/record
POST /api/session/{id}/metrics/compare
POST /api/session/{id}/metrics/chart
POST /api/session/{id}/review/summary
POST /api/session/{id}/agent-review-prompt/export
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
  scenario-plan.json
  scenario-plan.md
  change-records.json
  change-records.md
  visual-observations.json
  visual-observations.md
  next-action-review.json
  next-action-review.md
  metric-comparison.json
  metric-comparison.md
  metric-delta-chart.svg
  metric-delta-chart.md
  review-summary.json
  review-summary.md
  agent-review-prompt.json
  agent-review-prompt.md
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

`scenario-plan.md` records the intended before/after comparison before the evidence is interpreted. It lists the planned parameter change, hypothesis, expected metrics, required evidence sequence, and claim boundary. It is a plan, not proof that the change was applied.

Scenario templates prefill `scenario-plan.md` inputs for common workflows. They are reusable prompts for planning, not executable SUMO patches and not evidence.

`change-records.md` records structured edits such as controller parameters, detector mappings, route settings, or experiment assumptions with before value, after value, and rationale. It is the link between "what changed" and the visual/output evidence.

`visual-observations.md` records what the user noticed in the SUMO GUI or visual-diff matrix, such as queue growth, spillback, phase mismatch, deadlock, or density changes. When a known observation type is used, it also stores taxonomy guidance with evidence targets, suggested checks, next actions, and a claim boundary. It is a diagnostic annotation that should be checked against paired outputs before being used in a claim.

`next-action-review.md` turns the current evidence state into a concrete next Sidecar operation. It also uses visual-observation taxonomy guidance when available, so a `spillback` or `phase-mismatch` note can point to the missing output, timeline, change-record, or controller evidence that should be checked next. It is a diagnostic control screen, not a claim generator.

`metric-comparison.md` compares persisted baseline and variant output evidence using completion-first ordering. It reports loaded, inserted, arrived, running, waiting, teleports, and completion ratio before tripinfo means such as duration, waiting time, and time loss.

`metric-delta-chart.svg` visualizes the numeric deltas from `metric-comparison.json`. The chart uses `variant - baseline`, shows the actual delta values, and scales bars only within the artifact. It is a visual index, not a claim that a larger bar is better.

`review-summary.md` is the compact dashboard for agent review. It links structured changes, output inspection, completion-first metric highlights, metric chart status, visual diff status, timeline status, packet status, and the current claim boundary. It does not re-run SUMO or certify causality.

`agent-review-prompt.md` is the copy-paste bridge into Codex or Claude. It tells the agent which artifacts to open, what readiness and claim status apply, what next actions are suggested, and what claims are prohibited. It is a prompt wrapper over existing evidence, not new evidence.

`comparison/readiness` is a status gate, not an artifact. It reports `needs-evidence`, `ready-to-compare`, or `ready-for-agent-review` based on the current session evidence. `ready-to-compare` means diagnostic before/after review is possible; it does not certify causality, controller performance, or publishable validity.

`timeline.md` aligns session creation, scenario plan, screenshot checkpoints, user notes, structured change records, output inspection, metric comparison, visual diffs, and exported Codex packets. This is the quickest way to see what evidence was produced before and after a controller or configuration change.

Timeline presets write separate files such as `timeline-visual.md`, `timeline-outputs.md`, and `timeline-notes.md`. The default `full` preset keeps the existing `timeline.md` / `timeline.json` names. The `review` preset includes metric comparison, metric chart, structured change records, visual diff, Codex packet, and review summary; the `outputs` preset includes output inspection, metric comparison, and metric chart.

`visual-diff.md` pairs `before-change` and `after-change` screenshots and lists a visual comparison matrix: Baseline before, Baseline after, Baseline pixel diff, Variant before, Variant after, and Variant pixel diff. This is still diagnostic visual evidence; it does not replace output-based performance checks.

When possible, the sidecar also writes pixel-level diff artifacts under `visual-diff/`. White pixels indicate changed pixels and black pixels indicate unchanged pixels. The matrix reports changed-pixel counts and ratios for quick screening. If screenshots are not valid raster images, or if image dimensions differ, the export remains available as an index and records the pixel-diff warning instead of failing.

## Config Pair Preflight

`Create Config Patch` can generate a variant `.sumocfg` copy before session creation. It updates one existing SUMO option, writes an output config, and refuses to overwrite the source config or an explicitly named existing output file. It is useful for quick checks such as `step-length`, `begin`, `end`, or other existing `.sumocfg` options.

`Patch Config From Scenario` uses the Scenario Guide fields as the patch request: `parameter` becomes the SUMO option and `after value` becomes the new value. It also synchronizes the structured change fields and immediately runs config-pair preflight so the generated variant config is checked before a paired GUI session is created.

`Record Scenario Change` writes the same Scenario Guide fields into the active session's structured change records. It is still metadata about the intended/applied construction change, not proof that the simulation outcome is valid.

This helper does not edit controller scripts, route files, TLS logic, or detector definitions. It is a construction helper only. After creating the copy, run config-pair preflight and keep the run at diagnostic status until paired output and completion evidence exist.

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

- connect scenario plans/templates directly to safe config-patch suggestions and change records.
