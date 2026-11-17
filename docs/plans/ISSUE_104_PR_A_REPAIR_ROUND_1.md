# Issue #104 PR-A — Repair round 1/2 evidence

**PR:** https://github.com/roelofgootjesgit/QuantMetrics-Suite/pull/115  
**Branch:** `cursor/issue-104-pr-a-live-gate-3716` (draft)  
**Prior reviewed head (REQUEST CHANGES):** `ac4fabe3b64948badbc7827fd1a7b4b0d63bed64`  
**Repair round 1 code head (CI green):** `199673cd1c3e4dfc96bddbbc6598d6ca57d89e96`  
**Recheck SHA:** PR #115 branch tip at review time (`git rev-parse HEAD` / GitHub PR head)  
**Verdict target:** Claude CODE recheck PR-A (B1/B2)  
**Scope:** PR-A only — no PR-B, no brokers, no deployment, no live trading, no merge

---

## Stop line

**READY FOR CLAUDE CODE RECHECK PR-A**

---

## Blockers addressed

### B1 — dotenv / shell parser-equivalent refuse

| Requirement | Implementation | Tests |
|---|---|---|
| Parser-equivalent key detection (`export KEY=1`, tabs, quotes, spaced assignment) | `dotenv_values` in `live_execution_gate.env_file_contains_gate_keys` | N10 parametrized forms |
| Snapshot 3 gate keys before load; restore + deny on mutation | `snapshot_gate_keys` / `restore_gate_keys` / `load_dotenv_refusing_gate_keys` | N10 behavioral, N10b |
| Exact path consumed by loaders | `config.py` (`find_dotenv`), orchestrator `_bootstrap_env` | N10, N10b |
| Shell: snapshot set/unset **and** values; exit 2 before exec | `quantbuild/scripts/vps/run_live.sh` | N10c (`true; KEY=1`, `declare -x KEY=1`), W4c |
| Residual risk documented (source ≠ sandbox) | Gate + `run_live.sh` comments | — |

### B2 — behavioral negatives + killed mutations

| Requirement | Tests |
|---|---|
| Behavioral N10: real `quantbuild.config` import with malicious `.env` → nonzero, no retained auth | `test_n10_behavioral_config_import_subprocess` |
| Behavioral N10d: real `CTraderBroker._hydrate_credentials_from_dotenv` → deny before client | `test_n10d_behavioral_hydrate_real_method` |
| W4b: Oanda close/modify denied; zero API requests | `test_w4b_oanda_close_modify_denied_no_api_request` |
| Explicit empty env allowlist deny | `test_b2_explicit_empty_env_allowlist_denies` |
| cTrader `practice` hard-reject even if allowlisted | `test_b2_ctrader_practice_denied_even_if_allowlisted` |
| Scratch-copy mutations for every required wire — all KILLED | see mutation table below |

---

## Local evidence

Commands actually run on repair head:

```text
pytest tests -q
# → 69 passed

pytest tests/test_live_execution_gate_n.py \
        tests/test_live_execution_gate_w.py \
        tests/test_live_execution_gate_mutation.py -q
# → 64 passed

python run_demo.py
# → Verdict: VALIDATION_REQUIRED (0 validation errors)
```

---

## CI evidence

| Trigger | Run | Head SHA | Conclusion | Job |
|---|---|---|---|---|
| push | [44111113886](https://github.com/roelofgootjesgit/QuantMetrics-Suite/actions/runs/44111113886) | `199673c…` | **success** | `test-and-demo` |
| pull_request | [44111126237](https://github.com/roelofgootjesgit/QuantMetrics-Suite/actions/runs/44111126237) | `199673c…` | **success** | `test-and-demo` |

CI job steps (push run):

| Step | Result |
|---|---|
| Run tests (`pytest tests -q`) | **69 passed** |
| Run issue gate suite (N/W/mutation) | **64 passed** |
| Run deterministic demo | `VALIDATION_REQUIRED` |

---

## Mutation table (scratch copies — all KILLED)

| Mutation | Probe | Result |
|---|---|---|
| Remove cTrader session gate | connect / typo env | **KILLED** |
| Remove cTrader orders gates | place / close / modify | **KILLED** |
| Fail-open host selection → LIVE | connect with stub SDK | **KILLED** |
| Remove Oanda SESSION/ORDERS gates | connect / submit / close / modify | **KILLED** |
| Loader gate bypass | `_get_oanda_client` | **KILLED** |
| Dotenv scan always false | `assert_dotenv_path_has_no_gate_keys` | **KILLED** |
| Hydrate scan removed | `_hydrate_credentials_from_dotenv` | **KILLED** |
| Config uses plain `load_dotenv` | import `quantbuild.config` | **KILLED** |
| Shell skips snapshot check | `run_live.sh` + stub PYTHON | **KILLED** |
| Truthy auth coercion (`true`/`yes`) | ORDERS allow | **KILLED** |
| Live-freeze bypass | live SESSION without enablement file | **KILLED** |
| Leading-zero account accepted | `canonicalize_ctrader_account_id("0123")` | **KILLED** |
| Empty env allowlist fail-open | ORDERS with `ALLOWED_BROKER_ENVIRONMENTS=""` | **KILLED** |
| cTrader practice allowed | practice SESSION when allowlisted | **KILLED** |

Control (unmutated) probes still deny as expected.

---

## Files touched (repair round 1)

- `quantbridge/src/quantbridge/safety/live_execution_gate.py`
- `quantbridge/src/quantbridge/safety/__init__.py`
- `quantbuild/src/quantbuild/config.py`
- `quantmetrics_os/orchestrator/quantmetrics.py`
- `quantbuild/scripts/vps/run_live.sh`
- `tests/test_live_execution_gate_n.py`
- `tests/test_live_execution_gate_w.py`
- `tests/test_live_execution_gate_mutation.py`

---

## Non-goals (unchanged)

- No PR-B entrypoint preflights
- No systemd / EnvironmentFile migration
- No broker connections, credentials, deployment, or live trading
- No merge to `main`

---

## Next step

Independent Claude CODE recheck on the **exact PR #115 head SHA** at review time
(code repair `199673c` + this evidence MD on the same branch).

If round 2 still fails: **STOP & REDESIGN**.
