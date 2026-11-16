# Issue #104 — Fail-closed live execution safety (PLAN)

**Status:** PLAN ONLY — no implementation in this PR.  
**Issue:** [#104](https://github.com/roelofgootjesgit/QuantMetrics-Suite/issues/104)  
**Base:** current `main` at plan authoring time.  
**Workflow gate:** high-impact → independent Claude **PLAN** review on exact head SHA → only then implementation (split PR-A / PR-B).  
**Safety during this phase:** no broker credentials read, no broker connection, no live/smoke orders, no deployment changes, no production-code edits in this docs PR.

Companion inventory (static path catalog): `docs/plans/ISSUE_104_LIVE_SAFETY_INVENTORY.md`.

**PLAN remediation (2026-11-16):** Claude verdict on `7f3ad8b` was `REQUEST CHANGES`. This revision folds owner/tech-lead items **P1–P9** into the design below. See §14 for the checklist mapping.

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

Additional verified risk (**P1**): `quantbuild/src/quantbuild/config.py` calls `load_dotenv(override=True)`, so values from `.env` / dotenv can **overwrite** process environment. Gate keys must not be trustable from dotenv.

Documentary agent prohibitions are not a technical block (`AGENTS.md`).

---

## 2. Goals and non-goals

### Goals (after PLAN approval — via PR-A then PR-B)

1. **Default-deny** real order mutation (place / close / modify) unless explicitly authorized.  
2. **Strict environment allowlist** — unknown/empty/typo never maps to LIVE.  
3. **Explicit owner authorization** for order-capable execution, with dotenv non-authority (**P1**).  
4. **Account allowlist** — empty list means deny all (fail-closed); cTrader IDs strictly numeric (**P6**).  
5. Enforcement at **wire-level choke points** so alternate entrypoints cannot bypass.  
6. **Negative tests + mutation proofs** executed in **root CI** (**P2**).  
7. Preserve **demo dry-run, mock, backtest, and research** behaviour without requiring ORDERS auth.  
8. Gate import failure → deny, never silent fallback (**P3**).  
9. Cover Oanda read-path constructor in `oanda_loader` (**P4**).

### Non-goals

- Do not rewrite trading strategies, risk math, or propfirm simulators.  
- Do not change VPS systemd unit files or production EnvironmentFiles in the same PR (document operator migration only).  
- Do not purchase challenges, run smoke against brokers, or store secrets in git.  
- Do not claim branch protection covers module suites beyond what root CI actually runs.  
- Do not implement lifecycle deletion (#103) or PROP-01 FTMO rules engine.  
- Do not enable cTrader/Oanda **`live`** host until a **separate owner-only authorization file** outside the repo is designed and approved (**P1** live-enablement freeze).

---

## 3. Inventory summary (see companion doc for full tables)

| Class | Examples | Order risk |
|---|---|---|
| Primary CLI | `quantbuild/.../app.py live --real` → `LiveRunner` | High |
| Factory / brokers | `create_broker`, QB `CTraderBroker`, `OandaBroker`, bridge `CTraderBroker(mode=openapi)` | High |
| Wire client | `CTraderOpenApiClient` (`ProtoOANewOrderReq` / Close / Amend) | **Highest** |
| Direct API ctor | `quantbuild/.../io/oanda_loader.py` `_get_oanda_client` → `oandapyV20.API` (**P4** / #5b) | Connect / data |
| Bypass scripts | `ctrader_smoke.py` (QB+bridge), `run_order_lifecycle_check.py`, `run_runtime_control.py` (close), `diagnose_ctrader_connect.py` (connect) | High / connect |
| Launch / orch | `launch_live_safe.py`, `quantmetrics.py build --real`, `run_live.sh` | High |
| Deploy | `quantbuild-ctrader-demo.service` → always `--real` via launcher; `quantbridge-paper.service` OpenAPI close loop | High (operator) |
| Config / env | `config.py` `load_dotenv(override=True)` | **Auth bypass risk (P1)** |
| Safe paths | mock clients, `dry_run=True` order skip, backtest, research, paper_shadow | Keep intact |

**Bypass reality:** gating only `app.py` is insufficient. Smoke and bridge scripts construct brokers directly. Dotenv can override process gate keys unless blocked.

---

## 4. Authorization model (design)

### 4.1 Intents

| Intent | Meaning | Required checks |
|---|---|---|
| `SESSION` | TCP connect + account auth (market data / reconcile) | Environment allowlisted; account allowlisted + canonicalized; provider recognized; dotenv gate-key hygiene (**P1**) |
| `ORDERS` | place / close / modify | All `SESSION` checks **plus** owner execution authorization (exact `1`) |

Rationale: `LiveRunner` dry-run with `data.source=ctrader` may still connect for bars. That must not silently enable orders, but may still need session allowlists so a typo cannot auth against LIVE for data.

### 4.2 Environment policy (fail-closed host mapping)

Replace fail-open ternary with an explicit map after allowlist membership:

| Provider | Default allowlist (if env var unset) | Host mapping |
|---|---|---|
| cTrader | `demo` only | `demo` → DEMO_HOST; `live` → LIVE_HOST **only if** `live` is on allowlist **and** owner-only live-enablement file is satisfied (**P1 freeze**) |
| Oanda | `practice` only | `practice` → practice API; `live` → live API under the same live-enablement freeze |

Rules:

1. Normalize environment: strip + lower-case.  
2. Empty / unknown → **raise** `LiveExecutionDenied` (never default to LIVE).  
3. Allowlist source: `QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS` (comma-separated). If unset, use provider defaults above. If set to empty string after parse → deny all.  
4. `practice` is **not** a cTrader OpenAPI environment; using it for cTrader → deny (today it would incorrectly hit LIVE).  
5. **Live-host enablement freeze (P1):** until a separate owner-only authorization file outside the repo exists (example path: root-owned `/etc/quantmetrics/execution_authorization`), implementation **must deny** environment `live` even if listed in the allowlist. Demo/practice OpenAPI/API may proceed under ORDERS/SESSION rules. Spec of that file format is a follow-up owner decision; agents never create or write it.

### 4.3 Owner authorization (ORDERS intent) — frozen names (**P8**) and exact match (**P7**)

**Frozen process environment key names (P8) — do not rename in implementation without a new PLAN revision:**

| Variable | Semantics |
|---|---|
| `QUANTMETRICS_EXECUTION_AUTHORIZED` | Must be exact string `1` for `ORDERS`. |
| `QUANTMETRICS_ALLOWED_ACCOUNT_IDS` | Comma-separated allowlisted account IDs. |
| `QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS` | Comma-separated allowlisted environments. |

**Auth string rules (P7) — decision locked:**

- Accept **only** exact `1` (no leading/trailing whitespace).  
- Reject: missing, `0`, `true`, `yes`, `on`, ` 1`, `1 `, `01`, empty.  
- Mirrors #103 fail-closed boolean lesson: no truthy coercion.

Other notes:

- CLI `--real` alone is **never** sufficient.  
- Process environment is the runtime source of truth for gate keys **after** dotenv hygiene (**§4.7 / P1**).  
- **Residual risk (P1):** process env cannot protect against an attacker/operator with the same service-user shell who can export variables. Document this limit; do not claim OS isolation.

### 4.4 Account allowlist and cTrader ID canonicalization (**P6**)

| Variable | Semantics |
|---|---|
| `QUANTMETRICS_ALLOWED_ACCOUNT_IDS` | Comma-separated account IDs. |

Rules:

1. Missing variable or empty list → **deny all accounts** (fail-closed).  
2. Account ID used for the check is the resolved runtime account (post env/YAML merge), never a placeholder.  
3. Multi-account orchestration must pass each account through the same check.  
4. **cTrader account IDs (P6):** canonicalize strictly as **numeric digits only**.  
   - Reject: whitespace anywhere, leading zeros (e.g. `0123`), empty, non-numeric, mixed alphanumeric.  
   - Accept: `12345678` (no sign, no separators).  
   - Allowlist entries and runtime account must both pass the same canonicalizer before equality.  
5. **Oanda account IDs:** keep exact string match after strip for v1 (Oanda IDs are not the same numeric shape); do not apply cTrader leading-zero rule to Oanda. Document provider-specific canonicalizers in the gate module.

### 4.5 Shared API (canonical) — import fail-closed (**P3**)

Proposed module (implementation in **PR-A**):

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

def canonicalize_ctrader_account_id(account_id: str) -> str:
    """Strict numeric; reject whitespace / leading zeros / non-numeric."""
```

**P3 rules:**

1. QuantBuild **must import** this canonical QuantBridge module — **no duplicated policy copy** in quantbuild.  
2. If import of the gate fails (missing package, broken layout, ImportError) → treat as **`LiveExecutionDenied`**, never fall back to ungated broker construction.  
3. `validate_suite_layout()` is **mandatory** before `create_broker` returns a **non-mock** broker (and before any path that would construct real Oanda/OpenAPI clients via the factory).  
4. Tests required: `OandaBroker.connect` and `create_broker(non-mock)` when gate import is broken / layout invalid → deny.

### 4.6 What remains allowed without ORDERS auth

- `mock_mode=True` / bridge `mode=mock` — local simulation; **gate not invoked** for mock client.  
- `LiveRunner(dry_run=True)` order path (broker=None / no submit) — unchanged.  
- Backtests, research scripts, quantlog demo, analytics — unchanged.  
- `SESSION` on allowlisted `demo`/`practice` with allowlisted account — connect for data **without** `QUANTMETRICS_EXECUTION_AUTHORIZED=1`, subject to dotenv hygiene and live-host freeze.  
- `ORDERS` on demo OpenAPI — **still requires** owner flag + account allowlist (demo orders are still real broker API mutations).

### 4.7 Dotenv non-authority and config loader (**P1**)

**Fact:** `quantbuild/src/quantbuild/config.py` currently does `load_dotenv(override=True)`.

**Policy (PR-A must implement):**

1. Gate keys (`QUANTMETRICS_EXECUTION_AUTHORIZED`, `QUANTMETRICS_ALLOWED_ACCOUNT_IDS`, `QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS`) must **never** be supplied or overridden by dotenv into the trusted decision path.  
2. **Presence of any of these three keys inside dotenv-sourced material ⇒ deny** (fail closed), even if process env looks correct — forces operators to use process/systemd env only and surfaces misconfiguration.  
3. Preferred loader behaviour (implementation detail to choose in PR-A, both must satisfy tests):  
   - stop using `override=True` for these keys; and/or  
   - snapshot process env for gate keys **before** `load_dotenv`; restore/ignore dotenv values for those keys; and  
   - if dotenv file contains any gate key → gate denies.  
4. **N10 tests (P1):**  
   - Process key **missing**, dotenv has `QUANTMETRICS_EXECUTION_AUTHORIZED=1` → `ORDERS` **deny**.  
   - Process key explicitly `0`, dotenv has `1` → **deny**.  
   - Analogous cases for account/env allowlist keys appearing in dotenv → deny.  
5. **AGENTS.md (PR-A):** agents must never set these gate keys and never write them into `.env` / dotenv files.  
6. **Limitation:** process env does not protect against shell access as the same service user.

---

## 5. Where to enforce (so bypasses fail)

Ordered by leverage. **PR-A** lands the non-bypassable core; **PR-B** lands entrypoint UX (**P5**).

| # | Location | When | Intent | PR |
|---|---|---|---|---|
| 1 | `CTraderOpenApiClient.connect` | before choosing host / starting TCP | `SESSION` | **A** |
| 2 | `CTraderOpenApiClient.submit_market_order` / `close_trade` / `modify_trade` | before protobuf mutate | `ORDERS` | **A** |
| 3 | Host selection | inside connect after allowlist | n/a | **A** |
| 4 | QuantBridge `CTraderBroker.__init__` when `mode=="openapi"` | before constructing OpenAPI client | `SESSION` | **B** |
| 5 | `OandaBroker.connect` | before `oandapyV20.API(...)` | `SESSION` | **A** |
| 5b | `oanda_loader._get_oanda_client` (**P4**) | before `oandapyV20.API(...)` | `SESSION` **or** documented practice-only read-only exception + test | **A** |
| 6 | `OandaBroker.submit_market_order` / `close_trade` / modify | before API call | `ORDERS` | **A** |
| 7 | `create_broker` when returning non-mock / Oanda | construction time + `validate_suite_layout` (**P3**) | `SESSION` if non-mock | **B** (layout+import deny tests may land early in A if needed for W-wiring) |
| 8 | `LiveRunner` when `dry_run=False` | before `broker.connect` / first order | `ORDERS` | **B** |
| 9 | `app.py` when resolving `--real` | before `cmd_live` | `ORDERS` preflight | **B** |
| 10 | `launch_live_safe.py` preflight | before subprocess `--real` | `ORDERS` | **B** |
| 11 | `quantmetrics.py build --real` | before spawn | `ORDERS` | **B** |
| 12 | Smoke / lifecycle / runtime_control scripts | before connect/order | matching intent | **B** |
| — | `config.py` dotenv hygiene | load time | supports all | **A** |
| — | `AGENTS.md` agent bans for gate keys | docs | supports all | **A** |

**Invariant:** Even if a caller skips #7–12, #1–3 and #5–6 (and #5b) still deny. That is the non-bypassable core in PR-A.

**P4 decision for #5b:** prefer invoking the same `SESSION` gate inside `_get_oanda_client`. If a narrowly scoped **practice-only read-only exception** is kept for historical data fetch without account allowlist, it must: (a) hard-deny any environment other than `practice`; (b) never construct a client for `live`; (c) have an explicit unit test; (d) still apply dotenv gate-key hygiene. Default recommendation: **full SESSION gate** for consistency.

**Explicitly do not** rely on: Telegram labels, documentary AGENTS.md alone, YAML comments, service unit names (“demo” / “paper”).

### Deployment note (no unit edits unless owner asks)

Existing `quantbuild-ctrader-demo.service` will **stop working** until process EnvironmentFile sets (not dotenv):

- `QUANTMETRICS_EXECUTION_AUTHORIZED=1`  
- `QUANTMETRICS_ALLOWED_ACCOUNT_IDS=<demo-account-id>`  
- (optional) keep default env allowlist `demo`

Document this in PR-A/B; do not edit the unit unless owner requests.

---

## 6. Negative tests (design)

All tests use **monkeypatch / stubs** — no real DNS, TCP, credentials, or SDK network. Assert that denied paths raise `LiveExecutionDenied` **before** mocked connect/order bodies run.

### 6.0 Root CI requirement and mutation proof (**P2**)

1. **All N / W / E gate tests must execute in root CI** (extend `.github/workflows/ci.yml` with a step that runs the new test paths, **or** place/collect them under root `tests/` so `pytest tests -q` includes them). Module-only green is not enough.  
2. **Mutation proof (scratch copy in CI or a dedicated job):** on a temporary copy of sources, **remove** the gate at each of: connect, place, close, modify, host map, Oanda connect, Oanda order — **each removal must cause a test failure**. Restoring the old fail-open host ternary must fail **W1**.  
3. **W-tests constructor assertion:** assert **zero** calls to network-client constructors (`ctrader_open_api.Client`, `oandapyV20.API`) on denied paths. Optional AST guard that gated call sites invoke `assert_live_execution_allowed` / `resolve_ctrader_host`.  
4. Mutation proof runs against scratch trees only — never modifies the checked-out branch under test as the sole artifact.

### 6.1 Policy unit tests (`quantbridge`, imported by quantbuild)

| ID | Case | Expect |
|---|---|---|
| N1 | environment `""` / `prod` / `Practice` (cTrader) | deny; no LIVE host |
| N2 | environment `live` with default allowlist | deny |
| N3 | environment `live` with allowlist containing `live` but auth missing / live-file freeze | `ORDERS` deny; `SESSION` deny while freeze active |
| N4 | `QUANTMETRICS_EXECUTION_AUTHORIZED` missing / `0` / `true` / `yes` / ` 1` (**P7**) | `ORDERS` deny |
| N5 | auth `1` but `ALLOWED_ACCOUNT_IDS` missing/empty | deny |
| N6 | auth `1`, allowlist `111`, account `222` | deny |
| N7 | auth `1`, allowlist `111`, account `111`, env `demo` | `ORDERS` allow (policy only) |
| N8 | Oanda env `live` default allowlist | deny |
| N9 | Oanda env `practice` + account allowlisted + auth | `ORDERS` allow |
| N10 | dotenv has auth/`ALLOW*` keys; process missing or `0` (**P1**) | deny |
| N11 | cTrader account `0123` / `12 3` / `12a` (**P6**) | deny |
| N12 | gate import failure / missing module (**P3**) | `LiveExecutionDenied` (no ungated success) |

### 6.2 Wire / client tests

| ID | Case | Expect |
|---|---|---|
| W1 | OpenAPI `connect` with env typo **or** restored fail-open ternary (mutation) | raises / test fails; **zero** `Client(...)` calls |
| W2 | OpenAPI `submit_market_order` without auth | raises; no send; zero `Client` if connect also gated |
| W3 | OpenAPI close/modify without auth | same |
| W4 | Oanda `connect`/`OrderCreate` without auth or bad env | raises before `oandapyV20.API` / request; **zero** API ctor calls |
| W5 | `oanda_loader._get_oanda_client` live or unauthorized (**P4**) | deny; zero API ctor |

### 6.3 Entrypoint / bypass tests (mostly **PR-B**)

| ID | Case | Expect |
|---|---|---|
| E1 | `app.py` live `--real` without auth | non-zero / denied before orders |
| E2 | `create_broker` + smoke-style submit without auth | denied |
| E3 | Direct bridge `CTraderBroker(mode="openapi")` | denied at init or connect |
| E4 | `LiveRunner(..., dry_run=False)` without auth | denied |
| E5 | `launch_live_safe` preflight without auth | exit preflight; subprocess never started |
| E6 | Mock mode / dry_run paths | **still succeed** without auth |
| E7 | Backtest / `run_demo` / root pytest | unchanged green |
| E8 | `create_broker(non-mock)` when gate import fails (**P3**) | deny |
| E9 | `OandaBroker.connect` when gate import fails (**P3**) | deny |

---

## 7. Affected files (by PR split — **P5**)

### PR-A (merge first; exact-SHA Claude **code** review)

| File | Change type |
|---|---|
| `quantbridge/src/quantbridge/safety/live_execution_gate.py` | **Add** — canonical policy |
| `quantbridge/src/quantbridge/safety/__init__.py` | **Add** |
| `quantbridge/src/quantbridge/execution/clients/ctrader_openapi_client.py` | **Edit** — gate + fail-closed host map (#1–3) |
| `quantbuild/src/quantbuild/execution/broker_oanda.py` | **Edit** — SESSION/ORDERS (#5–6) |
| `quantbuild/src/quantbuild/io/oanda_loader.py` | **Edit** — #5b / **P4** |
| `quantbuild/src/quantbuild/config.py` | **Edit** — dotenv non-authority (**P1**) |
| `AGENTS.md` | **Edit** — never set/write gate keys (**P1**) |
| `.github/workflows/ci.yml` and/or root `tests/` | **Edit** — run N/W(+partial) gate tests + mutation proof (**P2**) |
| `quantbridge/tests/test_live_execution_gate.py` | **Add** |
| `quantbuild/tests/test_live_execution_gate_wire.py` | **Add** (Oanda/loader/import-fail) |

### PR-B (only after PR-A merged; exact-SHA Claude **code** review)

| File | Change type |
|---|---|
| `quantbridge/src/quantbridge/execution/brokers/ctrader_broker.py` | **Edit** — #4 |
| `quantbuild/src/quantbuild/execution/broker_factory.py` | **Edit** — #7 + `validate_suite_layout` for non-mock (**P3**) |
| `quantbuild/src/quantbuild/execution/broker_ctrader.py` | **Edit** — early deny when `mock_mode=False` |
| `quantbuild/src/quantbuild/execution/live_runner.py` | **Edit** — #8 |
| `quantbuild/src/quantbuild/app.py` | **Edit** — #9 |
| `quantbuild/scripts/launch_live_safe.py` | **Edit** — #10 |
| `quantmetrics_os/orchestrator/quantmetrics.py` | **Edit** — #11 |
| smoke / lifecycle / runtime_control scripts | **Edit** — #12 |
| Entrypoint E-tests under root CI | **Add** |

**Out of both PRs unless owner asks:** systemd unit bodies, VPS install scripts, filling real EnvironmentFiles, creating `/etc/quantmetrics/execution_authorization`.

---

## 8. Migration risks

| Risk | Impact | Mitigation |
|---|---|---|
| Existing demo OpenAPI systemd unit breaks | Service fails until process env set | Document required **process** env vars (not dotenv); optional follow-up unit comments |
| Dotenv previously “worked” for auth | Deny when keys present in `.env` | Intentional (**P1**); migrate keys to systemd/EnvironmentFile |
| Operators used typo env that “worked” as LIVE | Suddenly denied | Intentional; clear deny reason |
| Duplicate policy in QB | Drift | Forbidden (**P3**); single QuantBridge module |
| `SESSION` allowlist blocks dry-run ctrader data | Data bootstrap fails | List demo account; or use mock/dukascopy |
| False sense of safety | Same-user shell can export env | Document residual risk; AGENTS bans; future owner-only file for `live` |
| Emergency flatten denied without auth | Cannot close positions | **§9.1 / P9** operator procedure |
| PR-B delayed | Entrypoint UX weak until B | Acceptable: wire gates in A still block bypasses |

---

## 9. Acceptance criteria

### PR-A

1. Unknown/empty cTrader environment cannot select LIVE_HOST (W1 + mutation).  
2. Missing/false/`true`/` 1` owner auth → no OpenAPI/Oanda order mutation.  
3. Empty/missing account allowlist → deny; wrong account → deny; bad cTrader ID shapes → deny (**P6**).  
4. Dotenv cannot authorize; N10 green (**P1**).  
5. Gate import failure → deny for Oanda connect / non-mock factory paths tested in A scope (**P3**).  
6. `oanda_loader` covered (**P4**).  
7. All N/W tests (+ mutation proof) run in **root CI** and pass (**P2**); zero client ctor on deny.  
8. Mock/dry-run/backtest/`run_demo`/root suite remain green without ORDERS auth.  
9. No secrets; no real broker calls; Claude **code** review on exact PR-A SHA; owner merge approval.

### PR-B

1. E1–E9 (as applicable) green in root CI.  
2. Entrypoints #4, #7–12 wired; still no reliance on them alone for safety.  
3. Claude **code** review on exact PR-B SHA; owner merge approval.  
4. PROP roadmap H1 updated only after both merges as appropriate.

### 9.1 Emergency flatten authorization — operator procedure (**P9**)

**Design default remains:** flatten/close uses the same `ORDERS` auth (`QUANTMETRICS_EXECUTION_AUTHORIZED=1` + account allowlist). No separate `FLATTEN` flag in v1.

**Operator procedure (document in PR-A ops note / runbook snippet):**

1. **Authorize:** as the service owner, set process environment (systemd `Environment=` / `EnvironmentFile=` that is **not** a developer dotenv):  
   `QUANTMETRICS_EXECUTION_AUTHORIZED=1` and `QUANTMETRICS_ALLOWED_ACCOUNT_IDS=<account>`.  
2. **Execute** the minimum close/flatten path (e.g. runtime_control failsafe) — still subject to wire gates.  
3. **Remove authorization immediately after:** unset or set `QUANTMETRICS_EXECUTION_AUTHORIZED=0` / remove the key; reload systemd; confirm `systemctl show` / process environ no longer has `=1`.  
4. **Audit:** record UTC timestamp, operator identity, account ID, reason, commands run, and confirmation that auth was removed. Store outside git if it contains sensitive host details.  
5. **Never** leave `=1` in a checked-in `.env`, example env, or agent session.  
6. Agents must not perform this procedure.

---

## 10. Rollback

1. Revert PR-B first if needed, then PR-A (order preserves wire safety longer).  
2. Hotfix that weakens gates requires **explicit owner decision** and must not silently skip tests.  
3. Do not “fix” outages by allowlisting `*` or restoring fail-open ternary.  
4. Plan/inventory docs may remain; they do not affect runtime.

---

## 11. Implementation sequence (after PLAN approval only)

### PR-A

1. Land `live_execution_gate.py` + N1–N12 (incl. P1/P6/P7).  
2. Patch `CTraderOpenApiClient` host map + connect/order gates (W1–W3).  
3. Patch `OandaBroker` + `oanda_loader` (W4–W5, P4).  
4. Fix `config.py` dotenv hygiene; update `AGENTS.md` (P1).  
5. Wire root CI + mutation proof (P2).  
6. Record SHA; Claude code review; owner merge.

### PR-B (only after PR-A on `main`)

1. Wire #4, #7–12 + E-tests in root CI.  
2. Confirm smoke/lifecycle preflight or inherit wire deny.  
3. Record SHA; Claude code review; owner merge.

**STOP:** no PR-A/B implementation in this PLAN documentation PR.

---

## 12. Review checklist for Claude (PLAN recheck)

- [ ] P1 dotenv non-authority + N10 + live-host file freeze adequate?  
- [ ] P2 root CI + mutation proof + zero client ctor assertions adequate?  
- [ ] P3 import-fail → deny and no policy duplication adequate?  
- [ ] P4 `oanda_loader` SESSION vs practice-only exception choice acceptable?  
- [ ] P5 PR-A / PR-B split and review gates clear?  
- [ ] P6 numeric cTrader account rules correct?  
- [ ] P7 exact `1` only (reject ` 1`) locked?  
- [ ] P8 env key names frozen?  
- [ ] P9 emergency flatten procedure + removal/audit clear?  
- [ ] Inventory + wire enforcement still sufficient against bypasses?

**PLAN verdict requested:** `APPROVE` / `REQUEST CHANGES` / `BLOCK` tied to this PR head SHA.

---

## 13. Decisions locked / residual open items

**Locked by this remediation:**

| ID | Decision |
|---|---|
| P7 | Auth value exact `1` only; reject ` 1`. |
| P8 | Freeze the three `QUANTMETRICS_*` key names above. |
| P5 | PR-A then PR-B; no B before A merged. |
| P6 | cTrader accounts strictly numeric; no leading zeros. |
| P9 | Same ORDERS auth for flatten; operator authorize → flatten → remove → audit. |
| P1 live | No `live` host enablement until owner-only external authorization file exists. |

**Still owner-follow-up (non-blocking for PLAN approve if defaults accepted):**

1. Exact schema/path permissions for `/etc/quantmetrics/execution_authorization` (or successor).  
2. Whether #5b uses full SESSION gate (recommended) vs practice-only read-only exception.

---

## 14. P1–P9 remediation checklist (docs mapping)

| ID | Severity | Requirement (summary) | Plan section(s) |
|---|---|---|---|
| **P1** | BLOCKER | Dotenv must not supply/override gate keys; presence in dotenv ⇒ deny; N10; `config.py` in PR-A; AGENTS ban; residual same-user shell risk; no `live` until owner-only file outside repo | §1, §2, §4.2, §4.3, §4.7, §6.1 N10, §7 PR-A, §8, §9, §13 |
| **P2** | BLOCKER | All N/W/E gate tests in root CI; mutation proof (connect/place/close/modify/host map/Oanda); restoring ternary fails W1; zero `Client`/`oandapyV20.API` ctor; optional AST | §6.0, §6.2, §7 PR-A, §9 PR-A |
| **P3** | BLOCKER | Gate import failure ⇒ `LiveExecutionDenied`; tests on `OandaBroker.connect` + `create_broker(non-mock)`; `validate_suite_layout` mandatory for non-mock; canonical QuantBridge import only | §4.5, §5 #7, §6.1 N12, §6.3 E8–E9, §7 |
| **P4** | — | `oanda_loader._get_oanda_client` (#5b): SESSION gate or strict practice-only exception + test | §3, §5 #5b, §6.2 W5, §7 PR-A, §13 |
| **P5** | — | Split PR-A (gate, N/W, wire #1–3, Oanda #5–6, loader, dotenv, CI, AGENTS) vs PR-B (#4, #7–12 + E-tests) after A merged; each exact-SHA Claude code review | §2, §5, §7, §9, §11 |
| **P6** | — | cTrader account ID strictly numeric; reject whitespace / leading zero / non-numeric | §4.4, §6.1 N11, §9 |
| **P7** | — | Decide auth ` 1`; **exact `1` only** | §4.3, §6.1 N4, §13 |
| **P8** | — | Freeze env key names as the three `QUANTMETRICS_*` keys | §4.3, §13 |
| **P9** | — | Emergency flatten operator procedure; removal; audit | §9.1, §8, §13 |

---

**End of PLAN.** Implementation must not start until independent Claude PLAN recheck approves this design on the exact commit SHA of this plan PR.
