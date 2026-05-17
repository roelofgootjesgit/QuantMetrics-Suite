# Agent decision log — ontwikkel- en onderzoekspad

Dit bestand vangt **methodologische en technische keuzes** vast die in de Cursor-agentthread worden gemaakt, zodat het spoor auditable blijft. **Voeg per relevante user-input een sectie toe** (nieuwste bovenaan).

**Locaties:**

- **Per experiment:** `quantresearch/experiments/EXP-00N/AGENT_DECISION_LOG.md` (o.a. EXP-003).
- **Suite-breed (dit bestand):** `quantresearch/experiments/AGENT_DECISION_LOG.md`.

---

## 2026-05-04 — FREQ / EXP-A2 M5 **REJ-005** gecorrigeerd (`NO_TRADES_PIPELINE_ISSUE`)

- **Probleem:** Rolling `exp_a2_m5_baseline` → `NO_TRADES` was geïnterpreteerd als “M5 heeft geen edge”. Dat is **niet** ondersteund: market-data smoke zegt alleen dat parquet/lezen OK is.
- **Instrument:** `quantbuild/scripts/m5_engine_smoke.py` — laadt zelfde YAML, meet regime-verdeling, ruwe SQE (`run_sqe_conditions` vóór regime-loop), H1-gate, overlap met `regime==expansion`, daarna expansion `allowed_sessions` + `min_hour_utc`.
- **Bevinding (XAUUSD, venster 2025):** ruwe SQE-signalen **> 0** (325 bars met any signal); na H1 nog 121 bars; **post-H1 ∧ expansion**: 35 bars; na expansion profile sessie/uur: **0**. Breakdown van die 35: **Asia 30, London 5** — buiten `New York`/`Overlap` van strict_prod expansion-profiel.
- **Registry:** `REJ-005` herschreven — `reason`: `NO_TRADES_PIPELINE_ISSUE`, `registry_status`: `DIAGNOSTICS_COMPLETED`; geen economische “geen edge”-claim.
- **Open:** M5 frequentie/edge als hypothese vereist **nieuwe** pre-reg (regime-thresholds op 5m, en/of sessiefilters); niet af te leiden uit enkel rolling counts.

---

## 2026-05-04 — EXP-003 / HYP-003 **REJECT** (ledger + registry)

- **Ledger:** `quantresearch/experiments/EXP-003/experiment.json` — `governance_status` REJECT, `academic_status` FAIL, `effective_status` REJECTED, `rejection_reason` zoals in bestand.
- **Registry:** `REJ-002` in `quantresearch/registry/rejected_hypotheses.json`.
- **Detail + interpretatie:** `quantresearch/experiments/EXP-003/AGENT_DECISION_LOG.md`.
- **Falsificatie:** geen instrument haalt `ci_95_lower ≥ 0.028`; 4/5 negatieve `mean_r`. Combined n=2991 trades.
- **EXP-004:** geen vaste richting vastgelegd — opties: NAS100 geïsoleerd, reversal op EUR/GBP, of M15-variant; vereist **nieuwe** pre-registratie.

---

## 2026-05-03 — EXP-003 engine `london_ny_overlap_breakout` geïmplementeerd

- **Module:** `quantbuild/src/quantbuild/strategies/london_ny_overlap_breakout.py` — `run_london_ny_overlap_breakout_backtest` (retour: `List[Trade]`, zelfde patroon als HYP-002).
- **Router:** `backtest.engine` in `run_backtest` wanneer `backtest.engine: london_ny_overlap_breakout` (tak vóór `ny_sweep_reversion`).
- **Daglogica (UTC):** range = eerste H1 op die dag met `open time >= session_open_utc` (default 13:30); signal = volgende H1 op **dezelfde** dag; entry = open van de H1 **daarna**; spread via `broker.mock_spread` / `mock_spread`; SL/TP zoals pre-reg; simulatie = `_simulate_trade_price_levels` (SL vóór TP/MFE op dezelfde bar, gelijk aan HYP-002).
- **QuantLog:** `range_detected`, `breakout_signal`, `trade_action` (ENTER of `NO_ACTION` + `reason`), `trade_closed` met o.a. `mfe_r`, `bars_to_mfe`, `range_size`, `tp_multiplier`, `mock_spread`.
- **Tests:** `quantbuild/tests/test_london_ny_overlap_breakout.py` (5 tests, alle geslaagd). Geen minimum aantal rien in de dataframe (enkele dagen kunnen 1 bar hebben); dat voorkomt valse lege runs voor `no_signal_candle`-cases.
- **Open:** vijf YAML’s + `run_exp003_matrix.py` (volgende stap volgens user).

---

## 2026-05-04 — HYP-003 pre-registratie vastgelegd (pipeline JSON)

- **Bestand:** `quantresearch/pipelines/hyp003_preregistration.json`
- **`pre_registration_status`:** `locked_before_run`
- **`pre_registration_valid`:** `true`
- **`locked_at_utc` / `pre_registration_timestamp_utc`:** **`2026-05-04T09:27:53Z`** (UTC; afgeleid van committer time van `feat(research): EXP-003 HYP-003 pre-registration locked + validator`).
- **`run_start_utc`:** **`2026-05-04T09:58:27.576964Z`** (vroegste matrix-run; zie `hyp003_preregistration.json`).
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
