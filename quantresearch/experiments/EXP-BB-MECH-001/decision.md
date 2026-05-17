# decision.md — EXP-BB-MECH-001

**Datum:** 2026-05-17  
**Run ID:** qb_run_20260517T145022Z_6a1a7c65  
**Experiment:** BB-Only Isolation — EURUSD M15  
**Verdict:** `REJECT_AS_TRADE_STRATEGY` + `SIGNAL_BEHAVIOR_OBSERVED`

---

## Data-gap notitie (verplicht)

Config vroeg: 2022-01-01 → 2024-12-31  
Werkelijke dataset: **2023-02-02 → 2024-12-31** (47.614 M15-bars)  
2022 ontbreekt in Dukascopy-cache.

**Impact:** Dataset is ~33% korter dan gepland. N=1617 onafhankelijke signals is
voldoende voor reject-verdict (drempel: 100), maar onvoldoende voor een
promote-verdict. Dit experiment kan alleen REJECT of INSUFFICIENT opleveren —
nooit PROMOTE_CANDIDATE — zolang 2022 ontbreekt.

**Actie vereist:** 2022-data ophalen NA mechanisme-analyse, niet ervoor.

---

## Resultaten

| Metric | Waarde | Drempel | Status |
|--------|--------|---------|--------|
| N signals (independent) | 1.617 | ≥ 100 | OK |
| Clustering rate | ~73% | < 40% | **FAIL** |
| Win rate | 50.2% | — | — |
| Expectancy R | -0.09R | > 0 | **FAIL** |
| Profit Factor | 0.81 | ≥ 1.0 | **FAIL** |
| MFE / MAE | 0.85R / 0.85R | MFE > MAE | **FAIL** |
| Midline hit before SL | 53.6% | — | — |
| Permutation test | **niet uitgevoerd** | p < 0.05 | OPEN |

---

## Interpretatie

**Clustering (73%):** BB touches clusteren zwaar binnen trending/volatile episodes.
6.101 raw observations reduceren naar 1.617 independents. Ruwe sample is illusie.
Independence filter werkt correct — dit is geen implementatie-bug.

**Expectancy negatief bij 53.6% midline hit:** Mean reversion *treedt op* maar
compenseert adverse excursion niet. Trades bereiken de midline vaker dan SL, maar
de verliezende trades verliezen meer dan de winners winnen. SL-structuur (ATR×2.0)
absorbeert te veel adverse movement vóór reversion plaatsvindt.

**MFE ≈ MAE (0.85R / 0.85R):** Geen directional asymmetrie. Trades bewegen
symmetrisch in beide richtingen na entry. Dit is het kenmerk van een non-informative
signal in dit regime. Een echte edge laat MFE > MAE zien.

**Permutation test niet uitgevoerd:** Forward return distributie per bar (T+4/T+8/T+16)
nog niet gemeten. Dit onderscheidt "signal heeft geen informatie" van "executie-model
faalt op correcte signal." Blijft OPEN als follow-up item, maar verandert het
trade-strategy verdict niet — expectancy < 0 is voldoende voor REJECT.

---

## Verdict

```
REJECT_AS_TRADE_STRATEGY
```

BB-extension (length=20, stddev=2.0) op EURUSD M15 produceert **geen tradable
asymmetrie** als standalone executie-signal onder de gedefinieerde condities
(ATR×2.0 SL, midline exit, 0.25% risk).

```
SIGNAL_BEHAVIOR_OBSERVED
```

BB-extension detecteert **observeerbare mean-reversion behavior** (53.6% midline
hit). Dit is mogelijk bruikbaar als contextual feature in toekomstige modellen,
niet als executie-trigger.

---

## Wat dit experiment bewezen heeft

1. BB touches zijn geen onafhankelijke events op M15 EURUSD — clustering 73%
2. Naïeve sample size (6.101) was illusie — werkelijke informatie-dragende events: 1.617
3. Independence filter is functioneel correct en noodzakelijk
4. Mean reversion treedt op maar is niet sterk genoeg voor positieve expectancy
5. MFE ≈ MAE: geen directionele informatie in de signal definitie

---

## Verboden vervolgacties

```
❌ BB stddev aanpassen (2.5, 3.0) om resultaat te verbeteren
❌ SL aanpassen op basis van deze run
❌ Guards toevoegen om PF op te poetsen
❌ 2022-data ophalen en BB-run herhalen vóór MACD-mechanisme getest is
❌ Parameters tweaken
```

---

## Toegestane vervolgacties

```
✅ EXP-MACD-MECH-001 starten (component isolatie — onafhankelijk van BB-verdict)
✅ Forward return distributie meten als post-hoc analyse (optioneel)
✅ 2022-data ophalen NA EXP-MACD-MECH-001 en EXP-JOINT-001
```

---

## Volgende stap

**EXP-MACD-MECH-001** — MACD cross standalone, time-based exit (T+8 bars),
zelfde instrument en periode. Vraag: heeft MACD cross zelfstandige
directionele informatie op EURUSD M15?

---

*Experiment gesloten. Geen heropening zonder nieuw experiment-ID.*
