# DATA-002 I3 ↔ I2 integration (MERGE HOLD)

**Status:** I3 implements research source/instrument policy on current `main`
**without merging I2** (PR #137 APPROVED, MERGE HOLD per tech-lead).

## Research `auto` scope (FX / indices / metals)

Research ``auto`` is ``ctrader → dukascopy`` for **all** symbols — not only spot XAUUSD.
There is **no** yfinance fallback for FX pairs or indices either. Explicit
``source=yfinance`` remains available only for **non**-spot-XAUUSD symbols;
spot XAUUSD + yfinance/GC=F is always DENY.

## Limits of I3 alone (retained)

- Existing GC=F-tainted on-disk caches are **not** proven clean by I3 write/fetch gates.
- ``assert_research_provenance_claim`` is a helper for future I2 reader wiring — **not**
  yet enforced on ``load_parquet`` / ensure-read paths in this slice.
- I2 reader/provenance + I4 owner quarantine remain required before treating legacy
  cache as research-safe. I2 PR #137 stays **MERGE HOLD**.

## Why I3 does not depend on unmerged I2

| Concern | I3 (this PR) | I2 (PR #137, unmerged) |
|---|---|---|
| GC=F / yfinance as XAUUSD spot | **DENY at resolve + fetch** before any write | Persists `source`/`instrument`/`single_source` on disk |
| Auto after Dukascopy/cTrader fail | Research `auto` = `ctrader→dukascopy` only (FX/indices/metals) | N/A (write protocol) |
| Unknown / mixed origin | DENY unknown source string; DENY `single_source≠true` claims in policy helper | Reader DENY on missing/mismatched sidecar |
| Cache mutation on DENY | No write; inventory unchanged | Read-only DENY; identity mismatch leaves originals |

I3 therefore **does not import** `provenance_cache` and does not require sidecars on disk.
Forbidden futures bytes must not be *produced* by research ensure/fetch even while
legacy caches lack sidecars.

## Exact integration points (post I2 merge)

When I2 lands, wire these seams (out of I3 scope):

1. **`ensure_data` success path** → call I2 `write_parquet_atomic_with_sidecar` with
   `source` / `instrument=spot_xauusd` (or venue instrument) / `single_source=true`
   instead of bare `save_parquet`.
2. **`load_parquet` / research load** → I2 `load_sidecar_fail_closed` + I3
   `assert_research_provenance_claim` on sidecar fields (DENY yfinance / `gc_f_futures`
   / `single_source≠true` / unknown).
3. **I4 quarantine** → owner COPY for legacy parquet without sidecar; I3 policy alone
   cannot reinterpret untagged disks.
4. **Sequencing** → keep I2 draft until I3 (+ I4 dry-run) reviewed; then combine CI +
   source mutants before any merge. Do **not** merge I2 from this I3 PR.

## Callers checked (research vs live)

| Caller | Path | I3 effect |
|---|---|---|
| `parquet_loader.ensure_data` | Research fill | Policy + no yfinance in auto |
| `app.cmd_fetch` | CLI research fetch | Surfaces `ResearchSourcePolicyError` (exit 2) |
| `backtest.engine.run_backtest` | `ensure_data` default auto | Inherits no-GC=F auto |
| `scripts/sweep_detector.py` / `m5_engine_smoke.py` / `regime_analytics.py` | `ensure_data` | Same |
| `parquet_loader.ensure_live_data` | Live/paper | Unchanged (already rejects yfinance); **not activated** |
| `live_runner` / `cmd_live` | Live | Untouched; paper/live stay disabled |

## Non-goals (this slice)

I2 merge, I4 quarantine CLI, I5 live read gate, I6 HTF DTA bind, paper/live/VPS/broker/allowlist.
