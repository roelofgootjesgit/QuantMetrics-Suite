# Hypothesis — EXP-V4-EXIT-FIX-2026

**H4 (research):** Als negatieve net R onder trend-only vooral door **exit-gedrag** (trail vs fixed) kwam, dan verwacht je verbetering bij fixed 2R — **mits** de simulator trail gebruikt.

**Feit QuantBuild SQE-backtest:** `engine._simulate_trade` gebruikt **alleen vaste** TP/SL in R-multiples van `regime_profiles.*.tp_r` / `sl_r`. Er is **geen** trailing-exit in deze codepath.

Deze run test daarom:

1. **Trend-only** (expansion `skip`) over het **volledige** bar-venster zonder **equity kill switch** die de lus vroeg afbreekt (research analogie van Optie A-vraag).
2. Expliciet **tp_r: 2 / sl_r: 1** op het trend-profiel (gelijk aan stack-intentie; redundant maar auditbaar).

Interpretatie: verbetering t.o.v. “afgebroken” runs meet **temporele dekking**; het vergelijkt **niet** live-trail met backtest-fixture.
