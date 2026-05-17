# Frequentie-verhoging voor FTMO — Plan

## Status: **SUSPENDED** (2026-05)

Dit document beschrijft oorspronkelijk een route om het FTMO **tempo** (trades binnen 30 dagen) op te schalen. Die route is **volledig doorlopen** met de **huidige QuantBuild `run_backtest`-engine** en de **SQE XAUUSD-stack**. De conclusie is **consistent**: met deze engine en signaallogica is de **FTMO-challenge op het vereiste tempo niet haalbaar** via frequentie-opschaling, multi-instrument expansion, exit-aanpassingen of NAS100 als throughput-anker.

**Suspend betekent:** geen verdere uitvoering van het frequentieplan in deze vorm tot een **fundamenteel andere entry-laag** (Pad B) of een **expliciet andere challenge-strategie** (extern programma, ander kapitaalpad — Pad A) is gekozen.

---

## Onderbouwing — experimentketen (canonical engine)

| Experiment | Vraag | Uitkomst |
|------------|-------|----------|
| EXP-SLICE-BASE-2026 / BASE | Risk / equity | BASE **REJECT** FTMO als enkelvoudige stack; kill switch correct |
| EXP-SQE-XAUUSD-DECON / V4 | Trend-only, volledig venster | Trend **REJECT**: PF ~0.95, net negatief |
| EXP-TREND-EXIT-ADAPT-2026 | Trend + 1R TP | **REJECT**: hogere WR, lagere PF; entry-probleem, geen exit-fix |
| EXP-SQE-XAUUSD-EXPANSION-FIRST-DEFAULT | XAUUSD expansion-only | **VALIDATED**: ~38 trades/venster, WR ~60.5%, PF ~3.07 |
| EXP-EXPANSION-MULTI-INSTRUMENT-2026 | USDJPY / GBPUSD expansion | **REJECT** (USDJPY onder rubric; GBPUSD WR 0%) |
| EXP-NAS100-TREND-VERIFY-2026 | NAS100 trend-only reproduceert profiles | **REJECT**: geen match met profile-cijfers; zie instrument_profiles-verificatie |

**Enige component met robuuste edge in deze keten:** **XAUUSD expansion** (~38 trades op het gebruikte rolling venster; ~3 trades/maand — ruim onder wat nodig is om **10% in 30 dagen** puur uit expectancy × frequentie te halen bij 1% risico).

---

## Rekenkader (waarom FTMO-tempo faalt)

Order-of-magnitude (research-notitie, geen garantie):

- ~38 trades/jaar expansion × ~0.82R gemiddelde winst in R-eenheden × 1% risico per trade → **~2.6% verwacht maandelijks** als grove schatting — versus **10% challenge-target in 30 dagen**.

Multi-instrument expansion **lost dit niet op** (stap 2 gefaald). Trend-exit-varianten **lossen het niet op** (trend blijft negatief). NAS100 als tweede pijler **valt weg** (verify-run inconsistent met profile-getallen — zie `instrument_profiles.yaml`).

---

## Strategische keuze (niet technisch — wel vastleggen)

**Pad A — Huidige engine als funded-engine, niet als challenge-engine**

- Bouw rond **alleen de gevalideerde edge**: XAUUSD expansion.
- Accepteer **lage frequentie**; funded-rendement kan verdedigbaar zijn op langere horizon, maar **FTMO 10%/30d** vereist een **ander challenge-pad** (andere broker/prop structuur, kleiner account, of niet-prop).

**Pad B — Fundamentele herbouw trend / nieuwe entry-laag**

- Geen parameter-tweak van SQE-modules: **nieuw entry-model** voor trend (of nieuw regime‑gedrag), expliciet gekoppeld aan MAE/MFE‑realiteit.
- Tijdshorizon: **maanden**, geen enkel experiment.

**Je kunt niet beide tegelijk als primaire focus** zonder scope‑verlies; kies expliciet welk pad leidend is.

---

## Wat niet meer als actief plan geldt

- **Core(3) frequentie-route** als route naar FTMO-tempo — **afgesloten** zolang verify‑runs FX/NAS op deze stack negatief blijven.
- **NAS100** als gevalideerde throughput‑laag op basis van **oude profile‑totalen** — **tot engine‑reproductie** niet opnieuw als feit gebruiken.
- **Automatische promotie** van cijfers in `instrument_profiles.yaml` zonder `run_backtest`‑verificatie — zie profile‑bestand.

---

## Historische secties (archief)

Eerdere versies van dit document verwezen naar Core(3), accelerator en EURUSD MR als oplossingsrichtingen. Die blijven **code‑aanwezig**, maar de **frequentie‑route naar FTMO** is op basis van bovenstaande keten **gesuspendeerd**. Zie git‑geschiedenis voor de vorige tekst.

Diagnose data/truncatie (BASE): [`experiments/EXP-SLICE-BASE-2026/DIAGNOSIS_DATA_INTEGRITY.md`](../experiments/EXP-SLICE-BASE-2026/DIAGNOSIS_DATA_INTEGRITY.md).

---

**Samenvatting:** Het frequentieplan is **SUSPENDED**. De enige duurzaam gevalideerde SQE‑component in deze keten is **XAUUSD expansion**; dat volstaat niet voor het **challenge‑tempo** zoals hier bedoeld. Volgende stap is een **strategische keuze** (Pad A vs Pad B), niet een verdere frequentie‑iteratie op dezelfde kernel.
