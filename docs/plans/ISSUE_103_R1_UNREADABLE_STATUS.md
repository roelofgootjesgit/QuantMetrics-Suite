# Issue #103 — R1 repair (unreadable status test)

**Draft PR:** https://github.com/roelofgootjesgit/QuantMetrics-Suite/pull/120  
**Branch:** `cursor/issue-103-delete-allowed-plan-3716`  
**Prior head (REQUEST CHANGES):** `e5352f97e858dfe4f3e7bdd7f1f5a3c3a6eb21b3`  
**R1 head:** *(CI green after push)*  
**Scope:** tests only — `tests/test_data_lifecycle_delete_allowed.py`  
**Stop:** **READY FOR CLAUDE R1 DIFF RECHECK #103**

## Change

`test_t1_unreadable_status_json_denies` no longer uses `chmod(0)` (root can still read). It monkeypatches `Path.read_text` so only the fixture `status.json` raises `PermissionError("denied")`; other paths call the original method. Asserts `delete_allowed is False` and `status == "unknown"`.

No production code, workflow, reports, skip/xfail.

## Local evidence

| Environment | Command | Result |
|---|---|---|
| non-root uid 1000 | `pytest tests -q` | **156 passed** |
| root uid 0 (sudo + user site-packages) | `pytest tests -q` | **156 passed** |
| both | `pytest tests/test_data_lifecycle_delete_allowed.py -q` | **37 passed** |
| both | unreadable test alone | **1 passed** |

## CI evidence

| Trigger | Run | Head | Conclusion |
|---|---|---|---|
| *(fill after push)* | | tip | pending |

## Stop

**READY FOR CLAUDE R1 DIFF RECHECK #103**
