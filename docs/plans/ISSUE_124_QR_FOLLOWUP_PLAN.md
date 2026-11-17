# Issue #124 — QuantResearch follow-up: honest mutation evidence, EXP read-only check, synthetic dedupe (PLAN)

**Issue:** https://github.com/roelofgootjesgit/QuantMetrics-Suite/issues/124  
**Tech-lead brief:** issue comment `6960029841` (2026-11-17 21:26 Europe/Amsterdam) — DESIGN ONLY  
**Branch:** `cursor/issue-124-qr-followup-plan-3716`  
**Base:** `main` @ `822cbc6` (squash merge of #119 Impl-B / PR #123)  
**Reviewed Impl-B head (historical):** `57d28ee48016843a7a8aaf2abb82e8768a6fdd75`  
**Mode:** PLAN ONLY — no production code, no CI workflow edits, no historical research record changes  
**Stop line:** **READY FOR CLAUDE PLAN REVIEW #124**

**Constraints (unchanged):** PIT Gate A **BLOCKED**; production allowlist empty; no broker / VPS / paper / live; no CI soft-fail / xfail / deselection; #105 branch protection is **owner-parked / closed** (`protect-main` active per tech-lead) — **do not change governance settings**.

---

## 1. Objective

Close three non-blocking Claude findings after #119 Impl-B without weakening fail-closed research or CI policy:

| ID | Finding | Desired outcome |
|---|---|---|
| **M1** | `test_mutation_validate_temporal_integrity_always_true_killed` is a **monkeypatch selftest**, not source-level mutation evidence | Honest naming/docs; optional real source-mutation methodology; no false “KILLED mutant” claims from Cursor unless actually reproduced |
| **E1** | Optional offline check on committed EXP-2021-2025 records | Read-only assert that `validate_experiment` fails **only** for unavailable `suite_root` **if** evidence confirms sole error; keep full artefact validation `NOT RUN` |
| **D1** | Possible duplicate synthetic ledger green-path tests | Remove redundancy only if no distinct coverage is lost |

---

## 2. Non-goals (explicit)

| Out of scope | Why |
|---|---|
| Edits to `quantresearch/pipelines/hyp003_preregistration.json` | Scientific audit trail (#119 B1) |
| Edits to committed `experiments/**/experiment.json` or QuantOS run trees | Historical records; artefacts absent |
| Weakening suite_root fail-closed / inventing artefacts | O1 / Gate A policy |
| Changes to `.github/workflows/ci.yml` fail-closed guards (#104/#119) | Tech-lead: preserve offline guards and CI rules |
| Branch protection / ruleset changes (#105) | Owner-closed; do not touch governance |
| Broker / VPS / trading / allowlist | AGENTS.md |
| Claiming Cursor reproduced Claude’s source mutants without running them | Honesty rule in brief |

---

## 3. Audit evidence (commands actually run — this plan branch)

**Host:** Linux agent, Python **3.12.3**. Repo at `822cbc6`. No broker/live scripts. No source files mutated for mutant reproduction in this plan stage.

### 3.1 M1 — monkeypatch vs source mutation

**Current test** (`quantresearch/tests/test_preregistration.py`):

```python
def test_mutation_validate_temporal_integrity_always_true_killed(monkeypatch):
    ...
    monkeypatch.setattr(preg, "validate_temporal_integrity", lambda *a, **k: True)
    with pytest.raises(AssertionError):
        _assert_negative_run_before_lock(d, "2026-05-04T10:00:00Z")
```

**Classification:**

| Claim type | Status |
|---|---|
| Proves negative contract helper fails if temporal check always returns True **at call site** | **True** (runtime monkeypatch selftest) |
| Proves a **source** edit to `preregistration.py` would be detected by the QR suite | **False** — no file edit; name/`ISSUE_119_IMPL_B_EVIDENCE.md` over-claim “mutation KILLED” |
| Claude-reported source mutants (always-True; `<`→`<=`; skip prereg temporal; drop ledger suite_root error) | **NOT RUN by Cursor** on this plan branch — cite Claude only; do not re-attribute |

**Existing honest negative coverage already present (keep):**

- `test_hyp003_style_negative_tmp_run_before_lock_rejected` — real negative data path
- `test_valid_true_requires_lock_before_run` — v1 error when lock after run
- Historical hyp003 file test — locked + recorded start (no JSON edit)

### 3.2 E1 — committed EXP-2021-2025 `validate_experiment` (read-only)

```text
PYTHONPATH=quantresearch python3 -c "from quantresearch.ledger import validate_experiment; ..."

EXP-2021-2025-throughput-discovery-v1
  n_errs 1
  - suite.suite_root missing or invalid — cannot verify QuantOS artifacts
  suite_root in JSON: C:/Users/Gebruiker/quantmetrics-suite

EXP-2021-2025-session-relax-watchlist-v1
  n_errs 1
  - suite.suite_root missing or invalid — cannot verify QuantOS artifacts
  suite_root in JSON: C:/Users/Gebruiker/quantmetrics-suite

links.quantos_run_dir / canonical_artifact_path relative trees under cwd:
  quantmetrics_os/runs/EXP-2021-2025-throughput-discovery-v1 → NOT a directory
  quantmetrics_os/runs/EXP-2021-2025-session-relax-watchlist-v1 → NOT a directory
```

**Conclusion for optional CI/test:** On current `main`, both tracked EXP ids fail with **exactly one** error string matching unavailable/invalid `suite_root`. That is sufficient to justify a **narrow** read-only regression test **if** implemented carefully (assert `errs == [that exact message]` or `errs == […]` with sole membership).  

**Still mandatory evidence line (verbatim, unchanged policy):**

```text
validatie van de echte experimentrecords: NOT RUN in CI (artefacten niet in repo)
```

Meaning: CI does **not** claim full QuantOS artefact / edge_verdict / promotion consistency validation for these EXP folders — only the known fail-closed `suite_root` gate observation.

### 3.3 D1 — synthetic ledger green-path duplication

| Test | Behaviour |
|---|---|
| `test_validate_synthetic_completed_experiment_with_suite_root` | tmp suite + completed synthetic → `validate_experiment == []` |
| `test_validate_synthetic_session_style_completed_experiment` | **Same helper**, only different `eid` + `quantos_rel`; still empty `suite` metadata shape; **no** distinct session/watchlist validation rules exercised |

**Classification:** second test is **redundant** for validator behaviour. Distinct coverage that **must stay**:

- `test_validate_fail_closed_missing_suite_root`
- `test_validate_fail_closed_windows_suite_root`
- Other pre-existing ledger tests (pre_run, lineage, etc.)

---

## 4. Proposed design (implementation PR — not this PR)

### 4.1 M1 — honest mutation / selftest policy

**Recommended file diffs (Impl PR):**

| File | Change |
|---|---|
| `quantresearch/tests/test_preregistration.py` | Rename `test_mutation_validate_temporal_integrity_always_true_killed` → e.g. `test_selftest_negative_contract_fails_if_temporal_integrity_always_true`; docstring must say **monkeypatch selftest / regression**, **not** source mutation |
| `docs/plans/ISSUE_119_IMPL_B_EVIDENCE.md` (optional clarifying note) **or** Impl evidence for #124 | Retract / annotate prior “mutation KILLED” row: classify as selftest; point to Claude independent source mutants as external evidence **or** to new local source-mutation protocol below |

**Source-level mutation methodology (for Impl evidence pack — run intentionally, restore after):**

1. Worktree or temporary checkout; never leave mutants on the PR branch tip under review.  
2. Apply **one** source edit at a time under `quantresearch/quantresearch/`:  
   - M-A: `validate_temporal_integrity` body → `return True`  
   - M-B: strict `<` → `<=` in temporal compare  
   - M-C: bypass / delete the prereg `validate_temporal_integrity` call in `validate_preregistration_v1`  
   - M-D: remove / no-op the ledger `"suite.suite_root missing or invalid…"` error append  
3. Command: `pytest quantresearch/tests -q --disable-socket --allow-unix-socket`  
4. Record: mutant id, exact hunk, failing test node ids + counts, restore proof (`git checkout -- <file>` / clean worktree).  
5. Acceptance: each mutant produces **≥1 failing test**; clean tree after.  
6. Label evidence: `SOURCE_MUTATION` vs `MONKEYPATCH_SELFTEST` vs `INDEPENDENT_REVIEWER` (Claude).

**Cursor plan-stage status:** source mutants **NOT RUN** here (design-only). Claude’s counts may be referenced as `INDEPENDENT_REVIEWER` only.

**Alternative (if owner prefers leaner CI):** delete the monkeypatch test entirely and rely on negative tmp + lock-after-run tests + documented offline source-mutation script under `tests/` or `docs/plans/` evidence — still no false mutation claims.

### 4.2 E1 — optional read-only EXP suite_root observation

**Recommended (Impl PR):**

Add e.g. `quantresearch/tests/test_committed_exp_suite_root_fail_closed.py`:

```python
@pytest.mark.parametrize("eid", [
    "EXP-2021-2025-throughput-discovery-v1",
    "EXP-2021-2025-session-relax-watchlist-v1",
])
def test_committed_exp_validate_fails_only_unavailable_suite_root(eid):
    errs = validate_experiment(eid)
    assert errs == [
        "suite.suite_root missing or invalid — cannot verify QuantOS artifacts"
    ], errs
```

**Module docstring / evidence must include verbatim:**

```text
validatie van de echte experimentrecords: NOT RUN in CI (artefacten niet in repo)
```

**Rules:**

- Read-only: **no** writes to `experiment.json`, dossiers, or pipelines.  
- If Impl discovers **additional** errors later (e.g. after layout changes), **do not** broaden asserts to `any(...)` soft pass — stop, update plan/evidence, or drop the optional test.  
- Do **not** point suite_root at monorepo via monkeypatch to “make full validate green” — that would invent CI claims about missing run trees.

**Allowed files:** new/updated test under `quantresearch/tests/` only (+ evidence md).

### 4.3 D1 — remove redundant synthetic green path

**Recommended:** delete `test_validate_synthetic_session_style_completed_experiment` **or** merge into a single parametrized green-path test with one row.

**Keep** fail-closed missing/Windows tests and the primary synthetic success test.

**Acceptance:** QR suite still green; no loss of fail-closed coverage; collect count may drop by 1.

---

## 5. Proposed PR sequence

| Stage | Deliverable | Merge gate |
|---|---|---|
| **This PR** | Plan MD only | Draft; Claude PLAN REVIEW on exact SHA |
| **Impl** (after PLAN APPROVE) | M1 rename/docs + optional E1 test + D1 dedupe; source-mutation evidence pack if claiming SOURCE_MUTATION | CI green; hyp003/experiment.json diffs empty; independent review + owner |

Do not implement in the plan PR. Do not collapse into #105 work.

---

## 6. Offline test plan (implementation stage)

### 6.1 Positive

| Check | Command | Pass |
|---|---|---|
| QR full offline | `pytest quantresearch/tests -q --disable-socket --allow-unix-socket` | 0 failed |
| Root preservation still green | `pytest tests/test_ci_workflow_preservation.py -q` | pass (unchanged workflow) |
| E1 (if added) | parametrized committed EXP test | exact sole `suite_root` error |
| hyp003 / experiment.json | `git diff main -- quantresearch/pipelines/hyp003_preregistration.json` and `git diff main -- 'quantresearch/experiments/**/experiment.json'` | **empty** |

### 6.2 Negative / honesty

| Check | Expect |
|---|---|
| Monkeypatch selftest (renamed) | Still fails negative contract when temporal always True **or** removed per alternative |
| Source mutant M-A…M-D (Impl evidence only) | QR suite fails; restored before push of review SHA |
| Evidence labels | No row claims SOURCE_MUTATION for monkeypatch-only |

### 6.3 Explicitly NOT RUN (plan stage)

- Source-level mutants M-A…M-D on this plan branch  
- Full QuantOS artefact validation for EXP-2021-2025  
- Any live / paper / broker path  
- Branch protection API changes  

---

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Over-claiming mutation evidence again | Mandatory taxonomy: SOURCE_MUTATION / MONKEYPATCH_SELFTEST / INDEPENDENT_REVIEWER |
| E1 becomes brittle if ledger gains more checks | Exact equality on error list; escalate if new errors appear |
| Deleting “session” synthetic loses imagined coverage | Audit shows no distinct rules; keep fail-closed pair |
| Accidental edit to historical JSON | Pre-merge `git diff` gates in acceptance |
| Source mutants left dirty on branch | Worktree / restore checklist before push of review SHA |

---

## 8. Acceptance criteria

### 8.1 This plan PR

- [x] New branch from current `main` (`822cbc6`)
- [x] Only plan doc under `docs/plans/` (no code/CI/history edits)
- [x] Evidence for M1/E1/D1 with commands/results
- [x] Exact proposed files, methodology, risks, NOT RUN lines
- [ ] Independent Claude PLAN REVIEW on **exact** head SHA
- [ ] Owner PLAN APPROVE before implementation
- [x] Draft; no merge

### 8.2 Impl (post-approve)

- [ ] M1: no misleading `mutation`/`KILLED` claim for monkeypatch-only test
- [ ] E1 (if kept): sole `suite_root` error asserted; verbatim NOT RUN line present
- [ ] D1: redundant synthetic removed or parametrized without coverage loss
- [ ] `hyp003_preregistration.json` + committed `experiment.json` diffs empty
- [ ] QR offline suite green; no workflow soft-fail changes
- [ ] Any SOURCE_MUTATION claims backed by recorded local source-edit runs on Impl tip **or** explicitly attributed to independent reviewer
- [ ] CI green; independent CODE review on exact SHA; owner approval

---

## 9. Rollback

| Change set | Rollback |
|---|---|
| Plan-only PR | Close without merge |
| Impl | Revert PR; historical records untouched throughout |

---

## 10. Stop condition

**READY FOR CLAUDE PLAN REVIEW #124**

Plan-only draft PR. No implementation, no merge. Await independent review on the exact commit SHA of this plan and owner PLAN APPROVE before coding.
