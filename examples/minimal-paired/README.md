# Minimal Paired SUMO Example

This fixture is a public, private-data-free demo for SUMO Virtual Experiment Sidecar.

It contains:

```text
baseline.sumocfg
variant.sumocfg
grid.net.xml
demand.rou.xml
outputs/
  baseline/
  variant/
```

The baseline and variant intentionally use the same network and route demand. Their output paths are separated so the sidecar can demonstrate config preflight, paired GUI launch, and completion-first output inspection without implying a controller-performance comparison.

## Headless Smoke Run

From the repository root:

```powershell
sumo -c examples\minimal-paired\baseline.sumocfg
sumo -c examples\minimal-paired\variant.sumocfg
```

Expected generated files:

```text
examples/minimal-paired/outputs/baseline/summary.xml
examples/minimal-paired/outputs/baseline/tripinfo.xml
examples/minimal-paired/outputs/variant/summary.xml
examples/minimal-paired/outputs/variant/tripinfo.xml
```

Then inspect outputs through the sidecar API or web UI.

## Sidecar Demo Flow

1. Start the sidecar.
2. Run config preflight with `baseline.sumocfg` and `variant.sumocfg`.
3. Create a paired session to open two SUMO GUI windows.
4. Step or run both sessions.
5. Inspect the generated output XML files in the Output Evidence panel.

This is a construction and workflow demo. It is not evidence that one controller performs better than another.
