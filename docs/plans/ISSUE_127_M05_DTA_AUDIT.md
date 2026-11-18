# Issue #127 — M0.5 Data Timestamp Audit (DTA)

**Status:** PLAN / AUDIT ONLY — DOC repair after Claude **REQUEST CHANGES** @ `122bcbc`  
**Issue:** https://github.com/roelofgootjesgit/QuantMetrics-Suite/issues/127  
**Draft PR:** https://github.com/roelofgootjesgit/QuantMetrics-Suite/pull/132  
**Tech-lead:** comment `6970022474` on PR #132 (2026-11-18 05:29 UTC / 06:29 Europe/Amsterdam)  
**Prior DTA gate:** comment `6962244080` on #127  
**Code-fix follow-up (do not implement here):** https://github.com/roelofgootjesgit/QuantMetrics-Suite/issues/133 (**DATA-002**)  
**Base:** `main` @ `a2944c0d478863f96ad19fc23d015c32cde9b526` (Slice A via #129)  
**Branch:** `cursor/issue-127-m05-dta-audit-3716`  
**Mode:** read-only inventory + fail-closed contract — **no production code, cache, CI, or data changes**  
**Stop line:** **READY FOR CLAUDE DTA DIFF RECHECK #127**

**Gates unchanged:** PROP-03 **BLOCKED**; PIT Gate A **BLOCKED**; production allowlist empty; historical results **`UNVERIFIED_LOOKAHEAD`**.  
**Slice A:** merged. **Slice B:** blocked until owner-reviewed DTA attestation **and** DATA-002 provenance fixes as applicable.

---

## Change log (repair vs `122bcbc`)

| ID | Change |
|---|---|
| **B1** | Per-source timezone classification; drop blanket “UTC then naive = VERIFIED”; `timezone_storage` must be **proved per source** or DENY; future fix → #133 |
| **B2** | Document yfinance `XAUUSD`→`GC=F` same-cache write; `attrs` not persisted; contract `instrument` + `single_source`; research **DENY** GC=F as spot; **P7** source/timezone probe; future fix → #133 |
| **O1** | Bid Dukascopy vs mid Oanda; `offer_side` must tie to M3 cost/spread model |
| **O2** | cTrader `utcTimestampInMinutes` semantics **UNVERIFIED**; need owner API excerpt |
| **O3** | `ensure_live_data` shares research cache; potential paper/live impact noted (both disabled) |

---

## 1. Objective

1. Inventory **actual** M15/H1 parquet datasets (if accessible), ingestion code, provenance.  
2. Record evidence for: open vs close index label, **per-source** timezone/DST, candle completion / availability.  
3. Distinguish **VERIFIED** vs **UNVERIFIED**; never invent conventions or assume `+1h`.  
4. If data inaccessible: document **B-DATA-001**, list minimal evidence needed, propose fail-closed DTA contract.  
5. No Slice B HTF code; no merges; codefixes tracked in **#133**.

---

## 2. Non-goals

| Out of scope | Why |
|---|---|
| Slice B HTF / ffill / availability implementation | Owner-reviewed attestation first |
| Implementing DATA-002 loader fixes | Issue **#133** — separate plan/code PRs |
| Guessing open vs close / DST / lag / `+1h` | Forbidden |
| Re-fetching live vendor data in this agent | No credentials; Dukascopy not installed |
| CI / cache / trading / broker / allowlist changes | Tech-lead DOC-ONLY |
| PROP-03 unblock claim | Still blocked |

---

## 3. Method — commands actually run

**Host:** Linux Cloud Agent; repo `/agent/repos/QuantMetrics-Suite`; Python 3.12.  
**Audit base SHA (first DTA draft):** `a2944c0…`. **Reviewed SHA:** `122bcbc…`. This repair: docs only.

```bash
find . -name '*.parquet' 2>/dev/null | wc -l
ls quantbuild/data/market_cache
python3 -c "import importlib.util as u; print(bool(u.find_spec('dukascopy_python')), bool(u.find_spec('pyarrow')), bool(u.find_spec('pandas')))"
printf 'DATA_PATH=%s CACHE_TTL=%s\n' "${DATA_PATH-<unset>}" "${CACHE_TTL_HOURS-<unset>}"
git check-ignore -v quantbuild/data/market_cache/XAUUSD/15m.parquet
# Static reads: parquet_loader (incl. _fetch_yfinance / _normalize_ohlcv_frame /
# ensure_live_data), oanda_loader, fetch_dukascopy_xauusd, ctrader_openapi_client,
# sessions.py, engine._apply_h1_gate, ADR-001 §6.1.4, DIAGNOSIS_DATA_INTEGRITY.md
```

| Probe | Result |
|---|---|
| `find … '*.parquet' \| wc -l` | **0** |
| `ls quantbuild/data/market_cache` | **No such file or directory** |
| `dukascopy_python` / `pyarrow` / `pandas` | **False** / **False** / **True** |
| `DATA_PATH` / `CACHE_TTL_HOURS` | **unset** |
| Live vendor re-fetch | **NOT RUN** |
| America/New_York DST unit tests of loader | **NOT RUN** (no code change in this PR) |

---

## 4. Dataset inventory

### 4.1 On this host (VERIFIED)

| Path / claim | Status | Evidence |
|---|---|---|
| Any `*.parquet` under repo | **Absent** | find count = 0 |
| `quantbuild/data/market_cache/` | **Absent** | ls fails |
| Env `DATA_PATH` | **Unset** | printenv |
| Untracked `data/quantlog_events/` | JSONL only | not OHLC parquet |

### 4.2 Expected layout (contract text, not present files)

| Spec | Evidence |
|---|---|
| `data/market_cache/<SYMBOL>/<tf>.parquet` | `README_MARKET_CACHE.md`; `path_for` |
| Default `timeframes: [15m, 1h]` | `configs/default.yaml` |
| Cache gitignored | `quantbuild/.gitignore` |

### 4.3 Historical claim (UNVERIFIED here)

`EXP-SLICE-BASE-2026/DIAGNOSIS_DATA_INTEGRITY.md` claims `15m.parquet` 2019-06-21…2026-04-24, 161746 rows. **Not on this disk** — do not use as current DTA evidence.

### 4.4 Blocker **B-DATA-001**

**No authentic M15/H1 parquet is accessible here.** Absolute open/close, DST-on-real-bars, `available_at` lag, and H1→M15 `ffill` ≡ completed-H1 availability remain **unattested from data**.

---

## 5. Ingestion & provenance

### 5.1 Per-source timezone classification (B1 — replaces blanket claim)

**Do not** treat “parsed then `tz_localize(None)`” as uniformly **VERIFIED UTC-naive** across sources.

| Source | Path | What code does | Classification |
|---|---|---|---|
| **Oanda** | `oanda_loader.fetch_oanda_candles` | `pd.to_datetime(..., utc=True)` then `index.tz_localize(None)` | **VERIFIED UTC → naive UTC wall** (explicit `utc=True` before strip) |
| **yfinance** | `parquet_loader._fetch_yfinance` | `pd.to_datetime(data.index)` **without** `utc=True`; if tz-aware → **`tz_localize(None)` only** | **VERIFIED INCORRECT** for tz-aware **non-UTC** indexes: strip preserves **local wall time**, so America/New_York summer vs winter maps to **different** UTC offsets while looking “naive”. Naive yfinance indexes: **not assumed UTC** without attestation |
| **Dukascopy** | `_fetch_dukascopy` | `to_datetime(..., utc=True)` when building index from column; if tz-aware → `tz_localize(None)`. Library may already return aware/naive indexes | **UNVERIFIED** for tz-aware library indexes (whether always UTC before strip is not proved here) |
| **cTrader** | `_fetch_ctrader` → `_normalize_ohlcv_frame` | Normalize uses `to_datetime(..., utc=True)` then `tz_localize(None)` when tz set; trendbar stamp from `utcTimestampInMinutes` | **UNVERIFIED** whether library/adapter indexes are always UTC-aware before normalize; stamp **open vs close** also UNVERIFIED (§6 / O2) |

**Contract rule:** `timezone_storage` in §8.1 must be **proved per source** (attestation + P7). Unknown / mixed / yfinance-non-UTC-strip → **DENY** research use of that cache.

**Future fix (issue #133 — not this PR):** on tz-aware inputs use `tz_convert("UTC").tz_localize(None)`; unit-test America/New_York DST summer/winter; preserve correct handling of already-naive inputs; **do not** assume naive timestamps are UTC without contract.

### 5.2 Load / save / routing (VERIFIED code behaviour)

| Component | Finding |
|---|---|
| `path_for` / `load_parquet` / `save_parquet` | `base_path/SYMBOL/{tf}.parquet` |
| `auto` order | `ctrader` → `dukascopy` → `yfinance` |
| Dukascopy offer | `OFFER_SIDE_BID` |
| Oanda price | mid (`price: "M"`); skips `complete=False` |
| `_tag_source` | Sets `df.attrs["source_requested"|"source_actual"]` — **attrs are not written to parquet** |
| Consumers | `backtest/engine.py`, `live_runner.py` via `load_parquet` / `ensure_live_data` |

### 5.3 yfinance / GC=F instrument mix (B2)

| Fact | Evidence | Classification |
|---|---|---|
| `_fetch_yfinance` maps `XAUUSD` → ticker **`GC=F`** (COMEX gold **futures**) | `parquet_loader.py` ~L275 | **VERIFIED** |
| Result can be saved into the same `XAUUSD/<tf>.parquet` via `ensure_data` auto fallback | `ensure_data` source loop | **VERIFIED** path exists |
| Source identity not durable on disk | `attrs` only | **VERIFIED** gap |
| GC=F ≡ XAUUSD spot for research | — | **FORBIDDEN** — see §8.5 |

**Future fix (#133):** persist `source` / `instrument` in sidecar or column; **remove yfinance from research auto fallback** for XAUUSD spot.

### 5.4 Shared live cache (O3)

`ensure_live_data` reads/writes the **same** `base_path` market cache used by research/backtest. Stale, mixed-source, or GC=F-contaminated files could affect paper/live bootstrap **if** those paths were enabled. **Paper and live remain disabled** in this gate; impact is noted for risk tracking only — **no enablement** here.

### 5.5 What code does not record

| Missing | Status |
|---|---|
| Durable `source` / `instrument` / `offer_side` on parquet | **Absent** |
| `index_semantics`, `available_at` | **Absent** |
| Per-source proved `timezone_storage` | **Absent** (must be attested) |

---

## 6. Timestamp labels, timezone/DST, availability

| Topic | Classification | Notes |
|---|---|---|
| Open vs close parquet index | **UNVERIFIED** | No real file; **no +1h** assumption |
| **Per-source timezone** | See **§5.1** | Blanket “all UTC-naive VERIFIED” **withdrawn** |
| DST on OHLC index | **UNVERIFIED** | Sessions use fixed UTC hour bands (`sessions.py`); yfinance strip **breaks** UTC equivalence across DST |
| Oanda bar completion | **VERIFIED code:** skip incomplete | Does not prove Dukascopy/cTrader disk semantics |
| cTrader `utcTimestampInMinutes` | **UNVERIFIED** (O2) | Need **owner-provided official API excerpt**; do **not** guess open/close label |
| H1→M15 `ffill` ≡ completed H1 | **UNVERIFIED** | ADR-001 §6.1.4 |
| `available_at_utc <= decision_at_utc` on OHLC | **Absent** | PROP-02 / master |

---

## 7. HTF join sites (inventory only)

| Site | Path | Status |
|---|---|---|
| H1 structure gate | `engine._apply_h1_gate` | `ffill` — DTA-gated |
| Regime HTF | `regime/detector.py` + hub | `ffill` |
| NY sweep reversion | `ny_sweep_reversion_engine.py` | `ffill` |
| Explicit `label`/`closed` resample | `research/sweep_m5_xauusd.py` | Not SQE H1 path |

---

## 8. Fail-closed data contract (proposed)

Missing/unknown semantics → **DENY** research HTF (and spot-XAUUSD) use. Synthetic Slice A same-TF tests remain valid.

### 8.1 Required attestation fields

| Field | Allowed / meaning |
|---|---|
| `symbol` | e.g. `XAUUSD` |
| **`instrument`** | **`spot_xauusd`** \| **`gc_f_futures`** \| **`other`** — must match true underlying |
| `timeframe` | `15m` \| `1h` |
| `path` | Path to parquet |
| `content_sha256` | File hash |
| `source` | `dukascopy` \| `ctrader` \| `oanda` \| `yfinance` \| `other` |
| **`single_source`** | **`true`** required for research; unknown/mixed origin → **DENY** |
| `offer_side` | `bid` \| `ask` \| `mid` \| `unknown` — see §8.6 |
| **`index_semantics`** | `bar_open_utc` \| `bar_close_utc` \| `other` (non-blank) |
| **`timezone_storage`** | e.g. `naive_utc` — **must be proved per `source`** (attestation + P7); unproved → **DENY** |
| `dst_policy` | e.g. `none_utc_hours` |
| `bar_complete_rule` | Incomplete-bar policy |
| `availability_rule` | When bar may drive decisions / lag |
| `attested_by` / `attested_at_utc` / `method` | Attestor |
| `probe_results` | P1–**P7** |

### 8.2 Probe suite (after attested files exist)

| Probe | Role |
|---|---|
| **P1** | Spacing / gaps / duplicates |
| **P2** | Open/close heuristic **plus** vendor docs — never alone; also used by P7 session-open check |
| **P3** | DST span if claiming local TZ |
| **P4** | HTF join leakage under attested semantics |
| **P5** | Optional provenance re-fetch vs hash |
| **P6** | M15→H1 agg with explicit `label`/`closed`; incomplete hours quarantined — **relative only**; not absolute convention / lag |
| **P7 — source / timezone** | Compare first/last bar timestamps **and** prices to an independent vendor sample or known reference; run per-source session-open check (via P2). If ambiguous, record as **external corroboration**, not proof. Fail closed on contradiction or unknown `timezone_storage` / `instrument` |

### 8.3 Design option (does not lift DTA)

H1 derived from attested M15 via P6 ≠ clearing B-DATA-001 for absolute convention or lag.

### 8.4 Interim policy

- No hard-coded `+1h`.  
- Historical HTF/SQE conclusions: **`UNVERIFIED_LOOKAHEAD`**.  
- CEO-analyst notice before treating prior runs as evidence.

### 8.5 Research rule — GC=F / yfinance (B2)

**`GC=F` / yfinance data is NEVER accepted as XAUUSD spot research data.**  
Any cache whose `instrument` is `gc_f_futures`, `source` is `yfinance`, or origin is unknown/mixed (`single_source` ≠ true) → **DENY** for spot-XAUUSD research, Slice B, and PROP-03 evidence.

### 8.6 Bid vs mid and cost model (O1)

Dukascopy path is **bid-only**; Oanda path is **mid**. `offer_side` on the DTA contract must be tied to a **realistic spread / cost model (ADR-001 M3)** before any executable or edge claim. Bid series alone does **not** authorize treating prints as executable buys/sells.

---

## 9. Minimal evidence to clear B-DATA-001

1. Readable attested `15m` + `1h` parquets (or `DATA_PATH`).  
2. Attestation including **`index_semantics`**, **`timezone_storage` (proved per source)**, **`instrument`**, **`single_source: true`**, `source`, `offer_side`, `bar_complete_rule`.  
3. `content_sha256` per file.  
4. P1–**P7** permission (read-only).  
5. For cTrader-sourced bars: owner-supplied **official API excerpt** on `utcTimestampInMinutes` (O2).  
6. DATA-002 (#133) progress as required so research caches cannot silently mix GC=F / bad TZ strip.

Until then: **Slice B = BLOCKED**.

---

## 10. Relation to Slice A / #133 / PROP-03

| Item | Status |
|---|---|
| Slice A | Merged `a2944c0` (#129); F1 → #130 |
| This PR | DTA docs only |
| **DATA-002** | Issue **#133** — source/instrument/timezone codefixes (separate PRs) |
| Slice B | Blocked on attestation (+ provenance fixes) |
| PROP-03 | **BLOCKED** |

---

## 11. Acceptance (DOC repair)

| Criterion | Met? |
|---|---|
| Per-source TZ: Oanda VERIFIED UTC; yfinance VERIFIED FOUT; Dukascopy/cTrader UNVERIFIED | [x] |
| `timezone_storage` / `instrument` / `single_source` in contract; unproved DENY | [x] |
| GC=F research DENY + P7 | [x] |
| O1 bid/mid ↔ M3 costs; O2 cTrader uncertainty; O3 shared live cache | [x] |
| Codefixes deferred to **#133** | [x] |
| B-DATA-001 / NOT RUN / no +1h / P6 relative / Slice B & PROP-03 BLOCKED preserved | [x] |
| Docs-only; draft; no merge | [x] |

---

## Stop

**READY FOR CLAUDE DTA DIFF RECHECK #127** — exact head SHA on draft PR.
