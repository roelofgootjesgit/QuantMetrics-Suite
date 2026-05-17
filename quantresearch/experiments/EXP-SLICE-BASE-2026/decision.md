# Decision — EXP-SLICE-BASE-2026

## Formeel verdict (herzien)

```
VERDICT: BASE REJECTED voor FTMO en funded gebruik (interpretatie single-instrument SQE-run zoals gedocumenteerd)
REDEN:   DD-profiel bereikt 11R piek-tot-vallei op 42 gesloten trades (cum −11R vanaf +17R piek).
         Kill switch triggerde terecht op geconfigureerde 10R DD-van-piek — niet te conservatief.
ACTIE:   Eerst exit-/regime-diagnose (EXP-V4-EXIT-FIX-2026, H1-attributie) en BASE Optie A (research kill uit)
         voordat frequentie-opschaling wordt hervat.
```

**Ledger:** `promotion_decision`: **REJECT** (interpretatie: SQE BASE-stack onder deze condities niet geschikt als alleen-XAU-grondslag voor challenge).

## Toelichting

De eerdere status **INCONCLUSIVE / UNKNOWN** gold voor de **kalender-spreidingsvraag** op een artifact dat door kill-switch werd afgebroken. Na **Optie B** (`EQUITY_CURVE_OPTION_B.md`) is het oordeel over **risk-gedrag** wél helder: de kill werkte zoals bedoeld.

Zie ook:

- [`DIAGNOSIS_DATA_INTEGRITY.md`](DIAGNOSIS_DATA_INTEGRITY.md) — waarom jaar-slices op het oude BASE-jsonl misleidend waren.
- [`EQUITY_CURVE_OPTION_B.md`](EQUITY_CURVE_OPTION_B.md) — cumulatieve R-curve.

## Hold (herzien)

**Core(3)** niet als “volgende stap na slice” maar alleen als het **XAUUSD-component** een verdedigbaar DD-profiel heeft — zie [`../docs/FTMO_FREQUENCY_PLAN_2026.md`](../../docs/FTMO_FREQUENCY_PLAN_2026.md).
