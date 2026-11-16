# Issue #104 — Fail-closed live execution safety (PLAN)

**Status:** PLAN ONLY — no implementation in this PR.  
**Issue:** [#104](https://github.com/roelofgootjesgit/QuantMetrics-Suite/issues/104)  
**Base:** current `main` at plan authoring time.  
**Workflow gate:** high-impact → independent Claude **PLAN** review on exact head SHA → only then implementation PR.  
**Safety during this phase:** no broker credentials read, no broker connection, no live/smoke orders, no deployment changes.

Companion inventory (static path catalog): `docs/plans/ISSUE_104_LIVE_SAFETY_INVENTORY.md`.

---

## 1. Problem statement

Real broker sessions and orders are today controlled only by path-local defaults (`dry_run`, `mock_mode`, YAML strings). There is **no central fail-closed gate**.

Critical defect (owner-verified on main):

```text
CTraderOpenApiClient.connect:
  host = DEMO if environment.lower() == "demo" else LIVE
```

Any non-`demo` string (empty, typo, `practice`, `prod`) selects **LIVE_HOST**.  
`app.py live --real` sets `dry_run=False` with no owner flag, environment allowlist, or account allowlist. Scripts and systemd can reach OpenAPI **outside** `app.py`.

Documentary agent prohibitions are not a technical block (`AGENTS.md`).

---

## 2. Goals and non-goals

### Goals (implementation PR after PLAN approval)

1. **Default-deny** real order mutation (place / close / modify) unless explicitly authorized.  
2. **Strict environment allowlist** — unknown/empty/typo never maps to LIVE.  
3. **Explicit owner authorization** for order-capable execution.  
4. **Account allowlist** — empty list means deny all (fail-closed).  
5. Enforcement at **wire-level choke points** so alternate entrypoints cannot bypass.  
6. **Negative tests** that prove invalid configs cannot reach connect/order code paths (mocked; no real network).  
7. Preserve **demo dry-run, mock, backtest, and research** behaviour without requiring live auth.

### Non-goals (this issue / first implementation PR)

- Do not rewrite trading strategies, risk math, or propfirm simulators.  
- Do not change VPS systemd unit files or production EnvironmentFiles in the same PR (document operator migration only).  
- Do not purchase challenges, run smoke against brokers, or store secrets in git.  
- Do not claim branch protection or CI covers module suites.  
- Do not implement lifecycle deletion (#103) or PROP-01 FTMO rules engine.

---

## 3. Inventory summary (see companion doc for full tables)

| Class | Examples | Order risk |
|---|---|---|
| Primary CLI | `quantbuild/.../app.py live --real` → `LiveRunner` | High |
| Factory / brokers | `create_broker`, QB `CTraderBroker`, `OandaBroker`, bridge `CTraderBroker(mode=openapi)` | High |
| Wire client | `CTraderOpenApiClient` (`ProtoOANewOrderReq` / Close / Amend) | **Highest** |
| Bypass scripts | `ctrader_smoke.py` (QB+bridge), `run_order_lifecycle_check.py`, `run_runtime_control.py` (close), `diagnose_ctrader_connect.py` (connect) | High / connect |
| Launch / orch | `launch_live_safe.py`, `quantmetrics.py build --real`, `run_live.sh` | High |
| Deploy | `quantbuild-ctrader-demo.service` → always `--real` via launcher; `quantbridge-paper.service` OpenAPI close loop | High (operator) |
| Safe paths | mock clients, `dry_run=True` order skip, backtest, research, paper_shadow | Keep intact |

**Bypass reality:** gating only `app.py` is insufficient. Smoke and bridge scripts construct brokers directly.

---

## 4. Authorization model (design)

### 4.1 Intents

| Intent | Meaning | Required checks |
|---|---|---|
| `SESSION` | TCP connect + account auth (market data / reconcile) | Environment allowlisted; account allowlisted; provider recognized |
| `ORDERS` | place / close / modify | All `SESSION` checks **plus** owner execution authorization |

Rationale: `LiveRunner` dry-run with `data.source=ctrader` may still connect for bars. That must not silently enable orders, but may still need session allowlists so a typo cannot auth against LIVE for data.

### 4.2 Environment policy (fail-closed host mapping)

Replace fail-open ternary with an explicit map after allowlist membership:

| Provider | Default allowlist (if env var unset) | Host mapping |
|---|---|---|
| cTrader | `demo` only | `demo` → DEMO_HOST; `live` → LIVE_HOST **only if** `live` is on allowlist |
| Oanda | `practice` only | `practice` → practice API; `live` → live API **only if** allowlisted |

Rules:

1. Normalize: strip + lower-case.  
2. Empty / unknown → **raise** `LiveExecutionDenied` (never default to LIVE).  
3. Allowlist source: `QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS` (comma-separated). If unset, use provider defaults above. If set to empty string after parse → deny all.  
4. `practice` is **not** a cTrader OpenAPI environment; using it for cTrader → deny (today it would incorrectly hit LIVE).

### 4.3 Owner authorization (ORDERS intent)

| Variable | Semantics |
|---|---|
| `QUANTMETRICS_EXECUTION_AUTHORIZED` | Must be exact string `1` for `ORDERS`. Any other value / missing → deny. |

Notes:

- Do **not** treat truthy strings (`true`, `yes`, `on`) as authorized — mirrors #103 fail-closed boolean lesson.  
- CLI `--real` alone is **never** sufficient.  
- Authorization is process-environment based (systemd EnvironmentFile / operator shell). Not stored in git.  
- Optional future: signed owner token file — **out of scope** for v1.

### 4.4 Account allowlist

| Variable | Semantics |
|---|---|
| `QUANTMETRICS_ALLOWED_ACCOUNT_IDS` | Comma-separated account IDs. Comparison after strip; exact string match. |

Rules:

1. Missing variable or empty list → **deny all accounts** (fail-closed).  
2. Account ID used for the check is the resolved runtime account (post env/YAML merge), never a placeholder.  
3. Multi-account orchestration must pass each account through the same check.

### 4.5 Shared API (canonical)

Proposed module (implementation later):

`quantbridge/src/quantbridge/safety/live_execution_gate.py`

```text
class LiveExecutionDenied(RuntimeError): ...

@dataclass(frozen=True)
class LiveExecutionRequest:
    provider: str          # "ctrader" | "oanda"
    environment: str
    account_id: str
    intent: Literal["SESSION", "ORDERS"]

def assert_live_execution_allowed(req: LiveExecutionRequest, *, environ: Mapping[str, str] | None = None) -> None:
    """Raise LiveExecutionDenied unless policy allows. Pure; no I/O; no network."""

def resolve_ctrader_host(environment: str, *, environ=None) -> str:
    """Allowlist + map to DEMO/LIVE endpoint constant names; raise if denied."""
```

QuantBuild imports the same module for factory / Oanda / LiveRunner (suite already loads quantbridge for OpenAPI). No second divergent policy copy.

### 4.6 What remains allowed without ORDERS auth

- `mock_mode=True` / bridge `mode=mock` — local simulation; **gate not invoked** for mock client.  
- `LiveRunner(dry_run=True)` order path (broker=None / no submit) — unchanged.  
- Backtests, research scripts, quantlog demo, analytics — unchanged.  
- `SESSION` on allowlisted `demo`/`practice` with allowlisted account — connect for data **without** `QUANTMETRICS_EXECUTION_AUTHORIZED=1`.  
- `ORDERS` on demo OpenAPI — **still requires** owner flag + account allowlist (demo orders are still real broker API mutations).

---

## 5. Where to enforce (so bypasses fail)

Ordered by leverage. Implementation must wire **all** rows marked Required.

| # | Location | When | Intent | Required? |
|---|---|---|---|---|
| 1 | `CTraderOpenApiClient.connect` | before choosing host / starting TCP | `SESSION` | **Yes — primary** |
| 2 | `CTraderOpenApiClient.submit_market_order` / `close_trade` / `modify_trade` | before protobuf mutate | `ORDERS` | **Yes — primary** |
| 3 | Host selection | inside connect after allowlist | n/a | **Yes — replace fail-open** |
| 4 | QuantBridge `CTraderBroker.__init__` when `mode=="openapi"` | before constructing OpenAPI client | `SESSION` (early deny) | Yes (defense in depth) |
| 5 | `OandaBroker.connect` | before `oandapyV20.API(...)` | `SESSION` | **Yes** |
| 6 | `OandaBroker.submit_market_order` / `close_trade` / modify | before API call | `ORDERS` | **Yes** |
| 7 | `create_broker` when returning non-mock / Oanda | construction time | `SESSION` if non-mock | Yes (early UX) |
| 8 | `LiveRunner` when `dry_run=False` | before `broker.connect` / first order | `ORDERS` | Yes (clear error at CLI) |
| 9 | `app.py` when resolving `--real` | before `cmd_live` | `ORDERS` preflight | Yes (fail fast) |
| 10 | `launch_live_safe.py` preflight | before subprocess `--real` | `ORDERS` | Yes |
| 11 | `quantmetrics.py build --real` | before spawn | `ORDERS` | Yes |
| 12 | Smoke / lifecycle / runtime_control scripts | before connect/order | matching intent | Yes (or rely on #1–2 alone; prefer explicit preflight for clearer errors) |

**Invariant:** Even if a caller skips #7–12, #1–3 and #5–6 still deny. That is the non-bypassable core.

**Explicitly do not** rely on: Telegram labels, documentary AGENTS.md, YAML comments, service unit names (“demo” / “paper”).

### Deployment note (no file changes in plan/implement-unless-owner-asks)

Existing `quantbuild-ctrader-demo.service` will **stop working** until EnvironmentFile sets:

- `QUANTMETRICS_EXECUTION_AUTHORIZED=1`  
- `QUANTMETRICS_ALLOWED_ACCOUNT_IDS=<demo-account-id>`  
- (optional) keep default env allowlist `demo`

Document this in the implementation PR; do not edit the unit in the first PR unless owner requests.

---

## 6. Negative tests (design)

All tests use **monkeypatch / stubs** — no real DNS, TCP, credentials, or SDK network. Assert that denied paths raise `LiveExecutionDenied` **before** mocked connect/order bodies run.

### 6.1 Policy unit tests (`quantbridge` + import from quantbuild)

| ID | Case | Expect |
|---|---|---|
| N1 | environment `""` / `prod` / `Practice` (cTrader) | deny; no LIVE host |
| N2 | environment `live` with default allowlist | deny |
| N3 | environment `live` with allowlist containing `live` but auth missing | `SESSION` may allow if account ok; `ORDERS` deny |
| N4 | `QUANTMETRICS_EXECUTION_AUTHORIZED` missing / `0` / `true` / `yes` | `ORDERS` deny |
| N5 | auth `1` but `ALLOWED_ACCOUNT_IDS` missing/empty | deny |
| N6 | auth `1`, allowlist `111`, account `222` | deny |
| N7 | auth `1`, allowlist `111`, account `111`, env `demo` | `ORDERS` allow (policy only) |
| N8 | Oanda env `live` default allowlist | deny |
| N9 | Oanda env `practice` + account allowlisted + auth | `ORDERS` allow |

### 6.2 Wire / client tests

| ID | Case | Expect |
|---|---|---|
| W1 | OpenAPI `connect` with env typo | raises before Client/host use |
| W2 | OpenAPI `submit_market_order` without auth | raises; stub ensures no `ProtoOANewOrderReq` send |
| W3 | OpenAPI close/modify without auth | same |
| W4 | Oanda `connect`/`OrderCreate` path without auth or bad env | raises before API ctor/request |

### 6.3 Entrypoint / bypass tests

| ID | Case | Expect |
|---|---|---|
| E1 | `app.py` live `--real` without auth | non-zero / denied before `LiveRunner.run` orders |
| E2 | `create_broker` + smoke-style `submit_market_order` without auth | denied |
| E3 | Direct bridge `CTraderBroker(mode="openapi")` | denied at init or connect |
| E4 | `LiveRunner(..., dry_run=False)` without auth | denied |
| E5 | `launch_live_safe` preflight without auth | exit preflight failure (mocked subprocess never started) |
| E6 | Mock mode / dry_run paths | **still succeed** without auth (regression) |
| E7 | Backtest / `run_demo` / root pytest | unchanged green |

CI for this issue: extend **module** tests under `quantbridge/tests` and `quantbuild/tests`; root `pytest tests -q` remains green. Do not require live broker in CI.

---

## 7. Affected files (planned implementation set)

| File | Change type |
|---|---|
| `quantbridge/src/quantbridge/safety/live_execution_gate.py` | **Add** — canonical policy |
| `quantbridge/src/quantbridge/safety/__init__.py` | **Add** |
| `quantbridge/src/quantbridge/execution/clients/ctrader_openapi_client.py` | **Edit** — gate + fail-closed host map |
| `quantbridge/src/quantbridge/execution/brokers/ctrader_broker.py` | **Edit** — early gate on openapi |
| `quantbuild/src/quantbuild/execution/broker_oanda.py` | **Edit** — SESSION/ORDERS gates |
| `quantbuild/src/quantbuild/execution/broker_factory.py` | **Edit** — early deny for non-mock |
| `quantbuild/src/quantbuild/execution/broker_ctrader.py` | **Edit** — optional early deny when `mock_mode=False` |
| `quantbuild/src/quantbuild/execution/live_runner.py` | **Edit** — deny when `dry_run=False` before connect/orders |
| `quantbuild/src/quantbuild/app.py` | **Edit** — `--real` preflight |
| `quantbuild/scripts/launch_live_safe.py` | **Edit** — preflight uses gate |
| `quantmetrics_os/orchestrator/quantmetrics.py` | **Edit** — `--real` preflight |
| `quantbuild/scripts/ctrader_smoke.py` / `quantbridge/scripts/ctrader_smoke.py` | **Edit** — fail closed or document reliance on wire gate |
| `quantbridge/scripts/run_order_lifecycle_check.py` / `run_runtime_control.py` | **Edit** — same |
| `quantbridge/tests/test_live_execution_gate.py` | **Add** |
| `quantbuild/tests/test_live_execution_gate_wiring.py` | **Add** |
| `docs/plans/ISSUE_104_…` / short note in `docs/PROP_ROADMAP.md` H1 | Docs only as needed |

**Out of implementation PR unless owner asks:** systemd unit bodies, VPS install scripts, filling real EnvironmentFiles.

---

## 8. Migration risks

| Risk | Impact | Mitigation |
|---|---|---|
| Existing demo OpenAPI systemd unit breaks | Service fails preflight/connect until env set | Document required env vars; operator sets EnvironmentFile; optional follow-up PR for unit comments |
| Operators used typo env that “worked” as LIVE | Suddenly denied | Intentional; log clear deny reason |
| Duplicate policy if someone reimplements in QB only | Drift | Single module in quantbridge; QB imports it |
| `SESSION` allowlist blocks dry-run data from ctrader | Data bootstrap fails | Ensure demo account ID listed for data-only hosts; or keep mock/dukascopy sources |
| False sense of safety | Agents still must not hold creds | Keep AGENTS.md procedural bans; gate is necessary not sufficient |
| Close-only failsafe cannot flatten in emergency without auth | Runtime control denied | Require auth on VPS that runs failsafe; document emergency procedure |

---

## 9. Acceptance criteria (implementation PR)

1. Unknown/empty cTrader environment **cannot** select LIVE_HOST (unit proof).  
2. Missing/false/`true` owner auth → no OpenAPI/Oanda order mutation (negative tests W2–W4, E1–E5).  
3. Empty/missing account allowlist → deny; wrong account → deny; listed account + auth + allowlisted env → policy allow.  
4. Alternate paths (smoke, direct OpenAPI, Oanda, launch_live_safe, orchestrator `--real`) covered by tests or proven via wire-level gate tests.  
5. Mock / dry_run / backtest / `python run_demo.py` / root `pytest tests -q` remain green without auth env.  
6. No secrets committed; no real broker calls in CI.  
7. Independent Claude **code** review on implementation SHA; owner merge approval.  
8. PROP roadmap H1 updated to “gate implemented; verify on SHA …” only after merge.

---

## 10. Rollback

1. Revert the implementation PR (single logical commit series preferred).  
2. Gate is fail-closed: if a production hotfix must restore prior behaviour temporarily, that is an **explicit owner decision** and must not silently weaken tests.  
3. Do not “fix” outages by setting `ALLOWED_BROKER_ENVIRONMENTS=*` or treating any string as LIVE.  
4. Inventory/plan docs can remain; they do not affect runtime.

---

## 11. Implementation sequence (after PLAN approval only)

1. Land `live_execution_gate.py` + policy unit tests (N1–N9).  
2. Patch `CTraderOpenApiClient` host map + connect/order gates (W1–W3).  
3. Patch `OandaBroker` (W4, N8–N9).  
4. Wire factory / LiveRunner / app / launch_live_safe / orchestrator (E1–E5).  
5. Confirm smoke/lifecycle either preflight or inherit wire deny.  
6. Run root + targeted module tests; record SHA; request Claude code review.

**STOP:** no step of §11 in this PLAN PR.

---

## 12. Review checklist for Claude (PLAN)

- [ ] Inventory completeness adequate for choke-point design?  
- [ ] Is wire-level enforcement (#1–3, #5–6) sufficient against listed bypasses?  
- [ ] Are default allowlists (`demo` / `practice`) and empty-account deny-all correct?  
- [ ] Is separating `SESSION` vs `ORDERS` sound for dry-run market data?  
- [ ] Negative test matrix prove “no connect/order side effects” without real brokers?  
- [ ] Migration impact on existing demo systemd path acceptable?  
- [ ] Scope stays clear of deployment edits and trading logic?

**PLAN verdict requested:** `APPROVE` / `REQUEST CHANGES` / `BLOCK` tied to this PR head SHA.

---

## 13. Open questions (non-blocking if Claude/owner decide)

1. Should `SESSION` on demo require account allowlist from day one, or only `ORDERS`? **Plan default: both**, stricter.  
2. Should close/modify in emergency failsafe share `ORDERS` auth or a separate `QUANTMETRICS_FLATTEN_AUTHORIZED`? **Plan default: same ORDERS auth** (simpler).  
3. Exact env var names — freeze in implementation PR after PLAN approval; names above are proposals.

---

**End of PLAN.** Implementation must not start until independent Claude PLAN review approves this design on the exact commit SHA of the plan PR.
