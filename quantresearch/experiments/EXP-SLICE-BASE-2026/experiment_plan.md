# Plan — EXP-SLICE-BASE-2026

1. Ensure artifacts exist:  
   `quantmetrics_os/runs/EXP-SQE-XAUUSD-DECON-2026-{BASE,V3,V4}/single/quantlog_events.jsonl`

2. From suite root:

```bash
python quantresearch/scripts/slice_exp_slice_base_2026.py --suite-root .
```

3. Outputs: `SLICE_REPORT.md`, `slice_metrics.json` in this folder.
