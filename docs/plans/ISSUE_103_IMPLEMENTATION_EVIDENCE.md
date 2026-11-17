# Issue #103 — Strict `delete_allowed` implementation evidence

**Issue:** https://github.com/roelofgootjesgit/QuantMetrics-Suite/issues/103  
**Draft PR:** https://github.com/roelofgootjesgit/QuantMetrics-Suite/pull/120  
**Branch:** `cursor/issue-103-delete-allowed-plan-3716`  
**PLAN APPROVE head:** `e3e35ec2fb7690e90dd4e397a2a0436871219e99`  
**Implementation head:** *(CI green SHA after push)*  
**Production path note:** APPROVE text said `orchestrator/data_lifecycle.py`; actual module is `quantmetrics_os/scripts/data_lifecycle.py` (sole copy; matches plan + imports).  
**Stop line:** **READY FOR CLAUDE CODE REVIEW #103**

---

## T1–T4 delivery

| ID | Requirement | Delivery |
|---|---|---|
| T1 | `get("delete_allowed") is True` only; full negative matrix | `_delete_allowed_strict` + parametrized helper/scan tests |
| T2 | Scratch mutations `bool(...)` and `== True` fail real probe | `test_t2_mutation_*_killed` via subprocess against this suite’s cases |
| T3 | Real FS snapshot before/after `_scan_runs` and `main()` (tmp) | mtime/size maps equal; reports only under tmp `qmos/reports` |
| T4 | Do not edit tracked reports | No writes to `quantmetrics_os/reports/data_lifecycle_report.*` |

Helper docstring states: only literal JSON boolean true permits.

---

## Changed files

- `quantmetrics_os/scripts/data_lifecycle.py` — `_delete_allowed_strict` + use in `_scan_runs`
- `tests/test_data_lifecycle_delete_allowed.py` — **new** (T1–T4)
- `docs/plans/ISSUE_103_IMPLEMENTATION_EVIDENCE.md` — this file

**Not changed:** tracked reports, delete/compress features, #104 gates, CI workflow, brokers/trading.

---

## Mutation matrix (T2)

| Mutant | Probe | Result |
|---|---|---|
| Unmutated production module | STRICT_OK | **pass** |
| `is True` → `bool(...)` | string `"false"` / int `1` slip | **KILLED** (`MUTATION_UNDETECTED`) |
| `is True` → `== True` | int `1` slips (`1 == True`) | **KILLED** (`MUTATION_UNDETECTED`) |

---

## Local evidence

```text
pytest tests/test_data_lifecycle_delete_allowed.py -q
# → 37 passed

pytest tests -q
# → (see after run)

#104 N/W/mutation + E/mutation + run_demo.py
# → (see after run)

git diff quantmetrics_os/reports/
# → empty (T4)
```

---

## CI evidence

| Trigger | Run | Head | Conclusion |
|---|---|---|---|
| *(fill after push)* | | tip | pending |

---

## Residual risks

- Future delete features must call `_delete_allowed_strict` (not reintroduce `bool`/`== True`).
- String `"true"` remains deny (intentional fail-closed).
- PIT Gate A BLOCKED; production allowlist empty.

---

## Stop

**READY FOR CLAUDE CODE REVIEW #103**
