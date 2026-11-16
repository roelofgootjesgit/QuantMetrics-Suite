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
- **Not yet verified:** full code paths, data quality, execution safety, current CI outcome, module test coverage, propfirm simulator.
- **No trading/backtest results were produced by PROP-00.**

## Next execution task
Audit current code/test coverage and CI outcomes, then draft a product-specific FTMO rules specification from official dated sources. Do not implement trading or buy a challenge yet.
