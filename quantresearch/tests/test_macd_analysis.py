from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
for rel in ("quantbuild", "quantbuild/src", "quantresearch"):
    candidate = ROOT / rel
    if candidate.is_dir():
        sys.path.insert(0, str(candidate))

SCRIPT_PATH = ROOT / "quantresearch" / "scripts" / "analyze_exp_macd_mech_001.py"
SPEC = importlib.util.spec_from_file_location("analyze_exp_macd_mech_001", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


def test_directional_permutation_inputs_use_signal_direction_and_skip_invalid():
    dates = pd.date_range("2024-01-01", periods=12, freq="15min", tz="UTC")
    close = np.arange(10.0, 22.0)
    data = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.1,
            "low": close - 0.1,
            "close": close,
        },
        index=dates,
    )
    atr = pd.Series(np.ones(len(data)), index=data.index)
    entries = [
        {"bar_index": 0, "direction": "SHORT"},
        {"bar_index": 1, "direction": "LONG"},
        {"bar_index": 10, "direction": "LONG"},
    ]

    outcomes, signal_indices = analysis._directional_permutation_inputs(
        data, atr, entries, horizon=2
    )

    assert len(signal_indices) == 2
    assert np.allclose(outcomes[signal_indices], [-1.0, 1.0])


def test_find_latest_run_jsonl_skips_other_experiments(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    macd_run = runs / "older_macd.jsonl"
    other_run = runs / "newer_other.jsonl"
    macd_run.write_text(
        json.dumps({"event_type": "trade_closed", "strategy_id": "EXP-MACD-MECH-001"}) + "\n",
        encoding="utf-8",
    )
    other_run.write_text(
        json.dumps({"event_type": "trade_closed", "strategy_id": "EXP-BB-MECH-001"}) + "\n",
        encoding="utf-8",
    )
    os.utime(macd_run, (100.0, 100.0))
    os.utime(other_run, (200.0, 200.0))

    assert analysis._find_latest_run_jsonl(tmp_path, "EXP-MACD-MECH-001") == macd_run
