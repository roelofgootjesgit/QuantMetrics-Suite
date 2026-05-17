# Decision — EXP-V4-EXIT-FIX-2026

**Status:** `VALIDATION_REQUIRED`

**Summary:** Full-window trend-only run (kill disabled for loop completeness) completes **137** trades with **PF 0.95**, **WR ~32%**, **~−26R max DD** from peak on cumulative `pnl_r` path. Not a promotion candidate.

**H4 (trail vs fixed in this simulator):** Not testable here — SQE backtest has **no** trail; fixed 2R/1R was already the simulator behavior.

**Next:** EXP-H1-attributie (V1 path) and/or BASE Optie A (kill off on **full** BASE, not only trend) remain separate ledgers.
