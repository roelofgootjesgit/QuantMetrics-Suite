"""Regression tests for EXP-MACD-MECH-001 analytics."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "quantresearch" / "scripts" / "analyze_exp_macd_mech_001.py"
SPEC = importlib.util.spec_from_file_location("analyze_exp_macd_mech_001", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
analytics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analytics)


def test_directional_permutation_uses_short_side() -> None:
    dates = pd.date_range("2024-01-01", periods=8, freq="15min", tz="UTC")
    close = np.arange(10.0, 18.0)
    data = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.1,
            "low": close - 0.1,
            "close": close,
        },
        index=dates,
    )
    atr = pd.Series(1.0, index=dates)
    signals = [
        {"bar_index": 0, "direction": "SHORT"},
        {"bar_index": 3, "direction": "SHORT"},
    ]

    result = analytics._directional_permutation_test(
        data,
        atr,
        signals,
        horizon=1,
        n_permutations=100,
        seed=7,
    )

    assert result["n_signals"] == 2
    assert np.isclose(result["observed_hit_rate"], -0.5)
    assert np.isclose(result["baseline_mean_hit_rate"], -0.5)
