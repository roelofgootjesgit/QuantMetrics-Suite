## Summary

- Issue(s): #
- High-impact? (AGENTS.md: execution/broker, account risk, propfirm semantics, PIT, CI/security, >3 modules, spend money / real accounts): **yes / no**
- Touched modules:
- Explicit non-goals:

## Exact head SHA (for independent review)

```
<!-- paste `git rev-parse HEAD` of the commit under review -->
```

Independent review verdict must bind to **this exact SHA**. Any later push requires re-review of the new SHA.

## Tests run

| Command | Result | Evidence |
|---|---|---|
| `pytest tests -q` | | |
| #104 N/W/mutation | | |
| #104 E/mutation | | |
| Module suites (if touched) | | |
| `python run_demo.py` | | |

`NOT RUN` requires a reason. Do **not** skip/xfail/soft-fail to greenwash.

## CI

- Workflow run URL(s) on the reviewed SHA:
- Job name(s):

## Safety-critical / mutation evidence

Required when changing live gates, brokers, allowlists, or CI security:

- Reviewer-produced mutation evidence (or link) on the **same** SHA:
- Confirm production Cushing allowlist remains empty while Gate A is BLOCKED:

## Secrets / live safeguards

- [ ] No secrets, tokens, or gate keys (`QUANTMETRICS_EXECUTION_AUTHORIZED`, allowlists) in the diff or checkout env files
- [ ] No real broker connections, paper/live trading, or smoke against live APIs in this PR
- [ ] No systemd/VPS/deploy changes unless explicitly in scope

## Risk / rollback

- Residual risks:
- Rollback plan:

## Review & merge gates

- [ ] Independent review: APPROVE / REQUEST CHANGES / BLOCKED on exact head SHA above
- [ ] Owner merge authorization recorded
- [ ] Draft until gates satisfied; do not merge on engineering green alone
