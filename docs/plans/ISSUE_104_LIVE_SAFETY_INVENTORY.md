# Issue #104 — Live / real-order path inventory (PLAN)

**Status:** PLAN inventory only. No gate implementation in this document.  
**Design authority:** `docs/plans/ISSUE_104_FAIL_CLOSED_LIVE_SAFETY_PLAN.md` (authorization model, choke points, tests, acceptance, rollback).  
**Scope:** Fail-closed live safety design — catalog every code path that can open a real broker session or place/close/modify real orders.  
**Method:** Static code search across `quantbuild`, `quantbridge`, `quantmetrics_os`, scripts, deploy, systemd, CLI. **No broker connection, no credential reads, no smoke/live runs.**  
**Repo root inspected:** `/agent/repos/QuantMetrics-Suite`  
**Related:** GitHub issue #104; `docs/PROP_ROADMAP.md` H1; owner comment requiring PLAN + independent Claude PLAN review before implementation.  
**R2 note (2026-11-16):** Env-file / dotenv sources (a)–(e) expanded below to match PLAN §4.7 (**R1.1** / recommended **N-3**).

---

## Executive verdict

There is **no central fail-closed live gate** today. Real execution is gated only by loose, path-local controls:

1. QuantBuild CLI defaults `live` to `--dry-run` / `dry_run=True`, but `--real` flips it with no owner flag, env allowlist, or account allowlist.
2. cTrader OpenAPI host selection is **fail-open toward LIVE**: any `environment != "demo"` (case-insensitive) selects `EndPoints.PROTOBUF_LIVE_HOST`.
3. Multiple scripts construct brokers **outside** `app.py` and call `submit_market_order` / `close_trade` directly.
4. Systemd units and VPS wrappers can start `live --real` unattended once credentials exist in `EnvironmentFile`.
5. **Five env-file surfaces** can inject process or construction-time values (see § Env-file / dotenv sources) — including dotenv `override=True`, shell `source`, and an in-checkout systemd `EnvironmentFile`.

Documentary prohibitions are **not** a technical block.

---

## Critical host-selection fact (H1)

```208:208:quantbridge/src/quantbridge/execution/clients/ctrader_openapi_client.py
host = EndPoints.PROTOBUF_DEMO_HOST if self.environment.lower() == "demo" else EndPoints.PROTOBUF_LIVE_HOST
```

| Input `environment` | Host |
|---|---|
| `"demo"` (any case) | DEMO |
| `"live"`, `"practice"`, `""`, typo, `"prod"`, unset coerced to non-demo | **LIVE** |

There is **no** `CTRADER_ENVIRONMENT` / `OANDA_ENVIRONMENT` env override in code. Environment comes from YAML `broker.environment` (and constructor args). Account IDs come from YAML + `CTRADER_*` / `OANDA_*` env merges.

---

## Structured inventory

Legend for **Can place orders?**  
- **Yes** — can submit/modify/close real broker orders when credentials + non-mock/openapi + (where applicable) `dry_run=False`.  
- **Connect only** — can open a real broker session (auth / market data / reconcile) but does not place orders on the happy path.  
- **Close/modify only** — can flatten or amend existing positions without opening new ones.  
- **No** — mock/paper/observation/docs only.

### A. Primary QuantBuild entrypoints

| Entry point | Module | Can place orders? | Host selection | Current guards | Risk notes |
|---|---|---|---|---|---|
| `python -m src.quantbuild.app … live [--dry-run\|--real]` | `quantbuild/src/quantbuild/app.py` → `cmd_live` → `LiveRunner` | **Yes** if `--real` | Via `create_broker` → YAML `broker.environment`; cTrader non-`demo` → LIVE host | `--dry-run` default True; `--real` sets `dry_run=False`; suite layout preflight only | **Primary production loop.** No owner auth, no account allowlist, no env allowlist. |
| `app.py … fetch --source ctrader\|auto` | `app.py` `cmd_fetch` | Connect only (OHLCV) | Same factory | Needs credentials if `mock_mode=false` | Real TCP/auth for market data; no order submit. |
| `app.py … suite-notify --real` | `app.py` `cmd_suite_notify` | No | N/A | Labels Telegram only | Does not trade; can mis-signal “real” ops state. |
| `app.py … backtest` / `news-test` | `app.py` | No | N/A | N/A | Research / news only. |

CLI mechanism (`app.py`):

- `live --dry-run` → `action=store_true, default=True`
- `live --real` → if set, `args.dry_run = False` before `cmd_live`
- No mutual exclusion group on `live` (unlike `suite-notify`)

### B. LiveRunner loop

| Entry point | Module | Can place orders? | Host selection | Current guards | Risk notes |
|---|---|---|---|---|---|
| `LiveRunner(cfg, dry_run=…).run()` | `quantbuild/src/quantbuild/execution/live_runner.py` | **Yes** when `dry_run=False` | `create_broker(cfg)` then QuantBridge OpenAPI if `mock_mode=false` | `dry_run` skips order path; `OrderManager(broker=None)` when dry; execution_guards (spread/slippage/max positions/daily loss R); news gate; regime filters; `BasicRiskValidator` | Always constructs broker; connects when not dry_run **or** dry_run + `data.source=ctrader`. Submit via `QuantBridgeEngine.execute` → adapter → `submit_market_order`. Also `close_trade` on slippage flatten / thesis invalid. |
| Programmatic import of `LiveRunner` | same | **Yes** if caller passes `dry_run=False` | same | same | **Bypass of CLI defaults.** |

Order path (real): `_evaluate_and_execute` → `quantbridge.execute(ExecutionRequest)` → `CTraderAdapter`/`OandaAdapter.place_order` → broker `submit_market_order`.

### C. Broker factories and clients

| Entry point | Module | Can place orders? | Host selection | Current guards | Risk notes |
|---|---|---|---|---|---|
| `create_broker(cfg)` | `quantbuild/src/quantbuild/execution/broker_factory.py` | Constructs client capable of orders | cTrader: `environment` default `"demo"`; Oanda: default `"practice"`; `mock_mode` default **True** for cTrader | Defaults lean safe if YAML omits keys | **No allowlist.** Any caller with `mock_mode:false` + creds gets real transport. |
| `CTraderBroker` (QuantBuild wrapper) | `quantbuild/src/quantbuild/execution/broker_ctrader.py` | **Yes** when `mock_mode=False` | Passes `environment` to QuantBridge `CTraderBroker(mode="openapi")` | Cred check on connect; hydrates from bridge `.env`/`local.env` | Loads bridge via `QUANTBRIDGE_SRC_PATH` or suite layout. Direct `submit_market_order` / `close_trade` / `modify_trade`. |
| `OandaBroker` | `quantbuild/src/quantbuild/execution/broker_oanda.py` | **Yes** | `oandapyV20.API(..., environment=self.environment)` — `"practice"` vs `"live"` | Cred check; no dry_run inside client | **No mock mode.** Connect + `OrderCreate` / `TradeClose` / `TradeCRCDO` are real when env=`live`. Schema allows `practice|live` only (`config_schema.BrokerConfig`) — **not enforced at runtime** by factory. |
| QuantBridge `CTraderBroker` | `quantbridge/src/quantbridge/execution/brokers/ctrader_broker.py` | **Yes** if `mode=="openapi"` | Forwards `environment` to OpenAPI client | `mode` default `"mock"` | Factory-like constructor; scripts often force `mode=openapi`. |
| `CTraderOpenApiClient` | `quantbridge/.../clients/ctrader_openapi_client.py` | **Yes** | **DEMO iff env==`demo` else LIVE** | `connected` checks only | **Ultimate wire.** `ProtoOANewOrderReq`, `ProtoOAClosePositionReq`, `ProtoOAAmendPositionSLTPReq`. |
| `CTraderMockClient` | `quantbridge/.../clients/ctrader_mock_client.py` | No (local sim) | N/A | In-memory | Safe. |

### D. QuantBuild-internal execution adapters

| Entry point | Module | Can place orders? | Host selection | Current guards | Risk notes |
|---|---|---|---|---|---|
| `QuantBridgeEngine.execute` | `quantbuild/.../execution/quantbridge.py` | **Yes** | Inherited from wrapped broker | `BasicRiskValidator` only | Thin risk/router; no live gate. |
| `CTraderAdapter` / `OandaAdapter.place_order` | same | **Yes** | Inherited | Symbol map + unit normalize | Direct to `submit_market_order`. |
| QuantBuild `OrderManager` | `quantbuild/.../execution/order_manager.py` | Close/modify when `broker` set | Inherited | `broker=None` in dry_run | Trailing / BE / partial close call `modify_trade` / `close_trade`. |

### E. Scripts that can start real sessions or place orders

| Entry point | Module | Can place orders? | Host selection | Current guards | Risk notes |
|---|---|---|---|---|---|
| `quantbuild/scripts/launch_live_safe.py` | wrapper → subprocess `app.py live --real` | **Yes** | From config YAML (`ctrader_quantbridge_openapi.yaml` defaults `environment: demo`, `mock_mode: false`) | Preflight: provider=ctrader, `mock_mode` must be false, creds present; optional `--require-unpaused`; `--dry-launch` preflight-only; max runtime | **Explicitly launches `--real`.** Injects `CTRADER_*` into child env. Used by systemd. |
| `quantbuild/scripts/ctrader_smoke.py` | `create_broker` → connect → **place** → close | **Yes** | YAML `broker.environment` | None beyond config | **Bypasses app.py / dry_run.** Places real order if `mock_mode:false`. |
| `quantbridge/scripts/ctrader_smoke.py` | direct `CTraderBroker` | **Yes** if `--mode openapi` or `CTRADER_MODE=openapi` | YAML `environment` (default demo) | Mode default from YAML/`CTRADER_MODE` (often mock) | CLI overrides for account/token; **bypasses QuantBuild.** |
| `quantbridge/scripts/run_order_lifecycle_check.py` | `CTraderBroker` + `OrderManager.place_and_validate` | **Yes** if mode openapi | YAML env | PropGuard / pause file / account state optional | Can place+close real orders. |
| `quantbridge/scripts/run_runtime_control.py` | `RuntimeControlLoop` | **Close/modify only** (failsafe `close_all`) | YAML + mode | Pause file, account state machine, mismatch streak | systemd paper unit uses `--mode openapi` → **can close live/demo positions**. |
| `quantbridge/scripts/recover_execution_state.py` | `CTraderBroker` + recovery | Connect / sync (no place) | YAML + mode | Retries | Reconnects OpenAPI; rebuilds local registry. |
| `quantbuild/scripts/diagnose_ctrader_connect.py` | `create_broker` + `connect` | Connect only | YAML | Skips if mock_mode | Probes DEMO TCP; can auth to whatever env YAML says (LIVE if mis-set). |
| `quantbridge/scripts/run_multi_account_execution_check.py` | orchestrator + `OrderManager` | Mock only in this script (`mode="mock"` hard-coded) | N/A | Account selector / PropGuard | Pattern is a **bypass template** if someone swaps mode to openapi. |
| `quantbridge/scripts/run_account_orchestration_check.py` | selector only | No | N/A | Policy routing | No broker wire. |
| `quantbridge/scripts/run_vps_paper_cycle.py` | regression suite wrapper | Depends on suite steps | Profile-driven | Paper profile intended | Indirect; review suite steps before treating as safe. |
| `quantbridge/scripts/account_control.py` | account state machine | No | N/A | pause/enable | Controls tradability flags used by other paths. |
| `quantbridge/scripts/validate_account_env.py` | env presence check | No | N/A | `--require-secrets` | Documents per-account `QB_ACCOUNT_*` keys; does not gate runtime. |
| `quantbuild/scripts/market_data_smoke.py` | Dukascopy/parquet | No | N/A | N/A | No broker. |
| `quantbuild/scripts/watch_live_scan.py` | log tailer | No | N/A | N/A | Observability only. |

### F. Orchestrator / VPS wrappers

| Entry point | Module | Can place orders? | Host selection | Current guards | Risk notes |
|---|---|---|---|---|---|
| `quantmetrics.py build --real -c …` | `quantmetrics_os/orchestrator/quantmetrics.py` `cmd_build` | **Yes** | Child QuantBuild config | Forwards `--real` / `--dry-run` to `app.py live` | Loads orchestrator `.env` (creds). Comment in `.env.example` documents demo `--real`. |
| `quantmetrics.py build` without flags | same | No orders (default dry_run unless `--real`) | same | Default appends neither if both unset — QuantBuild live still defaults dry_run True | Safe by QuantBuild default. |
| `scripts/vps/run_live.sh … live --real` | sources orchestrator `.env` → `python -m src.quantbuild.app` | **Yes** | YAML | Same as app.py | Convenient path to load VPS secrets then real live. |
| `scripts/vps/start_weekrun.sh` | restarts systemd unit | **Yes** (via service) | Service config | N/A | Unattended restart of live-capable unit. |
| `scripts/vps/install_systemd_service.sh` | installs unit | Enables live-capable service | N/A | Copies empty env example | Operator must fill creds. |
| `quantbridge/ops/vps/install_paper_service.sh` | installs `quantbridge-paper.service` | Close/modify via runtime control | Unit uses `--mode openapi` | Named “paper” but OpenAPI | Misnamed risk: OpenAPI against demo/live host per YAML env. |

### G. Systemd / env / deploy

| Entry point | Module | Can place orders? | Host selection | Current guards | Risk notes |
|---|---|---|---|---|---|
| `quantbuild-ctrader-demo.service` | `quantbuild/deploy/systemd/quantbuild-ctrader-demo.service` | **Yes** | Config `configs/ctrader_quantbridge_openapi.yaml` (`environment: demo`, `mock_mode: false`) | launch_live_safe preflight; `--skip-recovery` | **Always `--real` via launcher.** Name says demo; host still follows YAML env string. |
| `quantbuild.env.example` | `deploy/systemd/quantbuild.env.example` | N/A (creds) | N/A | Empty placeholders | Installed to `/etc/quantbuild/quantbuild.env` (external path; compliant shape for future gate keys). |
| `quantbridge-paper.service` | `quantbridge/ops/vps/quantbridge-paper.service` | Close/modify | `ctrader_icmarkets_demo.yaml` + `--mode openapi` | Runtime pause/failsafe | OpenAPI reconcile/close loop. **`EnvironmentFile=/opt/quantbridge/local.env` is inside checkout — R1.1 (e) migration item.** |
| `quantbuild/.env.example`, `quantbridge/.env.example`, `quantmetrics_os/orchestrator/.env.example`, `config.vps.example.env` | env templates | N/A | Documents `QUANTBUILD_CONFIG`, CTRADER_*, OANDA_* | Examples only | Orchestrator example comments `build --real`. |
| Docker / compose | — | **None found** | — | — | No Dockerfile / compose in tree. |

### H. Data / IO connections (no orders)

| Entry point | Module | Can place orders? | Host selection | Current guards | Risk notes |
|---|---|---|---|---|---|
| `parquet_loader` via broker `fetch_ohlcv` | `quantbuild/src/quantbuild/io/parquet_loader.py` | Connect only | Broker already connected | Truth-mode fail-fast for ctrader | Used by LiveRunner bootstrap / fetch. |
| `oanda_loader` | `quantbuild/src/quantbuild/io/oanda_loader.py` | Connect only (pricing history) | `environment` param default practice | N/A | Can hit Oanda API; no OrderCreate. |

### I. Paper / shadow / research (non-order)

| Entry point | Module | Can place orders? | Notes |
|---|---|---|---|
| `PaperShadowRunner` | `quantbuild/.../execution/paper_shadow.py` | No | Observation dual-track; “Neither executes real trades”. |
| Backtest engine / research CLIs | quantbuild / quantresearch / quantmetrics_os matrix | No | `--dry-run` there means “don’t run backtests / don’t write registry”, not broker dry_run. |
| QuantLog sample/smoke | quantlog scripts | No | Event schema allows `environment=live` as **label** only. |
| `docs/v1_1_audit_pack/.../live_runner.py` | docs snapshot | No (not runtime import path) | Stale copy; do not treat as entrypoint. |
| `quantbuild_v2` | scaffold | No | No broker/order code. |

---

## Bypass matrix (paths that skip `app.py`)

| Bypass | How |
|---|---|
| `quantbuild/scripts/ctrader_smoke.py` | `create_broker` + `submit_market_order` |
| `quantbridge/scripts/ctrader_smoke.py` | Direct `CTraderBroker` + `submit_market_order` |
| `quantbridge/scripts/run_order_lifecycle_check.py` | Direct broker + `OrderManager.place_and_validate` |
| `quantbridge/scripts/run_runtime_control.py` | Direct broker + failsafe closes |
| `quantbridge/scripts/recover_execution_state.py` | Direct broker connect |
| Import `LiveRunner(..., dry_run=False)` | Skips CLI `--real` parsing |
| Import `CTraderOpenApiClient` / QuantBridge `CTraderBroker(mode="openapi")` | Skips QuantBuild factory defaults |
| Import `OandaBroker` + `connect`/`submit_market_order` | No mock_mode at all |
| `MultiAccountExecutionOrchestrator` + custom factory | Check script is mock; API is order-capable |
| systemd / `launch_live_safe` / `quantmetrics build --real` / `run_live.sh` | Still eventually hit `app.py`, but **operator-facing** alternate entry |

---

## Account ID / environment selection (current)

| Source | What it sets |
|---|---|
| YAML `broker.environment` | demo / practice / live / (any string) — **host switch for cTrader** |
| YAML `broker.account_id`, `access_token`, `client_id`, `client_secret`, `token` | Creds (prefer empty; filled from env) |
| YAML `broker.mock_mode` | QuantBuild cTrader local mock vs OpenAPI bridge |
| YAML `broker.mode` / env `CTRADER_MODE` | QuantBridge mock vs openapi (bridge scripts) |
| Env `CTRADER_ACCOUNT_ID`, `CTRADER_ACCESS_TOKEN`, `CTRADER_CLIENT_ID`, `CTRADER_CLIENT_SECRET` | Merged in `quantbuild/config.py` into broker dict; also constructor fallbacks; launch_live_safe / bridge scripts |
| Env `OANDA_ACCOUNT_ID`, `OANDA_TOKEN` | Oanda account |
| Env `QUANTBRIDGE_SRC_PATH` | Where QuantBuild loads bridge package |
| Bridge `local.env` / `.env` | Hydrated by QuantBuild `CTraderBroker` and many bridge scripts |
| Orchestrator `.env` | Sourced by `quantmetrics.py` and `run_live.sh` |
| systemd `EnvironmentFile` | Production injection (paths differ — see env-file table) |
| CLI `--account-id` / token overrides | `quantbridge/scripts/ctrader_smoke.py` only |
| `configs/accounts_baseline.yaml` + `QB_ACCOUNT_<ID>_*` | Multi-account policy / validate_account_env — **not wired into LiveRunner single-account path** |

**Not present today:** environment allowlist, account allowlist, owner authorization flag, enforced kill switch.  
**Frozen future gate key names (PLAN P8):** `QUANTMETRICS_EXECUTION_AUTHORIZED`, `QUANTMETRICS_ALLOWED_ACCOUNT_IDS`, `QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS`.

---

## Env-file / dotenv sources (R1.1 / N-3)

Complete catalog of files/loaders that can put values into process env or into broker construction. Gate keys must never be trusted from these surfaces (PLAN §4.7).

| ID | Path / module | Mechanism | What it affects today | Gate-key risk | PLAN fail-closed target |
|---|---|---|---|---|---|
| **(a)** | `quantbuild/src/quantbuild/config.py` | `load_dotenv(override=True)` at import | Overwrites QuantBuild process `os.environ` | **High** — can override process gate keys | Refuse startup if file contains any gate key; never authorize via dotenv |
| **(b)** | `quantmetrics_os/orchestrator/quantmetrics.py` `_bootstrap_env` | `load_dotenv(orchestrator/.env, override=True)` | Orchestrator process env; **inherited by child** QuantBuild | **High** — child inherits injected auth | Same refuse-on-presence; no auth via dotenv |
| **(c)** | `quantbuild/scripts/vps/run_live.sh` | `set -a; source …/orchestrator/.env; set +a` then `exec` Python | Entire process env **before** Python starts | **High** — shell source is not dotenv API but same injection | Scan file **before** `source`; gate key ⇒ nonzero exit; Python not launched |
| **(d)** | `quantbuild/src/quantbuild/execution/broker_ctrader.py` `_hydrate_credentials_from_dotenv` | `dotenv_values` on bridge `local.env` then `.env` | Merges into credential fields; **currently CTRADER_*** only | **Medium** — file may still contain gate keys; must not become auth channel | Gate key present ⇒ deny **before** `_init_real_bridge` / client construction; hydration stays CTRADER_* only |
| **(e)** | `quantbridge/ops/vps/quantbridge-paper.service` | `EnvironmentFile=/opt/quantbridge/local.env` | systemd service env for OpenAPI runtime_control | **High** — path is **inside** repo checkout `/opt/quantbridge` | Owner auth **only** via external root-owned file outside **all** checkouts, not writable by service user (e.g. `/etc/quantbuild/quantbuild.env`). Existing unit path = **migration item**; **no unit edits** in PLAN/PR-A/B without owner ask |

**Contrast (compliant pattern already used by QuantBuild demo unit):**  
`quantbuild/deploy/systemd/quantbuild-ctrader-demo.service` → `EnvironmentFile=/etc/quantbuild/quantbuild.env` (outside checkout). That is the shape owner authorization must use — not developer dotenv and not in-repo `local.env`.

**Related but not separate loaders:** `diagnose_ctrader_connect.py` docs suggest manually `source` orchestrator `.env` (same class as **(c)**); bridge scripts that read `local.env` for CTRADER_* (same class as **(d)** files).

---

## Existing safety checks (path-local, not central)

| Guard | Where | Gaps |
|---|---|---|
| CLI `dry_run` default True | `app.py` | Bypassed by `--real`, scripts, programmatic LiveRunner |
| `mock_mode` default True | `broker_factory` / many YAML | Live configs set `false`; smoke can still order |
| Bridge `mode` default mock | bridge YAML / `CTraderBroker` | Scripts/`CTRADER_MODE`/openapi force real |
| launch_live_safe preflight | credentials, mock_mode false, optional unpaused | Still aims to run `--real`; no LIVE host deny |
| Account state machine pause/breach | bridge accounts | Optional; not required on QuantBuild live |
| `trading.paused` file + RuntimeControlLoop | bridge runtime | Not used by QuantBuild LiveRunner |
| PropGuard / AccountLimits | bridge order lifecycle / multi-account | Not on QuantBuild LiveRunner path |
| LiveRunner execution_guards | spread, slippage, max positions, daily loss R | Risk controls, not env/account allowlist |
| `BasicRiskValidator` | QuantBuild QuantBridgeEngine | Geometry/risk % only |
| Paper shadow | observation | Not a gate |
| Suite layout validate | `app.py` main | Layout only |

---

## Candidate choke points for a central fail-closed gate

Ordered by leverage (single place blocks most bypasses):

1. **`CTraderOpenApiClient.connect` + order/close/modify methods**  
   Enforce: environment ∈ allowlist (`demo` only unless owner-authorized live); account_id ∈ allowlist; explicit authorization flag.  
   Blocks: all OpenAPI paths including smoke, lifecycle, runtime failsafe, QuantBuild bridge.

2. **`quantbridge.execution.brokers.ctrader_broker.CTraderBroker.__init__` when `mode=="openapi"`**  
   Same checks before constructing OpenAPI client.

3. **`quantbuild.execution.broker_factory.create_broker`**  
   Gate before returning any non-mock cTrader or Oanda live client.  
   Does **not** cover direct QuantBridge script imports → pair with (1)/(2).

4. **`OandaBroker.connect` / `submit_market_order` / `close_trade`**  
   Parallel gate for `environment=="live"` (and deny unknown).

5. **`LiveRunner.__init__` or `run` when `dry_run=False`**  
   Owner flag + allowlists before `broker.connect()`. Covers CLI/orchestrator/systemd; not smoke bypasses.

6. **`app.py` `live --real` resolution**  
   Require explicit env e.g. `QUANTBUILD_LIVE_ORDERS_AUTHORIZED=1` (name TBD) + refuse unless config env/account pass.  
   UX choke; still bypassable by import.

7. **`launch_live_safe.py` preflight**  
   Deny non-demo environment unless authorized; require account allowlist; refuse missing owner flag. Covers systemd unit.

8. **`quantmetrics.py cmd_build --real`**  
   Same authorization before spawning child.

9. **Shared pure function** (recommended design center)  
   e.g. `assert_live_execution_allowed(environment, account_id, *, want_real_orders: bool) -> None` used by (1)–(8). Fail closed: missing/false auth, unknown environment, account not listed → raise, no connect, no order.

### Suggested negative tests (from issue #104 / owner comment)

- Unknown / empty / typo environment must **not** select LIVE host (must fail or force demo).  
- Missing / false authorization → refuse `--real`, OpenAPI connect, and `submit_market_order`.  
- Wrong account_id → refuse.  
- Alternate paths: smoke scripts, `OrderManager.place_order`, direct OpenAPI client, Oanda live, `launch_live_safe`, orchestrator `--real`.  
- Never connect to broker in CI/agent runs; use mocks / monkeypatch EndPoints.

### Non-goals for the gate PR (per issue)

- Do not run smoke/live against brokers.  
- Do not change VPS deployments in the same PR without owner ask.  
- Do not weaken existing dry_run / mock defaults.

---

## Configs that already set `mock_mode: false` (demo env unless noted)

These can reach OpenAPI when credentials are present:

- `quantbuild/configs/ctrader_quantbridge_openapi.yaml` (systemd default)
- `quantbuild/configs/demo_loose_ctrader.yaml`
- `quantbuild/configs/demo_strict_ctrader.yaml`
- `quantbuild/configs/strict_prod_v2_ctrader_icmarkets.yaml`
- `quantbuild/configs/preflight_live_auto.yaml`
- `quantbuild/configs/preflight_live_ctrader.yaml`
- `quantbuild/configs/edge_unlock_discovery.yaml`

Oanda-oriented configs use `environment: practice` (not live) in checked YAMLs; factory still accepts `live` if YAML/operator sets it.

---

## PLAN gate criteria (for implementation PR — not this doc)

Before PROP-02 / agent execution:

1. Strict environment allowlist (fail-closed; unknown ≠ LIVE).  
2. Explicit owner authorization flag.  
3. Account allowlist.  
4. Negative tests across quantbuild + quantbridge including alternate execution paths.  
5. Independent Claude PLAN review on exact commit SHA; owner merge approval.

---

## Inventory completeness notes

- **No Docker** runtime paths found.  
- Root/module CI does not exercise live brokers.  
- Audit-pack `live_runner.py` under `docs/` is archival, not an entrypoint.  
- Env-file sources **(a)–(e)** listed above for PLAN R2 (**R1.1** / **N-3**).  
- This file is PLAN evidence for issue #104; implementation belongs on a separate reviewed PR.
