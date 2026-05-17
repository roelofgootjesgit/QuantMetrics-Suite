# Diagnose — waarom BASE alleen 2021–2022 in QuantLog lijkt te hebben

**Status:** uitgevoerd op suite-data (2026-05-04). Geen nieuwe backtest.

---

## Uitsluitingen (scenario’s A / B / C)

### Scenario A — Data te kort / parquet eindigt vroeg

**Verworpen.**

```text
quantbuild/data/market_cache/XAUUSD/15m.parquet
Start: 2019-06-21
End:   2026-04-24
Rows:  161746
```

De cache dekt het volledige venster dat een rolling `default_period_days: 1825`‑run kan gebruiken.

---

### Scenario B — SQE vuurt na 2022 structureel niet

**Gedeeltelijk verward met het echte probleem.**

Als we **`signal_detected` per jaar** tellen op de BASE-jsonl:

| Jaar | BASE `signal_detected` |
|------|-------------------------|
| 2021 | 74 |
| 2022 | 68 |
| 2023+ | **0** |

Op **dezelfde** prijsdata en hetzelfde soort run zonder vroege afbreking telt V3 (expansion-only) wél over alle jaren:

| Jaar | V3 `signal_detected` |
|------|------------------------|
| 2021 | 74 |
| 2022 | 122 |
| 2023 | 126 |
| 2024 | 100 |
| 2025 | 148 |
| 2026 | 135 |

Conclusie: de markt levert na 2022 nog bars en (onder V3) nog kandidaat-signalen. Het ontbreken van signalen in BASE is **niet** puur “markt droogt op”.

---

### Scenario C — Exit-bug: trades open in 2023+ maar geen `trade_closed`

**Verworpen als primaire verklaring.**

In BASE zijn er **geen** `signal_detected`-events na 2022-07-22. De motor verwerkt chronologisch **entry_signals**; zonder `signal_detected` worden latere jaren **niet eens geëvalueerd** in de loop. Dit gaat vóór exit-simulatie.

---

## Scenario D — **Bevestigd:** risk stop breekt de backtest-lus af

In `quantbuild` loopt de SQE-backtest over een vooraf berekende `entry_signals`-lijst. Na **equity kill switch** (`peak_r - cumulative_r >= equity_kill_switch_pct`) zet de engine `kill_switch_triggered` en **`break`** — alle **volgende** entries in de tijd worden niet meer bezocht.

In de BASE-jsonl (`qb_run_20260504T162055Z_15a5d61a`):

- Laatste `signal_detected`: **`2022-07-22T14:30:00Z`** (142 events totaal).
- Direct hierna: `risk_guard_decision` met **`guard_name`: `equity_drawdown_kill_switch`** (`raw_reason`: `risk_block`).

Zie engine: `quantbuild/src/quantbuild/backtest/engine.py` (lus over `entry_signals`, kill switch na emit van signal + eval).

**Gevolg:** de slice “alle exits in 2021–2022” meet vooral **“hoe ver kwam de simulatie voordat risk de keten afbrak”**, niet “unieke jaar-spreiding van edge over 2021–2025”.

---

## Wat dit betekent voor EXP-SLICE-BASE-2026

- De eerdere slice-tabellen op deze BASE-run zijn **niet** geschikt om tijdstabiliteit van SQE over vijf kalenderjaren te claimen.
- **Formeel:** het slice-verdict op deze artifact alleen is **INCONCLUSIVE** voor die research-vraag (equivalent: ledger `promotion_decision` → **UNKNOWN** / niet interpreteerbaar als volledige venster).

**Aanvulling Optie B (equity-curve):** cumulatief `pnl_r` over de 42 closes toont piek **+17R**, daarna DD vanaf piek **≥10R** precies op de kill-drempel — zie [`EQUITY_CURVE_OPTION_B.md`](EQUITY_CURVE_OPTION_B.md). Dit is **geen** te-strakke arbitrage-rond 3–5R; de motor stopte omdat het **geconfigureerde** 10R DD-van-piek werd gehaald.

---

## Verplichte vervolgstap (geen nieuwe parameters)

1. **BASE opnieuw draaien** met **research-risk**: o.a. `equity_kill_switch_pct` uitzetten of substantieel verhogen, en/of `EDGE_DISCOVERY` met effectieve risk-filters zoals in team-runbooks — zodat de lus het **volledige** prijsvenster doorloopt.
2. Optioneel expliciet venster: `backtest.start_date` / `end_date` (UTC) voor reproduceerbare kalender 2021-01-01 — 2025-12-31.
3. **Slice-analyse script opnieuw** op de nieuwe jsonl.

Tot die tijd: **harde stop** op Core(3) / frequentieplan zoals vastgelegd in `docs/FTMO_FREQUENCY_PLAN_2026.md`.
