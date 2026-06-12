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

4. Use the web page to step both sessions, run both sessions, and capture paired screenshots.

5. Ask Codex to inspect the session folder:

   ```text
   Read runs/<session_id>/manifest.json and comparison.md.
   Tell me what visual differences are supported by the evidence, and what still needs SUMO output metrics.
   ```

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

Load the evidence:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/session/<session_id>/evidence
```

## Evidence Boundary

GUI screenshots are useful for noticing obvious changes, such as queue spillback, phase mismatch, deadlock, unexpected teleport patterns, or controller timing behavior.

They are not sufficient for performance claims. Travel time, delay, waiting time, throughput, emissions, completion rate, and controller comparisons still need paired SUMO output files, matching seeds, matching demand, and explicit metric definitions.

Use screenshot evidence as a diagnostic signal first. Promote it into a report only after it is paired with reproducible output data.
