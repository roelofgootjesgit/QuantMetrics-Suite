# EXP-B1 — `expansion_threshold` 1.5 → 1.3

**Config:** `quantbuild/configs/experiments/freq_exp/exp_b1_threshold_1_3.yaml`  
**Baseline:** `strict_prod_v2.yaml`  
**Venster:** kalenderjaren 2022–2025 (N=4) — `rolling_year_runner.py`  
**Artifact:** `quantbuild/reports/rolling/exp_b1_threshold_1_3_2022_2025.json`

## Resultaten (mediaan over 4 jaren)

| set | median trades | median mean R | median WR | median PF |
|-----|---------------|---------------|-----------|-----------|
| B1 (1.3) | 20 | +0.333 | 44.4% | 1.60 |
| strict_prod_v2 | 21 | +0.280 | 42.6% | 1.49 |

**Consistentie:** beide 3/4 jaren met positieve mean R (zelfde jaren; 2022 negatief in beide).

## Delta per jaar (B1 − baseline)

- 2022–2023, 2025: identiek trade count en R (zelfde entry-set in die jaren).
- **2024:** −4 trades; mean R +0.106; PF +0.22; total R +1.0 — dunnere expansion-classificatie wijzigt vooral selectie in dit jaar, niet structuraal meer volume.

## Beslissing (rubric FREQ-plan)

- Mediaan trade count t.o.v. baseline: **−1** (20 vs 21) — geen +20% stijging.
- **Verdict: `NO_EFFECT`** op frequentie (geen stijging median trades/jaar; zelfs lichte daling).

**Opmerking:** Dit is `strict_prod_v2` (volledige stack), niet expansion-only. Voor vergelijking met Pad A / expansion-first kan een tweede rolling-run met `EXPANSION_FIRST_DEFAULT` worden gedraaid.

**Volgende stap:** EXP-B2 **niet** automatisch starten — plan voorzag B2 alleen bij WATCHLIST; hier NO_EFFECT. Optioneel: B1 opnieuw met expansion-only baseline voor coherentie met architecture decision.
