# EXP-SQE-XAUUSD-DECON-2026 — Run Analyse (verdict)

## Directe bevindingen per variant

| Variant | n | Net R | WR | PF | Status |
|--------|---|-------|----|----|--------|
| BASE | 42 | +9.28R | 38% | 1.23 | VALIDATION_REQUIRED |
| V1 — H1 off | 40 | +41.49R | 47.5% | 1.81 | Signaal aanwezig, n onvoldoende |
| V2 — combo=3 | 0 | — | — | — | **REJECT** |
| V3 — expansion only | 38 | sterk (o.a. +369.33R engine) | 60.5% | 3.07 | VALIDATION_REQUIRED (kleine n) |
| V4 — trend only | 34 | negatief (−9.18R) | 35.3% | 1.09 | VALIDATION_REQUIRED / REJECT-kandidaat |
| V5 — lookback 3 | 54 | +51.32R | 37% | 1.18 | VALIDATION_REQUIRED |

---

## Wat de data nu zegt

**V2 is definitief dood.**  
`combo=3` levert 0 fills over 5 jaar XAUUSD. Dit is geen edge-verlies — het is een signaal dat de drie modules zelden simultaan actief zijn binnen dezelfde bar. De 2-van-3 drempel is niet "laks" — het is de enige drempel waarbij het systeem überhaupt vuurt. Conclusie: de modules zijn los van elkaar zwak gecorreleerd in tijd. Dat is zelf al een bevinding over de signaalstructuur.

**V1 (H1 off) outperformt BASE op net R én WR.**  
V1: 40 trades, +41.49R, 47.5% WR.  
BASE: 42 trades, +9.28R, 38% WR.

Dit is het gevaarlijkste resultaat in de hele matrix. Drie mogelijke verklaringen, in volgorde van waarschijnlijkheid:

1. **Guard dominance:** de H1-gate blokkeert systematisch betere setups dan het doorlaat. De gate filtert op richting, maar niet op entry-kwaliteit.
2. **Omgekeerd effect:** H1-structuur is een lagging indicator op 15m-timeframe — het gate-mechanisme is te traag en verwerpt entries die al in de juiste richting bewegen.
3. **Kleine sample noise:** 40 vs 42 trades is statistisch ononderscheidbaar. Het verschil in net R (+41 vs +9) bij vergelijkbare n duidt op een paar extreme uitschieters in V1, niet per se op structureel verschil.

**Conclusie over V1:** de H1-gate verdient een separaat experiment, maar dit resultaat is nog geen bewijs dat de gate schadelijk is. Het is een **hypothese** geworden.

**V3 (expansion only) is de meest intrigerende variant — en de gevaarlijkste.**  
38 trades, WR 60.5%, PF 3.07. Dit bevestigt de secundaire hypothese: expansion-regime heeft andere distributionele eigenschappen dan trend.

Maar 38 trades over 5 jaar is 7–8 trades per jaar. Dat is geen statistisch sample — dat is een anekdote met mooie cijfers. WR 60.5% op n=38 heeft een 95%-interval van ruwweg 44%–75%. De PF van 3.07 kan volledig gedreven zijn door 3–4 grote winnaars.

**V4 (trend only) is negatief in net R.**  
Dit is consistent met de V3-bevinding, maar omgekeerd. Als expansion het enige positieve regime is, dan draait de SQE-kernel in trend-regime structureel met negatieve verwachting. Dat is een fundamentele claim over de strategie.

Alternatieve verklaring: trend-trades hebben langere houdtijden en een trail-exit die in dit backtest-window systematisch slechter uitpakt dan de fixed 2R in expansion. Het is **exit-gedrag**, niet per se signaalgedrag.

**V5 (lookback=3) produceert meer trades én hogere net R dan BASE.**  
54 trades (vs 42) met +51.32R (vs +9.28R), maar WR vrijwel gelijk (37% vs 38%). Hogere net R bij vergelijkbare WR betekent dat de extra entries gemiddeld grotere winnaars pakten, of minder grote verliezers. PF 1.18 (vs 1.23 BASE) — bevestiging blijft afhankelijk van distributie-analyse.

---

## Nieuwe hypothesen (vervolg)

**H2**  
> De H1-structuurgate elimineert asymmetrisch meer winstgevende dan verliezende entries. Zichtbaar in: WR-verschil H1-on vs H1-off per entry-type, en in MAE/MFE-distributies.

**H3**  
> SQE-signalen in EXPANSION-regime hebben een hogere base rate (WR > 50%) dan in TREND-regime (WR < 40%). Het combinatiesysteem draait primair op expansion-edge, niet op “drie-pijler”-edge in abstracte zin.

**H4**  
> De trail-exit in TREND-regime is de primaire driver van negatieve net R in V4, niet de entry-kwaliteit. Zichtbaar in: exit-typeverdeling (timeout vs TP vs SL) voor trend-trades.

---

## Verplichte volgende stap — exacte prioritering

**Prioriteit 1 — Jaar / sessie / regime slice-analyse op BASE en V3**  
Niet optioneel. Zonder dit weet je niet of de 38 expansion-trades geconcentreerd zijn in één volatiel jaar of verspreid over 5 jaar.

Gewenste output:

- BASE: WR/PF per jaar (2021–2025)  
- BASE: WR/PF per sessie (London / NY / Overlap)  
- V3: WR/PF per jaar (kritisch — is expansion-edge tijdgebonden?)  
- V4: exit-typeverdeling per trade (TP / SL / timeout)  

**Prioriteit 2 — V1 guard-attributie**  
Event-logs: welke trades worden door de H1-gate geblokkeerd, en wat was hun MAE/MFE? QuantLog-query, geen nieuwe backtest.

**Prioriteit 3 — Aparts exit-experiment voor V4**  
V4 (trend only) met **fixed 2R** exit i.p.v. trail. Als negatieve net R verdwijnt, wijst dat op trail-exit als drijver, niet per se op entry-logica.

---

## Wat je niet mag doen op basis van deze run

- V3 promoveren naar productie — n=38 is geen productie-sample  
- H1-gate uitzetten als "bewezen schadelijk" — V1 is 40 trades met onbekende outlier-structuur  
- Concluderen dat expansion-regime de "echte" edge is — minimaal 100 expansion-trades in isolatie, meerdere jaren  
- V5 (lookback=3) als gevalideerde verbetering behandelen — hogere net R zonder WR-verbetering is outlier-gevoelig  

---

## Formeel verdict

**VALIDATION_REQUIRED** — voor alle varianten met trades (V2: **REJECT**).

De matrix heeft twee dingen bereikt: V2 is geëlimineerd, en er zijn drie testbare hypothesen (H2, H3, H4). Dat is de correcte uitkomst van een eerste deconstructie-run.

**Volgende fase:** geen nieuwe parameter-variantenmatrix totdat slice-analyse op bestaande artifacts en (waar nodig) één gerichte V4 exit-run zijn afgerond. Meer varianten zonder meer robuuste data per conclusie lost niets op.

---

## Gerelateerd: challenge-tempo / frequentie (na slices)

XAUUSD-isolatie vs portfolio-Frequentie en FTMO (Core(3), accelerator, EURUSD MR):  
[`../../docs/FTMO_FREQUENCY_PLAN_2026.md`](../../docs/FTMO_FREQUENCY_PLAN_2026.md)
