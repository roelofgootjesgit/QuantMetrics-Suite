# QUANTMETRICS ALPHA ENGINE — MASTER v1.0

**Datum:** 2026-11-16  
**Status:** VOORGESTELDE KOERSWIJZIGING — nog niet toegepast in GitHub of Cursor  
**Eigenaar:** projecteigenaar  
**Voormalige hoofdfocus:** Satellite Intelligence Engine (SIE-01)  
**Nieuwe hoofdfocus:** algoritmische alpha-research en propfirm-geschikte intradaystrategieën

## 1. Strategisch besluit

Quantmetrics Alpha Engine (QAE) wordt de primaire ontwikkel- en onderzoeksrichting. Het doel is reproduceerbaar onderzoeken of eenvoudige en later complexere algoritmische handelsstrategieën een **netto statistisch voordeel** hebben én binnen de voorwaarden van een propfirm uitvoerbaar zijn. FTMO is de eerste referentie omdat de projecteigenaar dit platform kent; futures-propfirms zoals Topstep zijn alternatieven die op dezelfde objectieve maatstaven vergeleken kunnen worden.

**Geen winstgarantie.** Een historisch positieve backtest, geslaagde challenge en duurzame netto-uitbetalingen zijn drie verschillende bewijsvragen.

**SIE wordt `ON_HOLD`, niet verwijderd.** Cushing, Costco, satellietbeelden, economische forecastmodules en de SIE–Quantmetrics-bridge blijven intact als historische/experimentele onderzoekslijn. Er worden voorlopig geen nieuwe betaalde satellietdata gekocht en geen nieuwe satellietsprints gestart zonder expliciet nieuw besluit. De bestaande SIE-onderzoeksregels, PIT-gates en auditbevindingen blijven ongewijzigd. Een losstaande marktdata-strategie is niet afhankelijk van SIE Gate A; een SIE-afgeleid signaal wél.

## 2. Succesdefinitie

**Fase A — software betrouwbaar:** de repository, data-ingest, strategie-engine, kostenmodel en propfirmregels zijn getest en reproduceerbaar.

**Fase B — alpha aantoonbaar:** een vooraf gespecificeerde strategie presteert op onaangeroerde chronologische testdata na realistische spread, commissie, slippage en relevante financierings-/swapkosten, met onzekerheidsmarges en robuustheidstests. Positieve uitkomst is niet gegarandeerd.

**Fase C — propfirmgeschiktheid:** de strategie is geëvalueerd tegen de exact gedocumenteerde, gedateerde voorwaarden van een gekozen FTMO-product; de simulatie omvat intraday- en totale drawdown, equity inclusief open P&L waar toepasselijk, handelsuren, nieuws-/overnightregels, position sizing, eventuele consistentie- en payoutvoorwaarden, kosten van challenges en mislukte pogingen.

**Fase D — operationele beoordeling:** na onafhankelijke review en expliciete goedkeuring kan een demo-/paperfase worden onderzocht. Betaalde challenges, liveorders en autonome uitvoering vereisen afzonderlijke expliciete toestemming.

## 3. Scope en prioriteiten

### P0 — Quantmetrics code- en datakwaliteitsaudit
- Verifieer feitelijke repository, default branch, actuele commit, gebruikte programmeertaal, testdekking, CI, handelsdata, simulatie- en executionmodules.
- Identificeer herbruikbare componenten; verzin geen interfaces of bestaande mogelijkheden.
- Leg vast welke functies bewezen werken, welke alleen bestaan en welke ontbreken.
- Neem architectuurbesluit (ADR): één primaire P&L-/backtestengine; voorkom dubbelbouw.

### P1 — Propfirm Rules Engine
- Maak regels **configuratiegestuurd en versieerbaar** per firma, product en peildatum; geen hardcoded veronderstellingen over FTMO.
- Ondersteun equity-/balanceberekening, floating P&L, dagreset en tijdzone/DST, maximale dagelijkse en totale verliezen, fees, challenge targets, eventueel minimumhandelsdagen en payoutvoorwaarden.
- Modelleer fail/pass als toestandsmachine; voeg synthetische grensgevaltests toe.
- Laat regels verifiëren aan officiële firmadocumentatie en leg URL, versie en controledatum vast.

### P2 — Market Data & Execution
- Onderzoek eerst FTMO-relevante EURUSD en US100 als kandidaten; kies één instrument na audit van historische bid/ask-, tick- of voldoende fijne intradaydata, tijdzone, spreads en executionkosten.
- Data-ingest legt `event_time_utc`, `available_at_utc`, bron, licentie, versie en kwaliteitscontroles vast.
- Geen gratis OHLC-midprice gebruiken alsof het gegarandeerd uitvoerbare bied-/laatprijzen zijn.
- Simuleer beslismoment, orderlatentie, spreads, slippage, stops, gaps en handelsbeperkingen zonder look-ahead.

### P3 — Eerste strategie: verklaarbare baseline
- Onderzoek één eenvoudig intradayconcept (bijvoorbeeld opening-range breakout met vooraf vastgelegde trendfilter), plus nulstrategie en eenvoudige alternatieve baseline.
- Leg hypothese, instrument, handelsuren, exacte signaalregels, stop, exit, sizing, kosten en parameterzoekruimte vast vóór evaluatie.
- Beperk parameterzoektocht; log alle varianten inclusief mislukkingen.
- Geen machine learning vóór een eenvoudige baseline overtuigend is gevalideerd.

### P4 — Alpha Discovery Factory
- Voeg pas na een betrouwbaar backtestfundament hypothesegeneratie, experimentregistratie, beperkte automatische parameterverkenning en onafhankelijke falsificatie toe.
- Bewaak multiple testing, false discovery, data snooping en selectie-effecten; geen optimalisatie op de definitieve testset.

## 4. Onderzoeksprotocol — verplicht

1. **Hypothese eerst:** vooraf geregistreerd `experiment_id`, instrument, timeframe, regels, parameters, kosten en verwachte faalmechanismen.
2. **Data-audit:** herkomst, dekking, ontbrekende periodes, corporate actions indien relevant, handelskalender, tijdzone, licentie en bid/ask-kwaliteit.
3. **Chronologische splits:** development, validation en een onaangeroerde final holdout; grenzen vastleggen vóór testen. Walk-forward op eerdere periodes.
4. **Geen leakage:** orders kunnen pas worden uitgevoerd na beschikbaarheid van alle inputs; geen future bars, repainting of hindsight-aanpassingen.
5. **Kosten en risico:** spread, commissies, slippage, swaps waar van toepassing, leverage, margin, account-equity, propfirm-limieten en intrabar stop-/drawdownambiguïteit.
6. **Robuustheid:** parameterbuurten, subperioden, kostenstress, Monte-Carlo/bootstrap met aannames, opeenvolgende verliezen en gevoeligheid voor execution.
7. **Rapportage:** netto P&L, aantal trades, exposure, winrate, profit factor, expectancy, max drawdown, drawdown-duur, returnverdeling, kans op challenge pass/fail met betrouwbaarheidsinterval, en kosten per poging. Niet alleen Sharpe of een equitycurve.
8. **Onafhankelijke review:** reproduceerbaarheid, code, statistiek, regels, licenties en security. Afwijzing is een geldige onderzoeksuitkomst.
9. **Beslissing:** `GO_RESEARCH`, `REVISE`, `REJECT`, `BLOCKED`; geen automatische overgang naar betaalde challenge.

## 5. Technische architectuur

```text
Official rules / market data
         |              |
         v              v
 rules_registry     data_ingest + quality
         |              |
         |          features/signals
         |              |
         +-------> primary backtester <------ strategy registry
                         |
                  execution & costs
                         |
                  propfirm simulator
                         |
                metrics / trade ledger
                         |
               independent audit / report
                         |
                research decision gate
```

Voorkeursstack waar passend: Python, pytest, pandas/Polars, DuckDB/Parquet, GitHub Actions. Werkelijke repo-architectuur gaat voor: eerst auditen, dan pas definitieve modulepaden vastleggen. Geen API-sleutels of accountcredentials in Git. Geen koppeling met een broker of FTMO-account zonder toestemming.

## 6. AI Development Factory: rolverdeling

| Rol | Verantwoordelijkheid | Niet toegestaan |
|---|---|---|
| Projecteigenaar | Prioriteiten, kosten, risicobudget, definitieve go/no-go | Onbedoelde liveorders |
| ChatGPT / technical lead | Onderzoeksspecificatie, GitHub issues, acceptatiecriteria, review van bewijs, status | Testresultaten claimen zonder logs |
| Cursor Agent | Op aparte branch implementeren, unit-/integratietests uitvoeren, documenteren, draft PR maken | Stilzwijgend onderzoeksregels wijzigen, rechtstreeks op main pushen |
| Claude / onafhankelijke reviewer | Adversarial code-, statistiek-, leakage-, rules- en securityreview | Eigen code zonder onafhankelijke review goedkeuren |
| GitHub Actions | Lint, typechecks waar aanwezig, tests, regressies, secret scanning waar beschikbaar | Securitychecks uitschakelen om groen te worden |
| GitHub | Issues, branches, PR's, reviewbewijs, versiebeheer | Automatisch mergen zonder vereiste gates |

**Workflow:** IDEE → ISSUE/SPEC → CURSOR PLAN → CLAUDE PLAN REVIEW → CURSOR IMPLEMENTATIE → CI/TEST → CLAUDE CODE+QUANT REVIEW → PROJECTEIGENAAR MERGE → RAPPORT. Planreview mag itereren, maar met een begrensd aantal correctierondes en expliciete escalatie bij onopgeloste blokkades. Een directe ChatGPT–Cursor-trigger wordt niet verondersteld; GitHub Issues en PR's zijn de betrouwbare overdracht totdat een officieel ondersteunde integratie aantoonbaar is geconfigureerd.

## 7. Cursor-aanpassingen

Cursor moet de nieuwe prioriteiten lezen vanuit versiebeheer. Na repo-audit:

- Voeg in de **Quantmetrics-repository** `AGENTS.md` toe of werk het bestaande bestand bij met bovenstaande workflow, onderzoeksregels, testplicht en branchdiscipline.
- Gebruik waar ondersteund projectregels onder `.cursor/rules/` als compacte verwijzing naar `AGENTS.md` en dit MASTER-document; maak geen conflicterende tweede bron van waarheid.
- Leg vast dat Cursor geen SIE-satellietfeatures ontwikkelt tenzij een expliciet issue `SIE-REACTIVATE` is goedgekeurd.
- Iedere Cursor-taak bevat doel, betrokken bestanden, data, implementatieplan, tests, acceptatiecriteria en oplevering als draft PR.
- Cursor mag geen secrets in code opnemen, geen testgates uitzetten, geen historische resultaten verzinnen en geen betaalde acties starten.
- Cursor levert per PR concrete testcommando's, logs, commit-SHA, dataherkomst, beperkingen en openstaande risico's.

## 8. GitHub-aanpassingen

1. **Controleer eerst** of `roelofgootjesgit/QuantMetrics-Suite` de juiste actieve repository is en welke bestaande instructies, workflows en branch protection gelden.
2. Maak een aparte branch, bijvoorbeeld `docs/propfirm-alpha-pivot`.
3. Voeg dit MASTER-document toe als `docs/QUANTMETRICS_ALPHA_ENGINE_MASTER.md`; actualiseer README, `AGENTS.md`, `ROADMAP.md`, `PROJECT_STATUS.md` en `EXPERIMENT_LOG.md` *alleen na inspectie*, met behoud van bestaande inhoud.
4. Open een **draft PR** met rationale, gewijzigde scope, impactanalyse, documentatietests en reviewerchecklist. Geen directe main-commit.
5. Richt branch protection / required checks in voor zover toegangsrechten en abonnement dit ondersteunen; leg ontbrekende controles vast.
6. Open issues voor PROP-00 (audit), PROP-01 (rules engine), PROP-02 (data/execution), PROP-03 (baseline strategy), PROP-04 (validation), PROP-05 (alpha discovery).
7. SIE-repository: uitsluitend status/roadmap-update naar `ON_HOLD` via afzonderlijke docs-PR. **Geen modules verwijderen, geen PIT-gates afzwakken.**

## 9. Sprintplanning en acceptatiecriteria

### PROP-00 — Repo audit en koerswijziging
**Doel:** actuele codebasis en AI-factory verifiëren; nieuwe prioriteit documenteren.  
**Input:** Quantmetrics- en SIE-repo, huidige docs, CI-status.  
**Output:** auditrapport, modulekaart, ADR voor backtester, documentatie-PR, issuebacklog.  
**Acceptatie:** echte repo/commit gecontroleerd; bestaande tests geïnventariseerd; geen bestaande veiligheidsregels verwijderd; onafhankelijke docs-review; geen code of livehandel gewijzigd.

### PROP-01 — FTMO rulebook en simulator
**Doel:** gedateerde, officiële regels omzetten naar een deterministische toestandsmachine.  
**Input:** officiële FTMO-voorwaarden voor expliciet gekozen accounttype, valuta, handelsplatform en datum.  
**Output:** versioned rules config, state transitions, grensgevaltests, rulebook-verwijzingen.  
**Acceptatie:** dagreset, equity/floating P&L, limietoverschrijding, doelbereik, kosten en DST aantoonbaar getest; onafhankelijke rules-review.

### PROP-02 — Data en uitvoeringssimulatie
**Doel:** één markt met voldoende betrouwbare historische data en uitvoerbare kostenmodellering.  
**Output:** datasetmanifest, datakwaliteitsrapport, execution-testfixtures.  
**Acceptatie:** geen toekomstige informatie; reproduceerbare import; spread-/slippage-stress; duidelijke beperkingen bij ontbrekende tickdata.

### PROP-03 — Eerste strategie en baselines
**Doel:** één vooraf gespecificeerd intradaysysteem testen, zonder parameterjacht.  
**Output:** strategieconfig, trade ledger, baselinevergelijking, experimentlog.  
**Acceptatie:** deterministische replay; exact aantal trades; fees verwerkt; alle experimenten gelogd.

### PROP-04 — Onafhankelijke validatie
**Doel:** werkelijke OOS-robuustheid en propfirmgeschiktheid beoordelen.  
**Output:** walk-forwardrapport, holdoutresultaat, challenge-simulatie inclusief kosten, onafhankelijke review.  
**Acceptatie:** heldere `GO_RESEARCH/REVISE/REJECT/BLOCKED`; geen ongefundeerde rendementclaim; geen liveorder.

### PROP-05 — Gecontroleerde alpha discovery
**Voorwaarde:** PROP-00 t/m PROP-04 technisch afgerond; primaire backtester betrouwbaar.  
**Doel:** hypotheses systematisch genereren, testen, afwijzen en registreren met begrensde AI-kosten.

## 10. Bronnenbeleid

**Officiële bronnen:** FTMO-accountvoorwaarden, handelsregels, toegestane/verboden automatisering, platformspecificaties en payoutvoorwaarden; voor alternatieve propfirms dezelfde bronhiërarchie. Registreer bron-URL, producttype, peildatum en relevante regeltekst in de rules registry. Een marketingpagina of forum is geen voldoende bron voor een harde handelsregel.

**Marktdata:** bij voorkeur herleidbare historische bid/ask- of tickdata, met duidelijke licentie en tijdzones. Documenteer ontbrekende dekking en beperkingen. Niet aannemen dat data van een externe broker identiek zijn aan de uitvoeringscondities bij FTMO.

**Wetenschappelijke methodiek:** chronologische out-of-samplevalidatie, walk-forward, multiple-testingcorrectie, risico- en executionstresstests. Er wordt geen strategie als winstgevend aangeduid zonder onafhankelijk gecontroleerde resultaten.

## 11. Verboden shortcuts

- Geen aankoop van challenges of data zonder toestemming.
- Geen automatische livehandel, order-API of accountkoppeling zonder afzonderlijk akkoord.
- Geen martingale, onbeperkt middelen of verlies najagen als vervanging voor edge.
- Geen backtests met hindsight, cherry-picking of fictieve fills.
- Geen verwarring van demo-/simulatieresultaten met uitbetaalde winst.
- Geen autonoom mergebeleid, geen secrets in repo, geen uitschakeling van CI/security.
- Geen wijziging of verwijdering van bestaande SIE-validatiegates.

## 12. Status en eerstvolgende stap

**Status op documentdatum:** alleen koerswijziging en uitvoeringsplan opgesteld. Quantmetrics-repository, Cursor-regels, GitHub-instellingen en actuele FTMO-productvoorwaarden zijn in dit document nog niet live geverifieerd of gewijzigd. Er is geen backtest uitgevoerd en geen alpha aangetoond.

**Eén volgende stap:** voer PROP-00 uit: verifieer de echte Quantmetrics-repository, inventariseer de huidige code en regels, maak een docs-only branch/PR en laat deze onafhankelijk reviewen. Pas daarna wordt de eerste rules-engine-implementatie opgedragen.

---

**Besluitlog:** 2026-11-16 — voorstel om SIE op pauze te zetten en Quantmetrics Alpha Engine als hoofdproject te prioriteren. Uitvoering, repositorywijzigingen en kosten blijven afzonderlijke goedkeurings- en verificatiestappen.
