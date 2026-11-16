# PROP-00 — source master coverage audit (2026-11-16)

**Original source:** local project artifact `QUANTMETRICS_ALPHA_ENGINE_MASTER_V1.md`, 15,599 bytes; SHA-256 `3de00aef6cd047c446abd53a8fb97c849df54f9da86adfc9071763c458ea12be`. **The original is now committed as `docs/source/QUANTMETRICS_ALPHA_ENGINE_MASTER_V1_FULL.md` (commit `b257d398`).** This table is a section-level mapping, not a line-by-line equivalence. The compact repo master and full source are different documents. Independent comparison and hash verification of the committed source remain pending.

| Original source section | Current repository mapping | Coverage / remaining gap |
|---|---|---|
| 1. Strategisch besluit | master §1 | Adapted; SIE pause and trading approvals retained |
| 2. Succesdefinitie | master §3 and §12 | Adapted; four-stage success ladder retained conceptually |
| 3. Scope en prioriteiten | master §2, §6, §10; roadmap | Adapted; explicit existing engines and verdicts added after review |
| 4. Onderzoeksprotocol — verplicht | master §4, §11 | Adapted; some thresholds/holdout details pending decision |
| 5. Technische architectuur | master §2, §10 | Condensed; original flow diagram not reproduced |
| 6. AI Development Factory: rolverdeling | master §5, AGENTS.md | Adapted to one canonical workflow; original wording differs |
| 7. Cursor-aanpassingen | AGENTS.md, .cursor/rules/propfirm-alpha.mdc | Adapted; runtime loading not verified |
| 8. GitHub-aanpassingen | roadmap, AGENTS.md | Partly operationalized; branch protection, issue backlog and CI expansion pending |
| 9. Sprintplanning en acceptatiecriteria | master §6–7, roadmap | Condensed; original per-sprint input/output details not fully reproduced |
| 10. Bronnenbeleid | master §4, §12 | Condensed; official FTMO verification pending |
| 11. Verboden shortcuts | master §8, AGENTS.md | Adapted with additional explicit live path restrictions |
| 12. Status en eerstvolgende stap | roadmap, PR discussion | Adapted; current state recorded separately from historical source date |

**Merge gate:** verify SHA-256 of the committed full source against the stated local SHA-256 and obtain independent source-to-operational-master comparison tied to the new head SHA. Claude finding M6 is **PENDING RE-REVIEW**, not automatically closed.
