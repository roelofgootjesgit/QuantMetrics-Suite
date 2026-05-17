# EXP-MAE-MFE-REGIME-2026 — resultaten (bestaande JSONL)

Gegenereerd met `python quantresearch/scripts/mae_mfe_regime_from_quantlog.py <path>`.

**Belangrijkste vergelijking (post-entry, vaste 2R/1R sim):**

| Bron | Regime / venster | n | MFE_R p50 | share MFE_R ≥ 1 |
|------|------------------|---|-----------|-----------------|
| V3 | expansion, volledig venster | 38 | **2.067** | **68.4%** |
| V4 | trend, volledig venster | 137 | 0.726 | 45.3% |
| BASE | trend, kill-switch venster | 34 | 0.581 | 44.1% |
| BASE | expansion | 8 | 1.373 | 50.0% |

**Interpretatie (hypothese, niet bewijs van causaliteit):** In expansion is de verdeling van gunstige excursion duidelijk rechtser/hoger (hogere median MFE, groter aandeel trades dat minstens 1R gunstige beweging ziet) dan in trend over het lange venster. Winnaars in beide regimes hebben vergelijkbare gemiddelde MFE_R (~2.5R) — het verschil zit in de **verliezers** en in hoe vaak de prijs **ooit** 1R+ gunstig beweegt vóór de uiteindelijke exit.

Zie `QUANTLOG_FIELDS_MAE_MFE.md` voor velddefinities.

---

## Ruwe command-output (archief)

### BASE

```
### expansion (n=8)
  MAE_R: n=8  mean=0.988  p50=0.902  p90=1.617
  MFE_R: n=8  mean=1.358  p50=1.373  p90=2.666
  share with MFE_R >= 1: 50.0%

### trend (n=34)
  MAE_R: n=34  mean=1.037  p50=1.110  p90=1.878
  MFE_R: n=34  mean=1.196  p50=0.581  p90=2.700
  share with MFE_R >= 1: 44.1%
```

### V3 (expansion-only)

```
### expansion (n=38)
  MAE_R: n=38  mean=0.850  p50=0.764  p90=1.780
  MFE_R: n=38  mean=1.774  p50=2.067  p90=2.696
  share with MFE_R >= 1: 68.4%
```

### V4 (trend-only, full window)

```
### trend (n=137)
  MAE_R: n=137  mean=1.134  p50=1.177  p90=1.824
  MFE_R: n=137  mean=1.159  p50=0.726  p90=2.553
  share with MFE_R >= 1: 45.3%
```
