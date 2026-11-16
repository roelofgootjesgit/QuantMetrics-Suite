# PROP-00 — source master coverage audit (2026-11-16)

**Original source:** project artifact `QUANTMETRICS_ALPHA_ENGINE_MASTER_V1.md`, 15,599 bytes; expected SHA-256 `3de00aef6cd047c446abd53a8fb97c849df54f9da86adfc9071763c458ea12be`. **Committed as** `docs/source/QUANTMETRICS_ALPHA_ENGINE_MASTER_V1_FULL.md` (commit `b257d398`). **Local hash check (this repair):** `sha256sum docs/source/QUANTMETRICS_ALPHA_ENGINE_MASTER_V1_FULL.md` → `3de00aef6cd047c446abd53a8fb97c849df54f9da86adfc9071763c458ea12be` (**MATCH**). Compact operational master `QUANTMETRICS_ALPHA_ENGINE_MASTER_V1.md` is a different document (local SHA-256 `7856a38382fbf2fde15b65f868b561448c711f4c7604c2496541f615b83b2da8`, 10,284 bytes). This table is a section-level mapping, not line-by-line equivalence.

| Original source section | Current repository mapping | Coverage / remaining gap |
|---|---|---|
| 1. Strategisch besluit | master §1 | Adapted; SIE pause and trading approvals retained |
| 2. Succesdefinitie | master §3 (Bewijsladder) and §12 | Adapted; four-stage success ladder retained conceptually; Fase A–D wording condensed |
| 3. Scope en prioriteiten | master §2, §6, §10; roadmap | Adapted; P0–P4 detail shortened; explicit existing engines/verdicts added after review |
| 4. Onderzoeksprotocol — verplicht | master §4, §11 | Adapted; some thresholds/holdout details pending decision before PROP-02 |
| 5. Technische architectuur | master §2, §10 | Condensed; original ASCII flow diagram **not** reproduced (conscious shortening) |
| 6. AI Development Factory: rolverdeling | master §5, AGENTS.md | Adapted to one canonical workflow; original always-Claude-plan-review wording differs (high-impact gating) |
| 7. Cursor-aanpassingen | AGENTS.md, `.cursor/rules/propfirm-alpha.mdc` | Adapted; aligns with `quantbuild/docs/CURSOR_CONTEXT_RULES.md` 1–3 file budget; runtime loading not verified |
| 8. GitHub-aanpassingen | roadmap, AGENTS.md | Partly operationalized; branch protection, issue backlog and CI expansion pending (H2) |
| 9. Sprintplanning en acceptatiecriteria | master §6–7, roadmap | Condensed; original per-sprint input/output details not fully reproduced |
| 10. Bronnenbeleid | master §4, §12 | Condensed; official FTMO verification pending (PROP-01) |
| 11. Verboden shortcuts | master §8, AGENTS.md | Adapted with additional explicit live-path restrictions (H1 inventory) |
| 12. Status en eerstvolgende stap | roadmap, PR discussion | Adapted; current post-sync state recorded separately from historical source date |

**Conscious shortenings / non-goals of the compact master:** no full-text copy; no architecture diagram; no exhaustive per-sprint I/O lists; workflow unified in `AGENTS.md` rather than duplicating the original always-on Claude plan-review sequence.

**Potential wording tension (not a silent contradiction):** original §6 implies Claude plan review on the default path; compact/`AGENTS.md` require external design review for **high-impact** work only. Documented as intentional adaptation.

**Merge gate:** committed full-source SHA-256 **matches** the stated artifact hash. Independent source-to-operational-master comparison tied to the new head SHA remains required. Claude finding M6 is **hash-verified locally; content comparison PENDING RE-REVIEW**, not automatically closed.
