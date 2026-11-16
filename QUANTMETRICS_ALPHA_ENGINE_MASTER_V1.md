# QUANTMETRICS ALPHA ENGINE — MASTER v1.0
**Datum:** 2026-11-16  
**Status:** VOORGESTELDE KOERSWIJZIGING — ter review, nog niet gemerged  
**Prioriteit:** PROP-00  
**Bron:** projectdocument `QUANTMETRICS_ALPHA_ENGINE_MASTER_V1.md`; deze repositoryversie is een compacte, operationele vertaling voor review.

## 1. Strategisch besluit
Quantmetrics Alpha Engine (QAE) is de voorgestelde primaire onderzoeksrichting: aantoonbaar netto statistisch voordeel onderzoeken in algoritmische strategieën, met een aparte evaluatie voor propfirmvoorwaarden. FTMO is de eerste referentie; andere propfirms worden alleen op gedocumenteerde voorwaarden vergeleken.

**Geen winstgarantie.** Positieve historische resultaten, een geslaagde challenge en herhaalde netto-uitbetalingen zijn afzonderlijke bewijsniveaus. Geen betaalde challenges, liveorders of autonome orderuitvoering zonder afzonderlijke expliciete goedkeuring.

Satellite Intelligence Engine (SIE-01) wordt **ON_HOLD, niet verwijderd**. Cushing, Costco, satellietdata, eerdere experimenten en de SIE–Quantmetrics-bridge blijven behouden. De SIE point-in-time gates blijven van kracht voor elk SIE-afgeleid signaal. De QAE-marktdata-track is daarvan onafhankelijk.

## 2. Architectuur en feitelijke beginsituatie
Deze repository bevat volgens README de modules `quantbuild` (signalen/risk), `quantbridge` (execution), `quantlog` (append-only events), `quantanalytics` (read-only diagnostiek), `quantresearch` (baseline/candidate, promotion) en `quantmetrics_os` (orchestratie). Dat is een **gedocumenteerde architectuur**, geen bewijs dat iedere module volledig operationeel is. De code-, data- en integratieaudit is nog vereist. Geen tweede P&L/backtestengine bouwen voordat één primaire engine via een ADR is gekozen.

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

Workflow: IDEE → PRE-REGISTRATIE → SPEC → REVIEW → BRANCH → CODE → TEST → ONAFHANKELIJKE REVIEW → EIGENAARSGOEDKEURING → MERGE → RAPPORT.

## 6. Sprints
| Sprint | Doel | Exit-gate |
|---|---|---|
| PROP-00 | Repo-audit, documentatie, agentinstructies en draft PR | Reviewbare branch; niets gemerged |
| PROP-01 | FTMO-regelspecificatie en deterministische rules simulator | Versiebeheer van regels; grensgevallen getest |
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
