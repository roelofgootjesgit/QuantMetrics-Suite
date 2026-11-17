# ADR-001 — Canonical backtest engine (PLAN / design audit)

**Status:** PROPOSED — ADR text repair after Claude **REQUEST CHANGES (PLAN)** @ `69c1abb`  
**Issue:** https://github.com/roelofgootjesgit/QuantMetrics-Suite/issues/108  
**Tech-lead briefs:** issue comment `6960680399`; PR #126 comment `6960902724` (2026-11-17 22:01 Europe/Amsterdam) — **ADR TEXT ONLY**  
**Branch:** `cursor/issue-108-adr001-backtest-plan-3716`  
**Base:** `main` @ `729b2f17539994f03f260d4fa18a047d35bf7e5c`  
**Mode:** PLAN ONLY — no production code, no historical-data mutations, no trading/broker/VPS/paper/live, no new framework  
**Stop line:** **READY FOR CLAUDE ADR DIFF RECHECK #108**

**Authority chain:** AGENTS.md (“No new backtest engine until ADR-001”) → `QUANTMETRICS_ALPHA_ENGINE_MASTER_V1.md` §2 → `docs/PROP_ROADMAP.md` (ADR-001 before PROP-03 / #111).

---

## Change log (repair vs `69c1abb`)

| ID | Change |
|---|---|
| **B1** | §6.1 documents **verified** `center=True` future-bar look-ahead with exact paths; traces SQE / H1 gate / regime / NY engines / London; cites Claude truncation **INDEPENDENT_REVIEWER** (113/537); marks H1→M15 `ffill` + timestamp convention **UNVERIFIED** |
| **Decision** | Canonical = **public API** `run_backtest`, **not** a certified causal/execution-realistic engine |
| **M0.5** | Mandatory causal-feature gate **before** M3 / PROP-03 (pivots, HTF close alignment, truncation invariance in root CI, source-mutant kill); PROP-03 **BLOCKED** until M0.5 merged + validated |
| **UNVERIFIED_LOOKAHEAD** | Label for affected historical EXP/HYP runs — **document only**; do not mutate historical records in this ADR |
| **O2–O4** | Optimistic close-fill documented; propose next-open for shared M3 hook; no edge claims without costs → `VALIDATION_REQUIRED`; M2 fail-closed dates + dataset hash |
| **O5** | NY-sweep test audit re-checked this repair (commands below) |

---

## 1. Decision summary (recommendation)

| Decision | Choice |
|---|---|
| **Canonical market-backtest public API** | `quantbuild.backtest.engine.run_backtest` |
| **What that does *not* mean** | It is **not** a certified causal, PIT-safe, or execution-realistic engine today |
| **Canonical package ownership** | **quantbuild**; orchestrators call the hub, do not fork fill logic |
| **Strategy-specific engines** | **Pluggable** via `cfg["backtest"]["engine"]`; fill semantics **vary**; cross-engine metrics **non-comparable** until shared fill/cost rules (M3) + causal features (M0.5) |
| **Not canonical** | QuantLog `replay_trace`, FTMO/MC portfolio scripts, `PaperShadowRunner`, VPS paper cycles, audit-pack snapshots |
| **New seventh market engine** | **Rejected** by default |
| **PROP-03** | **BLOCKED** until **M0.5** is merged and validated (then M2/M3 as listed) |

**Minimal adoption path:** freeze new engines → treat hub as sole **public entry** → **M0.5 causal repair + CI** → fail-closed research dates + dataset hash (M2) → shared next-open + net-of-cost hook (M3) → deprecate direct strategy-engine imports outside tests.

This ADR does **not** implement any of the above.

---

## 2. Objective and non-goals

### 2.1 Objective

Inventory ≥6 real existing backtest entrypoints/interfaces; compare PIT/replay fidelity, costs, reproducibility, tests, ownership and migration cost; recommend **one** canonical **public API** and a **minimal** migration path that reuses QuantMetrics code — including an explicit causal look-ahead remediation gate before PROP-03.

### 2.2 Non-goals (explicit)

| Out of scope | Why |
|---|---|
| Code / CI / historical JSON mutations in this PR | Tech-lead: ADR text only |
| New backtest framework / seventh market engine | AGENTS.md |
| Trading, broker, VPS, paper, live changes | Hard safety |
| PROP-03 strategy implementation (#111) | Blocked on ADR + **M0.5** |
| Claiming performance / alpha / P&L bias % from truncation | Honesty; Claude label-diff ≠ PnL proof |
| Merging this PR | Owner only; keep draft |

---

## 3. Audit method (commands actually run)

**Host:** Linux agent, Python 3.12.3. Read-only; no broker/live scripts.

```bash
# Inventory + look-ahead (ADR repair)
rg -n "center=True|def run_.*backtest|def run_backtest" quantbuild/src/quantbuild --glob '*.py'
rg -n "add_structure_context|pivot_highs|MarketStructureShift|reindex\(.*ffill" \
  quantbuild/src/quantbuild --glob '*.py'
# O5 NY-sweep tests
rg -l 'ny_sweep|run_ny_sweep' --glob '**/test*.py'
rg -n 'ny_sweep|run_ny_sweep' quantbuild/tests quantresearch/tests tests --glob '*.py'
ls quantbuild/tests/ | rg -i 'sweep|ny_'
```

Pytest / truncation reproduction: **NOT RUN** by Cursor on this ADR branch. Claude’s 113/537 result is cited only as **INDEPENDENT_REVIEWER**.

---

## 4. Inventory — six named market-backtest entrypoints

Master §2 names these six. All under **quantbuild**. Public dispatch is the hub.

```text
CLI / OS / research
        │
        ▼
run_backtest(cfg)     ← CANONICAL PUBLIC API (not “certified engine”)
        │
        ├─ london_ny_overlap_breakout → run_london_ny_overlap_breakout_backtest
        ├─ ny_sweep_reversion         → run_ny_sweep_backtest
        ├─ ny_sweep_failure_reclaim   → run_ny_sweep_failure_reclaim_backtest
        ├─ bb_only                    → run_bb_only_backtest
        ├─ macd_only                  → run_macd_only_backtest
        └─ (default / unset)          → SQE bar loop + _simulate_trade*
```

Router: `quantbuild/src/quantbuild/backtest/engine.py` (`run_backtest`, dispatch ~L480–542).  
CLI: `app.py` `cmd_backtest`. OS: `quantmetrics_os/.../quantmetrics.py` subprocess → QB CLI.

### 4.1 Comparison matrix

| # | Entrypoint | Path | Interface | PIT / look-ahead | Replay / fills | Cost model | Repro | Tests (O5 where noted) |
|---|---|---|---|---|---|---|---|---|
| **1** | `run_backtest` (hub + default SQE) | `backtest/engine.py` | `cfg` → `List[Trade]` | SQE uses MSS + structure_context (**centered pivots**); H1 gate + regime use same; entry **close[i]**; rolling `now` if dates missing | Bar loop; SL-before-TP; exits from `i+1` | **None** on hub | Fixed dates needed; **no** dataset hash today | `test_backtest.py`, `test_backtest_2026_q1.py` |
| **2** | `run_bb_only_backtest` | `strategies/bb_only_engine.py` | Hub plugin | No `structure_context` / MSS import found; BB causality **assumed** not re-proven | Midline / ATR / time exit | Spread **guard** only | Config + data | `test_bb_only_strategy.py` |
| **3** | `run_macd_only_backtest` | `strategies/macd_only_engine.py` | Hub plugin | Same class as BB (no structure_context) | Time-exit bar loop | `_spread_ok` guard | Config + data | Helpers tested; full engine sparse |
| **4** | `run_london_ny_overlap_breakout_backtest` | `strategies/london_ny_overlap_breakout.py` | Hub plugin | **Next-open** entry + spread; may **consume** hub `regime_series` (regime ← structure look-ahead when provided) | `_simulate_trade_price_levels` | `mock_spread` on entry/SL | Config + data | `test_london_ny_overlap_breakout.py` |
| **5** | `run_ny_sweep_backtest` | `strategies/ny_sweep_reversion_engine.py` | Hub plugin | Calls `add_structure_context` on H1; H1 `ffill` | Limit/FVG bar path | No dedicated haircut found | Spec YAML | **O5:** no dedicated engine unit module (see §6.6) |
| **6** | `run_ny_sweep_failure_reclaim_backtest` | `strategies/ny_sweep_failure_reclaim_engine.py` | Hub plugin | Consumes hub `regime_series` (structure-derived when regime on) | Price-level sim | Half-spread R-adjust | hyp002 pipeline | Manifest/pipeline only (see §6.6) |

### 4.2 Shared fill helpers (hub)

| Helper | Role | Known bias |
|---|---|---|
| `_simulate_trade` | ATR SL/TP from **entry = close[i]**; scan from **i+1** | Optimistic market-on-close entry; same-bar SL-before-TP; mid ≠ bid/ask |
| `_simulate_trade_price_levels` | Absolute SL/TP | Same intrabar rule |

---

## 5. Related interfaces — not the canonical market API

| Interface | Path | Why not canonical |
|---|---|---|
| QuantLog `replay_trace` | `quantlog/.../replay/service.py` | Log replay ≠ market simulation |
| FTMO / portfolio MC scripts | `quantbuild/scripts/*ftmo*`, `portfolio_*`, `validation_protocol.py` | Assumed `pnl_r` / account sims — PROP-01/04 |
| `simulate_mr_trade` | `mean_reversion_eurusd.py` | Not a `backtest.engine` plugin |
| `PaperShadowRunner` / VPS paper | execution / quantbridge scripts | Paper/ops — out of scope |
| Audit-pack `backtest_engine.py` copy | `docs/v1_1_audit_pack_...` | Not runtime |

---

## 6. Cross-cutting findings

### 6.1 Point-in-time / look-ahead — **B1 verified centered pivots**

#### 6.1.1 Source locations (`center=True` → needs `pivot_bars` **future** bars)

| File | Location | Mechanism |
|---|---|---|
| `quantbuild/src/quantbuild/strategy_modules/ict/structure_context.py` | `compute_structure_labels` ~L17–20 | `rolling(2 * pivot_bars + 1, center=True, ...)` on high/low → `is_pivot_high` / `is_pivot_low` |
| `quantbuild/src/quantbuild/indicators/swing.py` | `pivot_highs` / `pivot_lows` ~L30–47 | Same centered window (`window = 2 * pivot_bars + 1`) |
| `quantbuild/src/quantbuild/strategy_modules/ict/market_structure_shift.py` | `calculate` ~L28–33 | `rolling(2 * lb + 1, center=True)` for `swing_high` / `swing_low` before MSS flags |

**Contrast (not the bug):** `swing_highs` / `swing_lows` in `swing.py` use `center=False` and optional `shift(1)` (documented as avoiding look-ahead). Centered **pivots** are the defect class.

**Also note:** `last_swing_low` / `last_swing_high` in `swing.py` inspect `i ± pivot_n` in a loop (future bars relative to candidate `i`) — separate look-ahead surface for trailing-stop helpers; include in M0.5 feature inventory if used on research paths.

#### 6.1.2 Dependent call graph (who inherits the look-ahead)

| Consumer | How |
|---|---|
| **Default SQE** | `strategies/sqe_xauusd.py` runs `MarketStructureShiftModule` + `add_structure_context` |
| **H1 structure gate** | `backtest/engine.py` `_apply_h1_gate` → `add_structure_context` on 1h, then `reindex(..., method="ffill")` onto M15 entries |
| **Regime detector** | `strategy_modules/regime/detector.py` → `add_structure_context` (prefer 1h) + `structure_label.reindex(..., ffill)` |
| **Hub `run_backtest`** | Builds `regime_series` via `RegimeDetector` before plugin dispatch; SQE path also uses H1 gate when enabled |
| **NY sweep reversion** | Imports `add_structure_context`; applies on H1 context |
| **NY sweep failure reclaim** | Uses hub-supplied `regime_series` (structure-tainted when regime enabled) |
| **London/NY overlap** | Does not call structure_context directly; **may label trades with** passed-in `regime_series` |

BB-only / MACD-only: **no** direct structure_context/MSS imports found in this audit.

#### 6.1.3 Claude truncation evidence — **INDEPENDENT_REVIEWER**

| Claim | Classification |
|---|---|
| Synthetic truncation: **113 / 537** structure labels differ (**21.0%**) between prefix-at-`i` vs full-history-at-`i` | **INDEPENDENT_REVIEWER** (Claude) — **not** re-run by Cursor on this ADR branch |
| Inference that 21% label mismatch equals 21% P&L / edge bias | **Forbidden** — do **not** infer; no PnL coupling proven here |

#### 6.1.4 Still **UNVERIFIED** (do not assume)

| Topic | Status |
|---|---|
| H1→M15 `reindex(..., method="ffill")` correctness vs true bar-close availability | **UNVERIFIED** — requires dataset timestamp-convention audit before assuming “+1h” (or any fixed offset) is always right |
| Whether parquet index is open-time, close-time, or broker-local | **UNVERIFIED** — inspect before causal HTF alignment in M0.5 |
| Research `available_at <= decision_at` on OHLC path | **Absent** (master §11 / PROP-02) |

#### 6.1.5 Other timestamp / fill PIT notes

| Finding | Status |
|---|---|
| Default SQE entry at signal **close[i]**; simulator scans exits from **i+1** | **Verified** — optimistic market-on-close |
| London/NY overlap **next-open** entry | **Verified** — proposed canonical fill for future shared M3 hook |
| Rolling window `end = datetime.now(UTC)` when dates omitted | **Verified** — non-reproducible |

### 6.2 Replay fidelity

| Finding | Status |
|---|---|
| All six are bar OHLC engines | **Verified** |
| No vectorbt / zipline / backtrader | **Verified** |
| Intrabar SL-before-TP | **Verified** (conservative vs ambiguous) |
| Partial fills / queue / latency | **Absent** |
| Plugin fill semantics differ | **Verified** — metrics not cross-comparable pre-M3 |

### 6.3 Cost models → research verdict

| Path | Fees / spread / slippage |
|---|---|
| Hub SQE | **None** |
| BB / MACD | Spread **gate** only |
| London/NY overlap | `mock_spread` on entry/SL |
| NY sweep reversion | No dedicated haircut found |
| NY sweep failure reclaim | Half-spread R-adjust |
| PROP-03 need | Net-of-cost on **shared** hub path (M3) |

**Normative:** no edge / return / pass-rate claims from these engines without a realistic cost+slippage model and M0.5-clean features. Default research verdict for current outputs: **`VALIDATION_REQUIRED`** (not GO_RESEARCH).  
`mock_spread` ≠ validated FTMO execution costs (**UNVERIFIED** vs official product rules — PROP-01/02).

### 6.4 Reproducibility

| Lever | Status / rule |
|---|---|
| Fixed UTC `start_date` + `end_date` | **Required** for research; M2 must **fail closed** if omitted (no `datetime.now` fallback in research mode) |
| Dataset content hash | **Required** under M2 (record with run); **not** on hub today |
| Experiment IDs | Partial / uneven |
| Direct `run_*_backtest` imports | Legacy; new code must use hub |

### 6.5 Ownership

| Layer | Owner |
|---|---|
| Hub + strategy plugins | **quantbuild** |
| Orchestration wrappers | **quantmetrics_os** |
| Experiment registry | **quantresearch** |
| Event log replay | **quantlog** (orthogonal) |
| FTMO account sims | scripts + **quantbridge** policy (PROP-01) |

### 6.6 O5 — NY-sweep test audit (this repair)

Commands in §3 were re-run on this branch:

| Check | Result |
|---|---|
| Files matching `test*ny*sweep*` | **0** |
| `rg ny_sweep\|run_ny_sweep` under `quantbuild/tests` | **No matches** |
| `quantresearch/tests/test_hyp002_manifest.py` | References HYP-002 **config path** only — not engine unit tests |
| `quantbuild/tests/test_sweep_m5_xauusd.py` | Filename “sweep”; **no** `ny_sweep` / `run_ny_sweep` references |

**Conclusion:** claim “no dedicated NY-sweep engine unit-test module” is **verified for this audit**. Manifest/pipeline coverage ≠ engine fill/PIT tests. M4 remains required before NY engines are PROP-03 vehicles.

---

## 7. Alternatives considered

| Option | Verdict | Reason |
|---|---|---|
| **A. `run_backtest` as canonical public API; pluggable engines** | **Recommended** | Existing call graph; no new framework |
| B. Treat hub as already certified causal/realistic | **Reject** | Centered pivots + uneven costs prove otherwise |
| C. Promote one strategy engine to sole engine | Reject | Strategy-specific; weaker/shared issues remain |
| D. New third-party BT framework | Reject | Forbidden; duplicates hub |
| E. QuantLog replay / FTMO MC as canonical market BT | Reject | Wrong abstraction |
| F. Six peer public APIs forever | Reject | Master/PROP require one API |

---

## 8. Decision details (proposed normative rules)

Once this ADR is **APPROVED** and merged by owner:

1. **Public API:** New research/OS/CLI market backtests MUST call `run_backtest(cfg)` (or QB/OS wrappers).  
2. **Certification:** Canonical API ≠ certified engine. Causal + cost realism require **M0.5** and **M3**.  
3. **Plugins:** Strategy logic only via `backtest.engine` dispatch.  
4. **No seventh engine** without a new ADR.  
5. **Research windows (M2):** omit `start_date`/`end_date` → **fail closed** in research mode; record **dataset hash**.  
6. **Fills (M3 target):** shared hook defaults toward **next-open** (London pattern), not optimistic signal-close; document remaining plugin exceptions.  
7. **Costs (M3):** net-of-cost/slippage on shared hub path before PROP-03 claims.  
8. **Look-ahead labels:** affected historical runs marked **`UNVERIFIED_LOOKAHEAD`** pending clean rerun (label in docs/ledger process — **do not rewrite** historical JSON in the ADR PR).  
9. **Non-market sims** keep separate names.

---

## 9. Minimal migration path (reuse-first)

| Step | Action | Gate |
|---|---|---|
| **M0** | Merge this ADR (docs) after Claude ADR recheck APPROVE + owner | This draft PR |
| **M0.5** | **Mandatory before M3 / PROP-03** — see §9.1 | Separate impl PR(s); Claude code review; root CI green |
| **M1** | Docs/docstring: canonical **API** wording; list `backtest.engine` keys; point PROP-03 at hub **after M0.5** | Tiny |
| **M2** | Research mode: **fail closed** if dates missing; emit/record **dataset hash** | Small; before PROP-03 claims |
| **M3** | Shared fill/cost hook (`_simulate_trade*`); prefer **next-open**; document per-engine spread | After M0.5; PROP-02/03 |
| **M4** | NY-sweep engine unit tests (fills, expire, structure) | Before NY as PROP-03 vehicle |
| **M5** | FTMO MC + QuantLog replay: docs cross-links only | No merge into hub |

**PROP-03 (#111) is BLOCKED until M0.5 is merged and validated.** M1 docs alone do **not** unblock PROP-03.

### 9.1 M0.5 — causal feature gate (mandatory)

| Requirement | Detail |
|---|---|
| **Causal pivots** | Pivots confirmed only after `pivot_bars` **future** observations exist (confirmation-time shift) **or** trailing-only / non-centered implementation — no `center=True` future dependency on research paths |
| **Repair surfaces** | `structure_context.py`, `swing.py` (`pivot_*` and any research-used `last_swing_*`), `market_structure_shift.py`, plus dependents: SQE, H1 gate, **regime labels**, NY sweep reversion/failure reclaim paths that consume them |
| **HTF availability** | Higher-TF features available only after **bar close**, using alignment derived from a **verified** dataset timestamp convention (open vs close indexing). Do **not** assume `+1h` until that audit completes |
| **Truncation invariance (root CI)** | For each covered feature at index `i`: value from prefix `data[:i+1]` **equals** full-history value at `i`. **Zero mismatches** required for structure labels, swing pivots, MSS flags, and regime labels |
| **Source mutant** | Intentional restore of centered future-looking feature **must be killed** by the suite (SOURCE_MUTATION protocol: scratch tree + `PYTHONPATH` + `__file__` check — see #124 evidence taxonomy) |
| **Historical runs** | EXP-2021-2025 / HYP-002 / HYP-003 (and other structure/regime-dependent runs): status **`UNVERIFIED_LOOKAHEAD`** until clean rerun — **document only** here; no historical file edits in ADR PRs |

---

## 10. Acceptance criteria (this ADR repair PR)

- [x] ≥6 entrypoints inventoried  
- [x] Verified look-ahead documented with paths + dependents  
- [x] Claude 113/537 cited as **INDEPENDENT_REVIEWER** only  
- [x] H1 `ffill` / timestamp convention marked **UNVERIFIED**  
- [x] Canonical framed as **API**, not certified engine  
- [x] **M0.5** mandatory before PROP-03; UNVERIFIED_LOOKAHEAD policy  
- [x] Next-open / costs `VALIDATION_REQUIRED` / fail-closed dates + dataset hash / NY test audit  
- [x] No code or historical-data changes in this PR  
- [ ] Claude **ADR DIFF RECHECK** on exact head SHA → APPROVE / REQUEST CHANGES / BLOCK  
- [ ] Owner merge authorization (later; keep draft)

---

## 11. Tiny next implementation slice (after ADR APPROVE)

**Not M1-alone for PROP-03.** First code slice after plan APPROVE should be **M0.5 scoping PR** (or M0.5 itself if sized): inventory every centered/future-looking feature call site + truncation-invariance test stubs failing on current pivots — still no broker/VPS. Full M0.5 repair may split across PRs but PROP-03 stays blocked until the gate in §9.1 is green.

Optional parallel **M1** docstring-only PR may proceed but must not claim causal certification.

---

## 12. Risks and open questions

| Risk / question | Disposition |
|---|---|
| Centered pivots invalidate legacy “edges” | Mark **UNVERIFIED_LOOKAHEAD**; rerun after M0.5 |
| Hub has no net cost model | `VALIDATION_REQUIRED`; M3 |
| Close-fill vs next-open inconsistency | Document; M3 shared hook |
| Timestamp convention unknown | Block causal HTF until audited |
| NY engine tests thin | Verified O5; M4 |
| Inferring PnL bias from 21% label diffs | **Forbidden** |

---

## 13. Stop

**READY FOR CLAUDE ADR DIFF RECHECK #108**

Review the **exact head commit SHA** of draft PR #126 (`cursor/issue-108-adr001-backtest-plan-3716`). Verdict: APPROVE / REQUEST CHANGES / BLOCK. No implementation in this PR.
