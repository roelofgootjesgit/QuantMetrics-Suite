# PROP Roadmap — Quantmetrics Alpha Engine
**2026-11-16 — Proposed, awaiting review/merge.**

| Sprint | Scope | Deliverable | Gate |
|---|---|---|---|
| PROP-00 | Audit, master, Cursor/agent guidance | Draft PR + audit findings | Owner review, no merge |
| PROP-01 | FTMO official rules by product/version | Deterministic rules simulator | Unit tests for boundary cases |
| PROP-02 | Intraday market data, timestamps, fees | Data audit and execution model | Reproducible data and cost assumptions |
| PROP-03 | One preregistered strategy, baseline | Repeatable net-of-cost backtest | No hindsight selection |
| PROP-04 | Walk-forward and challenge/payout simulations | Independent validation report | Explicit go/no-go |
| PROP-05 | Budgeted multi-agent alpha discovery | Hypothesis registry, review queue | Multiple-testing safeguards |

## PROP-00 observed facts
- Repository `roelofgootjesgit/QuantMetrics-Suite`, default branch `main`, public.
- Root README describes `quantbuild`, `quantbridge`, `quantlog`, `quantanalytics`, `quantresearch`, `quantmetrics_os`.
- `.github/workflows/ci.yml` is configured for `pytest tests -q` and `python run_demo.py` on push/PR.
- `quantbuild/docs/CURSOR_CONTEXT_RULES.md` already exists; preserve its module-first workflow.
- No root `AGENTS.md`, `MASTER.md`, `ROADMAP.md` or `.cursor/rules/project.mdc` was found in the inspected paths.
- **Not yet verified:** full data quality, execution safety, full module test coverage and propfirm simulator. PR #102 (`75b1b4e`) repaired the root run-scanner boundary test and is merged to `main`; this PROP-00 branch has integrated that commit. Root CI for this branch must be re-checked on the post-merge head SHA. Nested module workflows remain outside root CI.
- **No trading/backtest results were produced by PROP-00.**

## Execution/live inventory — H1
| Path | Observed risk | Gate |
|---|---|---|
| `quantbuild/src/quantbuild/app.py` | `live --real` sets dry_run=False | Agents prohibited; separate technical gate PR |
| `quantbuild/src/quantbuild/execution/live_runner.py` and `broker_oanda.py`, `broker_ctrader.py` | Live loop/broker adapters | No agent execution |
| `quantbridge/src/quantbridge/execution/clients/ctrader_openapi_client.py` | Unknown environment can select LIVE_HOST | Fail-closed allowlist + tests in separate PR |
| `quantbuild/scripts/launch_live_safe.py` and `ctrader_smoke.py` | Live launcher/smoke paths | Never run in agent session |
| `quantbuild/deploy/systemd/`, `quantmetrics_os/orchestrator/config.vps.example.env` | Deployment entrypoints | No unattended deployment |
| `CTRADER_ACCESS_TOKEN`, `CTRADER_ACCOUNT_ID`, `CTRADER_CLIENT_ID` | Broker credentials in environment | Remove from agent environments; do not expose |

**Execution safety is not technically enforced yet.** Owner approval and a separate reviewed implementation PR required before any live-capable automation.

## Existing FTMO research, engines and governance — H2/H3
- `quantresearch/docs/FTMO_FREQUENCY_PLAN_2026.md`: SUSPENDED on a 30-day assumption; **re-evaluate**, never silently discard.
- `quantbridge/src/quantbridge/accounts/account_policy.py`, `account_state_machine.py`, `configs/accounts_baseline.yaml`: existing rules/state handling.
- `quantbuild/src/quantbuild/execution/pass_accelerator.py`, `account_lifecycle.py`; scripts `robustness_and_ftmo.py`, `dual_book_ftmo_sim.py`, `pass_acceleration_sim.py`, `portfolio_adaptive_sim.py`, `portfolio_dual_mode.py`: existing propfirm simulations.
- At least six backtest entrypoints already exist. **ADR-001** chooses canonical engine before PROP-03; no seventh engine by default.
- `quantbuild/configs/challenge.yaml` (65.4% pass-rate claim) and `quantbuild/QUANTBUILD_OVERVIEW.md` performance/walk-forward claims: **UNVERIFIED_LEGACY**, not evidence.
- GitHub `main` branch protection: **NOT CONFIGURED (owner action)**. No required review/checks, no rulesets; root CI only 5 tests and demo on Ubuntu. Nested module workflows are not run by root GitHub Actions. Separate CI PR needed for module suites, PR template, review evidence; do not blindly require unverified suites.
- SIE repository `satelite.trade` ON_HOLD update remains pending; preserve open PR #28, #31 and #32 status and review SHA in a separate PR. Bridge location/functionality remains unverified.

## Review remediation and source traceability
PR #101 requires Claude re-review tied to the post-sync head SHA. Original full source master is committed at `docs/source/QUANTMETRICS_ALPHA_ENGINE_MASTER_V1_FULL.md` (commit `b257d398`); local SHA-256 of that file is `3de00aef6cd047c446abd53a8fb97c849df54f9da86adfc9071763c458ea12be` and matches the stated artifact hash. Section-by-section completeness comparison against the compact operational master remains **pending independent Claude review**, not falsely claimed complete. Coverage mapping: `docs/PROP_MASTER_SOURCE_COVERAGE.md`. F1 from PR #102 (strict boolean `delete_allowed`) is tracked as issue #103 and remains a separate prerequisite before any lifecycle deletion implementation.

## Next execution task
Audit current code/test coverage and CI outcomes, then draft a product-specific FTMO rules specification from official dated sources. Do not implement trading or buy a challenge yet.
