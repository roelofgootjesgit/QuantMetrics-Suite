# FASE 3 — Frequentie-experimenten vergelijking

Vul in na rolling runs. Alle waarden: **mediaan over N geteste jaren** (niet enkelvoudige lange backtest).

**N = 4** (2022–2025). Baseline hier = **`strict_prod_v2`** (volledige stack), niet expansion-only.

| Experiment | Trades/jr | WR | PF | Mean R | Max DD | Consist. | Verdict |
|------------|-----------|----|----|--------|--------|----------|---------|
| Baseline strict_prod_v2 | 21 | 42.6% | 1.49 | +0.280 | −7.5 | 3/4 | ref |
| B1 threshold 1.3 | 20 | 44.4% | 1.60 | +0.333 | −7.5 | 3/4 | NO_EFFECT |
| expansion_first_default (`extends` strict_prod_v2, trend off) | 4.5 | 75.0% | 6.00 | +1.250 | −1.0 | 4/4 | hogere R, veel minder trades |
| B2 threshold 1.2 | | | | | | /N | |
| B3 (`exp_b3_trend_plus_expansion` vs expansion kern) | 9.5 | 58.4% | 3.40 | +0.656 | −1.5 | 4/4 | **REJECT** (mediaan trades ≤10; zie REJ-003) |
| B4 no hour gate | | | | | | /N | |
| A2 M5 baseline (`exp_a2_m5_baseline`, vs expansion kern) | 0 | — | — | — | — | 0/4 | **REJECT** — `NO_TRADES_PIPELINE_ISSUE` (REJ-005; diagnose: zie `m5_engine_smoke.py`, geen "geen edge"-claim) |

*Jaren in runner: 2022, 2023, 2024, 2025.*
