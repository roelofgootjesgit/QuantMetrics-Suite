# Issue #127 — M0.5 plan: parquet timestamp audit + causal feature restoration

**Status:** PROPOSED — plan repair after Claude **REQUEST CHANGES** @ `fca1d44`  
**Issue:** https://github.com/roelofgootjesgit/QuantMetrics-Suite/issues/127  
**Draft PR:** https://github.com/roelofgootjesgit/QuantMetrics-Suite/pull/128  
**Tech-lead briefs:** issue comment `6961024293`; owner follow-up (REQUEST CHANGES planupdate) — **PLAN ONLY**  
**Branch:** `cursor/issue-127-m05-timestamp-plan-3716`  
**Base:** `main` @ `42e31d8ae07418c89bc050b6fe45412b21b30f25` (ADR-001 via #126)  
**Prerequisite ADR:** `docs/adr/ADR-001-canonical-backtest-engine.md`  
**Mode:** PLAN ONLY — no production code, no historical-record edits, no workflow/CI YAML, no trading/broker/VPS  
**Stop line:** **READY FOR CLAUDE M0.5 PLAN DIFF RECHECK #127**

**Gates unchanged:** PROP-03 BLOCKED; PIT Gate A **BLOCKED**; production Cushing allowlist **empty**.

---

## Change log (repair vs `fca1d44`)

| ID | Change |
|---|---|
| **B1** | §6 + Slice A expanded: **FVG**, **liquidity sweep**, **order blocks**; generic truncation harness over **all** `strategy_modules/` + `indicators/` output columns; missing coverage **fails** |
| **B2** | Exact per-event **confirmation-time** rules; no back-write to origin bar; **not-earlier** and **not-later** tests; trailing-only pivot = explicit strategy change |
| **O1** | MSS degeneration documented; repaired MSS = **new feature** → new baseline + new experiment IDs |
| **O2** | Fixtures: ties, short series, positive events, `validity_candles=1`; never-fires ≠ pass |
| **O3** | Mandatory killed SOURCE_MUTATION for structure_context, swing, MSS, FVG, sweep, OB — commands / `__file__` / failing node ids |
| **+** | M15→H1 aggregation probe (`label`/`closed`); H1-from-M15 design option (does **not** clear DTA); CEO-analyst text updated for default SQE entry triggers |

---

## Claude REQUEST CHANGES — acceptance checklist

| ID | Requirement | In this plan? |
|---|---|---|
| **B1** | FVG / sweep / OB in §6 + Slice A; harness covers all modules/indicators + all output columns; silent skip forbidden | [x] §6.2–6.3, §7 Slice A, §8 |
| **B2** | Exact confirmation rules; no origin back-write; not-earlier + not-later; trailing-only = strategy change | [x] §6.4 |
| **O1** | MSS degeneration; repaired MSS = new feature / new experiment IDs | [x] §6.5 |
| **O2** | Fixtures (ties, short, positive, `validity_candles=1`); never-fire ≠ pass | [x] §8.2 |
| **O3** | SOURCE_MUTATION kill evidence for ≥ structure, swing, MSS, FVG, sweep, OB | [x] §8.3 |
| **+probe** | M15→H1 agg probe with `label`/`closed`, full OHLC, incomplete hours; relative only | [x] §5.2 P6, §5.4 |
| **+option** | H1 derived from M15 as design option; does not lift DTA | [x] §5.4 |
| **+CEO** | Default SQE entry triggers hit; MSS non-fire in default config = **INDEPENDENT_REVIEWER** | [x] §9 |

Cursor did **not** independently re-run Claude’s truncation experiments; those counts remain **INDEPENDENT_REVIEWER**.

---

## 1. Objective

1. Audit **real** M15/H1 parquet timestamp semantics and provenance; separate **VERIFIED** / **UNVERIFIED**.  
2. If real OHLC absent: **B-DATA-001** + fail-closed **DTA** — no guessed `+1h` / open-close.  
3. Design **M0.5** so **all** ICT/indicator features used by SQE (including FVG, sweep, OB) become **confirmation-time causal**, with generic truncation harness + source mutants in root CI.  
4. Preserve historical records; mark prior SQE/structure conclusions **`UNVERIFIED_LOOKAHEAD`**; CEO-analyst notice before treating as evidence.

**There is currently no reliable basis to judge whether SQE “works”** until M0.5 (Slice A at minimum on synthetic data, Slice B + DTA for HTF) is validated. Magnitude of result distortion from look-ahead remains **unknown** (no PnL inference from label diffs).

---

## 2. Non-goals (this PR)

| Out of scope | Why |
|---|---|
| Any `.py` / workflow / CI YAML edits | Plan-only repair |
| Implementing causal features | After plan APPROVE |
| Mutating historical experiment JSON | Preserve; label only |
| Guessing timestamp convention | B-DATA-001 |
| Inferring PnL bias from Claude % | Forbidden |
| Merge | Draft only |

---

## 3. Audit method (commands actually run)

**Host:** Linux agent, Python 3.12.3. Base `42e31d8…`.

```bash
find . -name '*.parquet' | head
rg -n 'parquet|market_cache' quantbuild/.gitignore
rg -n 'center=True|bullish_fvg|bullish_sweep|bullish_ob' quantbuild/src/quantbuild --glob '*.py'
ls quantbuild/src/quantbuild/strategy_modules/ict quantbuild/src/quantbuild/indicators
python3 -c "import importlib.util as u; print(u.find_spec('dukascopy_python'), u.find_spec('pyarrow'))"
```

| Probe | Result |
|---|---|
| Real `*.parquet` OHLC | **None** (gitignored cache absent) |
| `dukascopy_python` / `pyarrow` | **Not installed** |
| ICT modules present | structure_context, MSS, FVG, liquidity_sweep, order_blocks, displacement, imbalance_zones, … |
| Claude truncation re-run by Cursor | **NOT RUN** |

---

## 4. Timestamp & provenance audit

### 4.1 VERIFIED

| ID | Finding | Evidence |
|---|---|---|
| **V1–V10** | Cache path, gitignore, naive UTC strip, bid-side Dukascopy, H1→M15 `ffill`, London “open time” **comment** | Unchanged from prior plan §4.1 |
| **V11** | Centered pivots/MSS (`center=True`) | `structure_context.py`, `swing.py`, `market_structure_shift.py` |
| **V12** | Claude structure truncation **113/537** (21.0%) | **INDEPENDENT_REVIEWER** — not PnL |
| **V13** | Default SQE runs **liquidity_sweep**, **fair_value_gaps**, **order_blocks**, **displacement**, **MSS**, **structure_context** in `_compute_modules_once` | `strategies/sqe_xauusd.py` |
| **V14** | FVG writes flags using a **3-candle** gap test but places True on the **middle** index (`bullish_fvg[1:-1] = bull_mask[2:]`) | `fair_value_gaps.py` ~L48–60 |
| **V15** | Sweep sets True on **sweep bar `i`** after scanning **future** `j ∈ [i, i+rev_n]` for reversal | `liquidity_sweep.py` ~L56–70 |
| **V16** | OB sets True on **origin bar `i`** using **future** `high/low[i+1 : i+1+n_c]` | `order_blocks.py` ~L42–54 |
| **V17** | MSS non-firing under default config in Claude’s experiment | **INDEPENDENT_REVIEWER** (not re-run by Cursor) |

### 4.2 UNVERIFIED

| ID | Question |
|---|---|
| **U1–U7** | Open vs close index, DST, availability lag, `ffill` ≡ completed H1, cache provenance, bid vs venue, DST session edges — **unchanged**; need real data + DTA |
| **U8** | Quantitative impact of FVG/sweep/OB/MSS look-ahead on SQE PnL / trade counts | **Unknown** — do not invent |

### 4.3 Blocker **B-DATA-001**

No authentic M15/H1 parquet in this environment/git. HTF absolute convention + availability lag remain blocked. Slice A may use **synthetic** OHLC after plan APPROVE. Slice B stays DTA-gated.

---

## 5. Fail-closed data contract (DTA) + probes

### 5.1 DTA fields (unchanged essence)

`symbol`, `timeframe`, `path`, `content_sha256`, `source`, `offer_side`, **`index_semantics`** (`bar_open_utc` \| `bar_close_utc` \| `other`), `timezone_storage`, `dst_policy`, `bar_complete_rule`, `attested_by` / `attested_at_utc` / `method`, `probe_results`.

Missing/unknown semantics → fail closed for research HTF use.

### 5.2 Probe suite

| Probe | Role |
|---|---|
| **P1–P5** | Spacing, open/close heuristic vs vendor docs, DST span, HTF join leakage, provenance re-fetch (prior plan) |
| **P6 — M15→H1 aggregation** | From an attested M15 series, aggregate to H1 with **explicit** pandas/`resample` **`label`** and **`closed`** parameters documented in the probe config. Compare **full OHLC** (and volume if present) to vendor/stored H1 where available. **Incomplete hours:** drop or quarantine partial buckets; never silently treat as complete. **Scope:** tests **relative** labeling consistency between M15 and derived H1. **Does not** prove absolute open/close convention of the vendor file, nor publication/`available_at` lag — those remain **separate** DTA evidence (U1/U3). |

### 5.3 Interim policy

All structure/regime/**SQE-entry** dependent historical conclusions: **`UNVERIFIED_LOOKAHEAD`** / **`VALIDATION_REQUIRED`**. No hard-coded `+1h`.

### 5.4 Design option — derive H1 from M15

| Option | Pros | Cons | DTA impact |
|---|---|---|---|
| Keep separate H1 parquet + attested join | Matches current loaders | Needs U1/U3 solved | Still requires DTA |
| **Derive H1 from M15** via P6 (`label`/`closed` fixed in code + tests) | Single source series; relative consistency enforceable in CI with synthetics + real M15 | Still needs M15 DTA for absolute time/availability; incomplete hours policy; may diverge from broker H1 | **Does not lift B-DATA-001 / DTA** for absolute convention or lag |

Decision deferred to Slice B design after plan APPROVE; documenting the option is mandatory so implementers do not treat derivation as a DTA bypass.

---

## 6. Affected causal paths (expanded)

### 6.1 Prior surfaces (ADR-001)

structure_context, swing pivots / `last_swing_*`, MSS, SQE, H1 gate, regime, NY engines, London regime labels.

### 6.2 Default SQE entry / ICT modules — **look-ahead / back-write**

| Module | Path | Current defect (VERIFIED in source) | SQE use |
|---|---|---|---|
| **FVG** | `ict/fair_value_gaps.py` | 3-candle gap; flag on **middle** bar needs **third** candle known | Entry pillar (`in_*_fvg`); default entry combo |
| **Liquidity sweep** | `ict/liquidity_sweep.py` | Flag on **sweep** bar after **future** reversal within `reversal_candles` | Entry pillar / combo (`*_sweep`) |
| **Order blocks** | `ict/order_blocks.py` | Flag on **origin** bar using **future** `min_candles` extrema | `in_*_ob` columns (available to SQE) |
| **MSS** | `ict/market_structure_shift.py` | `center=True` swings; default config may **never fire** | Trend pillar module list |
| **Displacement** | `ict/displacement.py` | Rolling sum looks **backward** only (likely causal) — still **must** be in harness | Entry combo |
| **Imbalance zones** | `ict/imbalance_zones.py` | Include in harness; classify causal vs leak in Slice A inventory | Module present |
| **Structure** | `ict/structure_context.py` | Centered pivots | Structure filters / H1 / regime |
| **Regime** | `regime/detector.py` | Via structure + ffill | Hub / NY / London |

**Conclusion:** Standard SQE **entry triggers** (sweep + FVG at minimum; OB columns computed every run) are in the look-ahead set. Basis to evaluate SQE edge: **absent** until M0.5.

### 6.3 Generic truncation harness (normative)

Harness discovers **every** calculatable unit under:

- `quantbuild/src/quantbuild/strategy_modules/` (including `ict/`, `regime/`, `news_gate` if it emits frame columns)
- `quantbuild/src/quantbuild/indicators/`

For each unit, after `calculate` / public indicator call, assert truncation invariance on **every output column** added or overwritten (bool/float/object).  

| Rule | Detail |
|---|---|
| Registration | Explicit registry list checked into tests; **OR** auto-discovery with allowlist |
| Missing module | If a module file exists under those trees but is **not** registered → **test FAIL** (no silent skip) |
| Empty fire | A module that never emits True/non-null on fixtures **fails** positive-event requirements (§8.2) — cannot “pass” truncation alone by being all-False |
| Root CI | Harness runs in **root** pytest path used by CI after impl (plan only here) |

### 6.4 Confirmation-time rules (no origin back-write)

**Invariant:** event flag / level becomes True only on the bar index at which the **last required observation** is known. **Never** write back onto an earlier origin bar.

| Event | Confirmation bar (normative) | Forbidden |
|---|---|---|
| **Pivot** (structure / swing) | First bar at or after origin where the full **right window** of `pivot_bars` (or MSS `swing_lookback`) has closed | `center=True` labeling on origin before right side exists |
| **FVG** | **Third candle** of the 3-candle pattern (the bar that closes the gap test) | Writing `bullish_fvg`/`bearish_fvg` on the middle/origin bar |
| **Sweep** | Bar of the **first valid reversal** within `reversal_candles` after the sweep excursion | Setting `*_sweep` on the sweep bar when reversal is still in the future |
| **Order block** | Bar at which the **full** confirmation condition is known (after `min_candles` forward extrema + move% satisfied) | Setting `*_ob` on the origin candle while future bars unread |
| **MSS** | Break bar evaluated only against **causally available** swing levels (confirmation-shifted or trailing policy) | Centered swing highs/lows |

**Timing tests (each event type):**

1. **Not earlier:** on prefix ending before confirmation, feature at confirmation index is false/absent.  
2. **Not later:** on prefix that **includes** the confirmation bar, feature becomes true **on that same index** (not delayed an extra bar beyond the rule).  

**Trailing-only pivots:** allowed only as an **explicit strategy/product change** (separate decision + config flag + experiment IDs). Default M0.5 repair path is **confirmation-time shift**, not silent trailing redefinition.

### 6.5 MSS degeneration (O1)

| Topic | Plan requirement |
|---|---|
| Current behavior | Centered swings + threshold; Claude reported **no fires** under default SQE MSS config → **INDEPENDENT_REVIEWER** |
| After causal repair | Confirmation-shifted (or explicitly trailing) swings change semantics and likely fire-rate |
| Research treatment | Restored MSS = **functionally new feature** |
| Governance | **New baseline** + **new experiment IDs**; do not attach repaired-MSS metrics to old EXP/HYP IDs; old MSS-dependent claims stay **`UNVERIFIED_LOOKAHEAD`** |

---

## 7. Ordered implementation slices

### Slice A — Causal ICT/indicators + harness (synthetic OK after APPROVE)

| Item | Spec |
|---|---|
| Repair | structure_context, swing, MSS, **FVG**, **sweep**, **OB** (+ displacement/imbalance/others per harness inventory) |
| Rules | §6.4 confirmation-time; no origin back-write |
| Tests | Generic truncation harness §6.3; not-earlier/not-later §6.4; fixtures §8.2 |
| Mutants | §8.3 minimum set |
| CI | Root CI includes harness |
| HTF | **Not** required for Slice A unit causality |

### Slice B — HTF availability (DTA / B-DATA-001)

Attested semantics; P6 agg probe; optional H1-from-M15 **without** claiming DTA bypass; regime/H1-gate masks truncation-clean.

### Slice C — Dataset hash + fail-closed research dates (ADR M2)

### Slice D — Labels / CEO-analyst notice / cross-links (no JSON body rewrites)

**PROP-03 unblock:** A + B green, DTA satisfied, mutants killed, independent review on impl SHA.

---

## 8. Truncation, fixtures, mutants

### 8.1 Truncation invariance

```text
For every harness feature column c and full series D:
  ∀ i in valid range:
    c(D[: i+1 ]).iloc[i]  ==  c(D).iloc[i]
```

Zero mismatches required for all registered output columns (including quality/in_* rolling columns once defined causally).

### 8.2 Fixtures (O2) — mandatory

| Fixture | Purpose |
|---|---|
| **Ties** | Equal highs/lows at pivot/sweep thresholds — deterministic, documented winner |
| **Short series** | Length &lt; lookback/validity — no crash; no false positives from empty windows |
| **Positive events** | Hand-built paths that **must** fire exactly one confirmation index per event type |
| **`validity_candles=1`** | FVG/OB “in_*” windows — causal persistence edge case |
| **Never-fire guard** | Config/data where a buggy always-False module would “pass” truncation → **fail** unless positive-event fixture passes for that module |

### 8.3 SOURCE_MUTATION (O3) — minimum kill set

For **each** of: `structure_context.py`, `swing.py` (pivots), `market_structure_shift.py`, `fair_value_gaps.py`, `liquidity_sweep.py`, `order_blocks.py`:

1. Copy package tree to scratch; apply mutant that restores future leak / origin back-write.  
2. `PYTHONPATH=<scratch>/quantbuild/src` (or attested layout);  
3. `python -c "import …; print(module.__file__)"` must print **scratch** path.  
4. Run focused harness + not-earlier tests; record **failing node ids**.  
5. Discard scratch. Label results **SOURCE_MUTATION** only if steps 2–3 verified.

Monkeypatch-only checks remain **MONKEYPATCH_SELFTEST** and do **not** satisfy O3.

Impl evidence table (to be filled in impl PR, not this plan):

| Mutant target | Command | `__file__` | Failing test IDs | Result |
|---|---|---|---|---|
| structure_context | _(impl)_ | _(impl)_ | _(impl)_ | |
| swing pivots | | | | |
| MSS | | | | |
| FVG | | | | |
| sweep | | | | |
| OB | | | | |

---

## 9. Historical research posture + CEO-analyst text

| Item | Policy |
|---|---|
| EXP-2021-2025 / HYP-002 / HYP-003 / SQE runs | **`UNVERIFIED_LOOKAHEAD`** until M0.5+DTA clean rerun |
| Historical files | **Do not mutate** |
| New work after repair | New experiment IDs; MSS especially = new baseline (O1) |

### CEO-analyst notice (template)

> We do **not** yet have a reliable basis to judge whether **SQE** works. Independent review found look-ahead / future-bar use not only in structure pivots and MSS, but also in **default SQE entry-path modules** (liquidity sweep, fair value gaps, order-block columns computed every run). MSS under default configuration was reported as **non-firing** in that review. Truncation label-change rates (e.g. 113/537) are **INDEPENDENT_REVIEWER** findings and are **not** P&L impact estimates. All related historical metrics are **`UNVERIFIED_LOOKAHEAD`** until M0.5 causal repair and timestamp attestation complete. PIT Gate A remains **BLOCKED**; production allowlist empty. No promotion or capital decisions on these numbers.

---

## 10. Acceptance criteria (this plan repair PR)

- [x] B1/B2/O1–O3 checklist table complete  
- [x] FVG / sweep / OB + full-module harness in §6 / Slice A  
- [x] Confirmation rules + not-earlier/not-later + trailing-only policy  
- [x] MSS new-feature governance  
- [x] Fixtures + never-fire guard  
- [x] SOURCE_MUTATION kill set specified  
- [x] M15→H1 P6 probe + H1-from-M15 option (DTA intact)  
- [x] CEO-analyst text updated; INDEPENDENT_REVIEWER provenance kept  
- [x] No code / historical / workflow changes  
- [ ] Claude **M0.5 PLAN DIFF RECHECK** on exact head SHA  
- [ ] Owner merge authorization (later; keep draft)

---

## 11. After APPROVE

1. **Slice A impl** with synthetic OHLC + harness + mutants (no PROP-03).  
2. Owner DTA sample → P1–P6 → **Slice B**.  
3. CEO-analyst notice issued when communicating status.

---

## 12. Stop

**READY FOR CLAUDE M0.5 PLAN DIFF RECHECK #127**

Review the **exact head commit SHA** of draft PR #128. Verdict: APPROVE / REQUEST CHANGES / BLOCK. No implementation in this PR.
