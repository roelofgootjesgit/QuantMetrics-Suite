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

### SOURCE_MUTATION protocol (scratch copy — when actually executed)

Editable `pip install -e ./quantresearch` can still import the **original** tree. Before claiming SOURCE_MUTATION:

1. Copy package tree to a scratch dir; apply the source edit only there.
2. Run with `PYTHONPATH=<scratch-copy>/quantresearch` (prepend; do not rely on editable alone).
3. Verify `import quantresearch.preregistration as m; print(m.__file__)` (and ledger) points **inside** the scratch copy.
4. Run `pytest quantresearch/tests -q --disable-socket --allow-unix-socket`; record failing node ids; restore/discard scratch.
5. Label results `SOURCE_MUTATION` only if steps 2–3 were verified. Reviewer-reported mutants stay `INDEPENDENT_REVIEWER`.

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

## B1 repair (REQUEST CHANGES @ `3205b29`)

- `test_committed_exp_existing_suite_root_missing_runs_not_auto_green`: host-independent scoped `Path.is_dir` — True suite_root, **False** `expected_run`/`expected_cap`, else `real_is_dir` (no recursion).
- Added `test_committed_exp_missing_artifact_false_wins_over_rich_host_simulation`: rich-host True then missing-artefact False wins → exact two errors.
- Deterministic `assert … is False` on patched paths (not host FS).

## Commands / results

| Command | Result |
|---|---|
| focused `test_committed_exp_suite_root.py -v` | **4 passed** |
| `pytest quantresearch/tests -q --disable-socket --allow-unix-socket` | **59 passed, 0 failed** |
| `pytest tests -q` | **175 passed** |
| `SOURCE_MUTATION` local source edits | **NOT RUN** |
| hyp003 / experiment.json vs main | **empty diffs** |

## Stop

**READY FOR CLAUDE B1 DIFF RECHECK #124**
