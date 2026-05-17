# XAUUSD M5 PDH/PDL sweep research (EXP-004)

Offline research line: **detector → JSONL → outcome simulator → slice stats**, implemented under `quantbuild/` (see `quantbuild/scripts/`).

**Ledger:** `experiments/EXP-004/` in this repo.

| Artifact | Purpose |
|----------|---------|
| `VERDICT.md` | Human verdict + herrun tables |
| `HERRUN_PROTOCOL.md` | Aligned multi-year protocol (2015/2019/2022/2024) |
| `results_manifest.json` | Frozen metrics (`pytest` guards drift) |
| `PIPELINE.md` | Command cheat sheet |

**Scripts (quantbuild):** `sweep_funnel_stats.py`, `sweep_forward_return_h2.py`, `sweep_alignment_audit.py`

**Registry:** `EXP-004` in `registry/experiments.json`; **rejected hypothesis** `REJ-006` in `registry/rejected_hypotheses.json`.

Python loader: `quantresearch.sweep_m5_research_manifest.load_results_manifest()`.

Index: regenerate `docs/RESEARCH_INDEX.md` after registry edits:

```python
from quantresearch.markdown_renderer import write_research_index
write_research_index()
```
