# EXP-004 — Verdict: XAUUSD M5 PDH/PDL sweep-reversal (offline)

**Status:** VALIDATION_REQUIRED (herrun aligned 2026-05-16) — pre-herrun outcome ledger **invalid**  
**Manifest:** `results_manifest.json` | **Protocol:** `HERRUN_PROTOCOL.md`

## Alignment (forensic — do this before trusting any R result)

`sweep_detector.py --year YYYY` loads a **year slice**; indices in JSONL are `iloc` into that slice.  
`sweep_outcome_sim.py` without `--year` used the **full parquet** → **37/37** ENTER in 2024 and **27/27** in 2025 pointed at the wrong bars (~2023 timestamps in sim vs ~2024/2025 in detector). **2023** was aligned (0/34 mismatch) because the full cache starts at 2023-01-29.

Audit: `python scripts/sweep_alignment_audit.py --year 2024 --sweeps sweeps_2024.jsonl`  
Fix: `python scripts/sweep_outcome_sim.py --year 2024 --sweeps sweeps_2024.jsonl ...`

## Hypothesis tested

> Sweep + reclaim + displacement + micro structure shift on PDH/PDL during London/NY (UTC) improves odds of a **1.5R** move vs a fixed stop beyond the sweep extreme (**+ 0.1×ATR** buffer), entry at displacement bar close.

## Pipeline (QuantBuild)

From repository root, `quantbuild/`:

1. **M5 cache** (Dukascopy):  
   `python scripts/fetch_dukascopy_xauusd.py --days 1200 --tf 5m`

2. **Detector** (per calendar year):  
   `python scripts/sweep_detector.py --year YYYY --out sweeps_YYYY.jsonl`  
   With optional HTF bias: `--htf-bias-filter` (4H EMA34 on M5-resampled OHLC).

3. **Outcome simulation** (ENTER rows only; **must** pass `--year YYYY`):  
   `python scripts/sweep_outcome_sim.py --year YYYY --sweeps sweeps_YYYY.jsonl --out sweep_outcomes_YYYY_aligned.jsonl`

4. **Subset depth analysis** (exclude 0.30 ≤ sweep_depth_atr < 0.60 on combined outcome files):  
   `python scripts/sweep_outcome_subset_stats.py`

Set `PYTHONPATH` to `quantbuild/src` when running QuantBuild CLIs (see `quantbuild/README` or project conventions).

## Pre-herrun results (INVALID — do not cite)

2023–2025 outcomes simulated **without** `--year` on full parquet. See `pre_herrun_invalid` in manifest.

## Herrun 2026-05-16 (aligned, years 2015 / 2019 / 2022 / 2024)

| Step | Result |
|------|--------|
| Data | Dukascopy M5, `--days 4200` (~2014-11 → 2026-05) |
| Funnel ENTER (combined) | **148** (≥100 threshold met) |
| H2 (10-bar forward vs baseline) | **PASS** (ENTER mean > 0 and > baseline) |
| H1 (1.5R / 48 bar, `--year`) | see below |

### Funnel (combined)

| Step | Count | % of raw |
|------|------:|---------:|
| raw sweeps | 14,248 | 100% |
| after reclaim | 1,664 | 11.7% |
| after acceptance | 1,531 | 10.7% |
| after displacement | 1,482 | 10.4% |
| **ENTER** | **148** | **1.0%** |

Dominant drop: **NO_RECLAIM** (~88% of raw sweeps).

### H1 aligned outcomes

| Year | n | WR (TP) | Exp R | Total R |
|------|--:|--------:|------:|--------:|
| 2015 | 33 | 39.4% | +0.26 | +8.72 |
| 2019 | 36 | 22.2% | −0.28 | −9.97 |
| 2022 | 42 | 31.0% | +0.03 | +1.25 |
| 2024 | 37 | 40.5% | +0.12 | +4.46 |
| **Combined** | **148** | **33.1%** | **+0.03** | **+4.46** |

PF combined ≈ **1.06** — above rejection floor but not a strong edge.

## Conclusion

- **H2:** detectie heeft lichte forward informatie vs sessie-baseline (geen exit).
- **H1:** gecombineerde expectancy **> 0** bij n=148, maar **zwak** (PF ~1.06); **2019** trekt negatief.
- **Verdict:** **VALIDATION_REQUIRED** — geen REJECT op basis van aligned herrun; geen promotie zonder shadow/paper en exit-hypothese apart.

## Follow-ups

- Exit-variatie (1R/2R/3R, timeouts) op aligned ENTER set — aparte hypothese.
- Reclaim-venster / throughput — funnel bottleneck, niet exit.
- Geen HTF-bias herintroduceren (eerder slechter).
