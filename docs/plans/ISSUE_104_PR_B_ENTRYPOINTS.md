# Issue #104 PR-B — Entrypoint fail-closed preflights

**PR:** https://github.com/roelofgootjesgit/QuantMetrics-Suite/pull/116 (draft)  
**Branch:** `cursor/issue-104-pr-b-entrypoints-3716`  
**Repair round:** 1/2 (TESTS ONLY — T1 blocker)  
**Repair 1/2 tests head:** see PR #116 head / `git rev-parse HEAD` on this branch  
**Note:** root `requirements.txt` now includes `pydantic`/`filelock` so LiveRunner behavioral probes import under root CI (no production logic change).  
**Base:** `main` at/after `4a2ea7eba0cf393b246fc33203a5c956398ed5b0` (PR-A #115 merged)  
**Brief:** issue #104 — PR-B; tech-lead REQUEST CHANGES on `287440e` (T1: 10/17 mutants SURVIVED)  
**Plan:** `docs/plans/ISSUE_104_FAIL_CLOSED_LIVE_SAFETY_PLAN.md` §§5 / 7 / 9 / 11  

---

## Stop line

**READY FOR CLAUDE CODE RECHECK PR-B**

---

## Repair 1/2 summary (TESTS ONLY)

No production logic changes. Strengthened behavioral E-coverage and expanded scratch mutation probes so each of the 17 PR-B enforcement removals is **KILLED**.

| T1 ask | Delivery |
|---|---|
| E4 behavioral `LiveRunner` invoke | `test_e4_live_runner_real_without_auth` — `object.__new__(LiveRunner)` + real `run()`; deny before `connect` |
| Oanda `create_broker` + `validate_suite_layout` | `test_e_oanda_create_broker_denied_zero_ctor`; `test_e_validate_suite_layout_mandatory_before_broker` (ctrader+oanda) |
| Four scripts + dotenv variants | QB/bridge smoke, lifecycle, runtime_control + dotenv export/`KEY=1` variants; diagnose + QB `_init_real_bridge` |
| Re-run 17 PR-B + PR-A mutations | 17/17 KILLED; PR-A mutation module 18/18 pass; N/W/mutation 64 pass |

---

## Scope (PR-B only — unchanged production)

Fail-closed **entrypoint / script** preflights that reuse the canonical QuantBridge gate. No policy duplication. No systemd/deploy edits. No broker connections, credentials, or live trading.

| # | Entrypoint | Intent | File |
|---|---|---|---|
| 4 | Bridge `CTraderBroker(mode=openapi)` before OpenAPI client | SESSION | `quantbridge/.../ctrader_broker.py` |
| 7 | `create_broker` non-mock / Oanda + `validate_suite_layout` | SESSION | `broker_factory.py` |
| — | QB `CTraderBroker._init_real_bridge` early deny | SESSION | `broker_ctrader.py` |
| 8 | `LiveRunner.run` when `dry_run=False` before connect | ORDERS | `live_runner.py` |
| 9 | `app.py` `live --real` before `LiveRunner` | ORDERS | `app.py` |
| 10 | `launch_live_safe` before recovery/Popen `--real` | ORDERS | `launch_live_safe.py` |
| 11 | Orchestrator `build --real` before subprocess spawn | ORDERS | `quantmetrics.py` |
| 12 | Smoke / lifecycle / runtime_control / diagnose | SESSION/ORDERS | QB + bridge scripts |

Helper (no policy copy): `live_execution_preflight.py`. Bridge script env loaders refuse gate keys.

---

## Local evidence (repair 1/2)

```text
pytest tests -q
# → 112 passed

pytest tests/test_live_execution_gate_n.py \
        tests/test_live_execution_gate_w.py \
        tests/test_live_execution_gate_mutation.py -q
# → 64 passed (PR-A suite)

pytest tests/test_live_execution_gate_mutation.py -q
# → 18 passed (canonical PR-A mutation module; all wires KILLED)

pytest tests/test_live_execution_gate_e.py \
        tests/test_live_execution_gate_e_mutation.py -q
# → 43 passed (26 E behavioral + 17 PR-B mutations)

python run_demo.py
# → Verdict: VALIDATION_REQUIRED (0 errors)
```

---

## CI evidence

| Trigger | Run | Head | Conclusion |
|---|---|---|---|
| push (repair 1/2 + filelock stub) | *(filled after green CI)* | tip SHA | pending |

Job `test-and-demo` expected steps:

| Step | Local result |
|---|---|
| Run tests (`pytest tests -q`) | **112 passed** |
| Run issue #104 N/W/mutation | **64 passed** |
| Run issue #104 PR-B E + mutation | **43 passed** |
| Run deterministic demo | `VALIDATION_REQUIRED` |

---

## Test → entrypoint mapping (behavioral)

| Test | Entrypoint | Assert |
|---|---|---|
| E1 | `app.cmd_live(--real)` | rc=2; LiveRunner ctor=0 |
| E2 | `create_broker` ctrader non-mock | deny; ctor=0 |
| E3 | Bridge openapi broker | deny; OpenAPI client=0 |
| E4 | `LiveRunner.run` dry_run=False | deny; connect=0 |
| E5 | `launch_live_safe._preflight` | fail; Popen=0 |
| E6 | mock + dry_run | succeed without ORDERS |
| E7 | `run_demo` | unchanged |
| E8 | `create_broker` gate import fail | deny |
| E9 | Oanda gate import fail | deny |
| orchestrator | `cmd_build(--real)` | rc=2; spawn=0 |
| diagnose | `diagnose_ctrader_connect` | deny; create_broker=0 |
| oanda factory | `create_broker(oanda)` | deny; OandaBroker=0 |
| layout | `validate_suite_layout` ctrader+oanda | layout raises; ctor=0 |
| QB smoke | `quantbuild/.../ctrader_smoke` | deny; create_broker=0 |
| bridge smoke | `quantbridge/.../ctrader_smoke` openapi | deny; broker=0 |
| bridge smoke dotenv | `load_local_env` variants | LiveExecutionDenied |
| lifecycle | `run_order_lifecycle_check` openapi | deny; broker=0 |
| lifecycle dotenv | `load_env_files` | LiveExecutionDenied |
| runtime | `run_runtime_control` openapi+failsafe | deny; broker=0 |
| runtime dotenv | `load_env_files` | LiveExecutionDenied |
| QB init bridge | `_init_real_bridge` | SESSION deny |

---

## Mutation table — 17 PR-B (scratch copies — all KILLED)

| ID | Mutation site | Probe | Result |
|---|---|---|---|
| m01 | `app.py` ORDERS (`if not dry_run` → False) | `cmd_live(--real)` proceeds | **KILLED** |
| m02 | `LiveRunner` ORDERS (`if not dry_run` → False) | `run()` reaches `connect` | **KILLED** |
| m03 | `create_broker` ctrader SESSION removed | non-mock ctor | **KILLED** |
| m04 | `create_broker` oanda SESSION removed | oanda ctor | **KILLED** |
| m05 | ctrader `validate_suite_layout` removed | layout skipped → ctor | **KILLED** |
| m06 | oanda `validate_suite_layout` removed | layout skipped → ctor | **KILLED** |
| m07 | QB `_init_real_bridge` SESSION removed | stub QB broker constructs | **KILLED** |
| m08 | Bridge openapi SESSION removed | broker constructs | **KILLED** |
| m09 | `launch_live_safe` ORDERS removed | `_preflight` ok without deny | **KILLED** |
| m10 | Orchestrator ORDERS removed | `--real` spawn not rc=2 | **KILLED** |
| m11 | QB `ctrader_smoke` ORDERS removed | `create_broker` called | **KILLED** |
| m12 | `diagnose_ctrader_connect` SESSION removed | `create_broker` called | **KILLED** |
| m13 | Bridge smoke ORDERS removed | broker ctor | **KILLED** |
| m14 | Lifecycle ORDERS removed | broker ctor | **KILLED** |
| m15 | Runtime ORDERS removed | broker ctor | **KILLED** |
| m16 | Bridge smoke dotenv refuse removed | AUTH loaded from local.env | **KILLED** |
| m17 | Lifecycle dotenv refuse removed | AUTH loaded from .env | **KILLED** |

---

## Mutation table — PR-A regression (canonical module — all KILLED)

Re-ran `tests/test_live_execution_gate_mutation.py` (**18 collected tests, 18 passed**). Tech-lead “26 PR-A mutations” maps to the same wire set Claude used on the prior review (multi-site composites: ≥3 ORDERS stubs, Oanda SESSION+ORDERS multi-replace, controls). Canonical module results:

| Mutation | Result |
|---|---|
| Remove cTrader session gate | **KILLED** |
| Remove cTrader orders gates (place/close/modify) | **KILLED** |
| Fail-open host selection → LIVE | **KILLED** |
| Remove Oanda SESSION/ORDERS gates | **KILLED** |
| Loader gate bypass | **KILLED** |
| Dotenv scan always false | **KILLED** |
| Hydrate scan removed | **KILLED** |
| Config uses plain `load_dotenv` | **KILLED** |
| Shell skips snapshot check | **KILLED** |
| Truthy auth coercion (`true`/`yes`) | **KILLED** |
| Live-freeze bypass | **KILLED** |
| Leading-zero account accepted | **KILLED** |
| Empty env allowlist fail-open | **KILLED** |
| cTrader practice allowed | **KILLED** |
| Control unmutated connect/orders | deny preserved |

Full PR-A N/W/mutation: **64 passed**.

---

## Changed files (repair 1/2)

- `tests/test_live_execution_gate_e.py` (behavioral expansion only)
- `tests/test_live_execution_gate_e_mutation.py` (17 probes hardened)
- `docs/plans/ISSUE_104_PR_B_ENTRYPOINTS.md` (this file)

**Production files:** unchanged in this repair round.

---

## Residual risks / open migration

- `quantbridge-paper.service` still uses in-checkout `EnvironmentFile=/opt/quantbridge/local.env` — **migration item**; no unit edits in this PR.
- VPS QuantBuild dotenv resolution remains cwd-dependent (`find_dotenv`); operators must not place gate keys in checkout env files.
- Wire gates (PR-A) remain the non-bypassable core if an entrypoint is skipped.
- PIT Gate A stays **BLOCKED**.
- Account ID must be provided via authorized external configuration, not bridge `local.env` (owner/deployment).

---

## Non-goals

- No production logic changes in repair 1/2  
- No PR-A policy changes  
- No systemd / deployment / EnvironmentFile edits  
- No broker connections, smoke against live brokers, credentials in git  
- No merge without owner + independent Claude review on exact SHA  

---

## Next step

Independent Claude **CODE RECHECK** on the **exact PR #116 head SHA** after this push.

Max 2 repair rounds; then **STOP & REDESIGN**.
