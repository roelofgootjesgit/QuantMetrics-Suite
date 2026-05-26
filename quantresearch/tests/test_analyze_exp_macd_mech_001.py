"""Regression tests for EXP-MACD-MECH-001 analytics helpers."""
from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.analyze_exp_macd_mech_001 import _directional_permutation_test


def _ohlc(close: np.ndarray) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=len(close), freq="15min", tz="UTC")
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 0.01,
            "low": close - 0.01,
            "close": close,
        },
        index=dates,
    )


def test_directional_permutation_scores_shorts_as_short_returns() -> None:
    close = np.array([10.0, 12.0, 14.0, 16.0])
    data = _ohlc(close)
    atr = pd.Series(np.ones(len(close)), index=data.index)
    entries = [
        {"bar_index": 0, "direction": "LONG"},
        {"bar_index": 1, "direction": "SHORT"},
    ]

    result = _directional_permutation_test(
        data, atr, entries, horizon=1, n_permutations=20, seed=1
    )

    assert result["observed_hit_rate"] == 0.0
    assert result["n_signals"] == 2


def test_directional_permutation_excludes_signals_without_full_horizon() -> None:
    close = np.array([10.0, 12.0, 14.0, 16.0])
    data = _ohlc(close)
    atr = pd.Series(np.ones(len(close)), index=data.index)
    entries = [
        {"bar_index": 0, "direction": "LONG"},
        {"bar_index": len(close) - 1, "direction": "LONG"},
    ]

    result = _directional_permutation_test(
        data, atr, entries, horizon=1, n_permutations=20, seed=1
    )

    assert result["observed_hit_rate"] == 1.0
    assert result["n_signals"] == 1
