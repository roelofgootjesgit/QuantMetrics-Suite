# Research index

_Auto-generated from `registry/`. Regenerate with `write_research_index()` after updating JSON registries._

## Experiments

| ID | Date | Title | Result | Status | Academic |
|----|------|-------|--------|--------|----------|
| EXP-001 | 2026-04-22 | Expansion-only regime test | positive | completed | — |
| EXP-002 | 2026-05-04 | HYP-002 NY sweep failure reclaim — V5A + expansion block (closed dossier) | positive | promoted | FAIL |
| EXP-004 | 2026-05-12 | XAUUSD M5 PDH/PDL sweep + reclaim + displacement + micro-shift (offline research) | negative | completed | REJECT |

## Confirmed edges

- Expansion regime shows positive expectancy in Q1 2026 backtest.
- HYP-002 NY sweep failure reclaim (V5A: C=2, expansion excluded) shows positive mean_r under mock_spread 0.5 on 2021-2025 and on both 2021-2023 and 2024-2025 splits (see EXP-002 metrics bundle).

## Rejected hypotheses

- Trend regime is profitable in the tested Q1 2026 baseline.
- London/NY overlap H1 breakout (close confirmation, tp_multiplier=1.5) generates positive expectancy on XAUUSD, NAS100, US30, EURUSD, GBPUSD
- EXP-B3 — Trend als secundaire bucket (0.5× size, NY-only, max 1 trade/sessie) op expansion_first_default haalt vooraf geregistreerde frequentiegrens (>10 trades/jaar mediaan) met behoud van edge-vloeren.
- Optie B (regime/tuning op M15) kan de expansion-first edge-context structureel opschalen in trade-frequentie binnen één pre-registered hygiëne-pad.
- EXP-A2 — Onder dezelfde expansion-first config is bewezen dat M5 per se 'geen edge' heeft (als conclusie uit enkel NO_TRADES backtests).
- XAUUSD M5 PDH/PDL liquidity sweep with reclaim + displacement + micro structure shift during London/NY (UTC) yields positive expectancy at 1.5R vs sweep-based SL (0.1 ATR buffer), without trend-aware selection.

## Open questions

- _(none — pass `open_questions=` to `write_research_index()` or edit after generate)_

## Next experiments

- EXP-002 Expansion × session filtering
- EXP-003 Expansion-only with regime_allowed_sessions relaxed
