"""Regression tests for EXP-MACD-MECH-001 analyzer statistics."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


def _load_analyzer_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "analyze_exp_macd_mech_001.py"
    spec = importlib.util.spec_from_file_location("analyze_exp_macd_mech_001", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_direction_preserving_permutation_scores_short_signals_as_shorts() -> None:
    analyzer = _load_analyzer_module()
    dates = pd.date_range("2024-01-01", periods=40, freq="15min", tz="UTC")
    close = np.linspace(100.0, 61.0, len(dates))
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
    entries = [{"bar_index": i, "direction": "SHORT"} for i in (2, 6, 10, 14)]

    result = analyzer._direction_preserving_permutation_test(
        data,
        atr,
        entries,
        horizon=2,
        n_permutations=200,
        seed=7,
    )

    assert result["n_signals"] == 4
    assert result["n_long_signals"] == 0
    assert result["n_short_signals"] == 4
    assert result["observed_hit_rate"] > 0.0
    assert result["baseline_mean_hit_rate"] > 0.0
