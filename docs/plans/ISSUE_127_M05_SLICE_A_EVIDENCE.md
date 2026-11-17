# Issue #127 — M0.5 Slice A evidence (causal ICT + harness)

**Plan APPROVE SHA:** `8aa855f7d9b64f1a5e1b21c38827f1c9900c069e` (PR #128)  
**Issue:** #127  
**Branch:** `cursor/issue-127-m05-slice-a-3716`  
**Slice B / DTA:** still **BLOCKED** (B-DATA-001)  
**Gates:** PIT Gate A **BLOCKED**; production allowlist empty; no paper/live

## B1 repair (round 1/2) — Claude review @ `7d4fa4f`

| ID | Finding | Handling |
|---|---|---|
| **B1** | Truncation / mutation did not prove dual-direction activation or look-ahead kill for bearish paths | Deterministic `UNIT_SEEDS`; required-true event columns both dirs; bearish fixtures + not-earlier/not-later; `validity_candles=1` both dirs; 12 SOURCE_MUTATION cases (8 targeted + 4 full reverts) all **KILLED** |
| **O1** | Registry vs actual module output columns | `assert_registry_matches_actual_columns` — missing or extra column fails |
| **O2** | MSS semantics unclear | Documented as **repeated state** above/below last confirmed swing (docstring only; behaviour unchanged) |
| **O3** | Separate NY-sweep / FVG logic vs PROP-03 | **Open scope** — recorded below; not admitted as PROP-03 vehicle in this PR |

## Delivered

| Item | Status |
|---|---|
| Confirmation-time pivots / structure / MSS / FVG / sweep / OB / imbalance | Done |
| Deterministic truncation data (`UNIT_SEEDS`, no `hash(unit_id)`) | Done |
| Dual-direction required event activation + per-unit counts | Done |
| Bearish fixtures + exact not-earlier / not-later (sweep/FVG/OB/imbalance) | Done |
| `validity_candles=1` both directions (FVG/OB/imbalance) | Done |
| O1 registry ≡ actual output columns | Done |
| SOURCE_MUTATION 12-case matrix | Done (all KILLED) |
| MSS = repeated state (doc only) | Done |
| NY-sweep/FVG open scope before PROP-03 | Documented (no behaviour change) |
| Historical JSON / workflows | **Not** modified |

## M3 fill-convention note (FVG)

FVG confirmation is the **close** of the third candle. Hub fills today use signal/close conventions. If ADR-001 **M3** switches the shared hook to **next-open**, SQE entries consuming FVG must shift **one bar** so close-confirmation and next-open fill are not mixed silently.

## O2 — MSS repeated-state semantics

`bullish_mss` / `bearish_mss` are **repeated state** flags for bars that trade above/below the **last confirmed** swing level (confirmation-time pivot price, ffilled), not one-shot edge triggers. Restored MSS remains a functionally new feature vs legacy centered swings → new baselines / experiment IDs. Behaviour unchanged by the documentation note.

## O3 — NY-sweep / FVG open scope (before PROP-03)

Separate NY-session sweep engines and any NY-specific FVG wiring remain **out of Slice A**. They are **open scope** and must not be treated as PROP-03-admissible strategy vehicles until M0.5 is merged/validated and the dedicated NY engine unit-test / PIT work (ADR-001 M4 / related) is completed. This PR does not change NY engine code.

## Event counts (truncation fixtures)

Command:

```bash
PYTHONPATH=quantbuild pytest quantbuild/tests/test_m05_truncation_harness.py::test_event_counts_report_for_evidence -q -s
```

| Unit | Config note | Counts (True bars) |
|---|---|---|
| `ict.liquidity_sweep` | `lookback_candles=5` | bullish_sweep=5, bearish_sweep=7 |
| `ict.fair_value_gaps` | (default) | bullish_fvg=1, bearish_fvg=1, in_bullish_fvg=10, in_bearish_fvg=4 |
| `ict.order_blocks` | (default) | bullish_ob=4, bearish_ob=1, in_bullish_ob=18, in_bearish_ob=6 |
| `ict.market_structure_shift` | (default) | bullish_mss=1, bearish_mss=1 |
| `ict.displacement` | (default) | bullish_disp=6, bearish_disp=6 |
| `ict.imbalance_zones` | (default) | bullish_imbalance=1, bearish_imbalance=1, in_bullish_imbalance=10, in_bearish_imbalance=4 |
| `ict.structure_context` | (default) | in_bullish_structure=10, in_bearish_structure=20 |
| `indicators.pivot_highs` | (default) | pivot_high=7 |
| `indicators.pivot_lows` | (default) | pivot_low=7 |
| `indicators.macd` | (default) | bullish_cross=1, bearish_cross=1 |

Missing required True → hard fail via `assert_required_events_fire`.

## SOURCE_MUTATION results (B1 — 12 cases)

Protocol: scratch tree + `PYTHONPATH=<scratch>/quantbuild` + print `module.__file__`.  
Command: `PYTHONPATH=quantbuild pytest quantbuild/tests/test_m05_source_mutation.py -q`

| Case ID | Kind | Result | Killed by |
|---|---|---|---|
| T1_structure_center | targeted | **KILLED** | truncation_mismatches |
| T2_swing_pivot_highs_center | targeted | **KILLED** | truncation / origin flag |
| T3_mss_center | targeted | **KILLED** | truncation_mismatches |
| T4_fvg_bullish_middle | targeted | **KILLED** | not-earlier timing |
| T5_fvg_bearish_middle | targeted | **KILLED** | not-earlier timing |
| T6_sweep_bullish_origin | targeted | **KILLED** | origin-flag assertion |
| T7_sweep_bearish_origin | targeted | **KILLED** | origin-flag assertion |
| T8_ob_bullish_origin | targeted | **KILLED** | origin vs conf timing |
| R1_structure_full_revert | full revert | **KILLED** | truncation_mismatches |
| R2_swing_full_revert | full revert | **KILLED** | truncation_mismatches |
| R3_mss_full_revert | full revert | **KILLED** | truncation_mismatches |
| R4_order_blocks_full_revert | full revert | **KILLED** | bull+bear origin timing |

No import / infrastructure failures in the kill path.

## Tests run (B1 repair)

| Command | Result |
|---|---|
| `PYTHONPATH=quantbuild pytest quantbuild/tests/test_m05_truncation_harness.py -q` | **71 passed** |
| `PYTHONPATH=quantbuild pytest quantbuild/tests/test_m05_source_mutation.py -q` | **13 passed** |
| `PYTHONPATH=quantbuild pytest quantbuild/tests/test_m05_truncation_harness.py quantbuild/tests/test_m05_source_mutation.py -q` | **84 passed** |
| `PYTHONPATH=quantbuild pytest quantbuild/tests -q --disable-socket --allow-unix-socket` | **334 passed** |
| `pytest tests -q` | **175 passed** |

## Stop

**READY FOR CLAUDE DIFF RECHECK #127 Slice A B1** — exact head SHA on draft PR (no merge).
