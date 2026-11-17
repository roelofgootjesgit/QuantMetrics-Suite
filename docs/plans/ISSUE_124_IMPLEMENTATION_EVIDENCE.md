# Issue #124 — implementation evidence (M1 / D1 / E1+C1)

**PR:** https://github.com/roelofgootjesgit/QuantMetrics-Suite/pull/125  
**Branch:** `cursor/issue-124-qr-followup-plan-3716`  
**Plan APPROVE SHA:** `7e8b4a52cce0e76fa36b476bf0fe3afee74300ad`  
**Tech-lead Impl auth:** PR comment `6960147289` (mandatory C1)

## Evidence classification taxonomy

| Label | Meaning |
|---|---|
| **MONKEYPATCH_SELFTEST** | Runtime stub at call site; does **not** prove source edit detection |
| **SOURCE_MUTATION** | Intentional edit to production `.py` source, run tests, restore — **NOT RUN** by Cursor in this PR |
| **INDEPENDENT_REVIEWER** | Claude-reported source mutants on Impl-B review — cited only; not re-attributed to Cursor |

## M1 — honest selftest rename

- Renamed `test_mutation_validate_temporal_integrity_always_true_killed` →  
  `test_selftest_negative_contract_fails_if_temporal_integrity_always_true`
- Classified **MONKEYPATCH_SELFTEST** in docstring
- **SOURCE_MUTATION:** NOT RUN (this PR)
- Claude source mutants: **INDEPENDENT_REVIEWER** only

## D1 — synthetic green-path dedupe

- Removed `test_validate_synthetic_session_style_completed_experiment` (redundant helper call)
- Kept primary synthetic success + fail-closed missing/Windows suite_root tests

## E1 / C1 — committed EXP machine-dependent validation

```text
validatie van de echte experimentrecords: NOT RUN in CI (artefacten niet in repo)
```

| Branch | Assert |
|---|---|
| configured `suite_root` not a dir | `errs == [SUITE_ROOT_ERR]` exactly |
| configured `suite_root` is a dir | `errs == []` (full artefact validation) |
| path-scoped `Path.is_dir` makes root look present; runs missing | exact QuantOS run dir + canonical_artifact_path errors — **not** auto-green |

CI (POSIX) hits unavailable-root branch (`C:/...` is not a local directory).

## Hard invariants

```text
git diff main -- quantresearch/pipelines/hyp003_preregistration.json → empty
git diff main -- 'quantresearch/experiments/**/experiment.json' → empty
```

No workflow / governance / production / broker changes.

## Commands / results

| Command | Result |
|---|---|
| `pytest quantresearch/tests -q --disable-socket --allow-unix-socket` | **58 passed, 0 failed** |
| `pytest tests/test_ci_workflow_preservation.py -q` | **26 passed** |
| `pytest tests -q` | **175 passed** |
| C1 unavailable-root (POSIX) | both EXP ids → exact `[SUITE_ROOT_ERR]` |
| C1 `Path.is_dir` scoped monkeypatch | exact run-dir + canonical_artifact errors (not auto-green) |
| `SOURCE_MUTATION` local source edits | **NOT RUN** |
| hyp003 / experiment.json vs main | **empty diffs** |

## Stop

**READY FOR CLAUDE CODE REVIEW #124**
