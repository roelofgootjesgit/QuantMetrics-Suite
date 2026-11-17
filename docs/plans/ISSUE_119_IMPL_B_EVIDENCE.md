# Issue #119 Impl-B evidence — QuantResearch tests + CI

**Branch:** `cursor/issue-119-impl-b-qr-ci-3716`  
**Base:** `main` @ post-#122 merge  
**Plan:** `docs/plans/ISSUE_119_CI_FOLLOWUPS_PLAN.md` §4.3 / O1 / O5 (Claude PLAN APPROVE @ `3651948`)

## Verbatim limitation (O1)

```text
validatie van de echte experimentrecords: NOT RUN in CI (artefacten niet in repo)
```

## hyp003 audit trail (B1)

```text
git diff main -- quantresearch/pipelines/hyp003_preregistration.json
→ empty (file not modified)
```

## Mutation table

| Mutant | Guard | Result |
|---|---|---|
| `validate_temporal_integrity` → always `True` | negative run-before-lock contract | **KILLED** |
| QR CI step removed | preservation positive QR require | **KILLED** |
| QR step without `--disable-socket` | preservation positive QR require | **KILLED** |

## Commands / results

| Command | Result |
|---|---|
| `pytest quantresearch/tests -q --disable-socket --allow-unix-socket` | **56 passed, 0 failed** |
| `pytest tests/test_ci_workflow_preservation.py -q` | **26 passed** (incl. QR step mutants KILLED) |
| `pytest tests -q` | **175 passed** |
| Install path | `-e ./quantresearch` in `requirements.txt`; CI `pip install -r requirements.txt -r requirements-dev.txt` |

## Stop

**READY FOR CLAUDE CODE REVIEW IMPL-B #119**
