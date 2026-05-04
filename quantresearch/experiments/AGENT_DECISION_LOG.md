# Agent decision log — ontwikkel- en onderzoekspad

Dit bestand vangt **methodologische en technische keuzes** vast die in de Cursor-agentthread worden gemaakt, zodat het spoor auditable blijft. **Voeg per relevante user-input een sectie toe** (nieuwste bovenaan).

**Canonical locatie:** `quantresearch/experiments/AGENT_DECISION_LOG.md` (naast andere experiment-/research-artifacts zoals `EXP-002/experiment.json`).

---

## 2026-05-04 — HYP-003 pre-registratie vastgelegd (pipeline JSON)

- **Bestand:** `quantresearch/pipelines/hyp003_preregistration.json`
- **`pre_registration_status`:** `locked_before_run`
- **`pre_registration_valid`:** `true`
- **`locked_at_utc` / `pre_registration_timestamp_utc`:** **`2026-05-04T09:27:53Z`** (UTC; afgeleid van committer time van `feat(research): EXP-003 HYP-003 pre-registration locked + validator`).
- **`run_start_utc`:** `null` tot eerste QuantBuild-run EXP-003 engine.
- **Validator:** `quantresearch/preregistration.py` staat `locked_before_run` + `valid true` toe **zonder** `run_start_utc` tot de run start.
- **Volgende stap:** QuantBuild engine `london_ny_overlap_breakout` + configs + matrix runner (nog te bouwen).

---

## 2026-05-04 — EXP-003 pre-registratie (HYP-003) + technische haalbaarheid

### Vergrendeld vóór formalisering document

- **Range-definitie:** **Definitie C** — eerste **volledige H1-candle** na **13:30 UTC** als dagelijkse range.
- **Breakout:** **B1** — **close** van de **volgende** H1-candle **strikt** boven range high (long) of **strikt** onder range low (short); entry = **open** van de H1-candle **na** de breakout-candle; SL = volledige range; TP = **1.5×** range; **één entry per instrument per dag**; bij **twee geldige breakouts** op dezelfde dag → **skip**.

### Pre-registratiedocument (samenvatting)

- **Experiment ID:** EXP-003  
- **H0 / H1:** zoals in `hyp003_preregistration.json` (dual gate: ci + profit factor).  
- **Instrumenten:** XAUUSD, NAS100, US30, EURUSD, GBPUSD.  
- **Venster:** 2021-01-01 — 2025-12-31, **H1**.

### Technische check QuantBuild

| Laag | Status |
|------|--------|
| **H1-data + 5 symbolen** | Ja — generieke parquet pipeline + `instrument_profiles` dukascopy mappings |
| **EXP-003 strategy engine** | Nog te bouwen |

---

## 2026-05-04 — Analytics: `tp_headroom` slice (exploratief)

- Module: `quantmetrics_analytics/analysis/tp_headroom.py`, schema `tp_headroom_v1`.
- CLI: `--reports tp_headroom` (niet in `all`).
- Geen `collect_run_artifact`.

## 2026-05-04 — Analytics: `mfe_timing` slice

- Commit `cc7ed17`: `mfe_timing_v1`, bundle `mfe_timing_report.json`.
- Conclusie: `bars_to_mfe` onderscheidt TP-magnitude niet materieel.

## Eerdere draad (samenvatting)

- HYP-002 lottery-profiel; `mfe` logging op `trade_closed`; pad 2 (winststaart) voorafgaand aan HYP-003.

---

*Onderhoud: nieuwe datums bovenaan toevoegen.*
