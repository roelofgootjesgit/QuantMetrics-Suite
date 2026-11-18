# Issue #133 — DATA-002 plan: fail-closed source, instrument & timezone provenance

**Status:** PROPOSED — **PLAN ONLY** (no implementation in this PR)  
**Issue:** https://github.com/roelofgootjesgit/QuantMetrics-Suite/issues/133  
**Tech-lead (initial):** comment `6970136820` (2026-11-18 05:37 UTC / 06:37 Europe/Amsterdam)  
**Tech-lead (Claude REQUEST CHANGES):** comment `6970367064` on PR #134 @ `936ab63b5e48fbdff876a5d2a03ad97184baeddd` (2026-11-18 05:51 UTC / 06:51 Europe/Amsterdam)  
**Prerequisite DTA:** PR #132 APPROVED @ `17bb2101e59d4d06975fa1d9440593f02e1d5a8b`, squash-merged `7a69cb1bc714fb9a9e8b989ff037cac13406c76d`  
**Base:** `main` @ `7a69cb1bc714fb9a9e8b989ff037cac13406c76d`  
**Branch:** `cursor/issue-133-data002-plan-3716`  
**Prior reviewed head:** `936ab63b5e48fbdff876a5d2a03ad97184baeddd`  
**Stop line:** **READY FOR CLAUDE PLAN DIFF RECHECK #133**

**Gates unchanged:** B-DATA-001 **active** (no real M15/H1 parquet on agent); Slice B **BLOCKED**; PROP-03 **BLOCKED**; PIT Gate A **BLOCKED**; production allowlist empty; historical runs **`UNVERIFIED_LOOKAHEAD`**.  
**This PR:** documentation only — no production code, CI YAML, cache migration, broker/VPS/paper/live enablement, or historical EXP edits.

---

## 1. Objective

Design a **minimal fail-closed** remediation for parquet market-cache provenance so research cannot silently treat GC=F / mixed / timezone-corrupt series as spot XAUUSD, and so live bootstrap cannot inherit untagged legacy files without a gate — **without** enabling trading.

Concrete design targets from tech-lead / issue body:

| ID | Target |
|---|---|
| **(a)** | Aware non-UTC indexes → `tz_convert("UTC").tz_localize(None)` for **all symbols** (incl. yfinance FX fallback); NY summer/winter tests; naive input requires verified provenance — **never** assume UTC |
| **(b)** | Persistent `source` / `instrument` / `offer_side` / timezone / label-convention provenance + **SHA-256** sidecar with **refresh-safe atomic write protocol** (lock + crash DENY); owner-attested fields preserved |
| **(c)** | Prohibit GC=F/yfinance as spot XAUUSD research fallback; reject mixed/unknown source |
| **(d)** | Load/ensure **read-only DENY**; separate owner-invoked quarantine (default COPY; `--move` only explicit; never delete) — no silent reinterpretation |
| **(e)** | Tests: negative cases, offline CI, backward compatibility; root CI runs parquet tests with `pyarrow` in `requirements-dev.txt` (no `importorskip`) |

**Normative distinction:** writer-generated sidecar fields are **not** independent evidence and are **not** vendor-confirmed open/close / Dukascopy-cTrader TZ proof. HTF research additionally requires **owner DTA attestation** bound to the same `content_sha256` (issue #127 / DTA §8.1 / §O2). Unknown or changed hash → **DENY**.

---

## 2. Non-goals (this plan PR)

| Out of scope | Why |
|---|---|
| Implementing loader / sidecar / tests | After plan APPROVE + separate impl PR |
| Clearing B-DATA-001 / Slice B / PROP-03 | Needs attested data + causal validation |
| Enabling paper/live/demo, broker, VPS, allowlist | Explicit ban — sidecar gate will also block demo/paper on future reactivation until valid provenance (**do not activate**) |
| Guessing open vs close or `+1h` | DTA rule |
| Rewriting historical EXP/HYP JSON | Preserve; label only |
| Claiming vendor TZ for Dukascopy/cTrader as proved | Still **UNVERIFIED** |
| Treating writer sidecar as independent DTA attestation | Sidecar ≠ owner attestation (§5.2 / §5.7) |

---

## 3. Problem statement (VERIFIED on `7a69cb1`)

| Defect | Evidence | Harm |
|---|---|---|
| `_fetch_yfinance` maps `XAUUSD` → **`GC=F`** and `ensure_data` can `save_parquet` into `XAUUSD/<tf>.parquet` | `parquet_loader.py` | Futures series masquerades as spot |
| `df.attrs` source tags set only in `ensure_live_data` returns; **not persisted** on parquet | `_tag_source` / `save_parquet` | Unknown/mixed origin after reload |
| Tz-aware non-UTC strip via `tz_localize(None)` without `tz_convert("UTC")` | `_fetch_yfinance` (all symbols using that path, not XAUUSD-only); normalize path when tz set after `utc=True` is OK for that path; yfinance path is **VERIFIED INCORRECT** | DST wall-time ≠ UTC |
| Dukascopy / cTrader aware-index semantics | DTA §5.1 | **UNVERIFIED** |
| Oanda | `to_datetime(..., utc=True)` then strip | **VERIFIED** UTC→naive |
| Shared `base_path` for research writers and `ensure_live_data` | inventory §4 | Contaminated cache readable as `cache_fresh` / `cache_stale` |
| No market-cache sidecar / content hash / quarantine | search on main | Fail-open legacy |
| `pyarrow` not in root `requirements-dev.txt` | `requirements-dev.txt` on `7a69cb1` | Parquet unit tests risk skip / miss in root CI |

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

### 4.3 Live / paper / demo

| Caller | Notes |
|---|---|
| `live_runner._load_recent_data` | `ensure_live_data` only; reads `attrs["source_actual"]` **in memory** |
| `app.cmd_live` | Constructs LiveRunner — **not enabled** in this gate |

**Migration gate (O3):** After DATA-002 impl, the `ensure_live_data` sidecar/provenance gate will also **block demo/paper** on any future reactivation until a valid sidecar (+ where required, DTA attestation) exists. DATA-002 **must not** activate demo, paper, or live.

### 4.4 Read-only research (sample)

Engines/scripts using `load_parquet` / `pd.read_parquet` without write: NY sweep reversion, validation_protocol, portfolio scripts, quantresearch MACD analyze, etc. They inherit whatever is on disk **without** source checks today.

### 4.5 Impact assessment (no trading activation)

| Path | Impact if DATA-002 missing | Plan stance |
|---|---|---|
| Research backtests / fetch | Silent GC=F or TZ-corrupt “XAUUSD” | DENY + owner quarantine after impl |
| Live/paper/demo bootstrap | Can load untagged / contaminated shared cache as fresh/stale | Gate on provenance when reading; **do not enable** live/paper/demo in DATA-002 |
| Broker / VPS / allowlist | None in this issue | Untouched |

---

## 5. Proposed design (normative for future impl PR)

### 5.1 Timezone conversion (a) — **O2**

| Rule | Detail |
|---|---|
| Scope | Canonicalization applies to **all symbols** that pass through shared loaders/writers, including **yfinance FX fallback** and non-XAUUSD symbols — not XAUUSD-only |
| Tz-aware input | **Always** `index.tz_convert("UTC").tz_localize(None)` before persist or research use |
| Naive input | **Do not assume UTC**. Accept only when verified provenance / contract / `timezone_storage` attestation says `naive_utc` (or equivalent proved policy) for that `source`; otherwise **DENY** |
| Oanda | Keep explicit `utc=True` then strip (already correct); still emit provenance |
| yfinance | Must convert via UTC path for **every** symbol using `_fetch_yfinance` / FX fallback **and** must not be research spot-XAUUSD fallback (§5.3) |
| Unit tests | Construct America/New_York **summer** and **winter** aware indexes; assert post-conversion naive timestamps equal known UTC instants; assert bare `tz_localize(None)` **fails** the test (negative); include at least one non-XAUUSD / FX-fallback symbol case |

### 5.2 Persistent provenance + SHA-256 + atomic refresh (b) — **B1**, **O4**

**Preferred minimal shape (impl may refine after APPROVE):**

| Artifact | Content |
|---|---|
| OHLC file | Unchanged path `base_path/SYMBOL/tf.parquet` (bytes hashed) |
| Sidecar | `base_path/SYMBOL/tf.provenance.json` (or `.meta.json`) |
| Lock | Per-cache lock file (e.g. `base_path/SYMBOL/tf.parquet.lock` via `filelock`) — required for concurrent writers/readers coordination |

#### 5.2.1 Required sidecar fields (align DTA §8.1)

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

**Owner-attested fields** (when present, bound to `content_sha256`): e.g. `index_semantics`, `timezone_storage` when DTA-proved, `attested_by` / `attested_at_utc` / `method`, probe refs. Writer **must not overwrite** these; see §5.2.3 / §5.7.

#### 5.2.2 Atomic write protocol (refresh-safe) — **B1**

**Do not** describe the pair as jointly atomic. Protocol:

1. Acquire **per-cache lock** for `SYMBOL/tf`.
2. If an existing sidecar+parquet pair is valid and metadata **identity** matches (§5.2.3), allow append/refresh; else DENY (leave originals untouched).
3. Write **temp parquet** in the same directory (same filesystem), fsync as practical, then `os.replace` onto `tf.parquet`.
4. Compute `content_sha256` of the **final** parquet bytes.
5. Write **temp sidecar** with updated `content_sha256` + writer fields, fsync, then `os.replace` onto `tf.provenance.json`.
6. Release lock.

**Crash / interrupted-write window:** Between parquet replace and sidecar replace (or if either temp is left behind), readers **must DENY** — absent sidecar, unreadable sidecar, or `content_sha256` ≠ current parquet bytes. Recovery is **never** silent acceptance of a half-written pair: operator re-runs a successful write under lock, or owner quarantines (§5.4). Leftover `*.tmp` files are ignored by loaders (not treated as authoritative).

**Concurrency:** Contended writers serialize on the per-cache lock. Readers that observe missing/mismatched sidecar DENY even if another writer holds/held the lock — no “best effort” load.

#### 5.2.3 Metadata identity for append/refresh — **B1**

Append or refresh of an existing cache file is allowed **only** when these identity fields are **identical** between existing sidecar and new write intent:

- `source`
- `instrument`
- `offer_side`
- `timezone_storage`
- bar-label convention (`index_semantics` / label convention)

Any change → **DENY**; originals (parquet + sidecar) remain **untouched**.

#### 5.2.4 Attested-field preservation — **B1**, **O4**

- Writer-generated sidecar is **writer belief only**, not independent evidence.
- Fields that carry **owner DTA attestation** bound to `content_sha256` **cannot** be overwritten by the ordinary writer.
- If parquet bytes change, prior attestation bound to the old hash is **invalid**; HTF research DENY until a new owner attestation binds the **new** `content_sha256` (§5.7).
- Unknown / missing / changed hash relative to attestation → **DENY**.

#### 5.2.5 Load policy

Research and (when eventually used) live/demo/paper bootstrap **DENY** if:

- sidecar missing or unreadable;
- `content_sha256` mismatch (incl. crash window);
- `single_source≠true`;
- `instrument` incompatible with requested spot symbol;
- `source` unknown/mixed;
- for HTF research: no owner DTA attestation bound to the **same** `content_sha256`, or attestation hash unknown/changed (§5.7).

### 5.3 Research DENY — GC=F / yfinance / mixed (c)

| Rule | Detail |
|---|---|
| Auto fallback | Remove `yfinance` from **research** `auto` order for spot XAUUSD (and any path writing `XAUUSD/*.parquet`) |
| Explicit `source=yfinance` | DENY for spot-XAUUSD research ensure/load |
| `instrument=gc_f_futures` | NEVER accepted as spot XAUUSD research |
| Mixed/unknown | DENY (`single_source` false / missing sidecar / conflicting append / identity mismatch) |
| Live | Keep existing yfinance reject; add same provenance DENY on read |

### 5.4 Legacy quarantine (d) — **B2**

#### 5.4.1 Load / ensure — read-only DENY

| Path | Behaviour |
|---|---|
| `load_*` / `ensure_data` / `ensure_live_data` (and research callers) | On missing/invalid sidecar, hash mismatch, identity failure, or policy DENY: **reject read-only** |
| File mutation | These paths **never** move, copy, or delete existing cache files when rejecting |
| Inventory | Rejected load/ensure **preserves** full file inventory (path, size, mtime) before vs after |

#### 5.4.2 Owner-invoked quarantine CLI (separate)

| Rule | Detail |
|---|---|
| Invocation | **Owner-only** explicit CLI / script — **not** called from load/ensure |
| Default | **COPY** to `base_path/_quarantine/<SYMBOL>/<tf>.<sha_or_ts>.parquet` (+ note JSON) |
| MOVE | Only with explicit `--move`; never the default |
| Delete | **Never** delete cache files |
| Semantics | Quarantine does **not** reinterpret bytes as UTC spot; research remains DENY until re-fetch under new writer + sidecar, or owner attestation binds old bytes |
| No silent migrate | Rewriting naive indexes as UTC without attestation is **forbidden** |

### 5.5 Tests & CI (e) — **O1**, plus B1/B2 cases

| Class | Cases |
|---|---|
| TZ (O2) | NY summer/winter aware → UTC-naive for shared helper; yfinance/FX-fallback / multi-symbol path; negative bare `tz_localize(None)`; naive without provenance DENY |
| DENY | yfinance/GC=F ensure_data; mixed append; missing sidecar; hash mismatch |
| Atomic / refresh (B1) | Same-source refresh **PASS**; changed-source (identity mismatch) **DENY** with original parquet+sidecar **untouched**; interrupted write (parquet replaced, sidecar stale/missing) **DENY**; owner-attested field cannot be overwritten by writer |
| Quarantine (B2) | Rejected load/ensure preserves inventory (path, size, mtime); quarantine CLI default COPY; `--move` only when flagged; no delete API |
| DTA bind (O4) | HTF research DENY without owner attestation for `content_sha256`; DENY when attestation hash ≠ current parquet hash |
| Compat | Load with valid sidecar; Oanda-like UTC path still works |
| Offline | No network in unit tests (synthetic frames + temp dirs) |
| Root CI (O1) | Add **`pyarrow`** to root `requirements-dev.txt` in the **implementation** PR; root CI must collect/run parquet provenance tests; **no** `pytest.importorskip("pyarrow")` (hard fail if missing). New tests under `quantbuild/tests/` (and/or root `tests/` as appropriate) on existing pytest paths |

### 5.6 Offer_side ↔ costs (from DTA O1)

Persist `offer_side`; research edge claims still require ADR-001 **M3** cost/spread model — bid≠executable buy.

### 5.7 Independent DTA attestation ↔ `content_sha256` — **O4**

| Rule | Detail |
|---|---|
| Writer sidecar | **Not** independent evidence of vendor TZ / open-close / instrument truth |
| HTF research | Requires **owner DTA attestation** (DTA §8.1 fields) whose `content_sha256` **equals** the on-disk parquet hash |
| Unknown hash | Attestation missing `content_sha256`, or hash blank/unknown → **DENY** |
| Changed hash | After refresh/rewrite, old attestation does not cover new bytes → **DENY** until re-attested |
| Slice B / PROP-03 | Still **BLOCKED**; DATA-002 provenance ≠ clearing those gates |

---

## 6. Ordered implementation slices (after plan APPROVE)

| Slice | Scope | Exit |
|---|---|---|
| **I0** | Add `pyarrow` to root `requirements-dev.txt`; ensure root CI installs it; parquet tests have **no** `importorskip` | Root CI runs parquet tests hard-fail without pyarrow |
| **I1** | Shared `canonicalize_index_utc_naive` for **all symbols** + NY DST + FX-fallback unit tests; wire yfinance/normalize/dukascopy (and other aware) paths; naive-without-provenance DENY | Tests green; no behaviour claim beyond conversion |
| **I2** | Sidecar write/read + SHA-256 + per-cache lock + atomic protocol; fail-closed load API; attested-field preserve; identity-gated refresh | B1 negative/positive tests DENY/PASS as specified |
| **I3** | Remove yfinance from research auto; DENY GC=F/spot mix; CLI/`ensure_data`/`run_backtest` respect DENY | No GC=F write path for spot XAUUSD |
| **I4** | Load/ensure stay **read-only DENY**; separate owner quarantine CLI (default COPY, `--move` only explicit, never delete); inventory preservation tests | Untagged cache not silently used; no mutation on reject |
| **I5** | `ensure_live_data` / LiveRunner read gate + demo/paper reactivation note (still **no** enable paper/live/demo) | Shared-cache contamination blocked at read; O3 documented |
| **I6** | Wire HTF research gate to owner DTA attestation bound to `content_sha256` | O4 DENY paths tested |

Independent Claude review on **impl** SHA required before merge of code PRs. DATA-002 does **not** by itself clear Slice B / PROP-03.

---

## 7. Acceptance criteria (plan)

| Criterion | Met in this PR? |
|---|---|
| Fresh branch from main @ `7a69cb1` | [x] |
| Research vs live consumer inventory | [x] §4 |
| TZ design for **all symbols** + NY summer/winter + naive provenance policy (O2) | [x] §5.1 |
| Atomic refresh-safe write + lock + crash DENY + identity + attested-field preserve (B1) | [x] §5.2 |
| GC=F/yfinance DENY + mixed/unknown | [x] §5.3 |
| Load/ensure read-only DENY; owner quarantine COPY default / `--move` only (B2) | [x] §5.4 |
| `pyarrow` in root requirements-dev + no importorskip (O1) | [x] §5.5 / I0 |
| Demo/paper reactivation blocked by sidecar gate; not activated (O3) | [x] §4.3 / I5 |
| Owner DTA attestation bound to `content_sha256` (O4) | [x] §5.7 |
| Impact on research/live without activating trading | [x] §4.5 |
| Provenance ≠ vendor confirmation / writer sidecar ≠ independent evidence | [x] §5.2 / §5.7 |
| No production / CI / cache / trading changes in this plan PR | [x] |
| Draft; no merge | [x] |
| Claude REQUEST CHANGES @ `936ab63` addressed (plan-only) | [x] |

---

## 8. Risks & open questions

| Item | Status |
|---|---|
| Real cache already GC=F-contaminated on owner hosts | **UNVERIFIED** here — owner quarantine CLI on first DATA-002 deploy; load/ensure only DENY |
| Dukascopy/cTrader TZ / open-close | **UNVERIFIED** — owner DTA attestation bound to `content_sha256` + optional API excerpt |
| Sidecar vs parquet footer metadata | Impl choice; sidecar preferred for reviewability + atomic replace protocol |
| Crash between parquet and sidecar replace | **Normative:** readers DENY; not jointly atomic; recovery via successful rewrite or quarantine — never silent accept |
| Multi-writer races | Mitigated by **per-cache lock** in protocol; residual risk only if lock bypassed (forbidden) |

---

## 9. Diff vs reviewed SHA `936ab63` (this recheck)

| ID | Change |
|---|---|
| **B1** | Replaced “immutable after write” with atomic temp→`os.replace` parquet then sidecar, per-cache lock, crash-window DENY, metadata-identity refresh gate, attested-field non-overwrite; tests listed |
| **B2** | Load/ensure read-only DENY (no move/copy/delete); owner quarantine CLI default COPY; `--move` only explicit; never delete; inventory preservation test |
| **O1** | Root `requirements-dev.txt` gains `pyarrow` in impl (I0); no `importorskip` |
| **O2** | UTC canonicalize for all symbols incl. yfinance FX fallback; naive requires verified provenance |
| **O3** | `ensure_live_data` gate blocks demo/paper on future reactivation; do not activate |
| **O4** | Writer sidecar ≠ independent evidence; HTF needs owner DTA attestation bound to same `content_sha256` |

---

## Stop

**READY FOR CLAUDE PLAN DIFF RECHECK #133** — exact head SHA on draft PR (after this commit).
