# AGENTS.md — Quantmetrics Alpha Engine
> Repo-wide agent instructions. Read `QUANTMETRICS_ALPHA_ENGINE_MASTER_V1.md` and the relevant module README before work.

## Mission
Evidence-first algorithmic strategy research. FTMO is the initial propfirm rules reference, not a promise of profitability. Satellite Intelligence Engine is on hold; preserve its work and point-in-time gates.

## Required workflow
1. State task ID, hypothesis/problem, source-of-truth files, scope, exclusions and acceptance tests.
2. Work on a task-specific branch. Never directly change `main`; never merge without owner approval.
3. Plan first. Have design reviewed before implementing high-impact changes; distinguish a requested Claude review from an actually completed review.
4. Make the smallest reviewable patch; keep module boundaries intact.
5. Run relevant tests and report exact commands, outputs, failures and CI status. Do not claim tests were run without logs.
6. Produce PR with evidence, risks, datasets/config hashes, and independent review status.

## Quant boundaries
- `quantbuild`: signal and risk decisions; `quantbridge`: orders/execution; `quantlog`: append-only event log; `quantanalytics`: read-only diagnostics; `quantresearch`: controlled experiments; `quantmetrics_os`: orchestration.
- Audit actual implementations before reusing or extending them. Do not invent APIs.
- One primary P&L/backtest engine; architecture decision before introducing another.
- Pre-register strategies; use chronological splits, realistic spreads/slippage/fees, no look-ahead, leakage or survivorship bias; record failed hypotheses.
- Propfirm rules are provider/product/date-specific. Include equity/open P&L, drawdown reset/timezones, challenge fees, resets and payout restrictions; never silently generalize rules.
- Challenge success is not proven long-run profitability.

## Safety and approvals
No live trading, paid challenge, new paid data, secrets, broker credentials, autonomous orders, destructive changes, or major architectural changes without explicit owner approval. No disabling CI/security controls. Do not trigger Cursor automatically unless a supported integration has been verified.

## Context efficiency
Follow existing `quantbuild/docs/CURSOR_CONTEXT_RULES.md`: inspect only relevant files, module-first, plan before patch; widen context only when evidence demands it.

## PROP-00
Documentation-only transition. No strategy, broker, CI or execution behavior changes. Report unverified areas and request separate implementation PRs.
