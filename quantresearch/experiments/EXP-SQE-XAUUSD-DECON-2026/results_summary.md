# Results summary — EXP-SQE-XAUUSD-DECON-2026

**Verdict & analyse:** zie [`RUN_VERDICT.md`](RUN_VERDICT.md).

**Run date (UTC):** 2026-05-04  
**Stack:** QuantBuild backtest (`system_mode=PRODUCTION`) → QuantLog JSONL → QuantAnalytics post-run → `quantmetrics_os/scripts/collect_run_artifact.py`  
**Baseline reference:** `A0_BASELINE` via `BASE.yaml` (extends throughput-discovery copy).

Metrics below are **console summary lines** from the backtest engine (`Result: net_pnl=…`). Expectancy ≈ `net_pnl / n` in R space for these runs.

| Variant | run_id | n | net_pnl (R) | PF | WR | max_dd (R) |
|---------|--------|---|-------------|-----|-----|------------|
| BASE | `qb_run_20260504T162055Z_15a5d61a` | 42 | 9.28 | 1.23 | 38.1% | −11.00 |
| V1 H1 off | `qb_run_20260504T162201Z_46b027c1` | 40 | 41.49 | 1.81 | 47.5% | −10.00 |
| V2 combo=3 | `qb_run_20260504T162543Z_520419a4` | **0** | — | — | — | — |
| V3 expansion only | `qb_run_20260504T162302Z_f47b5814` | 38 | 369.33 | 3.07 | 60.5% | −2.00 |
| V4 trend only | `qb_run_20260504T162403Z_d657d221` | 34 | −9.18 | 1.09 | 35.3% | −11.00 |
| V5 lookback 3 | `qb_run_20260504T162433Z_0ef5f4ec` | 54 | 51.32 | 1.18 | 37.0% | −11.00 |

## Notes

- **Trade count** for this A0-based stack in PRODUCTION mode is **far below** the 100+ trades hypothesised in the prereg — all rows are **VALIDATION_REQUIRED** on sample size alone (cf. failure criteria `trade_count < 50` → REJECT only applies to V2 here).
- **V2:** No qualifying setups (`combo_min=3`); **REJECT** as a usable configuration for this data window. Consolidated JSONL may be empty; artifact folder still collected after engine fix.
- **V3 vs V4:** On this run, **EXPANSION-only** shows much higher WR/PF than **TREND-only** — supports the secondary hypothesis directionally; slice/year confirmation still outstanding.
- **V1 vs BASE:** Turning **H1 gate off** increased net R and WR in this sample — **contradicts** the structural hypothesis that H1 only removes bad trades (guard may be filtering signal quality differently than assumed; needs slice analysis).
- **NewsGate:** Historical news parquet absent → passthrough; not identical to live news-block behaviour.

## Artifacts

Per variant: `quantmetrics_os/runs/EXP-SQE-XAUUSD-DECON-2026-<VARIANT>/single/`  
(`config_snapshot.yaml`, `resolved_config.yaml`, `quantlog_events.jsonl`, `run_info.json`, `analytics/*`).
