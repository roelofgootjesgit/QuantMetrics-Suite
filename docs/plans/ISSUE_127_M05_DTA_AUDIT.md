# Issue #127 — M0.5 Data Timestamp Audit (DTA)

**Status:** PLAN / AUDIT ONLY — no Slice B code  
**Issue:** https://github.com/roelofgootjesgit/QuantMetrics-Suite/issues/127  
**Tech-lead gate:** comment `6962244080` (2026-11-17 22:01 UTC / 23:01 Europe/Amsterdam) — *Next gate is DTA*  
**Base:** `main` @ `a2944c0d478863f96ad19fc23d015c32cde9b526` (Slice A squash-merge via #129)  
**Branch:** `cursor/issue-127-m05-dta-audit-3716`  
**Mode:** read-only inventory + fail-closed contract proposal  
**Stop line:** **READY FOR CLAUDE DTA REVIEW #127**

**Gates unchanged:** PROP-03 **BLOCKED**; PIT Gate A **BLOCKED**; production allowlist empty; historical results **`UNVERIFIED_LOOKAHEAD`**.  
**Slice A:** merged and out of scope for this PR. **Slice B:** blocked until owner-reviewed DTA attestation.

---

## 1. Objective

1. Inventory **actual** M15/H1 parquet datasets (if accessible), ingestion code, provenance.  
2. Record evidence for: open vs close index label, timezone/DST, candle completion / availability.  
3. Distinguish **VERIFIED** vs **UNVERIFIED**; never invent conventions or assume `+1h`.  
4. If data inaccessible: document **B-DATA-001**, list minimal evidence needed, propose fail-closed DTA contract.  
5. No Slice B HTF code; no merges.

---

## 2. Non-goals

| Out of scope | Why |
|---|---|
| Slice B HTF / ffill / availability implementation | Owner-reviewed attestation first |
| Guessing open vs close / DST / lag | Forbidden by issue + tech-lead |
| Re-fetching live vendor data in this agent | No broker credentials; Dukascopy not installed here |
| Changing causal ICT modules (Slice A) | Already merged |
| Historical EXP/HYP JSON rewrites | Preserve; label only |
| PROP-03 unblock claim | Still blocked |

---

## 3. Method — commands actually run

**Host:** Linux Cloud Agent; repo `/agent/repos/QuantMetrics-Suite`; Python 3.12.  
**Base SHA:** `a2944c0d478863f96ad19fc23d015c32cde9b526`.

```bash
git fetch origin main && git checkout main && git pull origin main
git checkout -b cursor/issue-127-m05-dta-audit-3716
find . -name '*.parquet' 2>/dev/null | wc -l
ls quantbuild/data/market_cache
python3 -c "import importlib.util as u; print(bool(u.find_spec('dukascopy_python')), bool(u.find_spec('pyarrow')), bool(u.find_spec('pandas')))"
printf 'DATA_PATH=%s CACHE_TTL=%s\n' "${DATA_PATH-<unset>}" "${CACHE_TTL_HOURS-<unset>}"
git check-ignore -v quantbuild/data/market_cache/XAUUSD/15m.parquet
rg -n 'market_cache|\.parquet' quantbuild/.gitignore
# Plus static reads of parquet_loader, oanda_loader, fetch_dukascopy_xauusd,
# ctrader_openapi_client._trendbar_to_ohlcv, sessions.py, engine._apply_h1_gate,
# ADR-001 §6.1.4, DIAGNOSIS_DATA_INTEGRITY.md
```

| Probe | Result |
|---|---|
| `find … '*.parquet' \| wc -l` | **0** |
| `ls quantbuild/data/market_cache` | **No such file or directory** |
| `dukascopy_python` / `pyarrow` / `pandas` | **False** / **False** / **True** |
| `DATA_PATH` / `CACHE_TTL_HOURS` | **unset** |
| `git check-ignore` on `…/XAUUSD/15m.parquet` | ignored by `quantbuild/.gitignore:11:data/market_cache/` |
| Live vendor re-fetch | **NOT RUN** (no credentials; Dukascopy package absent) |

---

## 4. Dataset inventory

### 4.1 On this host (VERIFIED)

| Path / claim | Status | Evidence |
|---|---|---|
| Any `*.parquet` under repo | **Absent** | find count = 0 |
| `quantbuild/data/market_cache/` | **Absent** | ls fails |
| `quantbuild/data/market_cache_dukascopy/` | **Absent** | not present |
| Env override `DATA_PATH` | **Unset** | printenv |
| Untracked `data/quantlog_events/` | **Present** (JSONL only) | not OHLC parquet |

### 4.2 Expected layout (VERIFIED as contract text, not as present files)

| Spec | Evidence |
|---|---|
| `data/market_cache/<SYMBOL>/<tf>.parquet` e.g. `XAUUSD/15m.parquet`, `XAUUSD/1h.parquet` | `quantbuild/data/README_MARKET_CACHE.md`; `parquet_loader.path_for` |
| Default YAML `data.base_path: data/market_cache`; `timeframes: [15m, 1h]` | `quantbuild/configs/default.yaml` |
| Cache gitignored | `quantbuild/.gitignore` lines 11–12, 21 (`*.parquet`) |

### 4.3 Historical claim on another host (UNVERIFIED here)

`quantresearch/experiments/EXP-SLICE-BASE-2026/DIAGNOSIS_DATA_INTEGRITY.md` (dated 2026-05-04) asserts:

```text
quantbuild/data/market_cache/XAUUSD/15m.parquet
Start: 2019-06-21
End:   2026-04-24
Rows:  161746
```

**Classification:** historical research note — **not reproducible on this agent disk**. Treat as **UNVERIFIED** for DTA until the same file (or attested copy) is presented with SHA-256 and loader provenance. Do **not** use those dates/row counts as current evidence.

### 4.4 Blocker **B-DATA-001**

**No authentic M15/H1 parquet is accessible in this environment.** Absolute open/close convention, DST edge behaviour on real bars, publication/`available_at` lag, and whether H1→M15 `ffill` equals completed-H1 availability **cannot** be attested from data on this host.

---

## 5. Ingestion & provenance (code — VERIFIED behaviour)

### 5.1 Load / save

| Component | Path | Finding |
|---|---|---|
| Canonical loader | `quantbuild/src/quantbuild/io/parquet_loader.py` | `path_for` → `base_path/SYMBOL/{tf}.parquet`; `load_parquet` / `save_parquet` |
| Source order (`auto`) | same | `ctrader` → `dukascopy` → `yfinance` |
| Dukascopy fetch | `_fetch_dukascopy` | `OFFER_SIDE_BID`; index parsed UTC then **`tz_localize(None)`** (naive) |
| Bulk XAUUSD script | `quantbuild/scripts/fetch_dukascopy_xauusd.py` | Writes `data/market_cache/XAUUSD/{15m,1h,…}.parquet`; same naive strip |
| Oanda path | `quantbuild/src/quantbuild/io/oanda_loader.py` | Mid price (`price: "M"`); skips `complete=False`; UTC parse then **`tz_localize(None)`** |
| cTrader trendbars | `quantbridge/.../ctrader_openapi_client.py` `_trendbar_to_ohlcv` | `utcTimestampInMinutes` → UTC ISO `timestamp`; **open vs close meaning of that stamp: not stated in code** |
| Consumers | `backtest/engine.py`, `execution/live_runner.py` | Load `15m` and `1h` via `load_parquet` |

### 5.2 What code does **not** record

| Missing field | Status |
|---|---|
| Explicit `index_semantics` ∈ {`bar_open_utc`, `bar_close_utc`, `other`} on cache | **Absent** |
| `available_at` / publication lag on OHLC path | **Absent** (ADR-001 §6.1.4) |
| Attestation sidecar (source, offer_side, content hash, attestor) | **Absent** |
| DST policy for bar index | **Absent** — sessions use fixed UTC hour bands only (`sessions.py`) |

---

## 6. Timestamp labels, timezone/DST, availability

| Topic | Classification | Notes |
|---|---|---|
| Open-time vs close-time parquet index | **UNVERIFIED** | No real file to inspect; vendor docs not attested in-repo; **do not assume +1h** |
| Stored timezone | **VERIFIED behaviour:** UTC-parsed then stored **naive** | Dukascopy / Oanda / normalize paths strip tz |
| DST adjustment of OHLC index | **UNVERIFIED / unused** | `session_from_timestamp` assumes UTC wall hours; no DST rewrite of bars |
| Bar completion (Oanda) | **VERIFIED code:** incomplete candles skipped | Does not prove parquet-on-disk semantics for Dukascopy/cTrader caches |
| H1→M15 `reindex(..., method="ffill")` ≡ completed H1 available | **UNVERIFIED** | `engine._apply_h1_gate`, regime, NY engines — ADR §6.1.4 |
| London “open time” wording | **Comment only** | Does not prove parquet index semantics |
| Research `available_at_utc <= decision_at_utc` on OHLC | **Absent** | Master / PROP-02 concern |

---

## 7. HTF join sites that depend on DTA (inventory only)

| Site | Path | Status |
|---|---|---|
| H1 structure gate | `backtest/engine.py` `_apply_h1_gate` | `ffill` onto M15 — correctness **UNVERIFIED** vs availability |
| Regime HTF | `strategy_modules/regime/detector.py` + hub | `ffill` |
| NY sweep reversion | `strategies/ny_sweep_reversion_engine.py` | H1 structure `ffill` |
| Explicit M5→4H `label`/`closed` | `research/sweep_m5_xauusd.py` | Only place with explicit resample label/closed; **not** SQE H1 path |

Slice B must not “fix” these until DTA attestation exists.

---

## 8. Fail-closed data contract (proposed)

Missing or unknown semantics → **deny** research HTF use (H1 gate / regime HTF / NY HTF claims). Synthetic Slice A tests remain valid for same-TF causality only.

### 8.1 Required attestation fields

| Field | Allowed / meaning |
|---|---|
| `symbol` | e.g. `XAUUSD` |
| `timeframe` | `15m` \| `1h` (M15/H1) |
| `path` | Absolute or repo-relative path to parquet |
| `content_sha256` | Hash of file bytes |
| `source` | `dukascopy` \| `ctrader` \| `oanda` \| `other` (+ version/note) |
| `offer_side` | `bid` \| `ask` \| `mid` \| `unknown` |
| **`index_semantics`** | **`bar_open_utc`** \| **`bar_close_utc`** \| **`other`** (must not be blank) |
| `timezone_storage` | e.g. `naive_utc` \| `utc_aware` |
| `dst_policy` | `none_utc_hours` \| documented exception |
| `bar_complete_rule` | How incomplete bars are excluded |
| `availability_rule` | When a bar may be used for decisions (e.g. after close); lag if known |
| `attested_by` / `attested_at_utc` / `method` | Owner or designated attestor |
| `probe_results` | P1–P6 outcomes |

### 8.2 Probe suite (to run **after** attested files exist)

| Probe | Role |
|---|---|
| **P1** | Index spacing vs timeframe (gaps/duplicates) |
| **P2** | Open/close heuristic **plus** vendor/attestor docs — never alone |
| **P3** | Span covering ≥1 DST transition if claiming local TZ (UTC-naive still record policy) |
| **P4** | HTF join leakage check under attested semantics |
| **P5** | Provenance re-fetch sample vs cache hash (optional, owner-gated) |
| **P6** | M15→H1 aggregation with **explicit** `label`/`closed`; full OHLC compare; incomplete hours quarantined — **relative** consistency only; does **not** prove absolute vendor convention or `available_at` lag |

### 8.3 Design option (does **not** lift DTA)

Deriving H1 from attested M15 via P6 may improve relative consistency; it **does not** clear B-DATA-001 for absolute convention or publication lag.

### 8.4 Interim policy

- No hard-coded `+1h` shift.  
- All HTF-dependent historical conclusions remain **`UNVERIFIED_LOOKAHEAD`**.  
- CEO-analyst notice before treating prior SQE/HTF runs as evidence (unchanged from plan #128).

---

## 9. Minimal evidence needed to clear B-DATA-001

Owner (or designated host) must supply **at least**:

1. Readable `XAUUSD/15m.parquet` and `XAUUSD/1h.parquet` (or attested alternate paths via `DATA_PATH`).  
2. Written attestation of `index_semantics`, `source`, `offer_side`, `timezone_storage`, `bar_complete_rule`.  
3. `content_sha256` for each file.  
4. Permission to run P1–P6 read-only (no Slice B code until attestation accepted).  

Optional: short vendor excerpt (Dukascopy / cTrader / Oanda) stating whether bar timestamps are open or close — attached as evidence, not paraphrased into invented certainty.

Until then: **Slice B = BLOCKED**.

---

## 10. Relation to Slice A / PROP-03

| Item | Status |
|---|---|
| Slice A causal ICT + truncation harness | Merged `a2944c0` (#129); F1 OB off-by-one tracked in #130 |
| This PR | DTA audit + contract only |
| Slice B | Blocked on owner-reviewed attestation |
| PROP-03 | **BLOCKED** until M0.5 A+B validated + independent review |

---

## 11. Acceptance for this plan-only PR

| Criterion | Met? |
|---|---|
| Fresh branch from latest `main` | [x] |
| Real parquet searched; absence recorded | [x] |
| Ingest paths + TZ strip + bid/mid behaviour cited | [x] |
| Open/close, DST, availability marked UNVERIFIED where due | [x] |
| Historical cache claim marked UNVERIFIED here | [x] |
| Fail-closed contract + P1–P6 proposed | [x] |
| No Slice B / production code | [x] |
| Draft PR; no merge | [x] |

---

## Stop

**READY FOR CLAUDE DTA REVIEW #127** — exact head SHA on draft PR.
