# Issue #106 — CI module coverage implementation (CODE)

**Issue:** https://github.com/roelofgootjesgit/QuantMetrics-Suite/issues/106  
**Draft PR:** https://github.com/roelofgootjesgit/QuantMetrics-Suite/pull/118  
**Branch:** `cursor/issue-106-ci-coverage-plan-3716`  
**Plan APPROVE head:** `481b064ea8538d5148c3f90fc638e9693337f8fd`  
**Implementation head (CI green):** `cfedc39e663f6974c634fa8af39fef3e7cca1233`  
**Base:** `main` @ `4f10151e1a33a94c1c29bf48c543e11eb9ffc06d`  
**Stop line:** **READY FOR CLAUDE CODE REVIEW #106**

---

## Scope delivered (Claude PLAN APPROVE conditions)

| ID | Condition | Delivery |
|---|---|---|
| V1 | Full `quantbuild/tests` in CI; `httpx` in `requirements-dev.txt`; no ignores | Yes — CI step runs entire `quantbuild/tests` |
| V2 | Socket guard on qb/log/analytics suites | `--disable-socket --allow-unix-socket` + negative proof test |
| V3 | QuantResearch out of this PR | No quantresearch CI step; workflow assert rejects `quantresearch` |
| V4 | Root regression parsing `ci.yml` for #104 + demo; no `continue-on-error` | `tests/test_ci_workflow_preservation.py` |
| A | PR template SHA-bound checklist | `.github/PULL_REQUEST_TEMPLATE.md` |
| Dev deps | Move test-only pydantic/filelock; LiveRunner probes still import | `requirements-dev.txt`; E4 still in root suite |

**Not changed:** production trading/broker/gate logic, allowlists, deploy, credentials. PIT Gate A BLOCKED.

---

## Changed files

- `requirements.txt` — remove pydantic/filelock (moved to dev)
- `requirements-dev.txt` — **new** (pytest, pydantic, filelock, httpx, pytest-socket + rationale pins)
- `.github/workflows/ci.yml` — install dev deps; add offline module steps P1–P3
- `.github/PULL_REQUEST_TEMPLATE.md` — **new**
- `tests/test_ci_workflow_preservation.py` — **new** (V2 negative + V4 preservation)
- `docs/plans/ISSUE_106_CI_MODULE_COVERAGE_IMPLEMENTATION.md` — this file
- Plan inventory MD remains for history

---

## Local evidence (implementation)

```text
pytest tests -q
# → 115 passed  (+3 workflow preservation / socket-guard proofs)

pytest tests/test_live_execution_gate_n.py \
        tests/test_live_execution_gate_w.py \
        tests/test_live_execution_gate_mutation.py -q
# → 64 passed

pytest tests/test_live_execution_gate_e.py \
        tests/test_live_execution_gate_e_mutation.py -q
# → 43 passed

python run_demo.py
# → Verdict: VALIDATION_REQUIRED

pytest quantanalytics/tests -q --disable-socket --allow-unix-socket
# → 45 passed

(cd quantlog && pytest tests -q --disable-socket --allow-unix-socket)
# → 61 passed

pytest quantbuild/tests -q --disable-socket --allow-unix-socket
# → 247 passed, 1 skipped
```

---

## CI evidence

| Trigger | Run | Head | Conclusion |
|---|---|---|---|
| push | [44138739111](https://github.com/roelofgootjesgit/QuantMetrics-Suite/actions/runs/44138739111) | `cfedc39…` | **success** |
| pull_request | [44138750567](https://github.com/roelofgootjesgit/QuantMetrics-Suite/actions/runs/44138750567) | `cfedc39…` | **success** |

Job `test-and-demo` on `cfedc39`:

| Step | Result |
|---|---|
| `pytest tests -q` | **115 passed** |
| #104 N/W/mutation | **64 passed** |
| #104 E/mutation | **43 passed** |
| `run_demo.py` | `VALIDATION_REQUIRED` |
| quantanalytics (socket guard) | **45 passed** |
| quantlog (cwd + socket guard) | **61 passed** |
| quantbuild (socket guard) | **247 passed, 1 skipped** |

---

## Independent-review checklist (for Claude CODE)

- [ ] Verdict on **exact** PR head SHA
- [ ] V1–V4 conditions met without skip/xfail/continue-on-error
- [ ] QuantResearch absent from CI
- [ ] No production/live/broker changes
- [ ] Mutation/security: N/A for this CI/docs/deps PR beyond workflow preservation + #104 still green
- [ ] Owner merge authorization still required; draft until then

---

## Residual risks

- Nested module workflows (Windows quantlog / sibling-layout quantbuild) remain unused by root CI — documented unsupported.
- `yaml.safe_load` maps workflow key `on:` → `True` (YAML 1.1); preservation tests intentionally inspect `jobs`/`steps` only.
- Socket guard is process-level for module steps; root #104 suite does not enable `--disable-socket` globally (unchanged behavior); V2 negative proof covers guard semantics.
- QuantResearch follow-up issue still required for the 4 failing tests (V3).
- #105 branch protection still parked (owner).

---

## Stop

**READY FOR CLAUDE CODE REVIEW #106**
