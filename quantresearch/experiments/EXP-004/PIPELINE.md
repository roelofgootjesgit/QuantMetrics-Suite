# EXP-004 — Reproduce / extend

All commands assume `cd` into `quantbuild/` and:

```powershell
$env:PYTHONPATH="<repo>/quantbuild/src"
```

## Outputs naming convention

| Step | Example output |
|------|----------------|
| Sweeps | `sweeps_2024.jsonl`, `sweeps_2024_bias.jsonl` |
| Outcomes | `sweep_outcomes_2024.jsonl` |
| Subset stats | run `sweep_outcome_subset_stats.py` (default paths to 2023–2025 outcomes) |

## Core code

- `src/quantbuild/research/sweep_m5_xauusd.py` — detection + optional `htf_bias_filter`
- `scripts/sweep_detector.py` — CLI
- `scripts/sweep_outcome_sim.py` — post-process ENTER → SL/TP/timeout
- `scripts/sweep_outcome_subset_stats.py` — depth-bucket aggregate on outcome JSONL files

## QuantResearch

- Frozen numbers: `experiments/EXP-004/results_manifest.json`
- Narrative: `experiments/EXP-004/VERDICT.md`
- Tests: `tests/test_exp004_sweep_m5_manifest.py`
- Loader: `quantresearch/sweep_m5_research_manifest.py`
