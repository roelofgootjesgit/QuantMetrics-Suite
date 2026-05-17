# Todo — BB + MACD Signal Research Battery v1.1

**Serie:** `EXP-BB-MECH`  
**Doel:** Bewijzen of Bollinger Band extension en MACD cross individueel en gezamenlijk voorspellende informatie bevatten boven random baseline.  
**Geen optimalisatie** — signal research battery.

**Architectuur:**
- `quantbuild` → indicatoren, strategieën, signalen, backtest
- `quantresearch` → permutation tests, experiment-dossiers, `decision.md`
- `quantlog` → canonical event spine; payload-uitbreiding alleen met contract tests

**Werkdirectory commands:** suite-root; Python-paden onder `quantbuild/src` en `quantresearch/quantresearch`.

---

## HARD CONSTRAINTS (niet onderhandelbaar)

- [ ] Geen parameter-tuning na eerste resultaten
- [ ] Geen combinatie van variabelen in één variant-run
- [ ] Indicatoren alleen in `quantbuild/src/quantbuild/indicators/`
- [ ] Strategieën alleen in `quantbuild/src/quantbuild/strategies/`
- [ ] Config volledig via YAML — geen hardcoded strategy params in Python
- [ ] Alle events via bestaande `QuantBuildEmitter` / QuantLog-contract
- [ ] Tests vóór implementatie (TDD waar mogelijk)
- [ ] Elk experiment: `decision.md` vóór volgende fase
- [ ] **Fase 2 altijd draaien** — ook als BB (fase 1) faalt
- [ ] Shadow exits = **shadow exit accounting**, geen echte dubbele orders

---

## Event-semantiek (funnel niet vervuilen)

| Event | Gebruik |
|-------|---------|
| `component_observed` | Losse BB- of MACD-conditie gezien (research observatie) |
| `candidate_signal` | Na independence filter; nog geen entry |
| `trade_action` | Echte `ENTER` / `NO_ACTION` (execution spine) |

Niet elke conditie als generiek `signal_detected` loggen zonder onderscheid.

---

# FASE 0 — INFRASTRUCTUUR

## 0.1 Bollinger Bands indicator

| # | Taak | Status |
|---|------|--------|
| 0.1a | Tests: `quantbuild/tests/test_bollinger.py` (mid==SMA, upper≥mid≥lower, warmup NaN, geen lookahead) | ☑ |
| 0.1b | Implementatie: `quantbuild/src/quantbuild/indicators/bollinger.py` | ☑ |
| 0.1c | Export in `indicators/__init__.py` | ☑ |

## 0.2 MACD indicator

| # | Taak | Status |
|---|------|--------|
| 0.2a | Tests: `quantbuild/tests/test_macd.py` (cross op synthetische data, geen lookahead, warmup, bull/bear niet tegelijk True) | ☑ |
| 0.2b | Implementatie: `quantbuild/src/quantbuild/indicators/macd.py` | ☑ |
| 0.2c | Cross-definitie: `bullish_cross = (macd > signal) & (macd.shift(1) <= signal.shift(1))` (idem bearish) | ☑ |

## 0.3 Signal independence filter

| # | Taak | Status |
|---|------|--------|
| 0.3a | Tests: `quantbuild/tests/test_signal_independence.py` | ☑ |
| 0.3b | Implementatie: `quantbuild/src/quantbuild/utils/signal_independence.py` (nieuwe `utils/` package) | ☑ |
| 0.3c | Criteria: `min_bars_gap`, `min_atr_distance * ATR`; eerste signal altijd `True` | ☑ |

## 0.4 QuantLog payload uitbreiding

| # | Taak | Status |
|---|------|--------|
| 0.4a | Inventariseer bestaande event types in `quantlog` contracts + `QuantBuildEmitter` | ☐ |
| 0.4b | Payload velden (component/candidate): `component_type`, BB/MACD flags, `bb_extension_normalized_atr`, `macd_cross_velocity`, `regime_at_signal`, `session_at_signal`, `bars_since_last_signal`, `price_distance_from_last_signal_atr`, `signal_is_independent` | ☐ |
| 0.4c | Payload velden (trade_closed / research outcome): `bars_to_midline`, `hit_midline_before_sl`, `exit_reason`, `bars_held`, `mfe_r`, `mae_r` | ☐ |
| 0.4d | Contract tests in `quantlog/tests/` bij schema-wijziging | ☐ |
| 0.4e | Wire-up in quantbuild emitter (geen ad-hoc JSON buiten contract) | ☐ |

## 0.5 Permutation test utility (quantresearch)

| # | Taak | Status |
|---|------|--------|
| 0.5a | Tests: `quantresearch/tests/test_permutation_test.py` | ☐ |
| 0.5b | Implementatie: `quantresearch/quantresearch/statistics/permutation_test.py` | ☐ |
| 0.5c | Output: `observed_hit_rate`, `baseline_mean_hit_rate`, `p_value`, `significant`, `n_signals`, `n_permutations`, `seed` | ☐ |
| 0.5d | Validatie: random → niet structureel p&lt;0.05; perfect predictor → p≈0; seed reproduceerbaar | ☐ |

**Fase 0 gate:** alle tests groen vóór strategie-werk.

---

# FASE 1 — EXP-BB-MECH-001 (BB standalone)

| # | Taak | Status |
|---|------|--------|
| 1.0 | Tests strategie: `quantbuild/tests/test_bb_only_strategy.py` | ☐ |
| 1.1 | Strategie: `quantbuild/src/quantbuild/strategies/bb_only.py` | ☐ |
| 1.2 | Config: `quantbuild/configs/exp_bb_mech_001.yaml` | ☐ |
| 1.3 | Registry: `quantresearch/experiments/EXP-BB-MECH-001/` dossier skeleton | ☐ |
| 1.4 | Run backtest EURUSD M15 2022-01-01 → 2024-12-31 | ☐ |
| 1.5 | Analytics: observations, independent candidates, entries, hit_midline, MFE/MAE, extension buckets, permutation test, regime/session attribution (geen filter) | ☐ |
| 1.6 | `decision.md` — verdict INSUFFICIENT / REJECT / VALIDATION_REQUIRED / PROMOTE_CANDIDATE | ☐ |

**Entry:** LONG `close < bb_lower`; SHORT `close > bb_upper`  
**Exit:** midline touch; time exit 32 bars; SL = 2× ATR

**Verdict regels:** N&lt;100 → INSUFFICIENT; p≥0.05 → BB not significant; p&lt;0.05 → BB informative

---

# FASE 2 — EXP-MACD-MECH-001 (MACD standalone)

> **Altijd uitvoeren** — ook als fase 1 BB reject/insufficient is.

| # | Taak | Status |
|---|------|--------|
| 2.0 | Tests: `quantbuild/tests/test_macd_only_strategy.py` | ☐ |
| 2.1 | Strategie: `quantbuild/src/quantbuild/strategies/macd_only.py` | ☐ |
| 2.2 | Config: `quantbuild/configs/exp_macd_mech_001.yaml` | ☐ |
| 2.3 | Exit: **fixed horizon** `time_exit_bars: 8` (geen midline) | ☐ |
| 2.4 | Run backtest | ☐ |
| 2.5 | Analytics: forward return T+4/T+8/T+16, win rate T+8, velocity buckets, permutation test | ☐ |
| 2.6 | `decision.md` in `quantresearch/experiments/EXP-MACD-MECH-001/` | ☐ |

---

# FASE 3 — EXP-JOINT-001 (BB + MACD)

**Start-voorwaarde:** minimaal één component informatief **of** expliciete rationale om joint toch te testen (niet “beide significant” vereisen).

| # | Taak | Status |
|---|------|--------|
| 3.0 | Tests: `quantbuild/tests/test_bb_macd_joint_strategy.py` | ☐ |
| 3.1 | Strategie: `quantbuild/src/quantbuild/strategies/bb_macd_joint.py` | ☐ |
| 3.2 | Config: `quantbuild/configs/exp_joint_001.yaml` | ☐ |
| 3.3 | `shadow_dual_exit`: research accounting only — primary time_exit 8; shadow_a fixed RR 1.5; shadow_b midline | ☐ |
| 3.4 | Run + analytics | ☐ |
| 3.5 | **Matched comparison** (geen simpele synergy-formule): joint vs BB-only en MACD-only opzelfde bars/regime/session/horizon | ☐ |
| 3.6 | Synergy drempel: +5pp hit-rate of +0.05R expectancy vs matched baselines | ☐ |
| 3.7 | Redundancy + exit-confound check | ☐ |
| 3.8 | `decision.md` — REDUNDANT / SYNERGY / VALIDATION_REQUIRED / REJECT | ☐ |

---

# FASE 4 — VARIANT MATRIX (alleen na promotie)

**Voorwaarden:** N&gt;200, p&lt;0.05, split-half reproduceerbaar, joint of BB-only verdedigbaar.

| Variant | Wijziging | Config (voorbeeld) | Status |
|---------|-----------|-------------------|--------|
| V2 | BB stddev 2.5 | `exp_joint_v2_bb_std_25.yaml` | ☐ |
| V3 | MACD 8/21/5 | `exp_joint_v3_macd_fast.yaml` | ☐ |
| V4 | NY session only | `exp_joint_v4_ny.yaml` | ☐ |
| V5 | London only | `exp_joint_v5_london.yaml` | ☐ |
| V6 | Compression regime only | `exp_joint_v6_compression.yaml` | ☐ |
| V7 | Trend regime only | `exp_joint_v7_trend.yaml` | ☐ |
| V8 | SL ATR 1.5 | `exp_joint_v8_sl_15.yaml` | ☐ |

Elke variant: aparte `experiment_id`, aparte run, aparte `decision.md`, **één wijziging**.

---

# DECISION MATRIX (na elk experiment)

1. **Sample size:** N&lt;100 → INSUFFICIENT  
2. **Clustering:** `clustering_rate` &gt; 40% → rapporteren vóór performanceconclusie  
3. **H0:** p≥0.05 → component niet bewezen; p&lt;0.05 → informatief  
4. **Performance:** expectancy_R&lt;0 (N≥200) → REJECT; PF&lt;1.0 → REJECT; MFE/MAE&lt;1.2 → zwakke structuur  
5. **Robustness:** split-half inconsistent → VALIDATION_REQUIRED; één kwartaal/regime draagt alles → regime-specific  
6. **Promotion:** expectancy_R&gt;0.15, PF&gt;1.25, N&gt;200, p&lt;0.05, split-half stabiel, geen dominante guard&gt;60% → PROMOTE_CANDIDATE

---

# QUANTRESEARCH DOSSIER (per experiment)

```text
quantresearch/experiments/EXP-BB-MECH-001/
├── EXPERIMENT_DOSSIER.md
├── hypothesis.md
├── config_snapshot.yaml
├── metrics_summary.json
├── permutation_results.json
├── attribution_table.json
├── split_half_results.json
└── decision.md          ← verplicht vóór volgende fase
```

**`decision.md` template:**

```md
# Decision — EXP-BB-MECH-001

Date:
Verdict: REJECT | INSUFFICIENT | VALIDATION_REQUIRED | PROMOTE_CANDIDATE

Primary result:
Sample size:
Permutation p-value:
Expectancy_R:
Profit factor:
MFE/MAE:
Clustering rate:

Decision rationale:

Next allowed action:
```

---

# UITVOERVOLGORDE (master checklist)

```text
[x] 0.1 Bollinger indicator + tests
[x] 0.2 MACD indicator + tests
[x] 0.3 Signal independence + tests
[ ] 0.4 QuantLog payload extension + contract tests
[ ] 0.5 QuantResearch permutation utility + tests

[ ] 1.0 bb_only strategy
[ ] 1.1 EXP-BB-MECH-001 config
[ ] 1.2 Run BB isolation
[ ] 1.3 Analyze BB isolation
[ ] 1.4 Write decision.md

[ ] 2.0 macd_only strategy          ← ALTIJD, ook na BB fail
[ ] 2.1 EXP-MACD-MECH-001 config
[ ] 2.2 Run MACD isolation
[ ] 2.3 Analyze MACD isolation
[ ] 2.4 Write decision.md

[ ] 3.0 bb_macd_joint strategy
[ ] 3.1 EXP-JOINT-001 config
[ ] 3.2 Run joint experiment
[ ] 3.3 Matched comparison + synergy test
[ ] 3.4 Exit confound check
[ ] 3.5 Write decision.md

[ ] 4.0 Only if promoted: variant matrix
```

---

# CURSOR MAG NIET

- Parameters aanpassen na resultaten  
- Guards toevoegen om performance mooier te maken  
- Twee variabelen tegelijk wijzigen in één variant  
- H0-test overslaan  
- N&lt;100 gebruiken voor harde conclusies  
- Positieve expectancy claimen zonder permutation test  
- Shadow exits uitvoeren alsof het echte orders zijn  
- Zonder `decision.md` doorgaan naar volgende fase  
- Permutation utility in `quantbuild` plaatsen  

---

## Voortgang log

| Datum | Fase | Notitie |
|-------|------|---------|
| 2026-05-17 | — | Werkplan aangemaakt; repo committed + pushed (`04769b2`) |
| 2026-05-17 | 0.1 | Bollinger indicator + 5 tests groen |
| 2026-05-17 | 0.2 | MACD indicator + 7 tests groen |
| 2026-05-17 | 0.3 | Signal independence filter + 5 tests groen |

---

## Volgende stap (samen)

**Start Fase 0.1:** schrijf `test_bollinger.py` met synthetische close-series, daarna `bollinger.py` tot tests groen zijn.
