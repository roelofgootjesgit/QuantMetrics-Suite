# Optie B — Equity-curve op bestaande BASE-run (42 trades)

**Bron:** `quantlog_events.jsonl` van `EXP-SQE-XAUUSD-DECON-2026-BASE` (`qb_run_20260504T162055Z_15a5d61a`).  
**Methode:** alle `trade_closed` chronologisch sorteren; cumulatieve som van `payload.pnl_r`; piek-equitý (running max van cum); drawdown vanaf piek = `peak_R − cum_R`.

**Kill-switch-check in engine:** `peak_r - cumulative_r >= equity_kill_switch_pct` met default **10.0** (R vanaf piek, niet “procent account”). Zie `quantbuild/src/quantbuild/backtest/engine.py`.

---

## Samenvatting

| Metric | Waarde |
|--------|--------|
| Aantal closes | 42 |
| **Piek cumulatieve R** | **+17.0R** (na win streak tot ca. mei–jun 2022) |
| **Eind cumulatieve R** (laatste close in jsonl) | **+6.0R** |
| **Max drawdown vanaf piek** | **11.0R** (na tweede −1R op `2022-07-22T07:30:00Z`) |
| **Eerste keer DD ≥ 10R vanaf piek** | na trade die **cum naar +7.0R** bracht — DD_exact **10.0R** (piek blijft +17R) |

Laatste `trade_closed` timestamps: **2022-07-22T07:30:00Z** (twee closes op hetzelfde bar-moment).  
De kill switch op **14:30** die dag (eerste `signal_detected` daarna geblokkeerd) sluit aan op: na die closes is DD vanaf piek ≥ **10R**, dus de volgende signaal-iteratie krijgt `equity_drawdown_kill_switch`.

---

## Interpretatie (Optie B vs jouw keuzes)

- Dit is **geen** “te conservatieve drempel bij −3 tot −5R”: het pad raakt de **geconfigureerde 10R**-DD-van-piek **wel**.
- **Optie A** (kill uit voor research) blijft legitiem om **signaalverdeling over jaren** te zien, maar de **eerlijke** FTMO-context blijft: *dit pad* zou onder dezelfde risk-regels de keten ook hebben stilgelegd.

**Conclusie voor de volgende stap:** BASE in deze vorm toont een **echte diepe drawdown-fase** (−10R+ vanaf piek) vóór het stoppen van de simulatie — geen puur artifact van een “per ongeluk te lage” kill. Core(3) “lost dat niet automatisch op”; het diversifieert alleen als de stack dat pad niet reproduceert.

---

## Volledige curve (42 closes)

```bash
python quantresearch/scripts/equity_curve_from_quantlog.py \
  quantmetrics_os/runs/EXP-SQE-XAUUSD-DECON-2026-BASE/single/quantlog_events.jsonl
```

Belangrijkste mijlpalen in de **werkelijke** jsonl-volgorde:

- Piek **+17R** bereikt na trade **22** (`2021-11-23` — twee **+2R** closes).
- Langere **erosie** feb–jul 2022: o.a. lijst verliezen `2022-02-24` … `2022-02-25` brengt DD naar **7R** vanaf piek.
- Trade **41** (`2022-07-22T07:30`): cum **+7R**, DD vanaf piek **exact 10.0R** → voldoet aan `equity_kill_switch_pct` (**≥10**).
- Trade **42** (zelfde tijdstempel): cum **+6R**, max DD **11R** vanaf piek.

Daarna: volgende **signal**-iteratie krijgt `equity_drawdown_kill_switch` (`14:30` die dag in QuantLog).
