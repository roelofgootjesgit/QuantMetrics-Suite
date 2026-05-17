# Regime-attributie (BASE) en V3 jaarverdeling

**Bron:** `quantresearch/scripts/regime_attribution_from_quantlog.py` op `trade_closed` in de JSONL’s. `payload.regime` en `payload.pnl_r` per trade; geen join op `trace_id` nodig.

**BASE:** `quantmetrics_os/runs/EXP-SQE-XAUUSD-DECON-2026-BASE/single/quantlog_events.jsonl`  
**V3:** `quantmetrics_os/runs/EXP-SQE-XAUUSD-DECON-2026-V3/single/quantlog_events.jsonl`

---

## Stap 1 — BASE (42 `trade_closed`)

| Regime     | n  | net R (Σ pnl_r) | W/L   | WR    | PF   |
|------------|-----|-----------------|-------|-------|------|
| expansion  | 8   | +4.00           | 4/4   | 50.0% | 2.00 |
| trend      | 34  | +2.00           | 12/22 | 35.3% | 1.09 |
| **totaal** | 42  | **+6.00**       | —     | —     | —    |

**Conclusie t.o.v. Verklaring 1:** BASE is hier **niet** een masker waarbij alleen expansion winst draagt en trend verlies compenseert. In deze 42 trades zijn **trend en expansion beide netto positief**; expansion draagt proportioneel zwaarder (8 vs 34 trades), maar trend blijft **+2R** met WR ~35% en PF > 1.

**Let op:** Som van `pnl_r` in deze run is **+6R**, niet +9.28R. Als elders +9.28R staat, komt dat waarschijnlijk van een andere metriek (bijv. USD/`net_pnl`) of een andere run — voor apples-to-apples altijd dezelfde bron gebruiken.

---

## Stap 2 — V3 (expansion-only, 38 trades) — net R per kalenderjaar (exit-timestamp)

| Jaar | n | net R (Σ pnl_r) |
|------|---|-----------------|
| 2021 | 9 | +3 |
| 2022 | 4 | +5 |
| 2023 | 8 | +4 |
| 2024 | 4 | +5 |
| 2025 | 5 | +10 |
| 2026 | 8 | +4 |

**Conclusie:** De edge zit **niet** geconcentreerd in één jaar (bijv. 2022 alleen). Er zijn meerdere jaren met positieve bijdrage; 2025 valt qua net R relatief hoog uit bij kleine n.

---

## Brug naar V4 (trend full window)

BASE-trend in het kill-switch venster is licht positief (+2R op 34 trades), terwijl V4 trend-only over het volledige venster negatief uitkomt. Dat onderstreept **sample / periode / configuratie** als verklaring naast regime-mix — niet “BASE maskeert een altijd-verlies trend” binnen die 42 trades.
