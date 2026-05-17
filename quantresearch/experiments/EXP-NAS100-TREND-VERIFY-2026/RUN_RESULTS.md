# EXP-NAS100-TREND-VERIFY-2026 — run

**Run:** `qb_run_20260504T182930Z_22feb34e`  
**Artifacts:** `quantmetrics_os/runs/EXP-NAS100-TREND-VERIFY-2026/single/`

| Metric | Waarde |
|--------|--------|
| n | 117 (trend only, expansion geskipt) |
| Σ `pnl_r` | **−16.50** (`position_size_mult` 0.5 toegepast in engine) |
| WR | 23.9% |
| PF | 0.63 |
| Engine `net_pnl` (sim) | −518.52 |

**Promotie (n > 100, exp > 0, PF > 1.1):** **faalt** — negatieve expectancy en PF ≪ 1.1.

## T.o.v. instrument_profiles benchmark

Profielen vermelden ~956 trades / 5 jaar en positieve trend-R — dit is **niet** gereproduceerd in deze run (SQE-backtest, rolling ~1825d, sessie `standard` + Overlap/NY, zelfde SQE-stack als XAUUSD).

Mogelijke verklaringen: ander venster/methodiek bij profieldata, andere filters/exits in het oorspronkelijke onderzoek, of index-/spread-model verschillen. Verdere diagnose is apart werk indien gewenst.
