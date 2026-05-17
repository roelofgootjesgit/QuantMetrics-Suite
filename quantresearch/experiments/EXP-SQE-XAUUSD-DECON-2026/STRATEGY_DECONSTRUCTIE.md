# SQE-XAUUSD — Strategie Deconstructie

## 1. Strategie Deconstructie

**Wat wordt hier echt gezegd?**

De SQE-kernel is een ICT-gebaseerd entry-model met drie conditionele lagen die simultaan of binnen een lookback-window actief moeten zijn, gecombineerd met regime-classificatie als primaire filter.

**Aannames die er impliciet in zitten:**

- Liquidity sweeps + FVG's + displacement samen zijn een betere predictor dan elk afzonderlijk
- ATR-ratio is een bruikbare proxy voor marktregime
- H1 structuur is een valide hogere-timeframe gate voor 15m entries
- "2 van 3" module-combinatie (sweep/disp/FVG) heeft hogere precision dan "alle 3"
- EXPANSION-regime in NY/Overlap heeft systematisch andere eigenschappen dan TREND

**Waar het nog vaag is:**

De gerapporteerde 70% WR en PF 5.24 zijn **showcase-level metrics** — gepresenteerd als "orde van grootte" in de OS-documentatie, niet als geauditeerde single-config resultaten. De QUANTBUILD_OVERVIEW zelf toont voor het concrete gevalideerde portfolio: XAUUSD +0.32R expectancy bij 254 trades over 5 jaar. Dat is het enige getal dat er nu toe doet.

**Dit is geen onaannemelijke claim.** Maar de kloof tussen 0.32R expectancy (echte engine) en "WR ~70%" (showcase) is een signaal dat die 70% óf uit een andere configuratie komt, óf selectief gerapporteerd is.

---

## 2. Geformaliseerde Strategie

**Entry conditions (15m, XAUUSD)**

```
PRECONDITIONS:
  regime IN [TREND, EXPANSION]
  session IN allowed_sessions(regime)
    TREND   → London, Overlap, New York
    EXPANSION → New York, Overlap, min_hour_utc >= 10
  H1 structure_context:
    LONG  → in_bullish_structure = True (HH/HL)
    SHORT → in_bearish_structure = True (LH/LL)

ENTRY SIGNAL:
  combo_count >= 2 within lookback_bars = 5, where combo =
    [liquidity_sweep, displacement, fair_value_gaps]

  liquidity_sweep:
    low < swing_low(lookback=20) AND close > swing_low (LONG)
    high > swing_high(lookback=20) AND close < swing_high (SHORT)
    sweep_threshold_pct = 0.15
    reversal_candles = 4

  displacement:
    min_body_pct = 60%
    min_candles = 2
    min_move_pct = 1.5%

  fair_value_gaps:
    min_gap_pct = 0.3%
    validity_candles = 80

EXIT:
  EXPANSION + NY → Fixed TP: 2R, SL: 1R
  TREND         → Partial +1R (50%), trail from 1.5R pullback

INVALIDATION:
  COMPRESSION regime → geen entry
  Session buiten allowed_sessions → BLOCK
  H1 structure niet aligned → BLOCK
```

---

## 3. Meetbare Hypothese

**Primaire:**
> Als de SQE-combo (≥2/3 van sweep+disp+FVG binnen 5 bars) actief is in TREND/EXPANSION regime met aligned H1 structuur en correcte sessie, dan is de verwachte R per trade > 0, zichtbaar in expectancy_r over minimaal 100 trades.

**Secundaire:**
> EXPANSION-regime heeft een hogere win rate dan TREND-regime, zichtbaar in regime-gesplitste WR en PF.

**Structurele:**
> De H1-gate filtert trades met negatieve expectancy eruit, zichtbaar in WR-verschil H1-gate aan vs. uit.

---

## 4. QuantMetrics Mapping

**QuantBuild — Decision Logic**

| Parameter | Huidig | Moet getest worden |
|---|---|---|
| combo_min_count | 2 | 1, 2, 3 |
| entry_sweep_disp_fvg_lookback_bars | 5 | 3, 5, 8 |
| expansion_threshold | 1.5x ATR SMA | 1.3x, 1.7x |
| structure_use_h1_gate | True | True vs False (guard impact test) |

**QuantLog — Events die gelogd moeten worden**

Elk van deze is al aanwezig in de JSONL-structuur, maar dit zijn de kritische velden per analyse:

- `entry_path`: welke combo-pad triggerde de entry
- `combo_active_modules_count`: hoeveel modules actief
- `regime`: per trade
- `session`: per trade
- `structure_label`: bullish/bearish alignment
- `trend_pillar_ok` / `liquidity_pillar_ok` / `trigger_ok`: individueel

**QuantAnalytics — Analyses vereist**

- Funnel: detected → evaluated → signal → guard-passed → filled → closed
- Guard dominance: welke guard blokkeert het meest (regime_allowed_sessions is al zichtbaar als dominante blocker in de JSONL)
- WR/PF per regime × sessie matrix
- Combo-pad breakdown: welke 2-van-3 combinatie scoort het best
- H1-gate impact: trades met/zonder als split

---

## 5. Testplan

**Baseline**

- Config: `A0_BASELINE.yaml` (reeds aanwezig)
- Period: 5 jaar, 2021-2025
- Metric: expectancy_r, WR, PF, trade_count, max_drawdown_r

**Varianten (prioriteit volgorde)**

| Variant | Interventie | Hypothese |
|---|---|---|
| V1: H1-gate off | `structure_use_h1_gate = False` | Kwantificeert guard-waarde |
| V2: combo_min=3 | `entry_sweep_disp_fvg_min_count = 3` | Hogere precision, minder trades |
| V3: EXPANSION only | Regime filter = EXPANSION only | Test of regime-claim klopt |
| V4: TREND only | Regime filter = TREND only | Baseline voor regime-split |
| V5: lookback=3 | `entry_sweep_disp_fvg_lookback_bars = 3` | Stricter temporal clustering |

**Slice-analyse (verplicht)**

```
tijd:        per jaar (2021, 2022, 2023, 2024, 2025)
sessie:      London / New York / Overlap / Asia
regime:      TREND / EXPANSION / COMPRESSION (als baseline)
combo-pad:   sweep+disp / sweep+fvg / disp+fvg
```

---

## 6. Failure Criteria

| Uitkomst | Conditie |
|---|---|
| **REJECT** | expectancy_r ≤ 0 over volledige 5-jaar periode, of trade_count < 50 |
| **VALIDATION_REQUIRED** | trade_count 50-100, of expectancy_r > 0 maar PF < 1.3, of drawdown_r > 20R |
| **PROMOTE CANDIDATE** | trade_count > 100, expectancy_r > 0.20R, PF > 1.4, max_drawdown < 15R, consistent across ≥3 van 5 jaren |

De huidig gerapporteerde XAUUSD metrics (254 trades, +0.32R expectancy, PF 1.65) zitten in de PROMOTE CANDIDATE zone — maar dat is portfolio-level, niet component-level.

---

## 7. Risico op Illusie van Edge

**Guard dominance — Kritisch risico**

In de JSONL-logs is al zichtbaar dat `regime_allowed_sessions` de dominante blocker is. Dit betekent: een substantieel deel van de "edge" kan session-filtering zijn, niet de SQE-signaallogica zelf. Test V1 (H1-gate off) en V4 (TREND only, alle sessies) kwantificeren dit.

**Sample size — Marginaal**

254 trades over 5 jaar = ~51 trades per jaar. Bij regime-splitting (TREND vs EXPANSION) en sessie-splitting kom je op subgroepen van 30-80 trades. Dat is statistisch onvoldoende voor definitieve conclusies. Elke subgroep-claim is **VALIDATION_REQUIRED** totdat je minimaal 100 trades per slice hebt.

**De 70% WR — Niet bruikbaar als referentie**

De showcase-documentatie meldt zelf: "meant to show the class of evidence, not live trading performance." Die 70% is waarschijnlijk afkomstig van de full-kernel + adaptive config, niet van de SQE-component in isolatie. Gebruik uitsluitend de engine-output uit `A0_BASELINE.yaml` als grondlijn.

**Overfitting risico — Aanwezig**

De config heeft 15+ tuneerbare parameters. Als deze op dezelfde 5-jaar dataset zijn geoptimaliseerd waarmee je ook valideert, heb je in-sample fitting. Mitigatie: walk-forward validatie per jaar, of een apart out-of-sample window (bijv. 2021-2023 in-sample, 2024-2025 out-of-sample).

---

**Bottomline**

De SQE-kernel is formeel gespecificeerd en meetbaar. De gerapporteerde 0.32R expectancy op 254 trades is een reëel startpunt — geen bullshit, maar ook geen bewezen edge. Het is een hypothese die de juiste structuur heeft om getest te worden. De vijf varianten hierboven, gecombineerd met de slice-analyse, leveren het verdict.

De 70% WR bestaat niet als geïsoleerd meetpunt. Die claim is nu **gesuspendeerd tot nader order.**
