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

## Mutation / selftest table (honesty reclassification — #124 M1)

| Claim | Classification | Result |
|---|---|---|
| monkeypatch `validate_temporal_integrity` → always `True` | **MONKEYPATCH_SELFTEST** (renamed in #124; not source mutation) | negative contract fails as designed |
| QR CI step removed | workflow text mutant vs preservation guard | **KILLED** |
| QR step without `--disable-socket` | workflow text mutant vs preservation guard | **KILLED** |
| Claude source edits to `preregistration.py` / ledger | **INDEPENDENT_REVIEWER** | cited on #119 review only; Cursor **SOURCE_MUTATION NOT RUN** in #119 Impl-B |

## Commands / results

| Command | Result |
|---|---|
| `pytest quantresearch/tests -q --disable-socket --allow-unix-socket` | **56 passed, 0 failed** |
| `pytest tests/test_ci_workflow_preservation.py -q` | **26 passed** (incl. QR step mutants KILLED) |
| `pytest tests -q` | **175 passed** |
| Install path | `-e ./quantresearch` in `requirements.txt`; CI `pip install -r requirements.txt -r requirements-dev.txt` |

## Stop

**READY FOR CLAUDE CODE REVIEW IMPL-B #119**
