# Experiment plan — EXP-SQE-XAUUSD-DECON-2026

## Configs (QuantBuild)

| Role | File | Interventie |
|------|------|-------------|
| BASE | `quantbuild/configs/experiments/sqe_xauusd_deconstruct_2026/BASE.yaml` | `extends` A0_BASELINE + quantlog consolidated + artifacts |
| V1 | `V1_h1_gate_off.yaml` | `structure_use_h1_gate: false` |
| V2 | `V2_combo_min_3.yaml` | `entry_sweep_disp_fvg_min_count: 3` |
| V3 | `V3_expansion_only.yaml` | `regime_profiles.trend.skip: true` |
| V4 | `V4_trend_only.yaml` | `regime_profiles.expansion.skip: true` |
| V5 | `V5_lookback_3.yaml` | `entry_sweep_disp_fvg_lookback_bars: 3` |

Parent stack: `quantbuild/configs/_throughput_discovery/EXP-2021-2025-throughput-discovery-v1/A0_BASELINE.yaml` (1825d, SQE, production effective filters on this run).

## Run (full suite)

From `quantbuild/`, with `PYTHONPATH=src` and `QUANTMETRICS_SUITE_ROOT` set to the suite root:

```powershell
.\scripts\run_sqe_xauusd_decon_matrix.ps1
```

Or per config: `python -m src.quantbuild.app --config <path> backtest`

## Slice analysis (agenda)

Per-year and regime×session matrix are **not** auto-generated in this pass; use QuantLog JSONL + QuantAnalytics reports under each `quantmetrics_os/runs/EXP-SQE-XAUUSD-DECON-2026-*/single/analytics/`. Next step: dedicated analytics script or manual slice on `regime` / `session` on `trade_closed` events.
