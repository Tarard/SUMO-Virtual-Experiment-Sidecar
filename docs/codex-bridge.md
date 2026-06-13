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
   Read runs/<session_id>/agent-review-prompt.md if present. If it is missing, read manifest.json, scenario-plan.md, comparison.md, change-records.md, visual-observations.md, metric-comparison.md, metric-delta-chart.md, review-summary.md, timeline.md, visual-diff.md, output-inspection.md, and codex-packet.md if present.
   Tell me what visual differences are supported by the evidence, what output evidence exists, and what claims remain unsupported.
   ```

For the bundled public demo, the shortest end-to-end path is:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8765/api/examples/minimal-paired/launch-full-workflow-gui -Method Post
```

This runs the guided demo, launches a paired GUI session, starts a demo scenario plan, captures first and before/after checkpoints, adds a timeline note, exports visual diff, exports metric comparison, exports a metric chart, exports full and review timelines, exports a review summary, exports a Codex packet, exports a next-action review, exports an agent review prompt, and returns workflow status. It is a diagnostic workflow demonstration, not a controller-performance claim.

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

The web UI also has `Patch Config From Scenario`. It uses the current Scenario Guide `parameter` and `after value` as the config-patch request, synchronizes the structured change fields, and immediately runs config-pair preflight on the baseline/generated-variant pair. This is a convenience bridge from plan to construction, not evidence that the experiment has been run.

After a paired session exists, `Record Scenario Change` writes the Scenario Guide fields into `change-records.md` through the same `/change/record` endpoint used by the manual change form.

Before recording a visual observation, Codex can inspect the public observation taxonomy:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/visual-observation/taxonomy
```

Use it to choose labels such as `queue-growth`, `spillback`, `phase-mismatch`, `insertion-teleport`, `density-change`, `deadlock-gridlock`, or `route-demand-mismatch`. These labels guide evidence checks; they are not automatic image understanding and do not prove a traffic mechanism.

After looking at the GUI or visual-diff matrix, record a human visual observation:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8765/api/session/<session_id>/visual-observation/record `
  -Method Post `
  -ContentType "application/json" `
  -Body '{
    "label": "queue-growth-eastbound",
    "observation_type": "queue-growth",
    "evidence_artifact": "visual-diff.md",
    "confidence": "diagnostic",
    "comparison_role": "variant",
    "visual_view": "after",
    "location": "eastbound approach near the stop line",
    "movement": "eastbound through",
    "link_or_lane": "edge or lane id if known",
    "visual_anchor": "visual-diff matrix, variant after cell, queue near the stop line",
    "note": "Variant appears to keep a longer eastbound queue after the change."
  }'
```

This writes `visual-observations.json` and `visual-observations.md`. Optional anchor fields tell Codex where to look in the paired evidence. Treat these observations as human annotations over visual evidence, not as formal output evidence.

For the fastest human-in-the-loop path, use the guided endpoint after a GUI observation:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8765/api/session/<session_id>/visual-observation/guided-record `
  -Method Post `
  -ContentType "application/json" `
  -Body '{
    "label": "possible-spillback",
    "observation_type": "spillback",
    "evidence_artifact": "visual-diff.md",
    "confidence": "diagnostic",
    "comparison_role": "variant",
    "visual_view": "after",
    "visual_anchor": "variant / after cell in the visual-diff matrix",
    "note": "The downstream queue appears to block the upstream approach."
  }'
```

This records the observation, exports `timeline-visual.md`, exports `next-action-review.md`, and refreshes `agent-review-prompt.md` in one call. Use it when the user has just noticed a visual difference and wants Codex to move directly to the next evidence check.

After evidence has accumulated, export the next-action review:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8765/api/session/<session_id>/next-action-review/export `
  -Method Post
```

This writes `next-action-review.json` and `next-action-review.md`. It reads comparison readiness, workflow status, visual observations, and exported artifacts, then suggests the next Sidecar operation. Treat it as a diagnostic control screen, not as an experiment conclusion.

When visual observations use known taxonomy labels, `next-action-review.md` also reports missing evidence targets and checks for those observations. For example, a `spillback` note can point Codex back to `output-inspection.md`, `timeline.md`, and completion/teleport checks before any mechanism claim is discussed.

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
Invoke-RestMethod -Uri http://127.0.0.1:8765/api/session/<session_id>/agent-review-prompt/export -Method Post
```

The visual-diff response includes a `matrix` for each before/after pair. Each matrix has one Baseline row and one Variant row, with Before, After, and Pixel diff artifacts plus changed-pixel counts and ratios. Use it for quick visual screening before asking Codex to inspect the full evidence bundle.

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

Export a copyable agent review prompt for the standalone Codex or Claude app:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8765/api/session/<session_id>/agent-review-prompt/export -Method Post
```

This writes `agent-review-prompt.json` and `agent-review-prompt.md`. Paste the Markdown prompt into Codex or Claude when you want the agent to inspect the current Sidecar evidence folder. The prompt includes the session folder, artifacts to open, readiness status, next actions, and the claim boundary.

After Codex or Claude replies, paste the response back into the Sidecar:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8765/api/session/<session_id>/agent-feedback/record `
  -Method Post `
  -ContentType "application/json" `
  -Body '{
    "label": "codex-output-check",
    "source_agent": "Codex",
    "prompt_artifact": "agent-review-prompt.md",
    "response_text": "Inspect output-inspection.md before making any performance claim.",
    "recommended_action": "Inspect Outputs",
    "claim_boundary": "Treat the current review as diagnostic only."
  }'
```

This writes `agent-feedback.json` and `agent-feedback.md`, adds the feedback to review timelines, and surfaces it in `review-summary.md`. It preserves the review loop; it does not make the agent response a validation result.

Turn the latest recorded feedback into a manual-only action plan:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8765/api/session/<session_id>/agent-action-plan/export -Method Post
```

This writes `agent-action-plan.json` and `agent-action-plan.md`. The plan maps the latest `recommended_action` to a likely Sidecar evidence target and repeats the manual execution boundary. It does not execute the action or validate the agent recommendation.

After manually following, skipping, or blocking the plan, record the outcome:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8765/api/session/<session_id>/agent-action-outcome/record `
  -Method Post `
  -ContentType "application/json" `
  -Body '{
    "label": "inspect-outputs-completed",
    "action_plan_artifact": "agent-action-plan.md",
    "action": "Inspect Outputs",
    "outcome_status": "completed",
    "evidence_artifact": "output-inspection.md",
    "note": "Output inspection was run and completion evidence is now available."
  }'
```

This writes `agent-action-outcomes.json` and `agent-action-outcomes.md`, adds the outcome to review timelines, and surfaces it in `review-summary.md`. It records manual workflow execution; it is not proof that the experiment or agent recommendation is valid.

Export a compact control-loop review when you want to see the whole bridge state in one artifact:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8765/api/session/<session_id>/agent-loop-review/export -Method Post
```

This writes `agent-loop-review.json` and `agent-loop-review.md`. The review summarizes `prompt -> feedback -> action plan -> outcome`, identifies the next missing bridge step, lists artifacts to open, and repeats the claim boundary. It is a workflow dashboard, not a validation result.

Export the top-level experiment state board when you want one compact view of visual evidence, metric evidence, agent-loop status, and claim-gate status:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8765/api/session/<session_id>/experiment-state-board/export -Method Post
```

This writes `experiment-state-board.json` and `experiment-state-board.md`. The board groups the session into four lanes: visual comparison, metric evidence, agent loop, and claim gate. The web page renders the same lanes with embedded before/after/diff thumbnails, the metric delta chart, key metric deltas, agent-loop steps, and claim-gate readiness. After the board is exported once, the web UI refreshes it after key evidence updates such as metric comparison, metric chart, visual diff, guided visual observation, and agent action outcome records. Use it as the first artifact to inspect before opening deeper files. It is still an evidence control panel, not a validity certificate.

In the web UI, `Enable Live Board` exports the board and activates that guarded refresh behavior for the current session. It does not create new scientific evidence; it keeps the existing evidence index current.

Check workflow status before asking Codex for review:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/session/<session_id>/workflow/status
```

The status response contains a checklist and next actions. Treat `review-ready` as "ready for agent review", not as proof that the experiment is scientifically valid.

Check whether the session has enough core evidence for before/after comparison:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/session/<session_id>/comparison/readiness
```

The readiness response focuses on the comparison gate: scenario plan, first checkpoint, before/after checkpoints, structured change record, output inspection, metric comparison, and visual diff. If these are present it returns `ready-to-compare`; it still recommends metric chart, timeline, review summary, and Codex packet before final agent review.

## Evidence Boundary

GUI screenshots are useful for noticing obvious changes, such as queue spillback, phase mismatch, deadlock, unexpected teleport patterns, or controller timing behavior.

They are not sufficient for performance claims. Travel time, delay, waiting time, throughput, emissions, completion rate, and controller comparisons still need paired SUMO output files, matching seeds, matching demand, and explicit metric definitions.

Use screenshot evidence as a diagnostic signal first. Promote it into a report only after it is paired with reproducible output data.

Pixel-level visual diff artifacts and visual comparison matrices are also diagnostic. They can show that pixels changed between before/after screenshots, but they do not explain why the change happened and do not replace SUMO output metrics.

Structured change records close part of that gap by recording what was intentionally changed, but they still do not prove causality. They should be read together with paired outputs, completion status, and reproduced runs.

Visual observations are also annotations. They help connect GUI inspection to evidence artifacts, but they do not prove why a pattern occurred.

Scenario plans make the before/after workflow explicit before evidence is interpreted. They are planning artifacts only; still verify that the planned change was actually applied and recorded.

Scenario templates are even lighter than scenario plans. They only provide reusable starting values for a plan. Keep the claim boundary at `diagnostic-demo` until the scenario is started, the intended change is recorded, paired visual checkpoints are captured, outputs are inspected, and completion-first metrics are reviewed.

Config patch generation is also construction support, not evidence. Treat the returned `.sumocfg` path as a candidate variant config, then run config-pair preflight and preserve paired outputs before interpreting behavior.

Patch-from-scenario is the same construction boundary with fewer manual fields. It links the plan form to the config-copy helper and runs config-pair preflight, but the generated config still needs paired GUI/output evidence and a recorded structured change.

Record-scenario-change closes the metadata loop by recording the planned/applied change in the session evidence bundle. It does not prove causality or controller performance.

Metric comparison makes output deltas easier to review, but it is still an evidence view. If completion, route demand, seed, horizon, or controller identity is unpaired, metric deltas should remain diagnostic rather than formal claims.

Metric charts make those deltas easier to scan, but they do not define improvement. Compare the numeric values, units, completion status, and metric definitions before interpreting the bars.

Review summary makes the evidence easier to enter, but it is still an index. If the underlying evidence is incomplete or unpaired, the summary should preserve that limitation instead of upgrading the claim.

Comparison readiness is also a status gate, not a validity certificate. `ready-to-compare` means there is enough diagnostic evidence for a before/after review, not that a performance claim is true.
