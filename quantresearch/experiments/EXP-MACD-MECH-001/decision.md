# decision.md — EXP-MACD-MECH-001

**Datum:** 2026-05-17  
**Run ID:** qb_run_20260517T150609Z_5ea614ca  
**Experiment:** MACD Cross Isolation — EURUSD M15  
**Verdict:** `REJECT` (component not informative)

---

## Data-gap notitie

Zelfde window als EXP-BB-MECH-001: **2023-02-02 → 2024-12-31** (47.614 bars).  
2022 ontbreekt in cache.

---

## Resultaten

| Metric | Waarde | Drempel | Status |
|--------|--------|---------|--------|
| N independent signals | 1.958 | ≥ 100 | OK |
| Clustering rate | 45.6% | < 40% | **FAIL** (marginaal) |
| Win rate (backtest T+8 exit) | 44.4% | — | — |
| Win rate forward @ T+8 | 48.8% | — | ~random |
| Expectancy R (backtest) | -0.035R | > 0 | **FAIL** |
| Profit Factor | 0.91 | ≥ 1.0 | **FAIL** |
| Permutation p-value | **0.79** | < 0.05 | **FAIL (H0 niet verworpen)** |
| Mean forward R @ T+8 | -0.035 | > 0 | **FAIL** |
| Velocity vs win @ T+8 (r) | 0.028 | predictief | **FAIL** |
| BB∩MACD same-bar (Pearson) | 0.012 | — | onafhankelijk |

---

## time_to_adverse_excursion (0.5R MAE)

| Metric | Waarde | Interpretatie |
|--------|--------|---------------|
| n gemeten | 1.344 / 1.958 | 68% bereikt 0.5R MAE binnen 16 bars |
| **Mean bars** | **4.5** | niet T+2 — cross niet onmiddellijk “te laat” |
| **Median bars** | **3.0** | |
| **≤ 2 bars** | **41.6%** | substantieel deel heeft snelle adverse move |
| **≤ 6 bars** | **76.3%** | ruimte voor executie-window na T+2 |

**Conclusie TAE:** Delayed-confirmation is **gedeeltelijk** aanwezig (42% binnen 2 bars), maar gemiddeld T+4–5 — niet extreem genoeg om alleen time-exit te verklaren. Het probleem is vooral **geen directionele edge**, niet alleen exit-mechanisme.

---

## Voorafgaande hypotheses — uitkomst

| Hypothese | Resultaat |
|-----------|-----------|
| MACD cross @ M15 near-random bij time-exit | **Bevestigd** (p=0.79, mean fwd R < 0) |
| Cross velocity voorspelt win @ T+8 niet | **Bevestigd** (r ≈ 0.03) |

---

## Verdict

```
REJECT
```

MACD cross (12/26/9) op EURUSD M15 bevat **geen bewezen directionele informatie** boven random timestamps onder independence filter en T+8 horizon.

---

## Implicatie voor EXP-JOINT-001

Joint test is **niet priority** tenzij expliciete rationale:
- BB: REJECT als trade + SIGNAL_BEHAVIOR_OBSERVED
- MACD: REJECT component
- Synergy vereist minimaal één informatieve component → **joint waarschijnlijk zinloos**

Toegestaan: joint alsnog draaien als **confirmatory negative** (gedocumenteerde redundancy check).

---

## Verboden

```
❌ MACD parameters tunen (8/21/5)
❌ Guards toevoegen
❌ Time exit bars wijzigen op basis van deze run
```

---

## Volgende stap

Optioneel: EXP-JOINT-001 confirmatory REJECT, of onderzoekslijn **sluiten** na registry-update.

*Metrics: `metrics_summary.json`, `permutation_results.json` in dit dossier.*
