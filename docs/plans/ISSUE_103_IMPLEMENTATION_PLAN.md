# Issue #103 — Strict `delete_allowed` boolean parse (IMPLEMENTATION PLAN)

**Issue:** https://github.com/roelofgootjesgit/QuantMetrics-Suite/issues/103  
**Branch:** `cursor/issue-103-delete-allowed-plan-3716`  
**Base:** `main` @ `b89d50f22e45649daf6dfa648f9120de98b40fad` (post #106 merge)  
**Mode:** **PLAN ONLY** — no production code in this PR  
**Tech-lead brief:** issue comment `6929411001`  
**Source:** Claude independent review PROP-00 PR #102 (finding **F1**)  
**Stop line:** **READY FOR CLAUDE PLAN REVIEW #103**

---

## 1. Doel en scope

### Doel

Zorg dat lifecycle-status `delete_allowed` **uitsluitend** de JSON boolean `true` accepteert (`is True`). Elke andere waarde (string `"false"`/`"no"`, getallen, `null`, ontbrekende key, ongeldige/non-dict JSON) moet **veilig ontkennen**. Dit is een **blocking prerequisite** vóór elke toekomstige delete/compress-implementatie.

### In scope (na plan-approval, implementatie-PR)

| Item | Toelichting |
|---|---|
| Parse-fix in scanner | Vervang `bool(...)` door strikte identity-check |
| Root CI tests | Parametrized negatives + missing/invalid JSON + mutation proof |
| Bewijs dat V0 niets verwijdert | Assert geen filesystem delete in scan-pad |

### Expliciet out of scope

| Item | Reden |
|---|---|
| Delete / compress / archive / `--apply-policy` features | Issue + brief verbieden; docs noemen toekomstige CLI’s maar V0 heeft ze niet |
| Wijzigen van live-execution gates (#104) | Orthogonaal; niet raken |
| Broker / credentials / paper/live / VPS | AGENTS.md hard bans |
| PIT Gate A openen / productie-allowlist vullen | Blijft BLOCKED / leeg |
| Herschrijven van `DATA_LIFECYCLE_SYSTEM.md` future CLI surface | Optioneel docs-note alleen als nodig voor consistentie |
| Nested quantmetrics_os package refactor | Minimale fix preferred |

---

## 2. Huidige situatie

### 2.1 Bron van de bug

`quantmetrics_os/scripts/data_lifecycle.py` regel ~111:

```python
delete_allowed = bool(status_payload.get("delete_allowed", False))
```

Python `bool("false")` / `bool("no")` / `bool("true")` / `bool(1)` → **`True`**. Alleen de lege string en `0`/`False`/`None` worden falsy.

### 2.2 Call graph (inventaris)

| Locatie | Rol |
|---|---|
| `_safe_read_json` | Laadt `status.json`; bij OS/JSON-fout of non-dict → `None` |
| `_scan_runs` | Enige productie-parse van `delete_allowed` |
| `RunScan.delete_allowed` | Dataclass-veld in rapport/tabel |
| `_markdown_report` / `_print_table` / `main` report JSON | Rapporteert de bool; **geen delete** |
| `tests/test_suite_boundaries.py` | Fixture zonder `status.json` → assert `delete_allowed is False` |
| `quantmetrics_os/reports/data_lifecycle_report.*` | Gegenereerde artifacts (geen parse-logica) |
| `quantmetrics_os/docs/DATA_LIFECYCLE_SYSTEM.md` | Specificeert voorbeeld `"delete_allowed": false` (JSON boolean) |

**Geen andere Python-call sites** zetten of lezen `delete_allowed` buiten deze scanner/rapportage.

### 2.3 V0 gedrag (veilig maar misleidend veld)

Module docstring en `main()`: **geen** deletion/compression/mutation van run-folders. `main()` schrijft alleen reports onder `quantmetrics_os/reports/`. Het veld is dus vandaag report-only, maar een toekomstige delete-feature die `bool(...)` hergebruikt zou **fail-open** zijn op string `"false"`.

### 2.4 Bestaande tests

| Test | Dekking t.o.v. #103 |
|---|---|
| `tests/test_suite_boundaries.py::test_quantmetrics_os_finds_run_artifacts` | Missing `status.json` → `delete_allowed is False` |
| *(geen)* | JSON `true`/`false`, strings, numbers, null, invalid JSON, non-dict, mutation |

Lokale baseline (design-host): `pytest tests/test_suite_boundaries.py -q` → **2 passed**.

### 2.5 Documentatie / governance

- **AGENTS.md:** high-impact includes CI/security and data integrity; fail-closed preferred; no secrets/live.
- **MASTER.md:** niet aanwezig als rootbestand; bronmaster staat onder `docs/source/QUANTMETRICS_ALPHA_ENGINE_MASTER_V1_FULL.md` (niet gewijzigd in deze taak).
- **PROP_ROADMAP.md:** F1 / #103 expliciet als prerequisite vóór lifecycle deletion.
- **#104:** live-execution fail-closed gates; **geen gedeelde code** met `delete_allowed`. Wel dezelfde ontwerpnorm: default-deny, geen truthy-string-coercie, tests + mutation in root CI.

### 2.6 Demonstratie van het defect (repro)

| Input | `bool(x)` | `x is True` (gewenst) |
|---|---|---|
| `true` (JSON bool) | True | True |
| `false` (JSON bool) | False | False |
| `"false"` | **True** ← bug | False |
| `"no"` | **True** ← bug | False |
| `1` | **True** ← bug | False |
| `null` / missing | False | False |

---

## 3. Voorgestelde wijzigingen per bestand

### 3.1 `quantmetrics_os/scripts/data_lifecycle.py` (implementatie-PR)

1. Voeg een kleine helper toe, bijv.:

```python
def _delete_allowed_strict(status_payload: dict[str, Any] | None) -> bool:
    """Only literal JSON boolean true enables deletion permission."""
    if not isinstance(status_payload, dict):
        return False
    return status_payload.get("delete_allowed") is True
```

2. In `_scan_runs`:
   - missing/invalid path (`status_payload is None`): blijft `delete_allowed = False`
   - else: `delete_allowed = _delete_allowed_strict(status_payload)`

3. **Geen** nieuwe CLI flags, geen delete-paden, geen wijziging aan report-schrijflocaties behalve correcte bool-waarden.

### 3.2 `tests/test_data_lifecycle_delete_allowed.py` (nieuw, root CI)

Parametrized / focused cases (issue + brief):

| Case | `status.json` body / conditie | Expect `delete_allowed` |
|---|---|---|
| JSON true | `{"status":"scratch","delete_allowed": true}` | `True` |
| JSON false | `{"delete_allowed": false}` | `False` |
| string false | `{"delete_allowed": "false"}` | `False` |
| string no | `{"delete_allowed": "no"}` | `False` |
| int 1 | `{"delete_allowed": 1}` | `False` |
| null | `{"delete_allowed": null}` | `False` |
| missing key | `{"status":"scratch"}` | `False` |
| invalid JSON | raw `{not-json` | `False` (via `_safe_read_json` → None path) |
| non-dict JSON | raw `[1,2,3]` | `False` |

Aanvullend:

- **Geen filesystem deletion:** monkeypatch/`unlink`/`rmtree` counters of tempfile inventory before/after `_scan_runs` — run tree unchanged.
- Behoud/regressie: bestaande `test_suite_boundaries` blijft groen (niet uitschakelen).

### 3.3 Mutation proof (scratch copy)

Tech-lead eis: scratch-copy van `data_lifecycle.py` waarin `_delete_allowed_strict` / `is True` teruggezet wordt naar `bool(...)`; de string-`"false"` test moet dan **falen** (mutant **KILLED**). Implementatie bij voorkeur als root test onder `tests/` (subprocess of temp-module), zelfde patroon als #104/#106 mutation tests.

### 3.4 CI / workflow

Geen aparte workflow-stap nodig: nieuwe tests vallen onder bestaande `pytest tests -q`. **Geen** `continue-on-error`, skip, xfail.

### 3.5 Docs (optioneel, minimaal)

Alleen indien nodig voor duidelijkheid: één zin in plan evidence of comment bij helper dat toekomstige delete-features **deze** helper moeten hergebruiken. Geen uitbreiding van toekomstige CLI’s in deze PR.

---

## 4. Veiligheidsanalyse

| Vraag | Analyse |
|---|---|
| Beïnvloedt #104 live gates? | **Nee** — geen shared modules met `live_execution_gate` / preflight. |
| Kan dit delete activeren? | **Nee in V0** — geen delete-codepad. Fix voorkomt fail-open **als** delete later `delete_allowed` hergebruikt. |
| Data-consistentie reports? | Reports kunnen `false` tonen waar `bool("false")` eerder `true` toonde → **correctie**, geen datavernietiging. |
| Secrets / brokers / allowlist? | Onberoerd. Productie-allowlist blijft leeg; Gate A BLOCKED. |
| Fail-closed alignement | `is True` is strikter dan truthy-coercie; matches #104 “no truthy auth coercion” spirit. |
| `_safe_read_json` non-dict/invalid | Al deny via `status_payload is None` → `delete_allowed=False`; tests moeten dit expliciet dekken. |

**Risico van te strikt parse:** legitieme producers die per ongeluk string `"true"` schreven zouden na fix `False` krijgen. Dat is **gewenst** fail-closed; producers moeten JSON boolean schrijven (docs-voorbeeld doet dat al).

---

## 5. Teststrategie

1. **Unit / parametrized** op `_delete_allowed_strict` of via `_scan_runs` tempfile fixtures (voorkeur: beide — helper unit + scan integration).
2. **Negatives:** alle issue-genoemde non-true waarden → `False`.
3. **Positive:** alleen literal `True`.
4. **Invalid / non-dict JSON file content** → treat as missing/unknown, `delete_allowed is False`.
5. **Regressie:** `tests/test_suite_boundaries.py` ongewijzigd laten slagen.
6. **No-delete invariant:** na scan bestaan alle fixture-bestanden nog; geen `shutil.rmtree`/`Path.unlink` calls (mock of filesystem diff).
7. **Mutation:** restore `bool(...)` in scratch → string-`"false"` case moet AssertionError geven.
8. **Root CI:** `pytest tests -q` (+ bestaande #104/#106 suites blijven groen; niet verzwakken).
9. **Demo:** `python run_demo.py` ongewijzigd verwachten (`VALIDATION_REQUIRED`).

Geen broker/live/smoke; geen network nodig.

---

## 6. Acceptatiecriteria (implementatie-PR)

- [ ] `delete_allowed` is `True` **iff** `status_payload.get("delete_allowed") is True`
- [ ] Parametrized tests dekken: `true`, `false`, `"false"`, `"no"`, `1`, `null`, missing, invalid JSON, non-dict JSON
- [ ] Mutation proof: `bool(...)` mutant wordt KILLED door `"false"` case
- [ ] Geen filesystem deletion/compressie in tests of codepad
- [ ] Geen bestaande tests disabled / xfail / soft-fail
- [ ] Root CI groen op exacte head SHA; draft PR; SHA-bound independent Claude CODE review; owner merge approval
- [ ] Geen live trading, credentials, VPS, Gate A open, allowlist non-empty

---

## 7. Risico’s en open vragen

| ID | Item | Voorstel |
|---|---|---|
| R1 | Report JSON in-repo kan verouderde waarden tonen tot opnieuw gescand | Geen verplicht herschrijven in #103; optioneel regenereer alleen als owner vraagt |
| R2 | Toekomstige delete-code zou helper kunnen omzeilen | Acceptatie: helper is single choke point; toekomstige feature-PR moet helper hergebruiken + mutation |
| R3 | String `"true"` wordt False | Intentioneel; documenteer in test docstring |
| Q1 | Helper publiek exporteren vs module-private `_` | Plan: private `_delete_allowed_strict` in zelfde module (minimaal) |
| Q2 | Apart issue voor delete-feature? | Ja — #103 is parse-only prerequisite; geen delete in dezelfde PR |

---

## 8. Concrete implementatiestappen (na PLAN APPROVE)

1. Op **deze** branch (of voortzetting ervan): helper + vervang `bool(...)` in `_scan_runs`.
2. Voeg `tests/test_data_lifecycle_delete_allowed.py` toe (param + no-delete + mutation).
3. Draai lokaal: boundaries, nieuwe suite, `pytest tests -q`, #104 suites, demo.
4. Push; bevestig GitHub CI; update evidence MD met SHA + CI URLs.
5. Draft PR body → **READY FOR CLAUDE CODE REVIEW #103**.
6. Max 2 repair rounds; geen merge zonder Claude + owner.

---

## 9. Design-phase deliverables (deze PR)

| Item | Status |
|---|---|
| Featurebranch vanaf actuele `main` | Done |
| Inventaris `delete_allowed` + tests + docs | Done |
| Ontwerpdocument | Dit bestand |
| Productiecode / CI wiring | **Geen** |
| Draft PR (docs-only) | Te openen |
| Stop | **READY FOR CLAUDE PLAN REVIEW #103** |

---

## 10. Relatie tot #104 (veiligheidsafspraken)

- #104 dwingt fail-closed **live execution** (SESSION/ORDERS, geen truthy auth).
- #103 dwingt fail-closed **lifecycle permission flag** (geen truthy `delete_allowed`).
- Geen code-overlap; wel dezelfde engineering-norm: explicit boolean, negatives + mutation, root CI, geen soft-fail.
- Deze plan-PR raakt **geen** gate keys, brokers, of allowlists.
