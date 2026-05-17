# Todo-uitvoeringsplan — Frequentie-experimenten (FREQ)

**Handleiding:** [`CURSOR_PLAN_FREQ_EXPERIMENTS.md`](CURSOR_PLAN_FREQ_EXPERIMENTS.md)  
**Vergelijking invullen:** [`FREQ_EXP_COMPARISON.md`](FREQ_EXP_COMPARISON.md)  
**Runner:** `quantbuild/scripts/rolling_year_runner.py`  
**Werkdirectory voor commands:** `quantbuild/` (onder suite-root).

---

## FASE 0 — Data + runner + baseline

| # | Taak | Status |
|---|------|--------|
| 0.1 | `cd quantbuild` — fetch XAUUSD `5m 15m 1h` (start bijv. `--days 1825`; uitbreiden als nodig) | ☑ |
| 0.2 | Smoke: `market_data_smoke.py` voor `15m` en `5m` — groen | ☑ |
| 0.3 | Optioneel: smoke `1h` als gate voor die configs gebruikt wordt | ☑ |
| 0.4 | Runner sanity: `python scripts/rolling_year_runner.py --config configs/strict_prod_v2.yaml --years 2024` (één jaar, snel) | ☑ |
| 0.5 | Baseline rolling: `strict_prod_v2.yaml` + `--years 2022 2023 2024 2025` — JSON in `reports/rolling/` | ☑ |
| 0.6 | Optioneel: baseline **expansion-first** naast strict — zelfde jaren voor eerlijke vergelijking met research-baseline | ☑ (`configs/expansion_first_default.yaml` → `reports/rolling/expansion_first_rolling.json`) |
| 0.7 | Map `quantbuild/configs/experiments/freq_exp/` aanmaken voor EXP-B/A YAML’s | ☑ |

---

## FASE 1 — Optie B (regime / buckets)

**Regel:** één experiment tegelijk; na elke run JSON bewaren en research-logregel.

| # | Taak | Status |
|---|------|--------|
| B1 | Maak `freq_exp/exp_b1_threshold_1_3.yaml` (`extends` + `expansion_threshold: 1.3`) | ☑ |
| B1 | Run rolling runner + `--compare configs/strict_prod_v2.yaml` | ☑ |
| B1 | Beslis: WATCHLIST / REJECT / NO_EFFECT — log `quantresearch/research_logs/EXP-B1_threshold_1_3.md` | ☑ |
| B2 | *Alleen als B1 ≥ WATCHLIST:* `exp_b2_threshold_1_2.yaml` + rolling + log | ☐ |
| B3 | *Hypothese trend bucket:* `exp_b3_trend_plus_expansion.yaml` + rolling + log | ☑ → **REJECT** (freq-gate; `registry/rejected_hypotheses.json` REJ-003) |
| B4 | *Alleen na B3:* `exp_b4_no_hour_gate.yaml` + compare tegen B3-config + log | ☐ |
| — | Vul tussentijds `FREQ_EXP_COMPARISON.md` (mediaan-kolommen) | ☑ (baseline, B1, expansion_first_default) |

---

## FASE 2 — Optie A (M5) — pas na afronding FASE 1

| # | Taak | Status |
|---|------|--------|
| A0 | **Stop-criterium:** Optie B volledig doorgelopen of expliciet gestopt met log | ☑ (`REJ-004` FREQ_CEILING_REACHED) |
| A1 | M5 smoke `market_data_smoke.py --timeframe 5m` — groen | ☑ |
| A2 | Maak `exp_a2_m5_baseline.yaml` — controleer `structure_use_h1_gate` / geen fictieve keys tenzij geïmplementeerd | ☑ (`configs/experiments/freq_exp/exp_a2_m5_baseline.yaml`) |
| A3 | Rolling + verdict M5 vs expansion-first (`exp_a2_m5_baseline`) | ☑ **REJECT M5** (`REJ-005`, 0 trades; rolling uitgevoerd) |
| A4 | *Alleen bij WATCHLIST:* slice-analyse (QuantAnalytics op run_ids) | ☐ *overslagen (REJECT)* |
| — | Update `FREQ_EXP_COMPARISON.md` | ☑ |

---

## FASE 3 — Afronding

| # | Taak | Status |
|---|------|--------|
| 3.1 | Vul `FREQ_EXP_COMPARISON.md` volledig (alle rijen + **N** jaren) | ☐ |
| 3.2 | Definitief verdict: PROMOTE / WATCHLIST / REJECT / `FREQ_CEILING_REACHED` | ☑ (`REJ-004`, `REJ-005`) |
| 3.3 | Bij ceiling: entry in `registry/rejected_hypotheses.json` of research-log + verwijs naar Pad A in `README.md` | ☑ (`REJ-004`) |
| 3.4 | Archiveer alle `reports/rolling/*.json` met datum in bestandsnaam of submap indien gewenst | ☐ |

---

## Snelle commando-referentie

```bash
cd <suite-root>/quantbuild

# Smoke
python scripts/market_data_smoke.py --symbol XAUUSD --timeframe 15m --count 500

# Fetch (pas days aan)
python scripts/fetch_dukascopy_xauusd.py --days 1825 --tf 5m 15m 1h

# Rolling (voorbeeld)
python scripts/rolling_year_runner.py --config configs/strict_prod_v2.yaml --years 2022 2023 2024 2025
```

---

## Afhankelijkheden / risico’s

- Lange runs: begin met **één jaar**, schaal op naar vier.
- Geen data vóór 2022: pas `--years` aan; noteer **N** overal.
- **Pad A** (architecture decision) blijft leidend bij `FREQ_CEILING_REACHED` — geen engine forceren voor challenge-tempo.
