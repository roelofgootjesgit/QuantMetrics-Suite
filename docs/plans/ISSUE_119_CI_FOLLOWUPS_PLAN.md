# Issue #119 — CI follow-ups: QuantLog skip, exact-command guard, QuantResearch, deps (PLAN)

**Issue:** https://github.com/roelofgootjesgit/QuantMetrics-Suite/issues/119  
**Draft PR:** https://github.com/roelofgootjesgit/QuantMetrics-Suite/pull/122  
**Tech-lead DESIGN brief:** issue comment `6958457005` (2026-11-17 20:23 Europe/Amsterdam)  
**Tech-lead REQUEST CHANGES (PLAN):** PR #122 comment `6958713818` (2026-11-17 20:33 Europe/Amsterdam) — plan revision only  
**Branch:** `cursor/issue-119-ci-followups-plan-3716`  
**Base:** `main` @ `1a42557 fix(safety): strict delete_allowed boolean parse (#103) (#120)`  
**Prior plan SHA (REQUEST CHANGES):** `0ff1776260300cfaf8bdd1f768dbcddb7b0c4627`  
**Mode:** PLAN ONLY — no production code, no tests, no CI / requirements / tracked experiment JSON modifications in this PR  
**Plan repair round:** 1 of max 2  
**Stop line:** **READY FOR CLAUDE PLAN DIFF RECHECK #119**

**Constraints (unchanged):** PIT Gate A **BLOCKED**; production Cushing allowlist empty; no broker / VPS / paper / live actions; no soft-fail / xfail / deselection of mandatory gates; independent SHA-bound review + owner approval before merge of any implementation PR.

---

## 0. Plan revision delta (vs `0ff1776`)

| ID | Severity | Decision (binding) |
|---|---|---|
| **B1** | BLOCKER | Do **not** edit tracked `quantresearch/pipelines/hyp003_preregistration.json`. Historical record is valid (locked before recorded run). Fix **tests** only: assert locked status + recorded `run_start_utc` + temporal integrity + `validate_preregistration_v1` with that timestamp. Add tmp pre-run + negative tmp cases; kill `validate_temporal_integrity → always True` mutant. Tracked JSON diff must stay empty. |
| **O1** | Required | Synthetic/`tmp_path` ledger+dossier tests prove **validator logic only**, not real EXP-2021-2025 records. Evidence must state verbatim: `validatie van de echte experimentrecords: NOT RUN in CI (artefacten niet in repo)`. Fail-closed tests for missing / Windows `suite_root`. **No** edits to committed `experiment.json`. |
| **O2** | Required | QuantLog resolve precedence: (1) `QUANTLOG_REPO_PATH`/`QUANTLOG_ROOT`; (2) `canonical_quantlog_repo_path()` when suite-root env set; (3) sibling `quantbuild_project_root().parent / "quantlog"` only if `src/quantlog` exists. Test that explicit env **wins** over sibling. |
| **O3** | Required | Exact CI allowlist also rejects `if:` on mandatory step/job and `shell:` overrides. Mutation matrix adds V4-M07 step `if: false`, V4-M08 job `if: false`, plus shell override mutant. |
| **O4** | Required | `pytest` is **dev-only** `>=9.0.3` in `requirements-dev.txt`; remove from `requirements.txt`. Runtime-only `pip install -r requirements.txt` still installs runtime editables; CI always installs both files. |
| **O5** | Required | Keep **Impl-A / Impl-B** split. Impl-B alone replaces `"quantresearch" not in joined` ban with a **positive** QR offline suite requirement in the **same** PR. |

---

## 1. Objective

Close four post-#106 gaps with fail-closed CI:

| ID | Gap | Desired outcome |
|---|---|---|
| **N1** | `test_quantlog_desk_grade_validation` silently skips in monorepo | Test **runs** offline and passes; skip only when QuantLog truly absent; env override wins |
| **V4** | Soft-fail denylist incomplete; required commands substring-matched; `if:`/`shell:` unguarded | Exact allowlist for mandatory #104 + demo; reject `\|\| exit 0`, `if: false`, non-default `shell:` |
| **QR** | Four QuantResearch failures + suite absent from root CI | Test redesign (no historical fixture rewrites); synthetic coverage + fail-closed path tests; then offline QR CI |
| **Deps** | Duplicate `pytest` in `requirements.txt` and `requirements-dev.txt` | Dev-only pin `pytest>=9.0.3` |

---

## 2. Non-goals (explicit)

| Out of scope | Why / tracker |
|---|---|
| Production trading / broker / VPS / EnvironmentFile | AGENTS.md; #117 |
| Branch protection / rulesets | #105 (owner; parked) |
| Opening PIT Gate A / non-empty production allowlist | Gate A BLOCKED |
| Soft-fail, `continue-on-error`, xfail, selective deselection | Fail-closed |
| Editing tracked `hyp003_preregistration.json` or committed EXP `experiment.json` | **B1 / O1** scientific audit trail |
| Claiming CI validates real EXP-2021-2025 QuantOS artifacts | Artefacts not in repo (**O1** NOT RUN) |
| Alpha / performance claims or research strategy changes | No invented evidence |
| Nested `quantbuild/.github` / Windows `quantlog` workflows as root CI | Prefer root job steps (#106 decision) |
| Implementing fixes in this PR | Design-only |

---

## 3. Audit evidence (commands actually run)

**Host:** Linux agent, Python **3.12.3** (root CI remains **3.11**). Repo at `1a42557` (unchanged for audit). No broker/live scripts.

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
- No rejection of step/job `if:` or `shell:` overrides on mandatory work
- Module socket guards for QA / QL / QB; **explicit ban:** `"quantresearch" not in joined.lower()`

**Mutation proof (local, this audit):**

```text
Mutate: "pytest tests -q" → "pytest tests -q || exit 0"
SOFT_FAIL_PATTERNS hits: []          # SURVIVES denylist
substring "pytest tests -q" still True  # SURVIVES required-command check
→ assert_workflow_fail_closed would PASS on a soft-failed mandatory step
```

**Classification:** incomplete fail-closed guard — denylist miss + substring allowlist + ungated `if:`/`shell:`.

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

**Four failures (exact) — revised classification after B1/O1:**

| Test | Failure | Classification (revised) |
|---|---|---|
| `test_dossier.py::test_render_dossier_contains_governance_and_compare_rows` | `assert "edge_verdict" in md` — MD warns missing/invalid `suite.suite_root`; no edge_verdict rows | **Test design defect:** couples to non-portable committed `suite.suite_root` + QuantOS run trees **not in repo**. Do **not** rewrite committed `experiment.json`. Move coverage to synthetic/`tmp_path` (**O1**). |
| `test_ledger.py::test_validate_throughput_discovery_experiment` | `['suite.suite_root missing or invalid — cannot verify QuantOS artifacts']` | Same — real EXP validation **cannot** run in CI without artefacts. Replace with synthetic validator tests + fail-closed path tests; leave committed JSON untouched. |
| `test_ledger.py::test_validate_session_watchlist_experiment` | same error | Same as above |
| `test_preregistration.py::test_hyp003_preregistration_file_validates_before_first_run` | `assert data.get("run_start_utc") is None` but file has `run_start_utc: "2026-05-04T09:58:27.576964Z"` with `pre_registration_status: "locked_before_run"` | **Test expectation wrong (B1).** Historical JSON is a **valid** locked-before-run record that later recorded a run start. Do **not** null `run_start_utc` in the tracked file. Revise the test (and add tmp cases). |

**Mandatory evidence line for Impl-B / CI (O1, verbatim):**

```text
validatie van de echte experimentrecords: NOT RUN in CI (artefacten niet in repo)
```

**Not classified as:** network/PIT defects, missing pytest deps (once import path set), or soft CI deselection.

**CI today:** root `.github/workflows/ci.yml` has **no** QuantResearch step (deferred in #106 V3). Preservation test **forbids** `quantresearch` in workflow run text — Impl-B must **replace** that ban with a positive offline QR requirement in the **same** PR (**O5**).

### 3.4 Dependency hygiene

```text
requirements.txt:      pytest          # unpinned — remove (O4)
requirements-dev.txt:  pytest>=9.0.3   # keep as sole pin
```

Root CI installs both (`pip install -r requirements.txt -r requirements-dev.txt`). Duplicate is hygiene debt; risk is pin drift / confusion, not current CI red.

### 3.5 Baseline controls preserved (this audit)

```text
python3 -m pytest tests/test_ci_workflow_preservation.py -q
→ 7 passed
```

---

## 4. Proposed design (implementation PRs — not this PR)

### 4.1 N1 — QuantLog monorepo resolution + anti-skip (**O2**)

**Binding path precedence** for `resolve_quantlog_repo_path`:

1. **`QUANTLOG_REPO_PATH` / `QUANTLOG_ROOT`** (explicit env) — if set and `(path / "src" / "quantlog").is_dir()`, return that path. **Wins over all later steps.**
2. **`canonical_quantlog_repo_path()`** — only when suite-root env (`QUANTMETRICS_SUITE_ROOT` or `QUANTMETRICS_OS_ROOT`) is set and the canonical tree contains `src/quantlog`.
3. **Sibling fallback** — `quantbuild_project_root().parent / "quantlog"` **only if** `(sibling / "src" / "quantlog").is_dir()`.

Do **not** weaken `suite_layout.resolve_suite_root()` fail-closed policy for unrelated callers.

**Tests / acceptance (N1):**

| Check | Expect |
|---|---|
| Monorepo sibling present, no env | resolve → sibling `…/quantlog`; desk-grade test **passes** (not skipped) |
| Explicit `QUANTLOG_REPO_PATH` pointing at a different valid tree (tmp fake with `src/quantlog`) while sibling also exists | resolve → **env path** (env wins) |
| Neither env nor sibling nor suite-root | resolve → `None`; desk-grade may skip only in true standalone checkout |
| Detectable monorepo sibling but import fails | prefer **fail**, not silent skip |

**Allowed files (N1 / Impl-A):**

- `quantbuild/src/quantbuild/quantlog_repo.py`
- `quantbuild/tests/test_quantlog_desk_grade_validation.py`
- `quantbuild/tests/test_quantlog_repo_resolve.py` (new; env-wins + sibling + negative)
- optionally `.github/workflows/ci.yml` env on quantbuild step only (belt-and-suspenders; not a substitute for sibling resolution)

**Non-goals for N1:** QuantLog validator schema changes; exporting test allowlists from production packages.

**Limitations / stop:** If env-wins requires inventing a second real QuantLog checkout in CI, use a **tmp** tree with only `src/quantlog/` marker dirs for the precedence unit test (no network).

---

### 4.2 V4 — exact expected-command allowlist (**O3**)

**Design:**

1. Replace substring `REQUIRED_RUN_SNIPPETS` with an **exact** allowlist of mandatory `run` strings (trimmed), at minimum:

   ```text
   pytest tests -q
   pytest tests/test_live_execution_gate_n.py tests/test_live_execution_gate_w.py tests/test_live_execution_gate_mutation.py -q
   pytest tests/test_live_execution_gate_e.py tests/test_live_execution_gate_e_mutation.py -q
   python run_demo.py
   ```

2. Assert each allowlist entry appears as a **full** step `run` (exact equality after strip), not as a substring of a longer soft-failed command.
3. Soft-fail / fail-open denylist includes at least: `|| true`, `|| :`, `; true`, `set +e`, `|| exit 0` (and document any additional `exit 0` trailing patterns chosen in Impl-A).
4. Keep job/step `continue-on-error` rejection (A1).
5. **Additionally reject** on the mandatory job and on steps that carry allowlisted runs:
   - any `if:` key (including `if: false`, `if: success() == false`, etc.)
   - any `shell:` override (non-default shell that could reinterpret fail-closed `run` semantics)
6. **Negative mutations (must fail):**

   | ID | Mutant | Must kill |
   |---|---|---|
   | V4-M01 | `pytest tests -q \|\| exit 0` | exact allowlist **or** soft-fail denylist |
   | V4-M02 | `python run_demo.py \|\| exit 0` | same |
   | V4-M03 | job `continue-on-error: true` | existing A1 |
   | V4-M04 | step `continue-on-error: true` on demo | A1 step-level |
   | V4-M05 | drop N/W gate command | missing required |
   | V4-M06 | strip `--disable-socket` from module steps | socket-guard assert |
   | **V4-M07** | mandatory step `if: false` | `if:` rejection (**O3**) |
   | **V4-M08** | job `if: false` | `if:` rejection (**O3**) |
   | **V4-M09** | mandatory step `shell: bash {0}` or other non-default `shell:` | `shell:` rejection (**O3**) |

**Allowed files (V4 / Impl-A):**

- `tests/test_ci_workflow_preservation.py`
- `.github/workflows/ci.yml` only if a command string must be normalized to match the exact allowlist (prefer matching the test to current exact strings first)

**Limitations / stop:** Do not expand allowlist to “any pytest invocation”; mandatory #104 + demo strings stay exact. Module socket-guard steps remain separately asserted.

---

### 4.3 QuantResearch — B1 + O1 redesign, then CI (**O5 → Impl-B**)

#### 4.3.1 B1 — hyp003 historical preregistration (BLOCKER)

**Forbidden:** any edit to tracked `quantresearch/pipelines/hyp003_preregistration.json` (including setting `run_start_utc` to `null`). Tracked JSON diff in Impl-B **must remain empty** for this file.

**Revised test intent** for the existing hyp003 file (rename test if needed so the name matches reality, e.g. locked-before-run with recorded start):

```python
assert data.get("pre_registration_status") == "locked_before_run"
assert data.get("run_start_utc")  # exists / non-null
assert validate_temporal_integrity(data, data["run_start_utc"]) is True
assert validate_preregistration_v1(data, run_start_utc=data["run_start_utc"]) == []
```

**Additional offline tests (tmp only — do not write into `pipelines/`):**

| Case | Construction | Assert |
|---|---|---|
| Pre-run tmp | copy/minimal dict: status locked_before_run, `run_start_utc=None` | `validate_preregistration_v1(..., run_start_utc=None) == []` (true pre-run) |
| Negative tmp | `locked_at_utc` **after** `run_start_utc` (run before lock) | `validate_temporal_integrity(...) is False`; `validate_preregistration_v1` reports error(s) |
| **Mutation** | `validate_temporal_integrity` monkeypatched / mutated to **always `True`** | **must fail** the negative real test (mutant killed) |

**Files (B1):** `quantresearch/tests/test_preregistration.py` only (+ optional new test module under `quantresearch/tests/`). **Not** `pipelines/hyp003_preregistration.json`.

**Acceptance:** green asserts on historical file as locked+recorded; pre-run and negative tmp coverage; mutant killed; `git diff -- quantresearch/pipelines/hyp003_preregistration.json` empty.

#### 4.3.2 O1 — ledger / dossier: synthetic coverage + fail-closed; no committed experiment edits

**Forbidden:** edits to committed `quantresearch/experiments/**/experiment.json` (or other tracked EXP records) to “make CI green.”

**Do instead:**

1. Rewrite / replace the three failing tests that currently call real EXP-2021-2025 ids so they use `tmp_path` + monkeypatch with **minimal synthetic** experiment + optional fake `edge_verdict.json` sufficient for **validator/render logic**.
2. Add **fail-closed** tests that a missing `suite.suite_root` or a Windows-style absolute `suite_root` that does not exist on the runner yields the existing validation / warning behaviour (error list / dossier warning) — proving fail-closed path handling without claiming real EXP artefacts.
3. Evidence pack / PR body / CI notes must include **verbatim**:

   ```text
   validatie van de echte experimentrecords: NOT RUN in CI (artefacten niet in repo)
   ```

4. Do **not** silence via xfail/skip/deselection.

**Limitation (explicit):** CI after Impl-B proves QuantResearch **library/test harness** behaviour offline. It does **not** re-validate the historical EXP-2021-2025 QuantOS run trees (absent from repo).

#### 4.3.3 Install + root CI step (Impl-B)

1. **Install path:** add `-e ./quantresearch` to root install **or** proven `PYTHONPATH=quantresearch` — zero collection errors on CI Python 3.11.
2. **Root CI step** (after local green):

   ```yaml
   - name: Run quantresearch tests (offline socket guard)
     run: pytest quantresearch/tests -q --disable-socket --allow-unix-socket
   ```

3. **Preservation contract (same PR — O5):** remove `"quantresearch" not in joined.lower()` ban and replace with a **positive** require: a step whose `run` includes `quantresearch/tests` and `--disable-socket` (and `--allow-unix-socket` consistent with other modules).
4. Full QR suite must pass with **no** deselection / soft-fail.

**Allowed files (Impl-B):**

- `quantresearch/tests/test_preregistration.py` (+ optional new test files under `quantresearch/tests/`)
- `quantresearch/tests/test_ledger.py`, `quantresearch/tests/test_dossier.py` (synthetic / fail-closed redesign)
- `requirements.txt` / install path only if `-e ./quantresearch` is chosen (prefer minimal; may live in Impl-B requirements touch — **not** pytest pin; pytest is Impl-A/O4)
- `.github/workflows/ci.yml` — add QR offline step
- `tests/test_ci_workflow_preservation.py` — positive QR requirement replacing ban

**Not allowed in Impl-B:** `quantresearch/pipelines/hyp003_preregistration.json`, committed EXP `experiment.json`, production research logic changes beyond what tests require, Gate A / allowlist.

---

### 4.4 Dependency hygiene (**O4**)

**Binding:**

- Remove bare `pytest` from `requirements.txt`.
- Keep **only** `pytest>=9.0.3` in `requirements-dev.txt` (dev/CI).
- Document in Impl-A evidence:
  - Runtime-only: `pip install -r requirements.txt` → still installs runtime editables (`-e ./quantbuild`, `-e ./quantlog`, `-e ./quantanalytics`, …) **without** pytest.
  - CI / contributors running tests: `pip install -r requirements.txt -r requirements-dev.txt` (unchanged workflow pattern).

**Allowed files:** `requirements.txt`, `requirements-dev.txt` (Impl-A). Docs only if an existing one-line install note would become wrong.

---

## 5. Proposed PR sequence (**O5** — preserved)

| Stage | Branch intent | Deliverable | Merge gate |
|---|---|---|---|
| **This PR (#122)** | `cursor/issue-119-ci-followups-plan-3716` | Plan MD only (repair round 1) | Draft; Claude PLAN DIFF RECHECK on new SHA |
| **Impl-A** | new feature branch from then-current `main` | **N1 (O2) + V4 (O3) + pytest hygiene (O4)** | CI green; mutation evidence incl. M01/M07/M08/M09; independent review + owner |
| **Impl-B** | new feature branch | **QR B1+O1 test redesign + QR CI step + preservation ban→positive require (same PR)** | CI green; hyp003 tracked JSON diff empty; verbatim NOT RUN evidence line; independent review + owner |

Do not merge plan-only PR for “progress”; implementation waits on **PLAN APPROVE**. Do not collapse Impl-A into Impl-B.

---

## 6. Offline test plan (implementation stage)

### 6.1 Positive

| Check | Command (illustrative) | Pass criteria |
|---|---|---|
| N1 desk-grade | `pytest quantbuild/tests/test_quantlog_desk_grade_validation.py -v` | **passed**, not skipped, when sibling `quantlog/` present |
| N1 env wins | resolve unit with `QUANTLOG_REPO_PATH` + sibling both valid | returns **env** path |
| V4 live workflow | `pytest tests/test_ci_workflow_preservation.py -q` | all pass incl. new `if:`/`shell:` guards |
| Root #104 + demo | existing CI commands | unchanged intent; green |
| Module offline | QA / QL / QB with `--disable-socket` | green |
| B1 hyp003 historical | preregistration tests against tracked JSON | locked_before_run + recorded start + temporal OK + v1 `[]` |
| B1 pre-run tmp | tmp null `run_start_utc` | validates as pre-run |
| O1 synthetic ledger/dossier | tmp_path tests | validator/render logic green |
| O1 fail-closed suite_root | missing / Windows non-existent root | errors/warnings asserted |
| QR full (Impl-B) | `pytest quantresearch/tests -q --disable-socket --allow-unix-socket` | **0 failed**, no soft deselection |

### 6.2 Negative / mutation

| Check | Expect |
|---|---|
| V4-M01 `\|\| exit 0` on `pytest tests -q` | preservation assert fails |
| V4-M02 `\|\| exit 0` on `run_demo.py` | fails |
| V4-M03/M04 continue-on-error | fails |
| V4-M07 step `if: false` | fails |
| V4-M08 job `if: false` | fails |
| V4-M09 `shell:` override on mandatory step | fails |
| N1: env path vs sibling | env wins; wrong precedence fails unit test |
| B1 mutant: `validate_temporal_integrity` → always `True` | **negative tmp test fails** (mutant killed) |
| O1: Windows / missing `suite_root` in synthetic fixture | fail-closed assert fires |

### 6.3 Explicitly NOT RUN

**Plan stage:**

- Full root CI matrix for unimplemented changes
- Any live / paper / broker path
- Inventing QuantOS run artifacts as “verified” research outputs

**Impl-B / ongoing CI (O1 — verbatim in evidence):**

```text
validatie van de echte experimentrecords: NOT RUN in CI (artefacten niet in repo)
```

---

## 7. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Sibling resolve too loose | False confidence in desk-grade | Require `src/quantlog`; precedence puts env first (**O2**) |
| Exact allowlist brittle to whitespace | CI red on formatting | Strip normalize; mandatory runs stay single-command exact strings |
| `if:`/`shell:` rules too broad | Blocks legitimate future conditional jobs | Scope rejection to mandatory job + steps carrying allowlisted runs; document |
| Editing hyp003 / EXP JSON “for CI” | Destroys scientific audit trail | **B1/O1 forbid**; empty tracked JSON diff as acceptance |
| Synthetic tests over-claimed as real EXP validation | False research confidence | Verbatim NOT RUN evidence line; no artefact invention |
| Missing QuantOS runs in git | Real EXP validate cannot pass | Expected; fail-closed + synthetic only |
| Adding QR without updating preservation ban | Contract break | Impl-B same PR: ban → positive require (**O5**) |
| Scope creep / merging Impl-A+B | Process violation | Keep split (**O5**) |
| Removing pytest from requirements.txt surprises runtime-only installs | Local confusion | Document runtime editables still install; tests need `-r requirements-dev.txt` (**O4**) |

---

## 8. Acceptance criteria

### 8.1 This plan PR (repair round 1)

- [x] Same branch from `main` (`1a42557`); only `docs/plans/ISSUE_119_CI_FOLLOWUPS_PLAN.md` changed
- [x] B1: no proposal to edit tracked hyp003 JSON; test revision + tmp + mutant specified
- [x] O1–O5 incorporated with files, tests, mutations, limitations, stop conditions
- [x] Impl-A / Impl-B split preserved
- [ ] Independent Claude PLAN DIFF RECHECK on **new** exact plan SHA
- [ ] Owner PLAN APPROVE before implementation
- [x] Draft retained; no merge; no code/tests/CI/requirements/tracked experiment edits

### 8.2 Impl-A (post-approve)

- [ ] Desk-grade QuantLog test **runs and passes** offline in monorepo without silent skip
- [ ] Resolve precedence O2 + env-wins unit test green
- [ ] `pytest tests -q || exit 0` mutant **killed**
- [ ] V4-M07 / M08 / M09 (`if:` / `shell:`) killed
- [ ] Existing A1 continue-on-error + soft-fail checks preserved
- [ ] pytest removed from `requirements.txt`; sole pin `pytest>=9.0.3` in `requirements-dev.txt`; dual-install documented
- [ ] No Gate A / allowlist / broker changes
- [ ] CI green; independent review on exact commit SHA; owner approval

### 8.3 Impl-B (post-approve)

- [ ] B1 hyp003 tests revised; tracked `hyp003_preregistration.json` diff **empty**
- [ ] Pre-run tmp + negative tmp + temporal-integrity mutant killed
- [ ] Ledger/dossier synthetic + fail-closed suite_root tests; no committed `experiment.json` edits
- [ ] Evidence contains verbatim: `validatie van de echte experimentrecords: NOT RUN in CI (artefacten niet in repo)`
- [ ] Full `quantresearch/tests` offline in root CI with socket guard
- [ ] Preservation: ban removed and **positive** QR suite requirement added **in the same PR**
- [ ] No xfail/skip/deselection soft-fail
- [ ] CI green; independent review on exact SHA; owner approval

---

## 9. Rollback

| Change set | Rollback |
|---|---|
| Plan-only PR | Close without merge; no runtime effect |
| Impl-A | Revert PR; desk-grade may skip again; V4 returns to substring/denylist/`if:` gap; pytest may reappear in requirements.txt — track as residual risk |
| Impl-B | Revert PR; remove QR CI step; restore preservation ban if needed for older main; historical JSON untouched throughout |

---

## 10. Evidence pack checklist (for implementers)

1. Exact base SHA and tip SHA  
2. Commands run + pass/fail/`NOT RUN` with reason  
3. N1: before (skipped) / after (passed); env-wins unit result  
4. V4-M01 + V4-M07 + V4-M08 + V4-M09 transcripts showing mutants killed  
5. B1: `git diff -- quantresearch/pipelines/hyp003_preregistration.json` empty; mutant kill for temporal integrity  
6. O1: synthetic suite counts + **verbatim** NOT RUN line for real EXP records  
7. Confirmation: PIT Gate A still BLOCKED; production allowlist empty; no secrets committed  

---

## 11. Stop condition (plan stage — superseded)

~~READY FOR CLAUDE PLAN DIFF RECHECK #119~~ — plan approved at `3651948`; Impl-A authorized (PR comment `6958915294`).

---

## 12. Impl-A evidence (N1 + V4 + deps) — CODE REVIEW

**Authorized by:** tech-lead comment `6958915294` on PR #122 (Claude APPROVE PLAN → Impl-A ONLY).  
**Scope kept:** no QuantResearch / hyp003 / experiment.json changes.  
`git diff main -- quantresearch/pipelines/hyp003_preregistration.json` → **empty**.

### Changed files (Impl-A)

| File | Change |
|---|---|
| `quantbuild/src/quantbuild/quantlog_repo.py` | Precedence: env → canonical(suite-root) → sibling |
| `quantbuild/tests/test_quantlog_repo.py` | Sibling + env-wins-over-sibling tests |
| `quantbuild/tests/test_quantlog_desk_grade_validation.py` | Fail (not skip) when repo resolves but import fails |
| `tests/test_ci_workflow_preservation.py` | Exact allowlist; `\|\| exit 0`; reject `if:` / `shell:`; V4-M01–M09 |
| `requirements.txt` | Remove pytest (runtime editables retained) |
| `requirements-dev.txt` | Sole `pytest>=9.0.3`; dual-install note |

### Commands / results (local agent, Python 3.12.3; root CI target 3.11)

| Command | Result |
|---|---|
| `pytest quantbuild/tests/test_quantlog_repo.py quantbuild/tests/test_quantlog_desk_grade_validation.py -v` (no QUANTLOG_*/suite-root env) | **6 passed** (desk-grade **PASSED**, not skipped) |
| `pytest tests/test_ci_workflow_preservation.py -v` | **16 passed** (incl. V4-M01–M09) |
| `pytest tests -q` | **165 passed** |
| #104 N/W/mutation | **64 passed** |
| #104 E/mutation | **43 passed** |
| `python run_demo.py` | Verdict `VALIDATION_REQUIRED` |
| `pytest quantanalytics/tests -q --disable-socket --allow-unix-socket` | **45 passed** |
| `(cd quantlog && pytest tests -q --disable-socket --allow-unix-socket)` | **61 passed** |
| `pytest quantbuild/tests -q --disable-socket --allow-unix-socket` | **250 passed** |
| QuantResearch suite / hyp003 edits | **NOT RUN / not changed** (Impl-B) |

### Deps proof (O4)

- `requirements.txt` contains `-e ./quantbuild`, `-e ./quantlog`, `-e ./quantanalytics`; **no** `pytest` package line.
- `requirements-dev.txt` pins `pytest>=9.0.3`.
- CI workflow still: `pip install -r requirements.txt -r requirements-dev.txt`.

### Stop

**READY FOR CLAUDE CODE REVIEW IMPL-A #119**
