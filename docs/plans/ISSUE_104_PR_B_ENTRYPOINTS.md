# Issue #104 PR-B — Entrypoint fail-closed preflights

**PR:** https://github.com/roelofgootjesgit/QuantMetrics-Suite/pull/116 (draft)  
**Branch:** `cursor/issue-104-pr-b-entrypoints-3716`  
**Head:** `62941e4541b943a68faab4e90936e67c28d90ec8`  
**Base:** `main` at/after `4a2ea7eba0cf393b246fc33203a5c956398ed5b0` (PR-A #115 merged)  
**Brief:** issue #104 comment PR-B implementation brief  
**Plan:** `docs/plans/ISSUE_104_FAIL_CLOSED_LIVE_SAFETY_PLAN.md` §§5/7/9/11  

---

## Stop line

**READY FOR CLAUDE CODE REVIEW PR-B**

---

## Scope (PR-B only)

Fail-closed **entrypoint / script** preflights that reuse the canonical QuantBridge gate. No policy duplication. No systemd/deploy edits. No broker connections, credentials, or live trading.

| # | Entrypoint | Intent | File |
|---|---|---|---|
| 4 | Bridge `CTraderBroker(mode=openapi)` before OpenAPI client | SESSION | `quantbridge/.../brokers/ctrader_broker.py` |
| 7 | `create_broker` non-mock / Oanda + `validate_suite_layout` | SESSION | `quantbuild/.../broker_factory.py` |
| — | QB `CTraderBroker._init_real_bridge` early deny | SESSION | `quantbuild/.../broker_ctrader.py` |
| 8 | `LiveRunner.run` when `dry_run=False` before connect | ORDERS | `quantbuild/.../live_runner.py` |
| 9 | `app.py` `live --real` before `LiveRunner` | ORDERS | `quantbuild/.../app.py` |
| 10 | `launch_live_safe` before recovery/Popen `--real` | ORDERS | `quantbuild/scripts/launch_live_safe.py` |
| 11 | Orchestrator `build --real` before subprocess spawn | ORDERS | `quantmetrics_os/orchestrator/quantmetrics.py` |
| 12 | Smoke / lifecycle / runtime_control / diagnose | SESSION/ORDERS | scripts under `quantbuild/` + `quantbridge/` |

Helper (no policy copy): `quantbuild/.../live_execution_preflight.py`.

---

## Local evidence

```text
pytest tests -q
# → 84 passed

pytest tests/test_live_execution_gate_e.py tests/test_live_execution_gate_e_mutation.py -q
# → 15 passed

pytest tests/test_live_execution_gate_n.py tests/test_live_execution_gate_w.py tests/test_live_execution_gate_mutation.py -q
# → (PR-A suite still green; included in full 84)

python run_demo.py
# → Verdict: VALIDATION_REQUIRED (0 errors)
```

## CI evidence

| Trigger | Run | Head | Conclusion |
|---|---|---|---|
| pull_request | [44121121750](https://github.com/roelofgootjesgit/QuantMetrics-Suite/actions/runs/44121121750) | `62941e4…` | **success** |

Job `test-and-demo`: root tests + PR-A gate suite + PR-B E suite + demo — all green.

---

## E-tests (behavioral)

| ID | Case | Expect |
|---|---|---|
| E1 | `app.py` live `--real` without auth | rc=2; LiveRunner not constructed |
| E2 | `create_broker` non-mock without SESSION | deny; zero broker ctor |
| E3 | Bridge openapi broker typo env | deny; zero OpenAPI client |
| E4 | LiveRunner ORDERS path without auth | deny before connect |
| E5 | `launch_live_safe` ORDERS deny | preflight fail; no Popen |
| E6 | mock + dry_run | succeed without ORDERS auth |
| E7 | `run_demo` | unchanged green |
| E8 | `create_broker` gate import fail | deny |
| E9 | Oanda gate import fail | deny |
| — | Orchestrator `--real` | rc=2; no subprocess |
| — | diagnose non-mock missing allowlist | deny before `create_broker` |

---

## Mutation table (scratch copies — KILLED)

| Mutation | Result |
|---|---|
| Remove `app.py` ORDERS preflight (`if not dry_run` → False) | **KILLED** |
| Remove `create_broker` non-mock SESSION preflight | **KILLED** |
| Remove bridge openapi SESSION `assert_live_execution_allowed` | **KILLED** |
| Remove `launch_live_safe` ORDERS `preflight_live_execution` | **KILLED** |

---

## Residual risks / open migration

- `quantbridge-paper.service` still uses in-checkout `EnvironmentFile=/opt/quantbridge/local.env` — **migration item**; no unit edits in this PR.
- VPS QuantBuild dotenv resolution remains cwd-dependent (`find_dotenv`); operators must not place gate keys in checkout env files.
- Wire gates (PR-A) remain the non-bypassable core if an entrypoint is skipped.
- PIT Gate A stays **BLOCKED**.

---

## Non-goals

- No PR-A policy changes beyond reuse  
- No systemd / deployment / EnvironmentFile edits  
- No broker connections, smoke against live brokers, credentials in git  
- No merge without owner + independent Claude review on exact SHA  

---

## Next step

Independent Claude CODE review on the **exact PR-B head SHA**.  
Max 2 repair rounds; then STOP & REDESIGN.
