# Stap 1 — Resultaten (EXP-SQE-XAUUSD-EXPANSION-FIRST-DEFAULT)

**Run:** `qb_run_20260504T173508Z_9d38e79c`  
**Config:** `quantbuild/configs/experiments/sqe_xauusd_deconstruct_2026/EXPANSION_FIRST_DEFAULT.yaml`  
**Artifacts:** `quantmetrics_os/runs/EXP-SQE-XAUUSD-EXPANSION-FIRST-DEFAULT/single/`

## Console metrics (engine)

| Metric   | Value   |
|----------|---------|
| Trades   | 38      |
| WR       | 60.5%   |
| PF       | 3.07    |
| net_pnl  | 369.33 USD (sim) |
| Max DD   | −2.00R  |

## JSONL (`trade_closed`)

| Metric        | Value      |
|---------------|------------|
| Σ `pnl_r`     | +31.00     |
| W/L           | 23 / 15    |
| Regime        | expansion only (38) |

## Per kalenderjaar (exit-timestamp)

| Jaar | n | net R |
|------|---|-------|
| 2021 | 9 | +3    |
| 2022 | 4 | +5    |
| 2023 | 8 | +4    |
| 2024 | 4 | +5    |
| 2025 | 5 | +10   |
| 2026 | 8 | +4    |

## Promotie vs rubric

- n ≥ 30: **38** — pass  
- WR > 50%: **60.5%** — pass  
- PF > 1.5: **3.07** — pass  

## Vergelijking met V3 (deconstruct)

Identiek op trade-count, R-som, WR, PF en jaarverdeling — zoals verwacht (`trend.skip` + zelfde A0-stack + `equity_kill_switch_pct: 999`).

## Volgende stap

EXP-EXPANSION-MULTI-INSTRUMENT-2026 (USDJPY, GBPUSD) na gate-go — zie experimentvolgorde in research agenda.
