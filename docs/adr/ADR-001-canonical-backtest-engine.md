# ADR-001 — Canonical backtest engine (PLAN / design audit)

**Status:** PROPOSED — plan only; awaiting Claude plan review  
**Issue:** https://github.com/roelofgootjesgit/QuantMetrics-Suite/issues/108  
**Tech-lead brief:** issue comment `6960680399` (2026-11-17 21:52 Europe/Amsterdam) — ADR-001 design/audit ONLY  
**Branch:** `cursor/issue-108-adr001-backtest-plan-3716`  
**Base:** `main` @ `729b2f17539994f03f260d4fa18a047d35bf7e5c`  
**Mode:** PLAN ONLY — no production code, no trading/broker/VPS/paper/live, no new framework  
**Stop line:** **READY FOR CLAUDE PLAN REVIEW #108**

**Authority chain:** AGENTS.md (“No new backtest engine until ADR-001”) → `QUANTMETRICS_ALPHA_ENGINE_MASTER_V1.md` §2 → `docs/PROP_ROADMAP.md` (ADR-001 before PROP-03 / #111).

---

## 1. Decision summary (recommendation)

| Decision | Choice |
|---|---|
| **Canonical market-backtest API** | `quantbuild.backtest.engine.run_backtest` |
| **Canonical package ownership** | **quantbuild** (Decision Engine); orchestrators call it, do not fork fill logic |
| **Strategy-specific engines** | Keep as **pluggable implementations** selected by `cfg["backtest"]["engine"]`; not competing public APIs |
| **Not canonical** | QuantLog `replay_trace`, FTMO/MC portfolio scripts, `PaperShadowRunner`, VPS paper cycles, audit-pack snapshots |
| **New seventh market engine** | **Rejected** by default (AGENTS.md / PROP roadmap) |

**Minimal adoption path:** freeze new engines → document hub as sole public entry → require fixed `start_date`/`end_date` for research claims → shared net-of-cost hook on hub fills before PROP-03 → deprecate direct strategy-engine imports outside tests.

This ADR does **not** implement any of the above. Implementation is a later tiny slice after owner + Claude APPROVE on this plan SHA.

---

## 2. Objective and non-goals

### 2.1 Objective

Inventory ≥6 real existing backtest entrypoints/interfaces; compare PIT/replay fidelity, costs, reproducibility, tests, ownership and migration cost; recommend **one** canonical engine and a **minimal** migration path that reuses QuantMetrics code.

### 2.2 Non-goals (explicit)

| Out of scope | Why |
|---|---|
| New backtest framework / seventh market engine | Tech-lead + AGENTS.md |
| Trading, broker, VPS, paper, live changes | Hard safety |
| PROP-03 strategy implementation (#111) | Blocked on this ADR |
| Walk-forward engine (PROP-04 / #112) | Separate sprint |
| Changing hyp003 / experiment.json / CI workflows | Unrelated |
| Claiming performance / alpha | UNVERIFIED_LEGACY / no invented data |
| Merging this PR | Owner only |

---

## 3. Audit method (commands actually run)

**Host:** Linux agent, Python 3.12.3. Repo at base SHA above. Read-only audit; no broker/live scripts.

```bash
# Inventory (representative)
rg -n "def run_.*backtest|def run_backtest|def simulate_" quantbuild --glob '*.py'
rg -n "mock_spread|slippage|commission" quantbuild/src/quantbuild --glob '*.py'
rg -n "ADR-001|run_backtest|PROP-03" QUANTMETRICS_ALPHA_ENGINE_MASTER_V1.md docs/PROP_ROADMAP.md AGENTS.md
```

No pytest suite was required for this plan-only ADR (docs only). Local import smoke of engines was **NOT RUN** as a gate; inventory is from source inspection.

---

## 4. Inventory — six named market-backtest entrypoints

Master §2 already names these six. All live under **quantbuild**. Public dispatch is the hub.

```text
CLI / OS / research
        │
        ▼
run_backtest(cfg)     ← CANONICAL PUBLIC API (recommended)
        │
        ├─ engine == london_ny_overlap_breakout → run_london_ny_overlap_breakout_backtest
        ├─ engine == ny_sweep_reversion         → run_ny_sweep_backtest
        ├─ engine == ny_sweep_failure_reclaim   → run_ny_sweep_failure_reclaim_backtest
        ├─ engine == bb_only                    → run_bb_only_backtest
        ├─ engine == macd_only                  → run_macd_only_backtest
        └─ (default / unset)                    → SQE bar loop + _simulate_trade*
```

Router: `quantbuild/src/quantbuild/backtest/engine.py` (`run_backtest`, dispatch ~L480–542).  
CLI: `quantbuild/src/quantbuild/app.py` `cmd_backtest` → `run_backtest`.  
OS: `quantmetrics_os/orchestrator/quantmetrics.py` `cmd_backtest` (subprocess into QB CLI).

### 4.1 Comparison matrix

| # | Entrypoint | Path | Interface | PIT / timestamps | Replay fidelity | Cost model | Repro | Tests | Migration cost if demoted |
|---|---|---|---|---|---|---|---|---|---|
| **1** | `run_backtest` (hub + default SQE) | `quantbuild/.../backtest/engine.py` | `cfg: dict` → `List[Trade]`; YAML via CLI | Bar OHLC index; entry at **close[i]**; regime/H1 `ffill`; rolling window uses `datetime.now(UTC)` if dates missing; **no** `available_at`/`decision_at` gate | Bar event-loop; shared `_simulate_trade` / `_simulate_trade_price_levels`; **SL checked before TP** same bar (conservative bias) | **None** in hub (no commission/slippage/spread PnL) | Deterministic given fixed OHLC + fixed dates; else wall-clock window; `run_id`/uuid per signal | `quantbuild/tests/test_backtest.py`, `test_backtest_2026_q1.py` | **Keep as canonical** |
| **2** | `run_bb_only_backtest` | `strategies/bb_only_engine.py` | Hub-routed; preloaded `data` + cfg | Causal rolling BB if windows causal (**assumed**, not re-proven here); entry close | Bar-loop midline / ATR SL / time exit | Spread **guard** (`broker.mock_spread` vs max) — **reject**, not haircut | Config + data; `experiment_id` / STRATEGY_ID | `test_bb_only_strategy.py` | Low — keep via `backtest.engine: bb_only` |
| **3** | `run_macd_only_backtest` | `strategies/macd_only_engine.py` | Hub-routed | Same class as BB | Time-exit bar loop | Same `_spread_ok` guard | Same | Component + sim helpers in `test_macd_only_strategy.py`; **full engine call sparsely covered** | Low — keep via hub key |
| **4** | `run_london_ny_overlap_breakout_backtest` | `strategies/london_ny_overlap_breakout.py` | Hub-routed | Signal bar then **next open** entry (better lag than close-fill); news-day skip | Uses hub `_simulate_trade_price_levels`; SL-before-TP | **`mock_spread` added to entry and SL** | Config + data + QuantLog events | `test_london_ny_overlap_breakout.py` | Low — keep via hub key |
| **5** | `run_ny_sweep_backtest` | `strategies/ny_sweep_reversion_engine.py` | Hub-routed; limit/FVG path | Limit fill when bar trades level; H1 `ffill`; expire bars | Closer to event/limit than SQE MOC; still OHLC bars | No dedicated fee/slippage haircut found | Spec YAML + data | **No dedicated `test_*ny*sweep*` module found** | Medium — keep; add tests before PROP-03 use |
| **6** | `run_ny_sweep_failure_reclaim_backtest` | `strategies/ny_sweep_failure_reclaim_engine.py` | Hub-routed; HYP-002 | Same bar-fill class; optional news gate | Price-level sim + QuantLog funnel | **Entry half-spread R-adjust** when `broker.mock_spread > 0` | Used by `hyp002_research_pipeline` | Manifest/pipeline tests; engine unit coverage weaker than BB/London | Low–medium — keep via hub; research already routes through `run_backtest` |

### 4.2 Shared fill helpers (hub)

| Helper | Role | Known bias |
|---|---|---|
| `_simulate_trade` | ATR-based SL/TP from entry close | Same-bar SL-before-TP; mid/close ≠ bid/ask (master §13) |
| `_simulate_trade_price_levels` | Absolute SL/TP prices | Same intrabar rule |

These helpers are the closest thing to a **shared execution simulator**. Strategy engines should continue to reuse them rather than invent new fill loops (London already does).

---

## 5. Related interfaces — explicitly **not** the canonical market engine

| Interface | Path | Role | Why not canonical |
|---|---|---|---|
| QuantLog `replay_trace` | `quantlog/.../replay/service.py` | Deterministic **event log** replay | Does not re-simulate market fills |
| FTMO / portfolio MC scripts | `dual_book_ftmo_sim.py`, `pass_acceleration_sim.py`, `portfolio_adaptive_sim.py`, `portfolio_dual_mode.py`, `robustness_and_ftmo.py`, `validation_protocol.py` | Challenge/path / heat sims on assumed `pnl_r` | Account/prop simulators; PROP-01/04 territory; not OHLC strategy backtests |
| `simulate_mr_trade` | `strategies/mean_reversion_eurusd.py` | Diagnostic MR fills | **Not** wired as `backtest.engine` |
| `PaperShadowRunner` | `execution/paper_shadow.py` | Dual scoring + optional `slippage_r` | Orphaned vs LiveRunner; paper path — out of ADR scope |
| VPS paper cycle | `quantbridge/scripts/run_vps_paper_cycle.py` | Regression profile orchestration | Not OHLC backtest |
| Audit snapshot copy | `docs/v1_1_audit_pack_.../backtest_engine.py` | Frozen docs copy | Not runtime |

Master §10 already lists the FTMO scripts as inventory before new build — consistent with keeping them **outside** ADR-001’s canonical market path.

---

## 6. Cross-cutting findings

### 6.1 Point-in-time / look-ahead

| Finding | Evidence status |
|---|---|
| Hub/default SQE entries at bar **close** | **Verified in source** (`_simulate_trade` entry = `close[i]`) |
| London/NY overlap uses **next open** + spread | **Verified in source** |
| Regime / H1 via `reindex(..., method="ffill")` | **Verified** in hub; causal only if higher-TF bars are aligned and fully observed — **alignment completeness NOT re-proven in this audit** |
| Research gates `available_at <= decision_at` | **Absent** on OHLC backtest path (master §11 is PROP-02+ research contract; not implemented here) |
| Rolling `end = now(UTC)` without fixed dates | **Verified** — non-reproducible research windows |

### 6.2 Replay fidelity

| Finding | Evidence status |
|---|---|
| All six are **bar OHLC** engines, not tick/L2 | **Verified** |
| No vectorbt / zipline / backtrader dependency | **Verified** (search) |
| Intrabar SL vs TP order fixed SL-first | **Verified** in hub helpers; matches master §13 conservative stance |
| Partial fills / queue / latency | **Absent** |
| QuantLog emission present on several engines | **Verified** (component / trade events) — supports post-hoc analytics, not fill fidelity |

### 6.3 Cost models

| Path | Fees / spread / slippage |
|---|---|
| Hub SQE default | **None** |
| BB / MACD | Spread **gate** only |
| London/NY overlap | Entry/SL adjusted by `mock_spread` |
| NY sweep reversion | No dedicated haircut found |
| NY sweep failure reclaim | Half-spread R-adjust |
| PROP-03 need | **Net-of-cost** repeatable backtest (`docs/PROP_ROADMAP.md`) — **gap on hub** |

**Unverified assumption:** treating `mock_spread` as a proxy for FTMO execution costs is **not** validated against official product spreads/commissions (PROP-01/02).

### 6.4 Reproducibility

| Lever | Status |
|---|---|
| Fixed `backtest.start_date` + `end_date` | Supported; required for research claims under this ADR |
| Dataset version / content hash in hub result | **Not** standardized on hub output |
| Experiment / strategy IDs | Partial (QuantLog / strategy constants); uneven |
| Seeds | N/A for deterministic bar engines; MC scripts use `seed=42` separately |
| Direct imports of strategy `run_*_backtest` | Possible; bypasses hub logging/window policy — **discourage** |

### 6.5 Ownership

| Layer | Owner |
|---|---|
| Market backtest hub + strategy engines | **quantbuild** |
| Orchestration CLI wrapping hub | **quantmetrics_os** |
| Experiment registry / preregistration consuming runs | **quantresearch** |
| Event replay of emitted logs | **quantlog** (orthogonal) |
| Account / FTMO path sims | **quantbuild scripts** + **quantbridge** account policy (PROP-01) |

---

## 7. Alternatives considered

| Option | Verdict | Reason |
|---|---|---|
| **A. `run_backtest` hub as canonical API; pluggable `backtest.engine`** | **Recommended** | Already the call graph; reuses fills; minimal migration; matches “no new engine” |
| B. Promote one strategy engine (e.g. HYP-002) to sole engine | Reject | Strategy-specific; weaker tests than hub; breaks SQE/BB/MACD/London callers |
| C. New unified framework (event bus / third-party BT lib) | Reject | Explicitly forbidden until ADR; high cost; duplicates hub |
| D. QuantLog replay as “the” backtester | Reject | Log replay ≠ market simulation |
| E. FTMO MC scripts as canonical | Reject | Not OHLC strategy evaluation; wrong abstraction for PROP-03 |
| F. Leave six peer public APIs forever | Reject | Master/PROP require one canonical choice before PROP-03 |

---

## 8. Decision details (proposed normative rules)

Once this ADR is **APPROVED** and merged by owner:

1. **Public API:** All new research/OS/CLI market backtests MUST call `run_backtest(cfg)` (or the QB `backtest` CLI / OS wrapper that does).  
2. **Plugin key:** Strategy-specific logic MAY exist only as `backtest.engine` implementations registered through the hub dispatch.  
3. **No seventh engine** without a new ADR amending this one.  
4. **Research windows:** Empirical claims MUST use fixed UTC `start_date`/`end_date` (no silent rolling-`now`).  
5. **Costs:** PROP-03 net-of-cost work MUST attach to the **hub fill path** (shared helper or single post-fill adjuster), not a parallel simulator. Strategy-local `mock_spread` behavior remains until that shared hook lands; divergence must be documented per engine.  
6. **Non-market sims** (FTMO MC, QuantLog replay, paper) KEEP separate names/docs so they are not confused with the canonical market engine.  
7. **Direct `run_*_backtest` imports** outside hub/tests: treat as legacy; new code must not add them.

---

## 9. Minimal migration path (reuse-first)

| Step | Action | Impl? |
|---|---|---|
| **M0** | Merge this ADR (docs only) after Claude APPROVE + owner | This PR |
| **M1** | Tiny docs/code-comment slice: mark `run_backtest` as canonical in `quantbuild/README` / module docstring; list allowed `backtest.engine` values; point PROP-03 at hub | Next impl issue (post-approve) |
| **M2** | Hub guardrail (optional tiny PR): warn or fail-closed in research mode when dates missing | Separate, small |
| **M3** | Shared cost/slippage hook on `_simulate_trade*` + document per-engine spread semantics | PROP-02/03 dependency |
| **M4** | Add missing unit tests for NY sweep engines before using them as PROP-03 vehicles | Quality gate |
| **M5** | Leave FTMO MC + QuantLog replay untouched except cross-links in docs | No merge into hub |

**Not in path:** rewriting strategy engines, deleting scripts, broker/VPS work, walk-forward.

---

## 10. Acceptance criteria (for this plan PR)

- [x] ≥6 real entrypoints inventoried with paths and interfaces  
- [x] PIT, replay fidelity, costs, reproducibility compared  
- [x] Unverified assumptions labeled  
- [x] One canonical recommendation + rejected alternatives  
- [x] Minimal migration path; reuse existing hub  
- [x] Tiny next implementation slice named (M1)  
- [x] No trading/broker/VPS/framework code in this PR  
- [ ] Claude plan review on **exact head SHA** → APPROVE / REQUEST CHANGES / BLOCK  
- [ ] Owner merge authorization (later; keep draft)

---

## 11. Tiny next implementation slice (after APPROVE)

**Issue-sized M1 only:** documentation + hub module docstring clarifying canonical API and engine plugin keys; optionally a one-line logger notice when `backtest.engine` is unset (SQE default). **No** fill-model rewrite, **no** cost model yet, **no** strategy edits.

Gate: separate implementation PR; Claude code review on that SHA; still no seventh engine.

---

## 12. Risks and open questions

| Risk / question | Impact | Disposition |
|---|---|---|
| Hub has **no** net cost model today | PROP-03 blocked until M3 | Explicit gap; do not fake fees |
| Uneven test coverage (NY sweep) | False confidence if chosen as first PROP-03 strategy | Prefer SQE/BB/London or add tests first |
| Close-fill vs next-open inconsistency across engines | Cross-engine metric incomparability | Document; unify only via shared helpers later |
| `available_at`/`decision_at` absent on OHLC path | Look-ahead policy incomplete vs master §11 | PROP-02 data contract; out of ADR-001 impl |
| Editable installs / multiple cwd entrypoints | Wrong module imported in research scripts | Operational; not solved here |
| Whether default SQE or a simple baseline engine is PROP-03’s first strategy | Product choice | **Not** decided by ADR-001 (engine ≠ strategy) |

---

## 13. Stop

**READY FOR CLAUDE PLAN REVIEW #108**

Review the **exact head commit SHA** of branch `cursor/issue-108-adr001-backtest-plan-3716` (draft PR). Verdict: APPROVE / REQUEST CHANGES / BLOCK. No implementation until plan APPROVE.
