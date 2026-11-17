# AGENTS.md — Quantmetrics Alpha Engine

## Scope and authority
Safety constraints override project plans; then the QAE master; then this workflow; then relevant module context rules. If instructions conflict, stop and report. Architecture descriptions are not proof of implementation: quantbuild also has broker/live execution code despite the intended quantbridge boundary. No new backtest engine until ADR-001.

## Canonical workflow
IDEA → (RESEARCH PRE-REGISTRATION when empirical) → SPEC → PLAN → (EXTERNAL DESIGN REVIEW if high-impact) → TASK BRANCH → IMPLEMENT → RELEVANT TESTS → INDEPENDENT REVIEW (high-impact) → OWNER MERGE APPROVAL → MERGE → REPORT.
Each task states objective, why, sources, affected files, exclusions, acceptance criteria, tests and deliverables. Use a task branch and draft PR. Review verdict must be APPROVE / REQUEST CHANGES / BLOCK tied to the **exact head commit SHA**, with evidence in PR discussion (even if reviewed externally). Any code change after review requires reassessment of the changed SHA. At most **two repair rounds per issue**; then STOP & REDESIGN with owner decision. Never claim an external review or CI pass without proof. Never merge or push to main without owner authorization.

**High-impact** means execution/broker, account risk, propfirm rule semantics, data ingestion/PIT, CI/security, cross-module architecture (>3 modules), or any operation that can spend money or modify real accounts. Routine docs/tests can use the smaller workflow without mandatory pre-code external review; all merges still require owner approval. Use only 1–3 directly relevant context files initially, expanding with a stated reason; don't indiscriminately load the master on every task.

## Research and modules
Preserve quantbuild, quantbridge, quantlog, quantanalytics, quantresearch and quantmetrics_os boundaries while auditing real implementation. Use existing quantresearch registration where applicable. Timestamp provenance, chronological validation, cost realism, baseline, multiple-testing and negative-result logging are mandatory for empirical claims. All FTMO conditions require official provider/product/date evidence. Treat legacy performance claims as UNVERIFIED_LEGACY.

## Research decision and SIE scope
Research verdicts are `GO_RESEARCH`, `REVISE`, `REJECT` or `BLOCKED` and never authorize a paid challenge. Do not use OHLC midprice as executable bid/ask; document intrabar stop/drawdown ambiguity. Test a null baseline and a simple interpretable baseline before ML. Verify DST and fail/pass transitions for propfirm rule engines.

## Hard safety prohibitions
**No martingale, unlimited averaging down or chasing losses as a substitute for evidence of edge.** Do not build SIE satellite features or start new SIE sprints without an explicitly approved `SIE-REACTIVATE` issue; no paid satellite data without separate owner consent. **Never run** `live --real`, `quantbuild/scripts/launch_live_safe.py`, `ctrader_smoke.py`, or any real broker order/smoke operation in an agent session. Agent environments **must not contain broker credentials** (including CTRADER_ACCESS_TOKEN, CTRADER_ACCOUNT_ID, CTRADER_CLIENT_ID). Do not read, copy or print secrets. Do not purchase data/challenges, disable tests, alter live deployment or launch unattended orders.

**Live-execution gate keys (issue #104):** agents must **never set**, export, or write `QUANTMETRICS_EXECUTION_AUTHORIZED`, `QUANTMETRICS_ALLOWED_ACCOUNT_IDS`, or `QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS` into process env, `.env`, `local.env`, orchestrator env files, or any path inside a git checkout. Those keys are owner/process/systemd-only (external EnvironmentFile outside repo checkouts). Presence of gate keys in dotenv-style files is a deny condition. Technical wire gates are implemented in PR-A; documentary bans remain mandatory. Branch protection is **not configured**; never treat the text as an enforced GitHub rule.

## Completion report
Record exact SHA, changed files, real test commands and results, CI URL, reviewer/verdict/SHA, outstanding risks, status and next action. Definition of done: acceptance criteria met, relevant tests run, review gate met, owner merge approval obtained; otherwise mark blocked/in review. No SIE deletion; SIE is proposed ON_HOLD, with status in its own repo still pending update.
