# Results — EXP-V4-EXIT-FIX-2026

**run_id:** `qb_run_20260504T172007Z_1de3437f`  
**artifacts:** `quantmetrics_os/runs/EXP-V4-EXIT-FIX-2026/single/`

## Engine headline (console)

| Metric | Value |
|--------|-------|
| Trades | 137 |
| `net_pnl` in log | +51.59 **(USD — `sum(profit_usd)` in `metrics.py`, not R)** |
| `total_profit_r` / sum `profit_r` | **≈ −5.0R** |
| PF | 0.95 |
| WR | 32.1% |
| max drawdown (engine, on R curve) | −26R |

## Equity reconstruction (`trade_closed` → `pnl_r`)

| | |
|---|---|
| Final cum R | **−5.0R** |
| Peak cum R | **+13.0R** |
| Max DD from peak | **26.0R** |

*Script: `quantresearch/scripts/equity_curve_from_quantlog.py` (sorteert op `timestamp_utc` op close).*

## Reading

Over het **volledige** venster blijft het trend-only pad een **diepe DD** en zwakke PF in **R**; de geconsolede `net_pnl` is **geen** “+51R” in risk-eenheden. Trend-isolatie levert in deze run geen verdedigbaar profiel op, onafhankelijk van vroege kill-truncation.
