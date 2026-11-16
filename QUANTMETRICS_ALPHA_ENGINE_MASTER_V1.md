# QUANTMETRICS ALPHA ENGINE — MASTER v1.0
**Datum:** 2026-11-16  
**Status:** VOORGESTELDE KOERSWIJZIGING — merge-status wordt in GitHub PR bijgehouden  
**Prioriteit:** PROP-00  
**Bron:** projectdocument `QUANTMETRICS_ALPHA_ENGINE_MASTER_V1.md`; deze repositoryversie is een compacte, operationele vertaling voor review.

## 1. Strategisch besluit
Quantmetrics Alpha Engine (QAE) is de voorgestelde primaire onderzoeksrichting: aantoonbaar netto statistisch voordeel onderzoeken in algoritmische strategieën, met een aparte evaluatie voor propfirmvoorwaarden. FTMO is de eerste referentie; andere propfirms worden alleen op gedocumenteerde voorwaarden vergeleken.

**Geen winstgarantie.** Positieve historische resultaten, een geslaagde challenge en herhaalde netto-uitbetalingen zijn afzonderlijke bewijsniveaus. Geen betaalde challenges, liveorders of autonome orderuitvoering zonder afzonderlijke expliciete goedkeuring.

Satellite Intelligence Engine (SIE-01) wordt **ON_HOLD, niet verwijderd**. Cushing, Costco, satellietdata, eerdere experimenten en de SIE–Quantmetrics-bridge blijven behouden. De SIE point-in-time gates blijven van kracht voor elk SIE-afgeleid signaal. De QAE-marktdata-track is daarvan onafhankelijk.

## 2. Architectuur en feitelijke beginsituatie
Deze repository bevat volgens README de modules `quantbuild` (signalen/risk), `quantbridge` (execution), `quantlog` (append-only events), `quantanalytics` (read-only diagnostiek), `quantresearch` (baseline/candidate, promotion) en `quantmetrics_os` (orchestratie). Dat is een **gedocumenteerde architectuur**, geen bewijs dat iedere module volledig operationeel is. De code-, data- en integratieaudit is nog vereist. De code bevat al minstens zes backtest-entrypoints (`run_backtest`, `run_bb_only_backtest`, `run_macd_only_backtest`, `run_london_ny_overlap_breakout_backtest`, `run_ny_sweep_backtest`, `run_ny_sweep_failure_reclaim_backtest`). **ADR-001** moet hun overlap, eigenaarschap en canonieke engine bepalen vóór PROP-03; tot dat besluit geen nieuwe engine bouwen.

De bestaande CI `.github/workflows/ci.yml` draait volgens configuratie `pytest tests -q` en `python run_demo.py` op push/PR. Dit bewijst niet dat alle modules of propfirmregels getest zijn.

## 3. Bewijsladder
1. **Softwarebetrouwbaarheid:** reproduceerbare builds, data-ingest, tijdstempels, simulatie en kosten.
2. **Strategische alpha:** vooraf geregistreerde hypothese; realistische spread, slippage, commissies, financiering; chronologische train/validatie/onaangeroerde test; walk-forward; onzekerheidsmarges; eenvoudige baselines.
3. **Propfirmgeschiktheid:** product- en datumgebonden regels; equity/open P&L; dag- en totale drawdown; resetmomenten/tijdzones; nieuws-/overnightbeperkingen; positie- en handelsbeperkingen; challengefees, mislukte pogingen, payoutregels.
4. **Operationele gate:** onafhankelijke review, simulatie/demo en expliciete eigenaarstoestemming voor iedere betaalde of live stap.

## 4. Onderzoek en integriteit
- Historische gegevens moeten echt en herleidbaar zijn. Registreer bron, datasetversie, tijdzone, beschikbaarheidstijd, codecommit, configuratie, fees en run-ID.
- Voorkom look-ahead, data leakage, survivorship bias, hindsight-selectie, multiple testing en onrealistische fills.
- Registreer ook afgewezen strategieën; wijzig nooit stilzwijgend regels of testperiodes.
- Rapporteer aantallen transacties, nettoresultaat, drawdown, verliesreeksen, stabiliteit per regime en onzekerheid.
- Optimaliseer niet uitsluitend challenge pass-rate: schat ook accountoverleving, netto-uitbetalingen, challenge- en resetkosten en de kans op ruïne.
- Test eerst eenvoudige, verklaarbare intradayhypothesen. US100 en EURUSD zijn onderzoekskandidaten, geen bewezen edges.

## 5. Werkverdeling
- **Projecteigenaar:** prioriteiten, kosten, risicobudget, architectuurkeuzes en merge/live-goedkeuring.
- **ChatGPT:** research lead, specificatie, acceptance criteria, issue/PR-coördinatie en rapportage.
- **Cursor Agent:** implementatie op afzonderlijke branches, tests en technische oplevering; geen directe ChatGPT–Cursor-trigger veronderstellen.
- **Claude/onafhankelijke reviewer:** plan-, code-, statistiek-, leakage- en reproducibility-review; alleen als de review werkelijk is uitgevoerd als 'reviewed' registreren.
- **GitHub Actions:** geautomatiseerde checks; een groene root-suite vervangt geen volledige module-/data-audit.

**Canonieke uitvoeringsworkflow en high-impact-criteria:** zie `AGENTS.md`; onderzoekspreregistratie is een verplichte gate vóór hypothesetests, geen verplicht ritueel voor documentatiewijzigingen.

## 6. Sprints
| Sprint | Doel | Exit-gate |
|---|---|---|
| PROP-00 | Repo-audit, documentatie, agentinstructies en draft PR | Reviewbare branch; niets gemerged |
| PROP-01 | Eerst officiële FTMO-productregels dateren en het bestaande SUSPENDED-verdict herbeoordelen; daarna bestaande account-policy/simulatoren auditen en pas dan een deterministische rules simulator specificeren | Regelversies en bronnen; grensgevallen getest |
| PROP-02 | Historische marktdata, tijdzones, spread/slippage/execution | Reproduceerbare datasets en kostenchecks |
| PROP-03 | Eén eenvoudige intradaystrategie | Baseline, preregistratie en eerste backtest |
| PROP-04 | Walk-forward, stress, challenge/payout-economie | Onafhankelijk go/no-go |
| PROP-05 | Beperkte Alpha Discovery Factory | Hypotheseledger, budgetlimieten, multiple-testing-control |

## 7. PROP-00 acceptatiecriteria
- Inventariseer feitelijke broncode, tests, workflows, data-interfaces en eventuele execution/livepaden.
- Leg herbruikbare onderdelen en ontbrekende onderdelen vast; voer tests echt uit voordat ze als geslaagd worden gemeld.
- Documenteer bestaande Cursor-regels en voorkom conflicten.
- Geen codewijzigingen of wijziging aan bestaande CI in de documentatie-PR.
- Maak alleen een draft PR; geen merge zonder projecteigenaar.
- Publiceer status 'gebouwd/getest/onderzocht/geblokkeerd' met bewijs en één volgende stap.

## 8. Veiligheid
Geen secrets of persoonlijke credentials in repo/logs. Geen ongeautoriseerde brokerverbindingen, liveorders, betaalde diensten, grote refactors of verwijdering van SIE-werk. Agents mogen tests of controles niet uitschakelen om een build groen te maken. Alle autonome herstelpogingen en kosten worden begrensd.

## 9. Documenthiërarchie
Dit masterplan definieert de nieuwe QAE-richting. `AGENTS.md` en `.cursor/rules/propfirm-alpha.mdc` vertalen dit naar agentgedrag; `docs/PROP_ROADMAP.md` naar taken. Bestaande README/CONTRIBUTING/modulecontracten blijven gelden waar niet strijdig. Bestaande SIE-regels worden niet gewijzigd; wijzigingen aan de onderzoeksstandaard vereisen expliciete besluitvorming.

## 10. Bestaande FTMO-assets en evidence-status
- `quantresearch/docs/FTMO_FREQUENCY_PLAN_2026.md`: **SUSPENDED** op basis van onder meer een 30-dagenpremisse. Niet verwijderen of stilzwijgend overrulen; eerst huidige officiële FTMO-regels per product en datum verifiëren, dan een expliciet herbeoordelingsbesluit registreren.
- `quantbridge/src/quantbridge/accounts/account_policy.py`, `account_state_machine.py`, `configs/accounts_baseline.yaml`: bestaande account-policy en drawdownconfiguraties; correctness nog niet bewezen.
- `quantbuild/src/quantbuild/execution/pass_accelerator.py`, `account_lifecycle.py` en simulatiescripts `robustness_and_ftmo.py`, `dual_book_ftmo_sim.py`, `pass_acceleration_sim.py`, `portfolio_adaptive_sim.py`, `portfolio_dual_mode.py`: inventariseren en vergelijken vóór nieuwbouw.
- Claims zoals '65.4% FTMO pass rate' in `quantbuild/configs/challenge.yaml` en rendementen in `quantbuild/QUANTBUILD_OVERVIEW.md` zijn **UNVERIFIED_LEGACY** totdat dataset, code, kosten en experiment reproduceerbaar zijn. Geen performancebewijs.

## 11. Research gates v1 — verplicht vanaf PROP-02
- Per observatie: `observed_at`, `published_at` (indien relevant), `available_at`, `decision_at`, tijdzone, revisie en bron. Harde PIT-gate: `available_at <= decision_at`; ontbrekende beschikbaarheidstijd = uitsluiten of expliciet quarantainen.
- Preregistreer hypothese, baseline, evaluatiemetrics, tijdvensters, parameterzoekruimte en stopregels in de bestaande `quantresearch`-registry (exacte interface eerst auditen). Chronologische splits en walk-forward; holdout-ID, inhoudshash en eerste toegang loggen; geen iteratief tunen op holdout.
- Meerdere kandidaten: rapporteer totaal aantal geteste varianten, afhankelijkheden en gecorrigeerde significantie (bijv. Holm/FDR of passende resampling); inspecteer bestaande `quantresearch/quantresearch/statistics/permutation_test.py` voordat nieuwe statistiekcode ontstaat.
- Per instrument/sessie: spread (inclusief nieuws/rollover), commissie, swap/financiering, slippage en onuitvoerbare fills modelleren. Scheid trade-level metrics van equity-/account-level metrics.
- **Nog te besluiten vóór PROP-02:** minimum aantal trades, onzekerheidsgrenzen, holdout-toegangsbeleid en stressdrempels. Geen willekeurige drempels als gevalideerd presenteren.

## 12. Propfirm-metrics contract — te valideren in PROP-01
Regelrecords bevatten `provider`, `product`, `account_type`, `source_url`, `retrieved_at`, `effective_at` (indien bekend), `timezone`, `rule_version` en bewijsstatus. Leg per product equity versus balance, resetmoment, static/trailing max loss, minimum handelsdagen, nieuws/weekend/EA-beperkingen en payoutvoorwaarden vast.
Meet per fase `P(pass)`, `P(breach_daily)`, `P(breach_total)`, tijd-tot-target, kans op ruïne over N pogingen en payoutverdeling. Netto-economie: ontvangen payouts na toepasselijke split minus challengefees, resets en overige kosten; expliciet per scenario en zonder winstclaim. Regels uit niet-officiële bronnen zijn alleen onderzoeksaanwijzingen.

## 13. Execution safety en governance-status
Bestaande livepaden zijn aanwezig; **documentaire verboden zijn geen technische blokkade**. Een afzonderlijke PR moet fail-closed live-hostselectie, eigenaarsautorisatie en account-allowlist testen vóór agentgestuurde execution. GitHub branch protection, verplichte reviews en volledige module-CI zijn **NOG NIET INGERICHT**. PROP-00 documenteert de kloof; de daadwerkelijke beveiliging vereist afzonderlijke uitvoering en verificatie.
