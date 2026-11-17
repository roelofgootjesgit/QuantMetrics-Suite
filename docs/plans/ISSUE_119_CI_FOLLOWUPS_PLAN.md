# Issue #119 — CI follow-ups: QuantLog skip, exact-command guard, QuantResearch, deps (PLAN)

**Issue:** https://github.com/roelofgootjesgit/QuantMetrics-Suite/issues/119  
**Tech-lead brief:** issue comment `6958457005` (2026-11-17 20:23 Europe/Amsterdam) — DESIGN ONLY  
**Branch:** `cursor/issue-119-ci-followups-plan-3716`  
**Base:** `main` @ `1a42557fix(safety): strict delete_allowed boolean parse (#103) (#120)`  
**Mode:** PLAN ONLY — no production code, no CI / requirements modifications in this PR  
**Stop line:** **READY FOR CLAUDE PLAN REVIEW #119**

**Constraints (unchanged):** PIT Gate A **BLOCKED**; production Cushing allowlist empty; no broker / VPS / paper / live actions; no soft-fail / xfail / deselection of mandatory gates; independent SHA-bound review + owner approval before merge of any implementation PR.

---

## 1. Objective

Close four post-#106 gaps with fail-closed CI:

| ID | Gap | Desired outcome |
|---|---|---|
| **N1** | `test_quantlog_desk_grade_validation` silently skips in monorepo | Test **runs** offline and passes; skip only when QuantLog truly absent |
| **V4** | Soft-fail denylist incomplete; required commands are substring-matched | Exact allowlist for mandatory #104 + demo runs; `pytest tests -q \|\| exit 0` **rejected** |
| **QR** | Four QuantResearch failures + suite absent from root CI | Diagnose, fix without deselection, then add full offline QR suite to root CI |
| **Deps** | Duplicate `pytest` in `requirements.txt` and `requirements-dev.txt` | Single justified declaration |

---

## 2. Non-goals (explicit)

| Out of scope | Why / tracker |
|---|---|
| Production trading / broker / VPS / EnvironmentFile | AGENTS.md; #117 |
| Branch protection / rulesets | #105 (owner; parked) |
| Opening PIT Gate A / non-empty production allowlist | Gate A BLOCKED |
| Soft-fail, `continue-on-error`, xfail, selective deselection | Fail-closed |
| Alpha / performance claims or research strategy changes | No invented evidence |
| Nested `quantbuild/.github` / Windows `quantlog` workflows as root CI | Prefer root job steps (#106 decision) |
| Implementing fixes in this PR | Design-only |

---

## 3. Audit evidence (commands actually run)

**Host:** Linux agent, Python **3.12.3** (root CI remains **3.11**). Repo at `1a42557`. No broker/live scripts.

### 3.1 N1 — QuantLog desk-grade skip

**Files:**

- `quantbuild/tests/test_quantlog_desk_grade_validation.py` — `skipTest` when `resolve_quantlog_repo_path()` / import fails
- `quantbuild/src/quantbuild/quantlog_repo.py` — resolves via `QUANTLOG_REPO_PATH` / `QUANTLOG_ROOT`, else `canonical_quantlog_repo_path()`
- `quantbuild/src/quantbuild/suite_layout.py` — `resolve_suite_root()` **requires** `QUANTMETRICS_SUITE_ROOT` or `QUANTMETRICS_OS_ROOT`; no path-inferred monorepo fallback

**Commands / results:**

```text
# Without suite-root env (matches current root CI quantbuild step):
python3 -m pytest quantbuild/tests/test_quantlog_desk_grade_validation.py -v
→ SKIPPED (1 skipped)

# resolve_quantlog_repo_path() → None because canonical_quantlog_repo_path()
# raises SuiteLayoutError("Missing suite root...") and is swallowed as Exception → None

# With suite root pointing at monorepo:
QUANTMETRICS_SUITE_ROOT=/agent/repos/QuantMetrics-Suite \
  python3 -m pytest quantbuild/tests/test_quantlog_desk_grade_validation.py -v
→ PASSED (1 passed)  # offline; no network
```

**Root cause (verified):** In the monorepo, `quantlog/` is a sibling of `quantbuild/`, and editable `-e ./quantlog` is installed — but `resolve_quantlog_repo_path` never checks the sibling path. It only succeeds when suite-root env is set (or `QUANTLOG_*`). Root CI does **not** set `QUANTMETRICS_SUITE_ROOT`, so the desk-grade integration is a **silent skip**, not a green pass of QuantLog validation.

**Classification:** path-resolution / test-harness defect in monorepo CI layout — **not** a QuantLog validator defect (validator passes when path resolves).

### 3.2 V4 — exact-command guard gap

**Files:** `tests/test_ci_workflow_preservation.py`, `.github/workflows/ci.yml`

**Current contract:**

- `REQUIRED_RUN_SNIPPETS` — **substring** membership in any step `run`
- `SOFT_FAIL_PATTERNS` — `|| true`, `|| :`, `; true`, `set +e` only
- Job/step `continue-on-error` rejected (A1)
- Module socket guards for QA / QL / QB; **explicit ban:** `"quantresearch" not in joined.lower()`

**Mutation proof (local, this audit):**

```text
Mutate: "pytest tests -q" → "pytest tests -q || exit 0"
SOFT_FAIL_PATTERNS hits: []          # SURVIVES denylist
substring "pytest tests -q" still True  # SURVIVES required-command check
→ assert_workflow_fail_closed would PASS on a soft-failed mandatory step
```

**Classification:** incomplete fail-closed guard — denylist miss + substring allowlist.

### 3.3 QuantResearch — four failures + collection env

**Install / collect:**

```text
# Without PYTHONPATH / editable install:
python3 -m pytest quantresearch/tests --collect-only -q
→ 9 ERRORS during collection (ModuleNotFoundError: quantresearch.*)

# With PYTHONPATH=quantresearch:
PYTHONPATH=quantresearch:$PYTHONPATH python3 -m pytest quantresearch/tests -q
→ 4 failed, 45 passed
```

**Four failures (exact):**

| Test | Failure | Classification |
|---|---|---|
| `test_dossier.py::test_render_dossier_contains_governance_and_compare_rows` | `assert "edge_verdict" in md` — rendered MD warns `Missing or invalid suite.suite_root`; section “Edge verdicts” has no rows / no literal `edge_verdict` | **Fixture / path env:** committed `experiment.json` has `suite.suite_root = "C:/Users/Gebruiker/quantmetrics-suite"` (non-portable). Also `quantmetrics_os/runs/EXP-2021-2025-throughput-discovery-v1` **absent** in this checkout — even a corrected suite root would not find edge_verdict artifacts unless fixtures are vendored or the test uses `tmp_path`. |
| `test_ledger.py::test_validate_throughput_discovery_experiment` | `['suite.suite_root missing or invalid — cannot verify QuantOS artifacts']` | Same Windows absolute `suite_root` + missing run tree |
| `test_ledger.py::test_validate_session_watchlist_experiment` | same error | Same pattern on session-watchlist experiment |
| `test_preregistration.py::test_hyp003_preregistration_file_validates_before_first_run` | `assert data.get("run_start_utc") is None` but fixture has `run_start_utc: "2026-05-04T09:58:27.576964Z"` while `pre_registration_status: "locked_before_run"` | **Fixture drift / semantic inconsistency** in `pipelines/hyp003_preregistration.json` vs test expectation (true pre-run) |

**Not classified as:** network/PIT defects, missing pytest deps (once import path set), or soft CI deselection.

**CI today:** root `.github/workflows/ci.yml` has **no** QuantResearch step (deferred in #106 V3). Preservation test **forbids** `quantresearch` in workflow run text — that ban must be **intentionally replaced** when QR is wired, not silently deleted without a new positive contract.

### 3.4 Dependency hygiene

```text
requirements.txt:      pytest          # unpinned
requirements-dev.txt:  pytest>=9.0.3   # pinned; comment admits duplicate
```

Root CI installs both (`pip install -r requirements.txt -r requirements-dev.txt`). Duplicate is hygiene debt; risk is pin drift / confusion, not current CI red.

### 3.5 Baseline controls preserved (this audit)

```text
python3 -m pytest tests/test_ci_workflow_preservation.py -q
→ 7 passed
```

---

## 4. Proposed design (implementation PRs — not this PR)

### 4.1 N1 — QuantLog monorepo resolution + anti-skip

**Preferred minimal fix (fail-closed, docstring-aligned):**

1. In `quantbuild/src/quantbuild/quantlog_repo.py` `resolve_quantlog_repo_path`:
   - Keep env overrides (`QUANTLOG_REPO_PATH` / `QUANTLOG_ROOT`).
   - **Add** explicit monorepo sibling: `quantbuild_project_root().parent / "quantlog"` when `(sibling / "src" / "quantlog").is_dir()`.
   - Keep `canonical_quantlog_repo_path()` when suite-root env is set.
   - Do **not** weaken `suite_layout.resolve_suite_root()` fail-closed policy for unrelated callers.
2. In `test_quantlog_desk_grade_validation.py`:
   - Prefer **fail** (not skip) when suite layout clearly contains `../quantlog` (or when `QUANTMETRICS_SUITE_ROOT` / sibling is detectable) but import still fails.
   - Retain skip **only** for true standalone quantbuild checkouts without QuantLog.
   - Add a small unit/contract test that `resolve_quantlog_repo_path()` returns non-`None` when the monorepo sibling exists (no network).
3. Optional belt-and-suspenders: set `QUANTMETRICS_SUITE_ROOT: ${{ github.workspace }}` on the quantbuild CI step — helpful for other suite_layout callers, but **not** a substitute for sibling resolution (nested/local runs still need the code path).

**Allowed files (N1):**

- `quantbuild/src/quantbuild/quantlog_repo.py`
- `quantbuild/tests/test_quantlog_desk_grade_validation.py`
- optionally `quantbuild/tests/test_quantlog_repo_resolve.py` (new)
- optionally `.github/workflows/ci.yml` env on quantbuild step only

**Non-goals for N1:** changing QuantLog validator schemas; exporting test allowlists from production packages.

### 4.2 V4 — exact expected-command allowlist

**Design:**

1. Replace substring `REQUIRED_RUN_SNIPPETS` with an **exact** allowlist of mandatory `run` strings (trimmed), at minimum:

   ```text
   pytest tests -q
   pytest tests/test_live_execution_gate_n.py tests/test_live_execution_gate_w.py tests/test_live_execution_gate_mutation.py -q
   pytest tests/test_live_execution_gate_e.py tests/test_live_execution_gate_e_mutation.py -q
   python run_demo.py
   ```

2. Assert each allowlist entry appears as a **full** step `run` (exact equality after strip), not as a substring of a longer soft-failed command.
3. Extend `SOFT_FAIL_PATTERNS` (or a dedicated shell denylist) to include at least:

   ```text
   || exit 0
   || exit 1   # optional; document
   exit 0      # trailing soft success patterns if used after `;`
   ```

   Keep existing `|| true` / `|| :` / `; true` / `set +e` and job/step `continue-on-error` rejection.
4. **Negative mutations (must fail):**

   | ID | Mutant | Must kill |
   |---|---|---|
   | V4-M01 | `pytest tests -q \|\| exit 0` | exact allowlist **or** soft-fail denylist |
   | V4-M02 | `python run_demo.py \|\| exit 0` | same |
   | V4-M03 | job `continue-on-error: true` | existing A1 |
   | V4-M04 | step `continue-on-error: true` on demo | A1 step-level |
   | V4-M05 | drop N/W gate command | missing required |
   | V4-M06 | strip `--disable-socket` from module steps | socket-guard assert |

5. When QR is later added, update module-guard asserts to **require** a QR offline step rather than banning the string `quantresearch`.

**Allowed files (V4):**

- `tests/test_ci_workflow_preservation.py`
- (implementation may touch `.github/workflows/ci.yml` only if a command string must be normalized to match the exact allowlist — prefer matching the test to current exact strings first)

### 4.3 QuantResearch — fix four failures, then CI

**Recommended approach (prefer test/fixture redesign over inventing suite artifacts):**

1. **Install path for CI:** add `-e ./quantresearch` to root install **or** `PYTHONPATH=quantresearch` / `working-directory` + editable — prove collection with zero import errors on CI Python 3.11.
2. **Ledger + dossier (3 tests):** stop depending on developer-absolute `C:/Users/...` and missing `quantmetrics_os/runs/...` trees.
   - Preferred: rewrite the three tests to use `tmp_path` + monkeypatch (pattern already used elsewhere in `test_ledger.py` / `test_dossier.py`) with **minimal synthetic** experiment + optional fake `edge_verdict.json` rows sufficient for assertions.
   - Alternative (heavier): normalize committed `suite.suite_root` to a portable relative layout **and** vendor minimal QuantOS run fixtures under a test-owned path — only if owner wants committed experiment JSON to remain the SUT.
   - Do **not** silence validation errors via xfail/skip.
3. **hyp003 preregistration:** restore fixture/test agreement for “before first run”:
   - Preferred: set `run_start_utc` to `null` in `hyp003_preregistration.json` if status remains `locked_before_run` and the test documents true pre-run; **or**
   - Split fixture: keep post-run JSON under a different filename and leave a clean pre-run fixture for this test.
   - Do not invent temporal claims; align fields with documented status.
4. **Root CI step (after green locally):**

   ```yaml
   - name: Run quantresearch tests (offline socket guard)
     run: pytest quantresearch/tests -q --disable-socket --allow-unix-socket
   ```

   (Exact install/`PYTHONPATH`/`working-directory` as proven in implementation evidence.)
5. Update `tests/test_ci_workflow_preservation.py` module guards: **require** QR offline flags; remove the `"quantresearch" not in joined` ban as part of the same change set.
6. Full suite must pass with **no** deselection / soft-fail.

**Scope split:** If fixture redesign + CI wiring exceeds three production modules or risks Gate A / research semantics debates → **separate implementation PR** (tech-lead brief allows this). Suggested split:

| PR | Scope |
|---|---|
| **Impl-A** | N1 + V4 + pytest hygiene |
| **Impl-B** | QR four fixes + QR CI step + preservation-test contract update |

### 4.4 Dependency hygiene

**Proposal:** keep **one** pytest declaration for suite CI/dev:

- Remove bare `pytest` from `requirements.txt` **or** move the pin solely into `requirements-dev.txt` and document that root CI always installs both files (current workflow).
- Prefer: `requirements.txt` = runtime editables + non-test libs; `requirements-dev.txt` = `pytest>=9.0.3` (+ existing CI extras). Confirm local contributor docs still say `pip install -r requirements.txt -r requirements-dev.txt`.
- No version inventing beyond the already-used `>=9.0.3` pin.

**Allowed files:** `requirements.txt`, `requirements-dev.txt` (and docs only if a one-line install note already exists and would become wrong).

---

## 5. Proposed PR sequence

| Stage | Branch intent | Deliverable | Merge gate |
|---|---|---|---|
| **This PR** | `cursor/issue-119-ci-followups-plan-3716` | Plan MD only | Draft; Claude plan review on SHA |
| **Impl-A** | new feature branch from then-current `main` | N1 + V4 + deps | CI green; mutation evidence; independent review + owner |
| **Impl-B** | new feature branch | QR fixes + CI + preservation update | Same; may follow Impl-A if V4 contract must allow `quantresearch` |

Do not merge plan-only PR for “progress”; implementation waits on **PLAN APPROVE**.

---

## 6. Offline test plan (implementation stage)

### 6.1 Positive

| Check | Command (illustrative) | Pass criteria |
|---|---|---|
| N1 desk-grade | `pytest quantbuild/tests/test_quantlog_desk_grade_validation.py -v` **without** relying on skip | **passed**, not skipped, when `quantlog/` sibling present |
| N1 resolve unit | new resolve contract test | returns path ending in `quantlog` |
| V4 live workflow | `pytest tests/test_ci_workflow_preservation.py -q` | all pass |
| Root #104 + demo | existing CI commands | unchanged intent; green |
| Module offline | QA / QL / QB with `--disable-socket` | green |
| QR full | `pytest quantresearch/tests -q --disable-socket --allow-unix-socket` (with proven install) | **0 failed**, 0 deselected soft |

### 6.2 Negative / mutation

| Check | Expect |
|---|---|
| V4-M01 `\|\| exit 0` on `pytest tests -q` | preservation assert fails |
| V4-M02 `\|\| exit 0` on `run_demo.py` | fails |
| V4-M03/M04 continue-on-error | fails |
| N1: break sibling path / remove quantlog from sys.path in controlled mutant | fail or explicit skip only when truly absent — document which |
| QR: reintroduce Windows absolute suite_root in a mutant fixture used by rewritten tests | must fail visibly |

### 6.3 Explicitly NOT RUN in plan stage

- Full root CI matrix on GitHub Actions for unimplemented changes
- Any live / paper / broker path
- Inventing QuantOS run artifacts as “verified” research outputs

---

## 7. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Sibling resolve too loose (picks wrong directory) | False confidence in desk-grade | Require `(repo / "src" / "quantlog").is_dir()`; prefer env override |
| Exact allowlist brittle to harmless whitespace | CI red on formatting | Normalize strip; document that mandatory runs must be single-command exact strings |
| QR suite_root rewrite changes research ledger semantics | Accidental policy change | Prefer **test redesign** over rewriting completed experiment JSON; escalate if owner wants portable committed paths |
| Missing QuantOS runs in git | Ledger validate cannot pass against real EXP ids | Do not claim artifact presence; use synthetic fixtures |
| hyp003 nulling `run_start_utc` | Loses historical post-run stamp | Prefer split fixture file over destructive edit if post-run data must be retained |
| Adding QR without updating preservation ban | Impl CI red or silent contract break | Same PR updates positive QR guard |
| Scope creep across >3 production modules | Process violation (AGENTS.md) | Enforce Impl-A / Impl-B split |
| Duplicate pytest removal breaks “pip install -r requirements.txt” only workflows | Local surprise | Document dual-file install; optional thin note in plan evidence |

---

## 8. Acceptance criteria

### 8.1 This plan PR

- [x] Branch from latest `main` (`1a42557` at branch creation)
- [x] Only `docs/plans/ISSUE_119_CI_FOLLOWUPS_PLAN.md` (plan-only; no code/CI/requirements edits)
- [x] Evidence for N1 skip, V4 `|| exit 0` survival, four QR failures, duplicate pytest
- [x] Scoped files, PR sequence, tests, mutations, risks, rollback
- [ ] Independent Claude review on **exact plan SHA**
- [ ] Owner PLAN APPROVE before implementation

### 8.2 Impl-A (post-approve)

- [ ] Desk-grade QuantLog test **runs and passes** offline in monorepo without silent skip
- [ ] `pytest tests -q || exit 0` mutant **killed**
- [ ] Existing A1 continue-on-error + soft-fail checks preserved
- [ ] Duplicate pytest declaration resolved with justified single pin
- [ ] No Gate A / allowlist / broker changes
- [ ] CI green; independent review on exact commit SHA; owner approval

### 8.3 Impl-B (post-approve)

- [ ] Four QR failures fixed without xfail/skip/deselection
- [ ] Full `quantresearch/tests` offline in root CI with socket guard
- [ ] Preservation tests require QR step (ban removed intentionally)
- [ ] Classification (fixture vs code) documented in PR evidence with commands
- [ ] CI green; independent review on exact SHA; owner approval

---

## 9. Rollback

| Change set | Rollback |
|---|---|
| Plan-only PR | Close without merge; no runtime effect |
| Impl-A | Revert PR; desk-grade may skip again; V4 returns to substring/denylist gap — track as residual risk |
| Impl-B | Revert PR; remove QR CI step; restore preservation ban if needed for older main |

---

## 10. Evidence pack checklist (for implementers)

Record in the implementation PR body / plan pin:

1. Exact base SHA and tip SHA  
2. Commands run + pass/fail/`NOT RUN` with reason  
3. N1: before (skipped) / after (passed) without `QUANTLOG_REPO_PATH` if sibling present  
4. V4-M01 transcript showing `|| exit 0` killed  
5. QR: collect errors without install path; four failure messages; post-fix full suite counts  
6. Confirmation: PIT Gate A still BLOCKED; production allowlist empty; no secrets committed  

---

## 11. Stop condition

**READY FOR CLAUDE PLAN REVIEW #119**

Plan-only draft PR. No implementation, no merge. Await independent review on the exact commit SHA of this plan and owner PLAN APPROVE before any Impl-A / Impl-B coding.
