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

4. Use the web page to step both sessions, run both sessions, capture paired screenshots, add timeline notes, and export visual evidence.

5. Refresh the workflow control screen:

   ```powershell
   Invoke-RestMethod http://127.0.0.1:8765/api/session/<session_id>/workflow/status
   ```

6. Ask Codex to inspect the session folder:

   ```text
   Read runs/<session_id>/manifest.json, comparison.md, timeline.md, visual-diff.md, output-inspection.md, and codex-packet.md if present.
   Tell me what visual differences are supported by the evidence, what output evidence exists, and what claims remain unsupported.
   ```

Before creating a session, Codex can also inspect the paired `.sumocfg` files:

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
Invoke-RestMethod -Uri http://127.0.0.1:8765/api/session/<session_id>/timeline/export -Method Post
Invoke-RestMethod -Uri http://127.0.0.1:8765/api/session/<session_id>/packet/export -Method Post
```

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
