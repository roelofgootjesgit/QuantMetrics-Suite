# Issue #127 — M0.5 plan: parquet timestamp audit + causal feature restoration

**Status:** PROPOSED — plan only; awaiting Claude plan review  
**Issue:** https://github.com/roelofgootjesgit/QuantMetrics-Suite/issues/127  
**Tech-lead brief:** issue comment `6961024293` (2026-11-17 22:07 Europe/Amsterdam) — **DATA TIMESTAMP AUDIT / PLAN ONLY**  
**Branch:** `cursor/issue-127-m05-timestamp-plan-3716`  
**Base:** `main` @ `42e31d8ae07418c89bc050b6fe45412b21b30f25` (ADR-001 squash merge via #126)  
**Prerequisite ADR:** `docs/adr/ADR-001-canonical-backtest-engine.md` (M0.5 gate before PROP-03)  
**Mode:** PLAN ONLY — no production code, no historical-record edits, no workflow/CI YAML changes, no trading/broker/VPS  
**Stop line:** **READY FOR CLAUDE M0.5 PLAN REVIEW #127**

---

## 1. Objective

1. Audit **real** M15/H1 parquet timestamp semantics and provenance (open vs close label, timezone/DST, bar availability, source).  
2. Separate **VERIFIED** (source/commands) from **UNVERIFIED** (needs data or external attestation).  
3. If real OHLC parquet is inaccessible: state an explicit **data-access blocker** and a **fail-closed data contract** — **do not guess** `+1h` or open/close.  
4. Design ordered **M0.5** implementation slices: causal pivots/MSS/regime, HTF availability after verified close, prefix/truncation invariance in **root CI**, source-mutant kill tests.  
5. Keep historical EXP/HYP records intact; treat prior conclusions as **`UNVERIFIED_LOOKAHEAD`**; request **CEO-analyst** communication before treating those runs as evidence.

**PROP-03 (#111) remains BLOCKED** until M0.5 is implemented, independently validated, and the timestamp contract is satisfied.

---

## 2. Non-goals (this PR)

| Out of scope | Why |
|---|---|
| Any `.py` / workflow / CI YAML edits | Tech-lead: plan only |
| Fetching live/broker data or writing parquet into the repo | Safety + gitignore; not this slice |
| Mutating historical `experiment.json` / dossiers | Preserve records; label only |
| Assuming open- vs close-time or `+1h` HTF shift | Forbidden without evidence |
| Claiming PnL impact from Claude’s 113/537 label diffs | Not a P&L estimate (**INDEPENDENT_REVIEWER**) |
| Merge | Draft only |

---

## 3. Audit method (commands actually run)

**Host:** Linux agent, Python 3.12.3. Repo at base SHA above.

```bash
git rev-parse HEAD   # 42e31d8… on branch start
find . -name '*.parquet' | head
rg -n 'parquet|market_cache' quantbuild/.gitignore
rg -n 'load_parquet|tz_localize\(None\)|OFFER_SIDE_BID|reindex\(.*ffill' \
  quantbuild/src/quantbuild --glob '*.py'
python3 -c "import importlib.util as u; print(u.find_spec('dukascopy_python'), u.find_spec('pyarrow'))"
```

**Results (this environment):**

| Probe | Result |
|---|---|
| `*.parquet` under repo working tree | **None found** (market OHLC absent) |
| `data/` / `quantbuild/data/` | `quantlog_events/` + `README_MARKET_CACHE.md` only — **no** `market_cache/*.parquet` |
| `quantbuild/.gitignore` | `data/market_cache/`, `data/market_cache_dukascopy/`, `*.parquet` — cache **intentionally not in git** |
| `dukascopy_python` / `pyarrow` | **Not installed** in this agent image |
| Network fetch of Dukascopy for this plan | **NOT RUN** (would be a data/ops action; plan forbids inventing conventions from a blind fetch without attested contract) |

**Implication:** empirical open/close/DST/availability checks on **real** M15/H1 files are **BLOCKED** here. Downstream design must fail closed until a attested sample is available.

---

## 4. Timestamp & provenance audit

### 4.1 VERIFIED (from repository source / local probes)

| ID | Finding | Evidence |
|---|---|---|
| **V1** | Canonical cache path is `data/market_cache/<SYMBOL>/{15m,1h,...}.parquet` | `parquet_loader.path_for`; `quantbuild/data/README_MARKET_CACHE.md` |
| **V2** | Market parquet is **gitignored**; clean clones / this agent have **no** committed OHLC | `.gitignore` + `find` |
| **V3** | Loader accepts DatetimeIndex or `timestamp` column; sorts on save | `load_parquet` / `save_parquet` |
| **V4** | After Dukascopy/cTrader/yfinance normalize, **tz-aware indices are stripped to naive** via `tz_localize(None)` | `_fetch_dukascopy` L174–175; `_normalize_ohlcv_frame` L229–230; fetch script L60–61 |
| **V5** | Range filters treat naive index as comparable to UTC when the other side is tz-aware (localize/convert then drop tz) | `load_parquet` L68–81 |
| **V6** | Dukascopy path requests **`OFFER_SIDE_BID`** only | `_fetch_dukascopy`; `fetch_dukascopy_xauusd.py` |
| **V7** | Fetch scripts pass **UTC** `start`/`end` when naive inputs are upgraded | `_fetch_dukascopy` L153–156; fetch script uses `datetime.now(timezone.utc)` |
| **V8** | London/NY overlap strategy **documents** H1 index as **“open time”** (code comment + test docstring) | `london_ny_overlap_breakout.py` header; `test_london_ny_overlap_breakout.py` “First bar with open time ≥ 13:30 UTC” |
| **V9** | Live stale telemetry compares wall-clock UTC to **last 15m bar index** (assumes index is a usable “bar time”, not proven open vs close) | `live_runner._bar_lag_minutes` |
| **V10** | H1→M15 alignment today is `Series.reindex(m15.index, method="ffill")` after structure/regime on H1 — **no** explicit close-shift | `engine._apply_h1_gate`; `regime/detector.py` |
| **V11** | Centered future-looking pivots/MSS exist (`center=True`) and feed SQE / H1 gate / regime / NY / London-regime — see ADR-001 §6.1 | ADR-001 + source paths |
| **V12** | Claude truncation: **113/537** labels differ (**21.0%**) | **INDEPENDENT_REVIEWER** only — not re-run here; **not** a P&L figure |

### 4.2 UNVERIFIED (must not be assumed)

| ID | Question | Why unverified |
|---|---|---|
| **U1** | Are stored M15/H1 index stamps **bar-open** or **bar-close** (or something else)? | No real parquet inspected; Dukascopy package docs not available offline; only London **comment** asserts open-time |
| **U2** | Is the stripped naive index always **UTC wall time**, or can DST/local broker zones leak before strip? | Strip erases tz metadata; no sample + no DST round-trip test in-repo for cache files |
| **U3** | When is an H1 bar **available** for M15 decisions (close instant vs next open vs provider lag)? | No `available_at` / publication lag fields on OHLC path |
| **U4** | Does `ffill` of H1→M15 equal “use last **completed** H1”? | Depends on U1/U3; `+1h` shift is **explicitly not assumed** |
| **U5** | Provenance of any given research cache: Dukascopy vs cTrader vs yfinance vs mixed overwrite? | `attrs` source tags exist on some live returns but are **not** persisted into parquet schema |
| **U6** | Bid-only Dukascopy vs FTMO/executable venue prices | Master §13; PROP-01/02 — out of M0.5 except as cost caveat |
| **U7** | Exact DST behavior across London session boundaries on cached series | Needs dated sample spanning DST transitions |

### 4.3 Explicit data-access blocker

| Blocker | Detail |
|---|---|
| **B-DATA-001** | This plan environment (and git) contain **no** authentic `15m.parquet` / `1h.parquet` for research symbols. |
| **Consequence** | HTF causal alignment rules **cannot** be finalized. Any implementation that hard-codes open/close or `+1h` before attestation is **out of policy**. |
| **Owner unblock** | Provide a **read-only** attested sample (or authorize a documented fetch job outside this plan PR) meeting the fail-closed contract in §5. |
| **CEO-analyst** | Until M0.5 + contract green, communicate that EXP-2021-2025 / HYP-002 / HYP-003 (and other structure/regime-dependent runs) are **`UNVERIFIED_LOOKAHEAD`** — not evidence for promotion. |

---

## 5. Fail-closed data contract (proposed; implement after plan APPROVE)

Research / HTF feature use MUST refuse to proceed unless a **Data Timestamp Attestation** (DTA) is present and valid.

### 5.1 Required attestation fields (per dataset / parquet file)

| Field | Meaning |
|---|---|
| `symbol`, `timeframe` | e.g. XAUUSD, `15m` / `1h` |
| `path` + `content_sha256` | Exact file hash |
| `source` | `dukascopy` \| `ctrader` \| `yfinance` \| `other` (+ version/URL if applicable) |
| `offer_side` | e.g. bid / mid / ask / unknown |
| `index_semantics` | **`bar_open_utc`** \| **`bar_close_utc`** \| **`other`** (must not be blank) |
| `timezone_storage` | `naive_utc` \| `aware_utc` \| other — must match loader behavior |
| `dst_policy` | How DST transitions were handled at ingest |
| `bar_complete_rule` | When OHLC row may be used for decisions (e.g. “after close instant”) |
| `attested_by`, `attested_at_utc`, `method` | Human/owner attestation or automated probe ID + evidence link |
| `probe_results` | Outputs of §5.2 probes |

**Fail closed:** if `index_semantics` is missing/unknown, or hash mismatches, or probe fails → **no** research HTF alignment, **no** PROP-03 claims, hub research mode returns structured error (implementation later).

### 5.2 Minimal probe suite (run on real sample; not in this PR)

| Probe | Pass criterion (illustrative) |
|---|---|
| **P1 Spacing** | Median Δt ≈ timeframe (15m/1h); flag gaps/duplicates |
| **P2 Open vs close heuristic** | Compare index to session logic **only as evidence**, e.g. London test expectation vs alternative close-shifted series — record which matches vendor docs; **do not** auto-pick without attestation |
| **P3 DST span** | Sample covering EU/US DST change weeks; no duplicated/missing hour anomalies beyond documented market hours |
| **P4 HTF join** | For assumed semantics S∈{open,close}, compute availability mask for H1→M15; show leakage under wrong S via truncation-style check |
| **P5 Provenance** | Re-fetch tiny window from declared source (owner-approved) and diff hashes/columns |

Probes produce **evidence artifacts** (tables/logs), not silent defaults.

### 5.3 Interim policy (until DTA exists)

- Treat all production research conclusions using current OHLC cache as **`UNVERIFIED_LOOKAHEAD`** / **`VALIDATION_REQUIRED`**.  
- Do **not** implement “shift by 1 hour” as the HTF fix.  
- Causal pivot repair (M0.5-A) may proceed on **synthetic** series for unit tests; **HTF alignment (M0.5-B)** stays blocked on **B-DATA-001**.

---

## 6. Affected causal paths (map for M0.5)

| Surface | Path | Defect class |
|---|---|---|
| Structure labels | `strategy_modules/ict/structure_context.py` | `rolling(..., center=True)` pivots |
| Swing pivots | `indicators/swing.py` `pivot_highs`/`pivot_lows` (+ review `last_swing_*`) | Centered / future window |
| MSS | `strategy_modules/ict/market_structure_shift.py` | Centered swing high/low |
| Default SQE | `strategies/sqe_xauusd.py` | Consumes MSS + structure |
| H1 gate | `backtest/engine.py` `_apply_h1_gate` | Structure on H1 + `ffill` |
| Regime | `strategy_modules/regime/detector.py` | Structure + `ffill` |
| NY sweep reversion | `strategies/ny_sweep_reversion_engine.py` | `add_structure_context` |
| NY failure reclaim | `strategies/ny_sweep_failure_reclaim_engine.py` | Hub `regime_series` |
| London overlap | `strategies/london_ny_overlap_breakout.py` | Optional regime labels; documents open-time |

Canonical API remains **`run_backtest`** (ADR-001) — not a certified engine until M0.5 (+ costs later).

---

## 7. Ordered implementation slices (after plan APPROVE)

No code in this PR. Suggested issue/PR split:

### Slice A — Causal pivots / MSS / structure (can start without real parquet)

| Item | Spec |
|---|---|
| **Goal** | Eliminate future-bar dependency: confirm pivots only after `pivot_bars` right-side bars exist (confirmation-time shift) **or** trailing-only non-centered windows |
| **Files** | `structure_context.py`, `swing.py`, `market_structure_shift.py` (+ call-site audits) |
| **Tests** | Per-feature **prefix truncation invariance**: for each `i`, `f(data[:i+1])[i] == f(data)[i]`; **zero mismatches** on structure labels, pivots, MSS |
| **Mutant** | SOURCE_MUTATION restoring `center=True` (or equivalent leakage) **must fail**; use scratch tree + `PYTHONPATH` + `__file__` check (#124 taxonomy) |
| **CI** | Root CI job/tests (implementation PR may extend root suite — **not** this plan PR) |
| **Out** | Regime/SQE/NY inherit fixes where they call repaired APIs |

### Slice B — HTF availability (blocked on DTA / B-DATA-001)

| Item | Spec |
|---|---|
| **Goal** | H1 feature available on M15 only after **verified** H1 bar completion per attested `index_semantics` + `bar_complete_rule` |
| **Forbidden until DTA** | Hard-coded `+1h` or blind `ffill` “fixes” |
| **Tests** | Truncation invariance on regime labels + H1-gate masks; wrong-semantics mutant killed |
| **Depends** | Owner sample + §5 probes green |

### Slice C — Dataset hash + research fail-closed dates (aligns ADR M2)

| Item | Spec |
|---|---|
| Record `content_sha256` + DTA id on research runs | |
| Missing `start_date`/`end_date` → fail closed in research mode | |

### Slice D — Documentation / governance labels

| Item | Spec |
|---|---|
| Publish `UNVERIFIED_LOOKAHEAD` list (EXP-2021-2025, HYP-002/003, …) without editing historical JSON bodies | |
| CEO-analyst notice template | |
| Cross-link ADR-001 §9.1 | |

**PROP-03 unblock checklist:** A green + B green (DTA satisfied) + truncation CI + mutant killed + independent review on impl SHA.

---

## 8. Truncation invariance & mutant protocol (normative for impl)

```text
For feature f and full series D:
  ∀ i in valid range:
    f(D[: i+1 ]).iloc[i]  ==  f(D).iloc[i]
```

| Feature set (minimum) | Zero mismatches required |
|---|---|
| Structure labels | yes |
| Swing pivots | yes |
| MSS bullish/bearish flags | yes |
| Regime labels | yes (after structure repair; HTF path after Slice B) |

**SOURCE_MUTATION:** edit only in scratch copy; `PYTHONPATH=<scratch>/...`; verify `module.__file__` under scratch; expect failing node ids listing the restored leak; discard scratch. Label honestly — monkeypatch ≠ source mutation.

**Claude 113/537:** keep as **INDEPENDENT_REVIEWER** baseline motivation; re-measure after Slice A on the same protocol and record new counts — still not PnL.

---

## 9. Historical research posture

| Item | Policy |
|---|---|
| EXP-2021-2025 / HYP-002 / HYP-003 / other structure-regime runs | **`UNVERIFIED_LOOKAHEAD`** until clean rerun on M0.5+DTA |
| Historical files | **Do not mutate** in M0.5 plan or casual cleanups |
| Communication | Request **CEO-analyst** briefing before any stakeholder treats those metrics as evidence |
| Rerun | Only after Slice A+B validated; new experiment IDs / explicit rerun governance |

---

## 10. Acceptance criteria (this plan PR)

- [x] Real-data audit attempted; absence documented as **B-DATA-001**  
- [x] VERIFIED vs UNVERIFIED separated; no open/close guess  
- [x] Fail-closed DTA + probe design  
- [x] Causal path map + ordered slices A–D  
- [x] Truncation invariance + source-mutant + root-CI requirements stated  
- [x] UNVERIFIED_LOOKAHEAD + CEO-analyst communication noted  
- [x] No code / historical / workflow changes  
- [ ] Claude **M0.5 PLAN REVIEW** on exact head SHA → APPROVE / REQUEST CHANGES / BLOCK  
- [ ] Owner merge authorization (later; keep draft)

---

## 11. Tiny next slice after APPROVE

1. **Owner:** supply attested M15+H1 parquet sample (or approve controlled fetch) → run §5 probes → fill DTA.  
2. **Impl PR #1 (Slice A):** causal pivots/MSS/structure + truncation tests + mutant — may use synthetic OHLC.  
3. **Impl PR #2 (Slice B):** HTF alignment only after DTA.  

Still no PROP-03, no broker/VPS, no historical JSON rewrites.

---

## 12. Stop

**READY FOR CLAUDE M0.5 PLAN REVIEW #127**

Review the **exact head commit SHA** of the draft PR on branch `cursor/issue-127-m05-timestamp-plan-3716`. Verdict: APPROVE / REQUEST CHANGES / BLOCK. No implementation in this PR.
