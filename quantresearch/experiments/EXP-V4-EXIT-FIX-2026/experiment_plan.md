# Plan — EXP-V4-EXIT-FIX-2026

## Config

`quantbuild/configs/experiments/sqe_xauusd_deconstruct_2026/V4_trend_only_research_fullwindow.yaml`

- `extends` → `V4_trend_only.yaml` (expansion skip).
- `risk.equity_kill_switch_pct: 999` — voorkomt vroege `break` in de entry-loop (zie EXP-SLICE diagnose).
- `artifacts.experiment_id`: `EXP-V4-EXIT-FIX-2026`

## Run

```powershell
cd quantbuild
$env:PYTHONPATH="src"
$env:QUANTMETRICS_SUITE_ROOT="<suite-root>"
python -m src.quantbuild.app --config configs/experiments/sqe_xauusd_deconstruct_2026/V4_trend_only_research_fullwindow.yaml backtest
```

## Equity curve

```bash
python quantresearch/scripts/equity_curve_from_quantlog.py quantmetrics_os/runs/EXP-V4-EXIT-FIX-2026/single/quantlog_events.jsonl
```
