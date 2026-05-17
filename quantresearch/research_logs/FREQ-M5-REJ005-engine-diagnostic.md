# FREQ — REJ-005 engine-diagnose (EXP-A2 M5)

**Datum:** 2026-05-04  
**Registry:** `quantresearch/registry/rejected_hypotheses.json` — **REJ-005**

## Wat níét aangetoond is

- Dat XAUUSD op M5 structureel geen edge heeft (die claim volgt niet uit `NO_TRADES` alleen).

## Wat wél gemeten is (`m5_engine_smoke.py`)

Config: `quantbuild/configs/experiments/freq_exp/exp_a2_m5_baseline.yaml` (zelfde keten als rolling).

### Voorbeeldslice: jaar **2025** (volledige kalender, lokale cache na fetch)

| Stap | Aantal |
|------|--------|
| M5 bars | 53 855 |
| Regime “expansion” (bars) | ~2,9% |
| Ruwe SQE any LONG/SHORT (pre H1, pre regime-loop) | 325 bars |
| Na H1-gate, any signal | 121 bars |
| Na H1 ∧ regime == expansion | 35 bars |
| Na expansion `allowed_sessions` + `min_hour_utc` | **0** |

Session-labels van de **35** post-H1+expansion bars: **Asia 30**, **London 5** — dus **geen** NY/Overlap; expansion-profiel uit `strict_prod_v2` blokkeert alles vóór simulatie.

## Gevolg

`NO_TRADES` = **filter-/config-interactie** (regime + sessie) op M5, **niet** “geen signalen” en **niet** bewezen marktconclusie.

## Opmerking over eerdere rolling 2022–2024

Zonder voldoende M5-parquet in cache kunnen jaarslices leeg blijven (`run_backtest` → lege lijst). Dat is een **data-dekking**-vraag, los van de bovenstaande logica.
