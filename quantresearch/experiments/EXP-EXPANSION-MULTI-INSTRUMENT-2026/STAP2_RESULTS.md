# Stap 2 — EXP-EXPANSION-MULTI-INSTRUMENT-2026 (resultaten)

**Venster:** zelfde als stap 1 (`default_period_days: 1825`, rolling; data Dukascopy 15m + 1h prefetch).

## USDJPY (`EXP-EXPANSION-MULTI-2026-USDJPY`)

| Metric | Engine console | JSONL (`trade_closed`) |
|--------|----------------|-------------------------|
| n | 21 | 21 |
| Σ `pnl_r` | — | **+3.00** |
| WR | 38.1% | 38.1% |
| PF | 1.23 | 1.23 |
| Max DD | −9R | — |

**Jaar (exit-ts):** 2022 +10R (n=8); 2023 −2R (2); 2024 −4R (10); 2025 −1R (1).

**Promotie-rubric (per instrument: n>30, WR>45%, PF>1.3):**

- n = 21 → **VALIDATION_REQUIRED** (n < 30)
- WR / PF → onder drempel → **REJECT** voor deployment van deze stack op USDJPY.

---

## GBPUSD (`EXP-EXPANSION-MULTI-2026-GBPUSD`)

| Metric | Engine console | JSONL |
|--------|----------------|-------|
| n | 12 | 12 |
| Σ `pnl_r` | — | **−12.00** |
| WR | 0.0% | 0.0% (0/12 wins) |
| PF | 0.00 | 0.00 |

**Jaar:** 2022 −3R (3 trades); 2024 −6R (6); 2025 −3R (3).

**Verdict:** **REJECT** — bevestigt het instrument_profiles‑inzicht (expansion eerder uitgeschakeld voor Cable); expansion‑only SQE-stack produceert hier geen bruikbare edge op dit venster.

---

## Config‑pad fix

Initiële `extends` gebruikte `../../sqe_...` (één niveau te veel → broken resolve). Correct:

`extends: ../sqe_xauusd_deconstruct_2026/EXPANSION_FIRST_DEFAULT.yaml`

---

## Runs / artifacts

| Instrument | run_id | artifacts |
|------------|--------|-----------|
| USDJPY | `qb_run_20260504T174321Z_c5a4d7e2` | `quantmetrics_os/runs/EXP-EXPANSION-MULTI-2026-USDJPY/single/` |
| GBPUSD | `qb_run_20260504T174427Z_0fe7286e` | `quantmetrics_os/runs/EXP-EXPANSION-MULTI-2026-GBPUSD/single/` |
