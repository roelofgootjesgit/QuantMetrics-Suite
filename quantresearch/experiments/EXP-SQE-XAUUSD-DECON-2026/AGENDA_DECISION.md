# Agenda & decision — SQE-XAUUSD deconstruction (EXP-SQE-XAUUSD-DECON-2026)

## Authoritative verdict

**Volledige interpretatie en formeel verdict:** [`RUN_VERDICT.md`](RUN_VERDICT.md)  
**Governance status:** `VALIDATION_REQUIRED` (zie [`decision.md`](decision.md))

---

## Waar de outputs staan

| Variant | `experiment_id` (QuantOS) | Pad |
|---------|---------------------------|-----|
| BASE | `EXP-SQE-XAUUSD-DECON-2026-BASE` | `quantmetrics_os/runs/EXP-SQE-XAUUSD-DECON-2026-BASE/single/` |
| V1 | `EXP-SQE-XAUUSD-DECON-2026-V1` | `…/EXP-SQE-XAUUSD-DECON-2026-V1/single/` |
| V2 | `EXP-SQE-XAUUSD-DECON-2026-V2` | `…/EXP-SQE-XAUUSD-DECON-2026-V2/single/` |
| V3 | `EXP-SQE-XAUUSD-DECON-2026-V3` | `…/EXP-SQE-XAUUSD-DECON-2026-V3/single/` |
| V4 | `EXP-SQE-XAUUSD-DECON-2026-V4` | `…/EXP-SQE-XAUUSD-DECON-2026-V4/single/` |
| V5 | `EXP-SQE-XAUUSD-DECON-2026-V5` | `…/EXP-SQE-XAUUSD-DECON-2026-V5/single/` |

Research index: `quantresearch/runs/EXP-SQE-XAUUSD-DECON-2026/README.md`

---

## Volgende fase (strikt — uit RUN_VERDICT)

**Geen** nieuwe parameter-variantenmatrix tot onderstaande klaar is.

| Prio | Taak | Type |
|------|------|------|
| **1** | Jaar- / sessie-slices BASE + V3; V4 exit-types | **Gedaan** → [`EXP-SLICE-BASE-2026/SLICE_REPORT.md`](../EXP-SLICE-BASE-2026/SLICE_REPORT.md) (`slice_exp_slice_base_2026.py`) |
| **2** | V1 H1-guard-attributie (welke blocks, MAE/MFE) | QuantLog-query |
| **3** | V4 trend-only met **fixed 2R** exit i.p.v. trail | **Eén** gerichte backtest (nieuw experiment-id) |

Hypothesen H2–H4: [`followup_hypotheses_H2_H4.md`](followup_hypotheses_H2_H4.md)

---

## Na slice-analyse: portfolio / FTMO-frequentie

Zodra Prioriteit 1 (jaar/sessie/regime op BASE + V3) af is, volgt **geen** “meer trades op één symbool door drempels te verlagen”. Het frequentiepad voor challenge-tempo zit in **multi-instrument**, **pass accelerator**, en **EURUSD MR additief** — vastgelegd in:

[`../../docs/FTMO_FREQUENCY_PLAN_2026.md`](../../docs/FTMO_FREQUENCY_PLAN_2026.md)

---

## Decision log

| Datum | Reviewer | Wijziging |
|-------|----------|-----------|
| 2026-05-04 | — | Eerste agenda na matrix-rerun |
| 2026-05-04 | — | `RUN_VERDICT.md` vastgelegd; prioriteit herschikt naar slice + attributie + V4-exit |

---

## Overige referenties

- `STRATEGY_DECONSTRUCTIE.md` — specificatie / risico’s  
- `results_summary.md` — ruwe cijfers run 2026-05-04  
- `experiment_plan.md` — configs & CLI  
