# Codex Bridge

SUMO Virtual Experiment Sidecar connects the Codex app to a local SUMO visual experiment through two plain interfaces: a localhost HTTP API and an evidence folder on disk.

It does not embed Codex inside SUMO, and it does not require VS Code. The user keeps the sidecar web page open, watches the paired SUMO GUI windows, and asks Codex to inspect or control the local sidecar when needed.

## Local Workflow

1. Run the sidecar:

   ```powershell
   .\.venv\Scripts\python -m sumo_sidecar
   ```

2. Open the local page:

   ```text
   http://127.0.0.1:8765
   ```

3. Enter two `.sumocfg` files:

   ```text
   baseline: fixed-time.sumocfg
   variant:  controller-change.sumocfg
   ```

4. Use the web page to load a scenario template if useful, start a scenario plan, step both sessions, run both sessions, capture paired screenshots, add timeline notes, and export visual evidence.

5. Refresh the workflow control screen:

   ```powershell
   Invoke-RestMethod http://127.0.0.1:8765/api/session/<session_id>/workflow/status
   ```

6. Ask Codex to inspect the session folder:

   ```text
   Read runs/<session_id>/manifest.json, scenario-plan.md, comparison.md, change-records.md, metric-comparison.md, metric-delta-chart.md, review-summary.md, timeline.md, visual-diff.md, output-inspection.md, and codex-packet.md if present.
   Tell me what visual differences are supported by the evidence, what output evidence exists, and what claims remain unsupported.
   ```

For the bundled public demo, the shortest end-to-end path is:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8765/api/examples/minimal-paired/launch-full-workflow-gui -Method Post
```

This runs the guided demo, launches a paired GUI session, starts a demo scenario plan, captures first and before/after checkpoints, adds a timeline note, exports visual diff, exports metric comparison, exports a metric chart, exports full and review timelines, exports a review summary, exports a Codex packet, and returns workflow status. It is a diagnostic workflow demonstration, not a controller-performance claim.

Before creating a session, Codex can also inspect the paired `.sumocfg` files:

Codex can generate a non-destructive variant config copy for one existing SUMO option:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8765/api/config/patch `
  -Method Post `
  -ContentType "application/json" `
  -Body '{
    "source_config": "C:\\path\\to\\baseline.sumocfg",
    "option": "step-length",
    "value": "0.5",
    "output_config": "C:\\path\\to\\variant-step-length.sumocfg"
  }'
```

This writes a new `.sumocfg` copy and refuses to overwrite the source config or an explicitly named existing output file. It only updates an existing SUMO option in the config file. It does not edit route files, controller scripts, TLS phases, or detector definitions.

The web UI also has `Patch Config From Scenario`. It uses the current Scenario Guide `parameter` and `after value` as the config-patch request, then synchronizes the structured change fields. This is a convenience bridge from plan to construction, not evidence that the experiment has been run.

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8765/api/config/preflight `
  -Method Post `
  -ContentType "application/json" `
  -Body '{
    "baseline_config": "C:\\path\\to\\baseline.sumocfg",
    "variant_config": "C:\\path\\to\\variant.sumocfg"
  }'
```

Use this to catch missing input files, missing output folders, mismatched route files, and shared output paths before opening SUMO GUI windows.

After a run, Codex can inspect paired SUMO output evidence:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8765/api/outputs/inspect `
  -Method Post `
  -ContentType "application/json" `
  -Body '{
    "baseline_summary": "C:\\path\\to\\baseline-summary.xml",
    "baseline_tripinfo": "C:\\path\\to\\baseline-tripinfo.xml",
    "variant_summary": "C:\\path\\to\\variant-summary.xml",
    "variant_tripinfo": "C:\\path\\to\\variant-tripinfo.xml"
  }'
```

The output inspection report follows the completion-first rule: check arrived, running, waiting-for-insertion, and teleports before interpreting travel-time or waiting-time averages.

When a sidecar session is active, prefer the session-scoped endpoint so the report is persisted into the evidence bundle:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8765/api/session/<session_id>/outputs/inspect `
  -Method Post `
  -ContentType "application/json" `
  -Body '{
    "baseline_summary": "C:\\path\\to\\baseline-summary.xml",
    "baseline_tripinfo": "C:\\path\\to\\baseline-tripinfo.xml",
    "variant_summary": "C:\\path\\to\\variant-summary.xml",
    "variant_tripinfo": "C:\\path\\to\\variant-tripinfo.xml"
  }'
```

This writes `output-inspection.json` and `output-inspection.md` into `runs/<session_id>/`.

## API Workflow

Codex can call the local API from the same machine:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/preflight
```

Create a session:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8765/api/session/create `
  -Method Post `
  -ContentType "application/json" `
  -Body '{
    "name": "queue-policy-check",
    "baseline_config": "C:\\path\\to\\baseline.sumocfg",
    "variant_config": "C:\\path\\to\\variant.sumocfg",
    "start": true
  }'
```

Start a guided before/after scenario before interpreting a parameter change:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/scenario/templates
```

This returns reusable template records for common scenario-plan forms. Templates are prefill helpers only: they do not edit SUMO files, run simulations, or prove that a change was applied.

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8765/api/session/<session_id>/scenario/plan `
  -Method Post `
  -ContentType "application/json" `
  -Body '{
    "label": "max-green-scenario",
    "parameter": "max_green",
    "before_value": "30",
    "after_value": "45",
    "hypothesis": "Longer green should reduce duration if completion remains unchanged.",
    "expected_metrics": ["completion_ratio", "mean_duration"],
    "note": "Use before-change and after-change screenshots around the parameter edit."
  }'
```

This writes `scenario-plan.json` and `scenario-plan.md`. It also returns `scenario_status`, which tells the next evidence step. Refresh it during the run:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/session/<session_id>/scenario/status
```

Capture a checkpoint:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8765/api/session/<session_id>/screenshot `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"label": "before-after-queue"}'
```

Capture a named before/after checkpoint:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8765/api/session/<session_id>/checkpoint/template `
  -Method Post `
  -ContentType "application/json" `
  -Body '{
    "template": "before-change",
    "note": "Before changing max green from 30 to 45 seconds."
  }'
```

Record a timeline note without taking a screenshot:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8765/api/session/<session_id>/timeline/note `
  -Method Post `
  -ContentType "application/json" `
  -Body '{
    "label": "parameter-change",
    "note": "Changed max green from 30 to 45 seconds."
  }'
```

Record the structured change that should connect before/after checkpoints to output evidence:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8765/api/session/<session_id>/change/record `
  -Method Post `
  -ContentType "application/json" `
  -Body '{
    "label": "max-green-change",
    "parameter": "max_green",
    "before_value": "30",
    "after_value": "45",
    "rationale": "Allow longer discharge after queue build-up.",
    "note": "Pair this with before-change and after-change screenshots."
  }'
```

This writes `change-records.json` and `change-records.md` into the evidence bundle and adds a `change-record` event to exported timelines.

Export the completion-first metric comparison after output inspection:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8765/api/session/<session_id>/metrics/compare -Method Post
```

This writes `metric-comparison.json` and `metric-comparison.md`. It compares persisted baseline and variant output evidence as `variant - baseline`, with completion, unfinished vehicles, and teleports reported before tripinfo means.

Export a visual metric-delta chart from the comparison:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8765/api/session/<session_id>/metrics/chart -Method Post
```

This writes `metric-delta-chart.svg` and `metric-delta-chart.md`. The chart uses the same `variant - baseline` definition and keeps the numeric deltas visible. The bar lengths are scaled within this artifact, so they are useful for visual scanning but not for cross-unit interpretation by themselves.

Load the evidence:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/session/<session_id>/evidence
```

The response includes:

```text
session_dir
manifest
comparison_markdown
artifacts
```

`artifacts` lists all files currently stored in the session folder, including screenshot files and any SUMO outputs later copied or generated there.

Export visual and agent-readable evidence:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8765/api/session/<session_id>/visual-diff/export -Method Post
Invoke-RestMethod -Uri http://127.0.0.1:8765/api/session/<session_id>/metrics/compare -Method Post
Invoke-RestMethod -Uri http://127.0.0.1:8765/api/session/<session_id>/metrics/chart -Method Post
Invoke-RestMethod -Uri http://127.0.0.1:8765/api/session/<session_id>/timeline/export -Method Post
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/session/<session_id>/timeline/export?preset=visual" -Method Post
Invoke-RestMethod -Uri http://127.0.0.1:8765/api/session/<session_id>/review/summary -Method Post
Invoke-RestMethod -Uri http://127.0.0.1:8765/api/session/<session_id>/packet/export -Method Post
```

Timeline presets:

```text
full     all events, written to timeline.md/json
review   high-signal review events
visual   screenshot checkpoints and visual diff events
outputs  output-inspection, metric-comparison, and metric-chart events
notes    scenario plan and user-authored timeline notes
```

Export a compact review summary when the session has enough evidence for Codex or Claude to inspect:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8765/api/session/<session_id>/review/summary -Method Post
```

This writes `review-summary.json` and `review-summary.md`. The summary links structured change records, output inspection, completion-first metric highlights, metric chart status, visual diff status, timeline status, packet status, next actions, and the current claim boundary. It is a dashboard over existing evidence, not a new validity proof.

Check workflow status before asking Codex for review:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/session/<session_id>/workflow/status
```

The status response contains a checklist and next actions. Treat `review-ready` as "ready for agent review", not as proof that the experiment is scientifically valid.

## Evidence Boundary

GUI screenshots are useful for noticing obvious changes, such as queue spillback, phase mismatch, deadlock, unexpected teleport patterns, or controller timing behavior.

They are not sufficient for performance claims. Travel time, delay, waiting time, throughput, emissions, completion rate, and controller comparisons still need paired SUMO output files, matching seeds, matching demand, and explicit metric definitions.

Use screenshot evidence as a diagnostic signal first. Promote it into a report only after it is paired with reproducible output data.

Pixel-level visual diff artifacts are also diagnostic. They can show that pixels changed between before/after screenshots, but they do not explain why the change happened and do not replace SUMO output metrics.

Structured change records close part of that gap by recording what was intentionally changed, but they still do not prove causality. They should be read together with paired outputs, completion status, and reproduced runs.

Scenario plans make the before/after workflow explicit before evidence is interpreted. They are planning artifacts only; still verify that the planned change was actually applied and recorded.

Scenario templates are even lighter than scenario plans. They only provide reusable starting values for a plan. Keep the claim boundary at `diagnostic-demo` until the scenario is started, the intended change is recorded, paired visual checkpoints are captured, outputs are inspected, and completion-first metrics are reviewed.

Config patch generation is also construction support, not evidence. Treat the returned `.sumocfg` path as a candidate variant config, then run config-pair preflight and preserve paired outputs before interpreting behavior.

Patch-from-scenario is the same construction boundary with fewer manual fields. It links the plan form to the config-copy helper, but the generated config still needs preflight, paired GUI/output evidence, and a recorded structured change.

Metric comparison makes output deltas easier to review, but it is still an evidence view. If completion, route demand, seed, horizon, or controller identity is unpaired, metric deltas should remain diagnostic rather than formal claims.

Metric charts make those deltas easier to scan, but they do not define improvement. Compare the numeric values, units, completion status, and metric definitions before interpreting the bars.

Review summary makes the evidence easier to enter, but it is still an index. If the underlying evidence is incomplete or unpaired, the summary should preserve that limitation instead of upgrading the claim.
