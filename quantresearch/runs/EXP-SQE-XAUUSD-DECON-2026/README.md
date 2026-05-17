# Run bundle — EXP-SQE-XAUUSD-DECON-2026

This folder is the **research index** for the SQE-XAUUSD deconstruction experiment. **Canonical QuantLog + analytics artifacts** are stored under QuantOS:

```text
quantmetrics_os/runs/EXP-SQE-XAUUSD-DECON-2026-BASE/single/
quantmetrics_os/runs/EXP-SQE-XAUUSD-DECON-2026-V1/single/
quantmetrics_os/runs/EXP-SQE-XAUUSD-DECON-2026-V2/single/
quantmetrics_os/runs/EXP-SQE-XAUUSD-DECON-2026-V3/single/
quantmetrics_os/runs/EXP-SQE-XAUUSD-DECON-2026-V4/single/
quantmetrics_os/runs/EXP-SQE-XAUUSD-DECON-2026-V5/single/
```

Each `single/` directory typically contains:

- `quantlog_events.jsonl`
- `config_snapshot.yaml`, `resolved_config.yaml`
- `run_info.json`
- `analytics/*.txt`, `*.md`, `*.json` (bundled from QuantAnalytics when available)

Experiment metadata, **formal verdict:** `quantresearch/experiments/EXP-SQE-XAUUSD-DECON-2026/RUN_VERDICT.md`  
Dossier-index: `quantresearch/experiments/EXP-SQE-XAUUSD-DECON-2026/`.

Re-run matrix (from `quantbuild/`):

```powershell
$env:QUANTMETRICS_SUITE_ROOT = "<path-to-quantmetrics-suite>"
.\scripts\run_sqe_xauusd_decon_matrix.ps1
```
