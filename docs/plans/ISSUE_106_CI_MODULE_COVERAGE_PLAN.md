# Issue #106 — PROP-00 CI: module coverage + PR template (PLAN)

**Issue:** https://github.com/roelofgootjesgit/QuantMetrics-Suite/issues/106  
**Branch:** `cursor/issue-106-ci-coverage-plan-3716`  
**Base:** `main` @ `4f10151e1a33a94c1c29bf48c543e11eb9ffc06d` (post PR #116 merge)  
**Mode:** PLAN ONLY — no production logic, no CI wiring yet, no merge  
**Tech-lead brief:** issue comment `6955519929` (2026-11-17)  
**Stop line:** **READY FOR CLAUDE PLAN REVIEW #106**

---

## 1. Objective

Extend reliable, reproducible GitHub Actions coverage across suite modules; add a root PR template and SHA-bound review checklist; **without** weakening existing root safety gates (#104 N/W/E + mutation) or the deterministic demo.

---

## 2. Non-goals (explicit)

| Out of scope | Why / tracker |
|---|---|
| VPS / systemd / EnvironmentFile migration | #117 |
| Branch protection / rulesets | #105 (owner; parked) |
| Live enablement, broker credentials, paper/live trading | AGENTS.md hard ban |
| Strategy / research alpha changes | PROP-03+ |
| Paid services / new deps for trading | Owner consent required |
| Disabling, skip/xfail, soft-fail, or ignoring existing checks | Fail-closed policy |
| PIT Gate A open | Stays **BLOCKED** |

---

## 3. Inventory (commands actually run — this branch base)

Inventory host: Python **3.12.3** local agent; root CI target remains **3.11** (see workflow). No broker/live scripts invoked.

### 3.1 Root CI today (`.github/workflows/ci.yml`)

| Step | Command | Observed (local on `4f10151`) |
|---|---|---|
| Install | `pip install -r requirements.txt` | editable `quantbuild`, `quantlog`, `quantanalytics` + pytest/dotenv/yaml + **pydantic/filelock** (added by #116 for LiveRunner probes) |
| Root tests | `pytest tests -q` | **112 passed** (~3.7s) |
| #104 PR-A gates | `pytest tests/test_live_execution_gate_{n,w,mutation}.py -q` | **64 collected** |
| #104 PR-B gates | `pytest tests/test_live_execution_gate_e{,_mutation}.py -q` | **43 collected** |
| Demo | `python run_demo.py` | deterministic `VALIDATION_REQUIRED` |

Python version in root CI: **3.11**. Nested module workflows exist but are **not** invoked by root Actions:

| Nested workflow | Runner / Python | Notes |
|---|---|---|
| `quantbuild/.github/workflows/ci.yml` | ubuntu / **3.10** | Assumes **sibling** clones (`../quantbridge`, `../quantlog`, …) — **not** monorepo layout |
| `quantlog/.github/workflows/ci.yml` | **windows** / 3.11 | `./scripts/ci_smoke.ps1` after `pip install -e .` |

**No** root `.github/PULL_REQUEST_TEMPLATE.md` (confirmed absent).

### 3.2 Root `requirements.txt` (current)

```text
-e ./quantbuild
-e ./quantlog
-e ./quantanalytics
pytest
python-dotenv>=1.0
pyyaml>=6.0
pydantic>=2.4.0
filelock>=3.20.3
```

Observations:

- Editable `quantbuild` does **not** pull `quantbuild/requirements.txt` (no package metadata deps) → `httpx`, `feedparser`, `yfinance`, etc. absent unless added at root or via a dedicated extras/dev file.
- `pydantic` / `filelock` are currently on the **root** install path because LiveRunner behavioral probes need them; treat as **test/CI runtime** until packaging metadata is fixed (proposal §5.3).
- `quantresearch` is **not** installed by root requirements.
- `quantbridge` is path-imported via `tests/conftest.py` (`quantbridge/src`); no editable install; bridge has **no** `tests/` tree.

### 3.3 Module test layouts and offline results

| Module | Test path | Collect | Offline run (suite root cwd unless noted) | Blockers / notes |
|---|---|---|---|---|
| **Root** | `tests/` (10 files) | **112** | **112 passed** ~3.7s | Includes #104 N/W/E + mutation + demo schema/boundary tests |
| **quantbuild** | `quantbuild/tests/` | 246 + **1 collection error** (`test_finnhub_source` → missing `httpx`) | `--ignore=…/test_finnhub_source.py` → **245 passed, 1 skipped** ~1.1s | Finnhub needs `httpx` (in `quantbuild/requirements.txt`, not root). `test_live_runner*` are **unit/mocked** (23 passed; no broker). Nested CI expects sibling layout. |
| **quantlog** | `quantlog/tests/` | **61** | From suite root: **5 failed, 56 passed** (relative fixture paths). From `cwd=quantlog/`: **61 passed** ~0.13s | CWD-sensitive fixtures under `tests/fixtures/contracts/`. Nested CI is Windows-only smoke. |
| **quantanalytics** | `quantanalytics/tests/` | **45** | **45 passed** ~0.9s | Looks CI-ready offline with current root install (`pandas`/`numpy`/`scipy` present via analytics editable). |
| **quantresearch** | `quantresearch/tests/` | errors without `PYTHONPATH=quantresearch` | With `PYTHONPATH=quantresearch`: **4 failed, 45 passed** | Not in root requirements. Failures: dossier/ledger/preregistration (suite_root / artifact / content asserts). Needs `-e ./quantresearch` + suite layout or path fixes before CI. |
| **quantbridge** | *(none)* | — | — | Safety gates live under **root** `tests/test_live_execution_gate_*.py` (#104). Do **not** claim bridge module coverage until a suite exists. |
| **quantmetrics_os** | *(no pytest suite found)* | — | — | Orchestrator scripts only; document as unsupported for module CI. |

### 3.4 Dependency / flakiness risk matrix

| Risk | Modules | Proposed handling |
|---|---|---|
| Missing optional news/HTTP deps (`httpx`, …) | quantbuild `test_finnhub_source` | Install via `requirements-dev.txt` **or** isolate file until extras exist; **no** skip/xfail of failing CI job |
| Network / external APIs | finnhub/news/yfinance paths | Keep **out** of default CI job; document as unsupported or mock-only subset |
| Broker / OpenAPI / credentials | quantbridge clients, smokes, launchers | **Never** in CI; already banned by AGENTS.md; #104 gates remain deny-first |
| CWD-relative fixtures | quantlog contracts | Run with `working-directory: quantlog` **or** make paths repo-root-safe in a follow-up implementation PR |
| Suite artifact / QuantOS paths | quantresearch ledger/dossier | Fix install + suite_root resolution before enabling; else document unsupported |
| Nested workflow layout mismatch | quantbuild nested CI | Do **not** enable nested workflows from monorepo root blindly; prefer **root** job steps with explicit paths |
| Python version drift | root 3.11 vs qb nested 3.10 vs local 3.12 | Keep root CI on **3.11**; optionally matrix later (plan approval) |

### 3.5 Supported Python versions (declared)

| Package | `requires-python` |
|---|---|
| quantlog | `>=3.10` |
| quantanalytics | `>=3.10` |
| quantresearch | `>=3.10` |
| quantbuild nested CI | runs **3.10** |
| **Root CI (authoritative)** | **3.11** |

---

## 4. Coordination with #104 (mandatory)

Per tech-lead brief and earlier #106 brief:

1. Root CI **must keep** PR-A N/W/mutation and PR-B E/mutation steps **unchanged in intent** (commands may stay explicit; counts may grow only by additive tests).
2. Do **not** remove, soft-fail, or gate these behind module-suite success.
3. quantbridge may lack a module pytest tree; **root gate tests remain the coverage** for live-execution safety.
4. Any new module job failure must not be “fixed” by weakening #104 assertions.

**Acceptance floor (post-implementation):** no loss of current **112** root tests or PR-A/B gate suites (counts may increase).

---

## 5. Proposed implementation (subject to plan approval)

Implementation happens **only after** Claude PLAN APPROVE, on **this same feature branch**, stopping later at `READY FOR CLAUDE CODE REVIEW #106`.

### 5.1 Phase A — PR template + checklist (docs/process only)

Add `.github/PULL_REQUEST_TEMPLATE.md` requiring:

- Linked issue(s) and high-impact yes/no (AGENTS.md definition)
- Touched modules / explicit non-goals
- Exact head SHA for independent review
- Test commands + pass/fail + `NOT RUN` with reason
- CI run URL(s) on that SHA
- Mutation evidence when safety-critical
- Secrets / live / broker safeguards attestation
- Independent review + **owner merge approval** gates
- Risk / rollback notes

### 5.2 Phase B — Incremental offline module suites in **root** CI

Add **separate** workflow steps (fail-closed, no `continue-on-error`) **only** for suites proven green offline on the implementation head:

| Priority | Candidate step | Gate to enable |
|---|---|---|
| P0 (already live) | root `tests` + #104 N/W + #104 E + demo | Keep |
| P1 | `quantanalytics/tests` | Reconfirm green on CI Python 3.11 after install |
| P2 | `quantlog/tests` with `working-directory: quantlog` (or path fix) | Must be **61 passed** from CI cwd strategy; no fixture skips |
| P3 | `quantbuild/tests` offline subset | Need `httpx` (dev/extras) **or** explicit exclude **only if** documented as unsupported module file — prefer installing deps and running full offline suite; never xfail |
| P4 | `quantresearch/tests` | Only after `-e ./quantresearch` + failing 4 tests repaired or scoped with owner-approved unsupported list |

**Document unsupported (do not pretend coverage):**

- quantbridge module pytest (absent) — covered by root #104 gates
- quantmetrics_os pytest (absent)
- Nested Windows quantlog smoke / nested quantbuild sibling CI (layout incompatible)
- Any test requiring live brokers, paid APIs, or network without mocks

### 5.3 Phase C — Dev / test dependency hygiene

Proposal (no production behavior change):

1. Introduce `requirements-dev.txt` (or `[project.optional-dependencies] dev` at suite level) including at least: `pytest`, `pydantic`, `filelock`, and quantbuild offline needs such as `httpx` (and other **verified test-only** pins discovered during implementation).
2. Root CI `Install dependencies` becomes: `pip install -r requirements.txt -r requirements-dev.txt` (exact shape TBD in implementation).
3. Keep runtime/editable installs reproducible; avoid silently expanding production attack surface.
4. Re-verify #104 LiveRunner probes still import under the new split.

### 5.4 Phase D — Negative / invariant proofs

- Re-run root #104 N/W/E + mutation on the implementation SHA (must stay green).
- Add or retain a small CI assertion that new module steps did not delete/rename the #104 step commands (optional workflow comment + evidence MD).
- No broker connections in any new step.

### 5.5 Explicitly deferred

- Branch protection (#105)
- Enabling nested module workflows as-is
- Full quantbuild news/network suite against live Finnhub
- quantresearch ledger/dossier failures until suite_root story is designed

---

## 6. Allowed / forbidden file touch list (implementation PR)

**Likely allowed after plan approval:**

- `.github/workflows/ci.yml` (additive steps only)
- `.github/PULL_REQUEST_TEMPLATE.md` (new)
- `requirements.txt` / new `requirements-dev.txt` (dep hygiene)
- `docs/plans/ISSUE_106_*.md` evidence
- Minimal test path/CWD fixes **only if required** to make an offline suite deterministic (prefer workflow `working-directory` first)
- quantresearch install wiring if enabling that suite

**Forbidden without new owner scope:**

- Production trading/broker/gate policy logic
- Softening #104 tests
- Secrets, deploy units, live scripts execution
- Skip/xfail to greenwash

---

## 7. Acceptance criteria (for later CODE review)

1. Draft PR; **no merge** without owner + independent review on **exact SHA**.
2. Root suite ≥ **112** tests; #104 PR-A/B suites still present and green.
3. Every newly added module suite runs in root CI, offline/deterministic, fail-closed.
4. Unsupported modules documented in evidence MD (not claimed covered).
5. PR template usable for SHA-bound review.
6. Exact SHA, commands, CI URLs, runtimes recorded.
7. Max **2** repair rounds after CODE review; then STOP & REDESIGN.

---

## 8. Plan-phase deliverables (this PR)

| Item | Status |
|---|---|
| Branch from `main` @ `4f10151…` | Done |
| Inventory of CI / modules / deps / runtimes | Done (this doc) |
| Concrete phased implementation proposal | Done (§5) |
| Production / CI code changes | **None** (plan only) |
| Draft PR | To be opened |
| Stop | **READY FOR CLAUDE PLAN REVIEW #106** |

---

## 9. Next step after plan approval

Cursor implements Phases A→D on **this branch**, pushes evidence + green CI, updates PR body, and stops at:

**READY FOR CLAUDE CODE REVIEW #106**
