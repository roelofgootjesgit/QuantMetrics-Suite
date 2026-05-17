# CURSOR PLAN — Frequentie Experimenten

## Optie A: Tijdframe verlaging | Optie B: Regime verbreding

**Doel bestand:** bouwhandleiding voor de frequentie-experimenten.  
**Locatie in repo:** `quantresearch/work_files/CURSOR_PLAN_FREQ_EXPERIMENTS.md`  
**Todo-uitvoering:** [`FREQ_EXP_TODO_PLAN.md`](FREQ_EXP_TODO_PLAN.md)  
**Status:** RESEARCH — geen productie aanpassingen  
**Principe:** één variabele per experiment, alles vergeleken tegen baseline  
**Gevalideerde baseline:** XAUUSD expansion-only (EXPANSION_FIRST / expansion-first kernel), WR ~60.5%, PF ~3.07 — config o.a. `quantbuild/configs/experiments/sqe_xauusd_deconstruct_2026/EXPANSION_FIRST_DEFAULT.yaml`

---

## Suite-paden (vereist voor alle commands)

Layout in deze suite (aanpassen naar je eigen machine):

```text
<quantmetrics-suite-root>/
  quantbuild/              → backtest, fetch, scripts/rolling_year_runner.py
  quantbuild/data/market_cache/XAUUSD/   → parquet cache
  quantbuild/scripts/
  quantbuild/configs/
  quantbuild/reports/rolling/            → rolling JSON output (aan te maken)
  quantresearch/
  quantresearch/work_files/              → dit bestand
```

Alle commands hieronder: **`cd` naar `quantbuild/`** (niet naar een losse `C:\...\quantbuild` tenzij dat jouw checkout is — in deze repo zit `quantbuild` **onder de suite-root**).

```bash
cd <quantmetrics-suite-root>/quantbuild
```

---

## Architectuur van het plan

```
FASE 0 — Data prep + rolling runner bouwen
FASE 1 — Optie B first     (lage risico, bekende engine)
FASE 2 — Optie A           (hoge risico, nieuwe pipeline)
FASE 3 — Vergelijking      (beide opties naast elkaar)
```

Optie B eerst. Reden: de engine is bekend, de data bestaat al, het risico
op architectural debt is laag. Optie A vereist nieuwe data-pipeline,
nieuwe signal-logic en volledige hervalidatie — dat doe je pas als je
weet wat Optie B oplevert.

---

## KERNPRINCIPE: Rolling Year-Slice Runner

Alle experimenten draaien via een **rolling year-slice runner** in plaats
van één enkele lange backtest.

**Waarom:**

- M5 data: 1 jaar ≈ 105.000 bars vs 525.000 voor 5 jaar. 5× sneller per run.
- Je ziet welke jaren de edge dragen en welke niet (anti-overfitting).
- Elk jaar is een onafhankelijke observatie → betere statistische spreiding.

**Tijdsvenster — flexibel:**

Start met de jaren waarvoor stabiele data beschikbaar is (bijv. 2022–2025).
Breid uit naarmate de fetch meer data oplevert. Rapporteer altijd als
**"N jaren getest"** — nooit een vast getal hardcoden in conclusies.

**Aggregatieregel:**

Rapporteer mediaan over jaren (niet gemiddelde — één uitschieter
vervormt het gemiddelde). Plus: hoeveel van de N jaren positieve mean R.

M5 pas activeren nadat 15m/1h stabiel en gevalideerd zijn.

---

## FASE 0 — Data voorbereiding + Runner bouwen

### Taak 0.1 — Fetch data (start met beschikbare jaren)

```bash
# Start met ~5 jaar — breid uit als Dukascopy het toelaat
python scripts/fetch_dukascopy_xauusd.py --days 1825 --tf 5m 15m 1h

# Smoke test per tijdframe
python scripts/market_data_smoke.py --symbol XAUUSD --timeframe 15m --count 500
python scripts/market_data_smoke.py --symbol XAUUSD --timeframe 5m --count 500
```

Acceptatiecriterium: smoke tests groen, geen gaps > 30 min in NY sessie.
M5 pas gebruiken als 15m en 1h stabiel zijn en de smoke test groen is.

---

### Taak 0.2 — Rolling year-slice runner implementeren

Maak `quantbuild/scripts/rolling_year_runner.py` (in deze repo: **geïmplementeerd** — zie bestand; PF gebruikt brutowinst/-verlies uit alle `profit_r`, inclusief TIMEOUT).

**Implementatienotities voor Cursor:**

- `run_backtest(cfg)` retourneert `List[Trade]` — importeer uit
  `src.quantbuild.backtest.engine`
- `Trade` is een Pydantic model (`src.quantbuild.models.trade`):
  - `profit_r: float`
  - `result: TradeResult` (enum: `TradeResult.WIN`, `TradeResult.LOSS`,
    `TradeResult.TIMEOUT`) — vergelijk **altijd als enum**, nooit als string
  - `timestamp_open: datetime`, `timestamp_close: datetime`
- De engine leest `cfg["backtest"]["start_date"]` en
  `cfg["backtest"]["end_date"]` als `"YYYY-MM-DD"` strings — runtime
  override werkt door deze keys in de dict te zetten vóór aanroep
- `quantlog.run_id` in de cfg (`quantlog.run_id`) wordt door de emitter gebruikt — patroon `rolling_{config_stem}_{year}`
- `load_config(path)` retourneert een plain dict; overschrijf keys direct na load

Zie broncode: `quantbuild/scripts/rolling_year_runner.py`.

---

### Taak 0.3 — Baseline vastleggen via rolling runner

```bash
python scripts/rolling_year_runner.py \
  --config configs/strict_prod_v2.yaml \
  --years 2022 2023 2024 2025
```

Breid `--years` uit naar eerdere jaren zodra data beschikbaar is.
Output → `reports/rolling/strict_prod_v2_rolling.json` (of `--out`).

---

## FASE 1 — Optie B: Regime definitie verbreden

### Context

Huidige drempels in `src/quantbuild/strategy_modules/regime/detector.py`:

- `expansion_threshold: 1.5` (ATR ratio > 1.5× SMA = expansion)
- `compression_threshold: 0.7`

Verbreden = de expansiezone eerder laten beginnen.
Risico: meer bars als expansion → meer trades, maar mogelijk lagere edge
per trade (ook zwakkere expansion-signalen worden gepakt).

---

### EXP-B1 — Expansion threshold 1.5 → 1.3

**Hypothese:** Als de threshold van 1.5 naar 1.3 wordt verlaagd worden
meer bars als expansion geclassificeerd, wat leidt tot hogere mediaan
trade-frequentie over N jaar zonder dat mediaan mean R onder 0.4R daalt.

Maak config onder bijv. `quantbuild/configs/experiments/freq_exp/` met correct `extends:`-pad naar `strict_prod_v2.yaml`.

```yaml
extends: ../../strict_prod_v2.yaml

regime:
  expansion_threshold: 1.3
```

```bash
python scripts/rolling_year_runner.py \
  --config configs/experiments/freq_exp/exp_b1_threshold_1_3.yaml \
  --compare configs/strict_prod_v2.yaml \
  --years 2022 2023 2024 2025
```

**Metrics (mediaan over N jaar):** trade count/jaar · mean R · PF · consistentie

**Beslisregel:**

- count +20% EN mean R > 0.4R → `WATCHLIST`
- count +20% EN mean R < 0.4R → `REJECT`
- count stijging < 10% → `NO_EFFECT`

Research log → `quantresearch/research_logs/EXP-B1_threshold_1_3.md`

---

### EXP-B2 — Expansion threshold 1.5 → 1.2

Alleen uitvoeren als EXP-B1 `WATCHLIST` of beter is.

```yaml
extends: ../../strict_prod_v2.yaml

regime:
  expansion_threshold: 1.2
```

```bash
python scripts/rolling_year_runner.py \
  --config configs/experiments/freq_exp/exp_b2_threshold_1_2.yaml \
  --compare configs/strict_prod_v2.yaml \
  --years 2022 2023 2024 2025
```

---

### EXP-B3 — Trend als secundaire bucket

**Hypothese:** Trend als secundaire bucket naast expansion verhoogt frequentie;
check expectancy — historische +0.208R is niet gegarandeerd (trend is in research REJECT op XAUUSD volledig venster).

```yaml
extends: ../../strict_prod_v2.yaml

regime_profiles:
  trend:
    skip: false
    tp_r: 2.0
    sl_r: 1.0
    max_trades_per_session: 1
    position_size_mult: 0.5
    allowed_sessions:
      - New York
  expansion:
    tp_r: 2.0
    sl_r: 1.0
    max_trades_per_session: 3
    position_size_mult: 1.0
    allowed_sessions:
      - New York
      - Overlap
    min_hour_utc: 10
  compression:
    skip: true
```

```bash
python scripts/rolling_year_runner.py \
  --config configs/experiments/freq_exp/exp_b3_trend_plus_expansion.yaml \
  --compare configs/strict_prod_v2.yaml \
  --years 2022 2023 2024 2025
```

**Acceptatie:** mediaan trades/jaar > 15 · mediaan mean R > 0.3R ·
consistentie ≥ 60% van N jaren · geen verdubbeling mediaan max DD

---

### EXP-B4 — Geen hour gate

```yaml
extends: exp_b3_trend_plus_expansion.yaml  # of volledige inhoud kopiëren met juiste extends

regime_profiles:
  expansion:
    min_hour_utc: 0
    allowed_sessions:
      - New York
      - Overlap
      - London
```

```bash
python scripts/rolling_year_runner.py \
  --config configs/experiments/freq_exp/exp_b4_no_hour_gate.yaml \
  --compare configs/experiments/freq_exp/exp_b3_trend_plus_expansion.yaml \
  --years 2022 2023 2024 2025
```

Beslisregel: mediaan mean R daalt t.o.v. B3 → gate is terecht → KEEP.
Mediaan mean R gelijk of hoger én trades stijgen → gate verwijderen is candidate.

---

## FASE 2 — Optie A: Tijdframe verlaging naar M5

**Voer Optie A pas uit als Optie B volledig afgerond is én M5 smoke test groen.**

M5 vereist: nieuwe primaire bars pipeline · H1 gate → M15 gate (controleer of
`structure_use_m15_gate` bestaat in `src/quantbuild/strategies/sqe_xauusd.py`;
zo niet → tijdelijk `structure_use_h1_gate: false` + open issue) ·
hervalidatie ICT params · nieuwe regime ATR `atr_sma_period`.

---

### EXP-A1 — M5 smoke test

```bash
python scripts/market_data_smoke.py --symbol XAUUSD --timeframe 5m --count 500
```

Faalt → stop, data-fetch herhalen, daarna pas verder.

---

### EXP-A2 — M5 config

Zie origineel YAML-blok; plaats onder `configs/experiments/freq_exp/exp_a2_m5_baseline.yaml` en test met één jaar voordat je rolling draait.

---

### EXP-A3 — M5 rolling backtest

```bash
python scripts/rolling_year_runner.py \
  --config configs/experiments/freq_exp/exp_a2_m5_baseline.yaml \
  --compare configs/strict_prod_v2.yaml \
  --years 2022 2023 2024 2025
```

Mediaan WR < 45% of mediaan PF < 1.5 → `REJECT M5`.
Mediaan WR > 50% en mediaan PF > 2.0 → `WATCHLIST M5`.

---

### EXP-A4 — M5 slice analyse

Alleen bij WATCHLIST van A3. Slices via QuantAnalytics op rolling run_ids:
uur (0–10 vs 10–22 UTC) · sessie · per jaar.
Check mediaan max intraday drawdown op hogere frequentie.

---

## FASE 3 — Vergelijkingstabel

Vul in: `quantresearch/work_files/FREQ_EXP_COMPARISON.md`

Alle waarden zijn mediaan over N geteste jaren:

| Experiment | Trades/jr | WR | PF | Mean R | Max DD | Consist. | Verdict |
|-----------|-----------|----|----|--------|--------|----------|---------|
| Baseline expansion-first | ~5–6 | ~60.5% | ~3.07 | ? | ? | ?/N | PROVEN |
| B1 threshold 1.3 | ? | ? | ? | ? | ? | ?/N | ? |
| B2 threshold 1.2 | ? | ? | ? | ? | ? | ?/N | ? |
| B3 trend + expansion | ? | ? | ? | ? | ? | ?/N | ? |
| B4 no hour gate | ? | ? | ? | ? | ? | ?/N | ? |
| A2 M5 baseline | ? | ? | ? | ? | ? | ?/N | ? |

---

## Beslisregels (hard)

**PROMOTE:** trades/jaar > 2× · mean R > 0.4R · PF > 1.8 · DD ≤ 1.5× · ≥ 70% jaren positief

**WATCHLIST:** trades/jaar > 1.5× · mean R > 0.3R · PF > 1.5 · ≥ 60% jaren positief

**REJECT:** mean R < 0.3R, of PF < 1.5, of DD > 2×, of < 60% jaren positief

**NO_EFFECT:** trade count stijging < 15%

---

## Regels voor Cursor

1. Eén config-wijziging per experiment. Nooit twee tegelijk.
2. Eigen config-bestand per experiment. Geen inline overrides.
3. Elke rolling run → JSON in `quantbuild/reports/rolling/`.
4. Baseline altijd meelopen via `--compare`.
5. Engine errors op M5 → stop, open issue, niet omheen werken.
6. Geen conclusies bij mediaan trades/jaar < 3.
7. Optie A pas starten als Optie B volledig klaar is.
8. `TradeResult` altijd als enum vergelijken — nooit als string.

---

## Failure criteria

Als geen Optie B variant mediaan frequentie > 1.5× baseline behaalt
met mediaan PF > 2.0 en consistentie ≥ 60%:

→ **`FREQ_CEILING_REACHED`**

Actie: registreer in `quantresearch/registry/rejected_hypotheses.json` (of apart research-log); terug naar **Pad A** — provider/challenge-keuze conform [`quantresearch/README.md`](../../README.md) (architecture decision).

---

*Locatie: `quantresearch/work_files/CURSOR_PLAN_FREQ_EXPERIMENTS.md`*  
*Zie `quantresearch/README.md` documentatietabel voor vindplaats.*  
*`quantbuild/scripts/rolling_year_runner.py` is geïmplementeerd in deze suite.*
