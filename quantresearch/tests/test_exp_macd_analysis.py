from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


def _load_analysis_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "analyze_exp_macd_mech_001.py"
    spec = importlib.util.spec_from_file_location("analyze_exp_macd_mech_001", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_directional_permutation_observed_matches_t8_forward_returns() -> None:
    mod = _load_analysis_module()
    n = 12
    dates = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")
    close = np.full(n, 100.0)
    close[8] = 104.0
    close[9] = 90.0
    data = pd.DataFrame(
        {"open": close, "high": close + 0.1, "low": close - 0.1, "close": close},
        index=dates,
    )
    atr = pd.Series([1.0] * n, index=dates)
    entries = [
        {"bar_index": 0, "direction": "LONG"},
        {"bar_index": 1, "direction": "SHORT"},
        {"bar_index": 5, "direction": "LONG"},
    ]

    result = mod._directional_t8_permutation_test(data, atr, entries, n_permutations=10, seed=7)

    expected = np.mean(
        [
            mod._forward_return_r(data, atr, 0, "LONG", 8),
            mod._forward_return_r(data, atr, 1, "SHORT", 8),
        ]
    )
    assert result["observed_hit_rate"] == expected
    assert result["n_signals"] == 2
