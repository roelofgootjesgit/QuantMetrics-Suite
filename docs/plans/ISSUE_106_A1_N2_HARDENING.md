# Issue #106 — A1 + N2 hardening (DIFF RECHECK)

**Issue:** https://github.com/roelofgootjesgit/QuantMetrics-Suite/issues/106  
**Draft PR:** https://github.com/roelofgootjesgit/QuantMetrics-Suite/pull/118  
**Branch:** `cursor/issue-106-ci-coverage-plan-3716`  
**Prior CODE APPROVE head:** `5bed81e67c186ff3817279525ff1961df4130d54`  
**This hardening head (CI green):** `552d817a601187c7f18d46cdfa1b529a424a04b1`  
**Scope:** **A1 + N2 only** (tech-lead comment `6956182578`)  
**Stop line:** **READY FOR CLAUDE A1 DIFF RECHECK #106**

---

## Changes (tests + evidence only)

| File | Change |
|---|---|
| `tests/test_ci_workflow_preservation.py` | A1: job+step `continue-on-error` ban; soft-fail ban (`\|\| true`, `\|\| :`, `; true`, `set +e`); four mutation kills; N2: hard `import pytest_socket` (no `importorskip`) |
| `docs/plans/ISSUE_106_A1_N2_HARDENING.md` | this evidence |

**Not modified:** production code, workflow steps, requirements, quantresearch, existing quantbuild skip, VPS/services.

---

## A1 four-mutant matrix (all KILLED)

| ID | Mutant | Prior | Now |
|---|---|---|---|
| m01 | `python run_demo.py \|\| true` | SURVIVED | **KILLED** |
| m02 | job-level `continue-on-error: true` | SURVIVED | **KILLED** |
| m03 | drop #104 N/W/mutation command | (existing) | **KILLED** |
| m04 | strip `--disable-socket` from module steps | (existing) | **KILLED** |

Live workflow also rejects step-level `continue-on-error` and soft-fail patterns `|| :`, `; true`, `set +e` via the same checker.

---

## N2

`test_n2_socket_guard_blocks_network_hard_requirement` imports `pytest_socket` directly (fails hard if missing). Offline AF_INET construction still raises `SocketBlockedError`. `pytest-socket` remains in `requirements-dev.txt` (CI install unchanged).

---

## Local evidence

```text
pytest tests -q
# → 119 passed

pytest tests/test_live_execution_gate_{n,w,mutation}.py -q
# → 64 passed

pytest tests/test_live_execution_gate_e{,_mutation}.py -q
# → 43 passed

python run_demo.py
# → VALIDATION_REQUIRED

pytest quantanalytics/tests -q --disable-socket --allow-unix-socket
# → 45 passed

(cd quantlog && pytest tests -q --disable-socket --allow-unix-socket)
# → 61 passed

pytest quantbuild/tests -q --disable-socket --allow-unix-socket
# → 247 passed, 1 skipped

pytest tests/test_ci_workflow_preservation.py -q
# → 7 passed (incl. 4 A1 mutants KILLED)
```

---

## CI evidence

| Trigger | Run | Head | Conclusion |
|---|---|---|---|
| push | [44141436457](https://github.com/roelofgootjesgit/QuantMetrics-Suite/actions/runs/44141436457) | `552d817…` | **success** |
| pull_request | [44141450822](https://github.com/roelofgootjesgit/QuantMetrics-Suite/actions/runs/44141450822) | `552d817…` | **success** |

Job counts on `552d817`: **119** / **64** / **43** / demo / **45** / **61** / **247+1 skip**.

---

## Residual risks

- Same-PR edit weakness of workflow self-checks remains (#105 branch protection still owner-parked).
- QuantResearch / N1 desk-grade skip remain separate follow-ups.
- PIT Gate A BLOCKED; production allowlist empty.

---

## Stop

**READY FOR CLAUDE A1 DIFF RECHECK #106**
