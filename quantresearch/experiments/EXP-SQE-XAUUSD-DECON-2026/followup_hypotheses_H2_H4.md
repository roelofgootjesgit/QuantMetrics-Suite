# Follow-up hypothesen — na EXP-SQE-XAUUSD-DECON-2026

Afgeleid van `RUN_VERDICT.md`. Eén test per hypothese; aparte experiment-ids wanneer er weer backtests nodig zijn.

| ID | Statement | Voorkeursbewijs |
|----|-----------|-----------------|
| **H2** | H1-gate laat asymmetrisch winst weg t.o.v. verlies | MAE/MFE + entry-type split BASE vs V1; guard-attributie op geblokkeerde bars |
| **H3** | Expansion > trend in base rate (WR) wanneer geïsoleerd | Jaar-slices V3; vergelijking met V4 opzelfde venster |
| **H4** | Trend-negativiteit (V4) komt door trail-exit, niet entry | V4 rerun met fixed 2R/1R zoals expansion-profiel; exit-type uit bestaande V4 JSONL |
