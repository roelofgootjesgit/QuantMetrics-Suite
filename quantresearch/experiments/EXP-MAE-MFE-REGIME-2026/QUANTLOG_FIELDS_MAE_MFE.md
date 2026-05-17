# `mae_r` en `mfe_r` in QuantLog `trade_closed`

## Wat

Op elk `trade_closed` event staan in `payload` (backtest: `quantbuild` → `backtest_engine`):

| Veld | Betekenis |
|------|-----------|
| **`mfe_r`** | Maximum Favorable Excursion in **R-eenheden** vanaf entry tot exit: het gunstigste prijsniveau dat de trade *ooit* bereikte, uitgedrukt in risico (typisch 1R = afstand tot SL). |
| **`mae_r`** | Maximum Adverse Excursion in **R-eenheden**: de diepste beweging tegen de positie in voordat de uiteindelijke exit. |
| `mfe_peak_timestamp_utc` | Tijdstip waarop `mfe_r` werd gehaald (indien bekend). |
| `bars_to_mfe` | Aantal 15m-bars tot MFE-piek (indien bekend). |

Deze waarden komen uit de post-entry simulatie in `_simulate_trade` (vaste TP/SL in de standaard backtest); ze beschrijven **gedrag na entry**, niet de entry-regel.

## Waarom (onderzoek)

- Zelfde SQE-entry, andere **regime**-label (trend vs expansion): als expansion een hogere WR heeft, kan dat komen doordat de **prijsstructuur na entry** gunstiger is (hogere MFE t.o.v. MAE, vaker MFE ≥ 1R vóór stop, enz.).
- Zonder nieuwe backtest: direct vergelijken per regime uit bestaande `quantlog_events.jsonl` (BASE = mix, V3 = expansion-only, V4 = trend-only).

## Bronbestanden (huidige runs)

| Run | JSONL | Gebruik |
|-----|-------|---------|
| EXP-SQE-XAUUSD-DECON-2026-BASE | `quantmetrics_os/runs/EXP-SQE-XAUUSD-DECON-2026-BASE/single/quantlog_events.jsonl` | Trend + expansion |
| EXP-SQE-XAUUSD-DECON-2026-V3 | `.../V3/.../quantlog_events.jsonl` | Alleen expansion |
| EXP-V4-EXIT-FIX-2026 | `quantmetrics_os/runs/EXP-V4-EXIT-FIX-2026/single/quantlog_events.jsonl` | Alleen trend (volledig venster) |

Script: `quantresearch/scripts/mae_mfe_regime_from_quantlog.py`.
