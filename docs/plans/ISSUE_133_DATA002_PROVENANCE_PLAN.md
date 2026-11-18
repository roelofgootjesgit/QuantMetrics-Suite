# Issue #133 — DATA-002 plan: fail-closed source, instrument & timezone provenance

**Status:** PROPOSED — **PLAN ONLY** (no implementation in this PR)  
**Issue:** https://github.com/roelofgootjesgit/QuantMetrics-Suite/issues/133  
**Tech-lead:** comment `6970136820` (2026-11-18 05:37 UTC / 06:37 Europe/Amsterdam)  
**Prerequisite DTA:** PR #132 APPROVED @ `17bb2101e59d4d06975fa1d9440593f02e1d5a8b`, squash-merged `7a69cb1bc714fb9a9e8b989ff037cac13406c76d`  
**Base:** `main` @ `7a69cb1bc714fb9a9e8b989ff037cac13406c76d`  
**Branch:** `cursor/issue-133-data002-plan-3716`  
**Stop line:** **READY FOR CLAUDE PLAN REVIEW #133**

**Gates unchanged:** B-DATA-001 **active** (no real M15/H1 parquet on agent); Slice B **BLOCKED**; PROP-03 **BLOCKED**; PIT Gate A **BLOCKED**; production allowlist empty; historical runs **`UNVERIFIED_LOOKAHEAD`**.  
**This PR:** documentation only — no production code, CI YAML, cache migration, broker/VPS/paper/live enablement, or historical EXP edits.

---

## 1. Objective

Design a **minimal fail-closed** remediation for parquet market-cache provenance so research cannot silently treat GC=F / mixed / timezone-corrupt series as spot XAUUSD, and so live bootstrap cannot inherit untagged legacy files without a gate — **without** enabling trading.

Concrete design targets from tech-lead / issue body:

| ID | Target |
|---|---|
| **(a)** | Aware non-UTC indexes → `tz_convert("UTC").tz_localize(None)`; NY summer/winter tests; explicit naive-input policy |
| **(b)** | Persistent `source` / `instrument` / `offer_side` / timezone / label-convention provenance + **SHA-256** (immutable sidecar or equivalent) |
| **(c)** | Prohibit GC=F/yfinance as spot XAUUSD research fallback; reject mixed/unknown source |
| **(d)** | Legacy cache migration / **quarantine** — no silent reinterpretation |
| **(e)** | Tests: negative cases, offline CI, backward compatibility |

**Normative distinction:** code-verified behaviour and attestation fields are **not** vendor-confirmed open/close / Dukascopy-cTrader TZ evidence. Vendor confirmation remains DTA / owner excerpt territory (issue #127 / DTA §O2).

---

## 2. Non-goals (this plan PR)

| Out of scope | Why |
|---|---|
| Implementing loader / sidecar / tests | After plan APPROVE + separate impl PR |
| Clearing B-DATA-001 / Slice B / PROP-03 | Needs attested data + causal validation |
| Enabling paper/live, broker, VPS, allowlist | Explicit ban |
| Guessing open vs close or `+1h` | DTA rule |
| Rewriting historical EXP/HYP JSON | Preserve; label only |
| Claiming vendor TZ for Dukascopy/cTrader as proved | Still **UNVERIFIED** |

---

## 3. Problem statement (VERIFIED on `7a69cb1`)

| Defect | Evidence | Harm |
|---|---|---|
| `_fetch_yfinance` maps `XAUUSD` → **`GC=F`** and `ensure_data` can `save_parquet` into `XAUUSD/<tf>.parquet` | `parquet_loader.py` | Futures series masquerades as spot |
| `df.attrs` source tags set only in `ensure_live_data` returns; **not persisted** on parquet | `_tag_source` / `save_parquet` | Unknown/mixed origin after reload |
| Tz-aware non-UTC strip via `tz_localize(None)` without `tz_convert("UTC")` | `_fetch_yfinance`; normalize path when tz set after `utc=True` is OK for that path; yfinance path is **VERIFIED INCORRECT** | DST wall-time ≠ UTC |
| Dukascopy / cTrader aware-index semantics | DTA §5.1 | **UNVERIFIED** |
| Oanda | `to_datetime(..., utc=True)` then strip | **VERIFIED** UTC→naive |
| Shared `base_path` for research writers and `ensure_live_data` | inventory §4 | Contaminated cache readable as `cache_fresh` / `cache_stale` |
| No market-cache sidecar / content hash / quarantine | search on main | Fail-open legacy |

---

## 4. Consumer inventory — research vs live (read-only)

**Method:** AST/ripgrep on `7a69cb1`; no parquet on disk.

### 4.1 Shared writers / core

| Surface | Role | GC=F → XAUUSD write? |
|---|---|---|
| `parquet_loader.ensure_data` | Research/shared fill | **YES** (auto → yfinance) |
| `parquet_loader.ensure_live_data` | Live/paper fill | **NO** (yfinance rejected) — still **reads** shared path |
| `parquet_loader.save_parquet` / `load_parquet` | Shared I/O | Writes whatever DF given; **no metadata** |
| `oanda_loader.fetch_and_cache` | Shared write to `…/XAUUSD/{tf}.parquet` | No GC=F (Oanda mid) |
| `scripts/fetch_dukascopy_xauusd.py` | Research ingest | No GC=F (bid) |

### 4.2 Research callers that can trigger GC=F write via `ensure_data`

| Caller | Notes |
|---|---|
| `app.cmd_fetch` | `--source auto` / `yfinance` |
| `backtest.engine.run_backtest` | Rolling window sparse cache → `ensure_data` |
| `scripts/m5_engine_smoke.py` | `ensure_data` |
| `scripts/regime_analytics.py` | `ensure_data` if sparse |
| `scripts/sweep_detector.py` | `ensure_data(..., source="auto")` |

### 4.3 Live / paper

| Caller | Notes |
|---|---|
| `live_runner._load_recent_data` | `ensure_live_data` only; reads `attrs["source_actual"]` **in memory** |
| `app.cmd_live` | Constructs LiveRunner — **not enabled** in this gate |

### 4.4 Read-only research (sample)

Engines/scripts using `load_parquet` / `pd.read_parquet` without write: NY sweep reversion, validation_protocol, portfolio scripts, quantresearch MACD analyze, etc. They inherit whatever is on disk **without** source checks today.

### 4.5 Impact assessment (no trading activation)

| Path | Impact if DATA-002 missing | Plan stance |
|---|---|---|
| Research backtests / fetch | Silent GC=F or TZ-corrupt “XAUUSD” | DENY + quarantine after impl |
| Live/paper bootstrap | Can load untagged / contaminated shared cache as fresh/stale | Gate on provenance when reading; **do not enable** live/paper in DATA-002 |
| Broker / VPS / allowlist | None in this issue | Untouched |

---

## 5. Proposed design (normative for future impl PR)

### 5.1 Timezone conversion (a)

| Rule | Detail |
|---|---|
| Tz-aware input | **Always** `index.tz_convert("UTC").tz_localize(None)` before persist or research use |
| Naive input | **Do not assume UTC** unless contract/`timezone_storage` attestation says `naive_utc` for that `source` |
| Oanda | Keep explicit `utc=True` then strip (already correct); still emit provenance |
| yfinance | Must convert via UTC path **and** must not be research spot fallback (§5.3) |
| Unit tests | Construct America/New_York **summer** and **winter** aware indexes; assert post-conversion naive timestamps equal known UTC instants; assert bare `tz_localize(None)` **fails** the test (negative) |

### 5.2 Persistent provenance + SHA-256 (b)

**Preferred minimal shape (impl may refine after APPROVE):**

| Artifact | Content |
|---|---|
| OHLC file | Unchanged path `base_path/SYMBOL/tf.parquet` (bytes hashed) |
| Sidecar | `base_path/SYMBOL/tf.provenance.json` (or `.meta.json`) — **immutable after write** except owner-attested replace |

**Required sidecar fields** (align DTA §8.1):

| Field | Notes |
|---|---|
| `symbol` | Cache directory name |
| `instrument` | `spot_xauusd` \| `gc_f_futures` \| `other` |
| `timeframe` | e.g. `15m` |
| `source` | `dukascopy` \| `ctrader` \| `oanda` \| `yfinance` \| `other` |
| `single_source` | Must be `true` for research accept |
| `offer_side` | `bid` \| `ask` \| `mid` \| `unknown` |
| `timezone_storage` | Proved per source (e.g. `naive_utc`) |
| `index_semantics` | `bar_open_utc` \| `bar_close_utc` \| `other` — may remain `unknown` → research HTF DENY until DTA |
| `content_sha256` | SHA-256 of parquet bytes |
| `written_at_utc` / `writer` | Tool/version |
| `schema_version` | Sidecar schema id |

**Load policy:** research and (when eventually used) live bootstrap **DENY** if sidecar missing, hash mismatch, `single_source≠true`, `instrument` incompatible with requested spot symbol, or `source` unknown/mixed.

**Provenance claim vs vendor evidence:** sidecar records **what the writer believes**; it does **not** replace owner/vendor attestation for Dukascopy/cTrader open-close or TZ. Mark such fields `UNVERIFIED` until DTA attestation.

### 5.3 Research DENY — GC=F / yfinance / mixed (c)

| Rule | Detail |
|---|---|
| Auto fallback | Remove `yfinance` from **research** `auto` order for spot XAUUSD (and any path writing `XAUUSD/*.parquet`) |
| Explicit `source=yfinance` | DENY for spot-XAUUSD research ensure/load |
| `instrument=gc_f_futures` | NEVER accepted as spot XAUUSD research |
| Mixed/unknown | DENY (`single_source` false / missing sidecar / conflicting append) |
| Live | Keep existing yfinance reject; add same provenance DENY on read |

### 5.4 Legacy quarantine (d)

| Step | Detail |
|---|---|
| Detect | Existing `SYMBOL/tf.parquet` without valid sidecar, or hash/provenance mismatch |
| Action | Move/copy to `base_path/_quarantine/<SYMBOL>/<tf>.<sha_or_ts>.parquet` (+ note JSON); **do not** silently reinterpret as UTC spot |
| Research | Fail closed until re-fetch under new writer + sidecar, or owner attestation binds old bytes |
| No silent migrate | Rewriting naive indexes as UTC without attestation is **forbidden** |

### 5.5 Tests & CI (e)

| Class | Cases |
|---|---|
| TZ | NY summer/winter aware → UTC-naive; negative bare `tz_localize(None)` |
| DENY | yfinance/GC=F ensure_data; mixed append; missing sidecar; hash mismatch |
| Compat | Load with valid sidecar; Oanda-like UTC path still works |
| Offline | No network in unit tests (synthetic frames + temp dirs) |
| Root CI | New tests under `quantbuild/tests/` included in existing pytest path after impl |

### 5.6 Offer_side ↔ costs (from DTA O1)

Persist `offer_side`; research edge claims still require ADR-001 **M3** cost/spread model — bid≠executable buy.

---

## 6. Ordered implementation slices (after plan APPROVE)

| Slice | Scope | Exit |
|---|---|---|
| **I1** | Shared `canonicalize_index_utc_naive` + NY DST unit tests; wire yfinance/normalize/dukascopy paths | Tests green; no behaviour claim beyond conversion |
| **I2** | Sidecar write/read + SHA-256; fail-closed load API for research | Negative tests DENY |
| **I3** | Remove yfinance from research auto; DENY GC=F/spot mix; CLI/`ensure_data`/`run_backtest` respect DENY | No GC=F write path for spot XAUUSD |
| **I4** | Legacy quarantine helper + docs; optional one-shot script (owner-run) | Untagged cache not silently used |
| **I5** | `ensure_live_data` / LiveRunner read gate (still **no** enable paper/live) | Shared-cache contamination blocked at read |

Independent Claude review on **impl** SHA required before merge of code PRs. DATA-002 does **not** by itself clear Slice B / PROP-03.

---

## 7. Acceptance criteria (plan)

| Criterion | Met in this PR? |
|---|---|
| Fresh branch from main @ `7a69cb1` | [x] |
| Research vs live consumer inventory | [x] §4 |
| TZ design + NY summer/winter tests specified | [x] §5.1 |
| Persistent provenance + hash | [x] §5.2 |
| GC=F/yfinance DENY + mixed/unknown | [x] §5.3 |
| Legacy quarantine without silent reinterpretation | [x] §5.4 |
| Impact on research/live without activating trading | [x] §4.5 |
| Provenance ≠ vendor confirmation called out | [x] §5.2 |
| No production / CI / cache / trading changes | [x] |
| Draft; no merge | [x] |

---

## 8. Risks & open questions

| Item | Status |
|---|---|
| Real cache already GC=F-contaminated on owner hosts | **UNVERIFIED** here — quarantine on first DATA-002 deploy |
| Dukascopy/cTrader TZ / open-close | **UNVERIFIED** — DTA attestation + optional API excerpt |
| Sidecar vs parquet footer metadata | Impl choice; sidecar preferred for immutability/reviewability |
| Multi-writer races on same cache path | Impl should write sidecar atomically after parquet (document race as residual risk) |

---

## Stop

**READY FOR CLAUDE PLAN REVIEW #133** — exact head SHA on draft PR.
