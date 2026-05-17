# EXP-SLICE-BASE-2026 — Slice report

> **⚠️ Lees eerst [`DIAGNOSIS_DATA_INTEGRITY.md`](DIAGNOSIS_DATA_INTEGRITY.md).**  
> De onderstaande tabellen op **dit** BASE-artifact zijn **niet** geschikt om jaar-stabiliteit van SQE te beslissen: de run werd **afgebroken door `equity_drawdown_kill_switch`** (`2022-07-22`); latere jaren ontbreken daarom in de JSONL — niet alleen bij `trade_closed`, ook bij `signal_detected`.

Generated from **existing** QuantLog artifacts (no new backtest).

- Generated UTC: `2026-05-04T17:08:16Z`
- Suite root: `C:\Users\Gebruiker\quantmetrics-suite`

## Ordering gate

This experiment **must** complete before Core(3) / portfolio frequency work: if BASE trades cluster in one or two years, downstream frequency plans rest on unstable single-instrument evidence.

---

## Interpretation (quick)

- **BASE trades span only 2 calendar year(s)** (`n=42`). 
Before scaling frequency via Core(3), confirm whether this reflects **data/bar coverage** for the BASE run 
(e.g. exits only through early window) vs a stable multi-year edge.

---

## BASE — By calendar year (exit `timestamp_utc`)

### BASE (SQE XAUUSD — EXP-SQE baseline run)

| Year | n | Net R | WR | PF |
|------|---|-------|----|----|
| 2021 | 23 | +16.00 | 56.5% | 2.6 |
| 2022 | 19 | -10.00 | 15.8% | 0.375 |


## BASE — By session (at trade exit)

### BASE

| Session | n | Net R | WR | PF |
|---------|---|-------|----|----|
| London * | 5 | +1.00 | 40.0% | 1.3333 |
| New York * | 13 | +2.00 | 38.5% | 1.25 |
| Overlap * | 24 | +3.00 | 37.5% | 1.2 |

*Focus sessions for plan: London, New York, Overlap.


## V3 — Expansion-only — By year (critical: time stability)

### V3 (regime_profiles.trend.skip)

| Year | n | Net R | WR | PF |
|------|---|-------|----|----|
| 2021 | 9 | +3.00 | 44.4% | 1.6 |
| 2022 | 4 | +5.00 | 75.0% | 6.0 |
| 2023 | 8 | +4.00 | 50.0% | 2.0 |
| 2024 | 4 | +5.00 | 75.0% | 6.0 |
| 2025 | 5 | +10.00 | 100.0% | ∞ |
| 2026 | 8 | +4.00 | 50.0% | 2.0 |


## V4 — Trend-only — Exit distribution

### V4 — Exit-type distribution (trade_closed.exit)

| Exit tag | Count | Share |
|----------|-------|-------|
| SL | 22 | 64.7% |
| TP | 12 | 35.3% |


---

## Raw metrics JSON

See `slice_metrics.json` in this folder.
