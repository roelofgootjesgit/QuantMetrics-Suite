# Issue #127 — M0.5 Slice A evidence (causal ICT + harness)

**Plan APPROVE SHA:** `8aa855f7d9b64f1a5e1b21c38827f1c9900c069e` (PR #128)  
**Issue:** #127  
**Branch:** `cursor/issue-127-m05-slice-a-3716`  
**Slice B / DTA:** still **BLOCKED** (B-DATA-001)  
**Gates:** PIT Gate A **BLOCKED**; production allowlist empty; no paper/live

## Delivered

| Item | Status |
|---|---|
| Confirmation-time pivots / structure / MSS / FVG / sweep / OB / imbalance | Done |
| Generic truncation harness + disk coverage fail | `quantbuild/.../testing/truncation_harness.py` + tests |
| Not-earlier / not-later + fixtures (`validity=1`, ties, short, positive) | `test_m05_truncation_harness.py` |
| SOURCE_MUTATION kills (6 targets) | `test_m05_source_mutation.py` |
| FVG close-confirm vs future M3 next-open note | Module docstring + below |
| Historical JSON / workflows | **Not** modified |
| UNVERIFIED_LOOKAHEAD / CEO-analyst | Policy unchanged; MSS = new feature (module docstring) |

## M3 fill-convention note (FVG)

FVG confirmation is the **close** of the third candle. Hub fills today use signal/close conventions. If ADR-001 **M3** switches the shared hook to **next-open**, SQE entries consuming FVG must shift **one bar** so close-confirmation and next-open fill are not mixed silently.

## SOURCE_MUTATION results (local)

| Target | Command | `__file__` under scratch | Killed by |
|---|---|---|---|
| swing pivots | `pytest quantbuild/tests/test_m05_source_mutation.py::test_mutation_swing_center_true_killed` | yes (tmp pytest path) | truncation_mismatches |
| FVG | `...::test_mutation_fvg_middle_backwrite_killed` | yes | third-candle timing / truncation |
| sweep | `...::test_mutation_sweep_origin_flag_killed` | yes | origin-flag assertion |
| OB | `...::test_mutation_ob_origin_flag_killed` | yes | origin vs conf timing |
| MSS | `...::test_mutation_mss_center_true_killed` | yes | truncation_mismatches |
| structure_context | `...::test_mutation_structure_context_center_killed` | yes | truncation_mismatches |

Protocol: scratch tree + `PYTHONPATH=<scratch>/quantbuild` + print `module.__file__`.

## Tests run

| Command | Result |
|---|---|
| `pytest quantbuild/tests/test_m05_truncation_harness.py test_m05_source_mutation.py -q` | **35 passed** |
| `pytest quantbuild/tests -q --disable-socket --allow-unix-socket` | **285 passed** |
| `pytest tests -q` | **175 passed** |

## Stop

**READY FOR CLAUDE CODE REVIEW #127 Slice A** — exact head SHA on draft PR.
