# Agent decision log — EXP-003 (HYP-003)

Experiment-specifieke audittrail voor **EXP-003**. Suite-brede beslissingen staan ook in `quantresearch/experiments/AGENT_DECISION_LOG.md`.

---

## 2026-05-04 — Verdict: HYP-003 **REJECT**

**Governance / ledger:** `governance_status`: REJECT, `academic_status`: FAIL, `effective_status`: REJECTED.

**Pre-registratie falsificatie getriggerd:**

- `ci_95_lower < 0.028` op **alle vijf** instrumenten.
- **Vier van vijf** instrumenten: negatieve `mean_r` (XAUUSD, US30, EURUSD, GBPUSD); NAS100 alleen zwak positief (`mean_r ≈ +0.101`, `ci_lower ≈ +0.017`).

**Inference-snapshot (QuantAnalytics `inference`, trade_closed R, n≥200):**

| Instrument | mean_r | ci_95_lower | stat | econ |
|------------|--------|-------------|------|------|
| XAUUSD | -0.109 | -0.196 | FAIL | FAIL |
| NAS100 | +0.101 | +0.017 | PASS | FAIL |
| US30 | -0.011 | -0.094 | FAIL | FAIL |
| EURUSD | -0.498 | -0.509 | PASS | FAIL |
| GBPUSD | -0.496 | -0.504 | PASS | FAIL |

**Registry:** `REJ-002` in `quantresearch/registry/rejected_hypotheses.json`.

---

## Interpretatie (mechanistisch, geen nieuwe hypothese zonder pre-reg)

1. **EURUSD / GBPUSD:** sterke negatieve expectancy → breakout-richting keert systematisch terug (mean-reversion in dit venster), geen continuation-edge.

2. **XAUUSD:** negatieve mean_r; ander mechanisme dan HYP-002 op dezelfde cache — geen ondersteuning voor overlap-breakout-continuation op H1 zoals gespecificeerd.

3. **NAS100:** enige positieve mean_r; `ci_lower` nog onder economische drempel (0.017 < 0.028). Eventueel vervolg alleen via **nieuwe** pre-registratie (bijv. alleen index, andere TP/M15).

---

## Eerdere stappen (samenvatting)

- **2026-05-04:** `hyp003_preregistration.json` locked (`locked_at_utc` vóór `run_start_utc`).
- **2026-05-04:** Engine `london_ny_overlap_breakout`, vijf YAML’s, matrix runner; fetch H1 voor alle instrumenten; matrix **2991** trades totaal.
- **QuantLog:** `consolidated_run_file: true`; artifacts onder `quantmetrics_os/runs/EXP-003/variant`.

---

## EXP-004 richting (open keuze — niet vastgelegd)

Mogelijke **nieuwe** experimenten na aparte pre-reg: NAS100 geïsoleerd; reversal-setup op FX; M15-variant van definitie. Geen van deze is onderdeel van HYP-003.
