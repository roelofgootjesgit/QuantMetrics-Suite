# PROP-00 — source master coverage audit (2026-11-16)

**Original source:** project artifact `QUANTMETRICS_ALPHA_ENGINE_MASTER_V1.md`, 15,599 bytes; expected SHA-256 `3de00aef6cd047c446abd53a8fb97c849df54f9da86adfc9071763c458ea12be`. **Committed as** `docs/source/QUANTMETRICS_ALPHA_ENGINE_MASTER_V1_FULL.md` (commit `b257d398`). **Local hash check (this repair):** `sha256sum docs/source/QUANTMETRICS_ALPHA_ENGINE_MASTER_V1_FULL.md` → `3de00aef6cd047c446abd53a8fb97c849df54f9da86adfc9071763c458ea12be` (**MATCH**). Compact operational master `QUANTMETRICS_ALPHA_ENGINE_MASTER_V1.md` is a different document (local SHA-256 `7856a38382fbf2fde15b65f868b561448c711f4c7604c2496541f615b83b2da8`, 10,284 bytes). This table is a section-level mapping, not line-by-line equivalence.

| Original source section | Current repository mapping | Coverage / remaining gap | Bewust weggelaten |
|---|---|---|---|
| 1. Strategisch besluit | master §1 | Adapted; SIE pause and trading approvals retained | Nee |
| 2. Succesdefinitie | master §3 (Bewijsladder) and §12 | Adapted; four-stage success ladder retained conceptually; Fase A–D wording condensed | Nee |
| 3. Scope en prioriteiten | master §2, §6, §10; roadmap | Adapted; P0–P4 detail shortened; explicit existing engines/verdicts added after review | Nee |
| 4. Onderzoeksprotocol — verplicht | master §4, §11 | Adapted; some thresholds/holdout details pending decision before PROP-02 | Nee |
| 5. Technische architectuur | master §2, §10 | Condensed; original ASCII flow diagram not reproduced | Ja: ASCII-diagram |
| 6. AI Development Factory: rolverdeling | master §5, AGENTS.md | Adapted to one canonical workflow; high-impact-only plan review approved by project owner on 2026-11-16 | Ja: mandatory plan review for every task; owner-approved exception for routine work |
| 7. Cursor-aanpassingen | AGENTS.md, `.cursor/rules/propfirm-alpha.mdc` | Restored SIE-REACTIVATE restriction; aligns with `quantbuild/docs/CURSOR_CONTEXT_RULES.md` 1–3 file budget; runtime loading not verified | Nee |
| 8. GitHub-aanpassingen | roadmap, AGENTS.md | Partly operationalized; branch protection and CI expansion pending; issues #104–#113 now created (H2) | Nee |
| 9. Sprintplanning en acceptatiecriteria | master §6–7, roadmap | Condensed; original per-sprint input/output details not fully reproduced | Nee |
| 10. Bronnenbeleid | master §4, §12 | Condensed; official FTMO verification pending (PROP-01) | Nee |
| 11. Verboden shortcuts | master §8, AGENTS.md | Restored martingale / averaging-down / loss-chasing prohibition and live-path restrictions | Nee |
| 12. Status en eerstvolgende stap | roadmap, PR discussion | Adapted; current post-sync state recorded separately from historical source date | Nee |

**Conscious shortenings / non-goals of the compact master:** no full-text copy; no architecture diagram; no exhaustive per-sprint I/O lists; workflow centralized in `AGENTS.md`; deviation from mandatory Claude plan review approved by owner on 2026-11-16. README, PROJECT_STATUS.md and EXPERIMENT_LOG.md were not updated in this docs PR; follow-up scope to be agreed.

**Potential wording tension (not a silent contradiction):** original §6 implies Claude plan review on the default path; compact/`AGENTS.md` require external design review for **high-impact** work only. **Owner decision recorded (2026-11-16):** Claude plan review is mandatory for high-impact changes only. Routine changes may use a lighter plan workflow; relevant tests, SHA-bound review requirements, and explicit owner merge approval remain unchanged. This is an explicit deviation from the original source §6.

**Merge gate:** committed full-source SHA-256 **matches** the stated artifact hash. Independent source-to-operational-master comparison tied to the new head SHA remains required. Claude finding M6 is **hash-verified locally; content comparison PENDING RE-REVIEW**, not automatically closed.
