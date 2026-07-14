"""Regression tests for EXP-MACD-MECH-001 post-run analytics."""
from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.analyze_exp_macd_mech_001 import _direction_aware_permutation_test


def test_permutation_scores_mixed_signals_in_their_trade_direction() -> None:
    dates = pd.date_range("2024-01-01", periods=12, freq="15min", tz="UTC")
    close = np.full(12, 100.0)
    close[8] = 102.0
    close[9] = 98.0
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
        {"bar_index": 0, "direction": "LONG"},
        {"bar_index": 1, "direction": "SHORT"},
    ]

    result = _direction_aware_permutation_test(
        data,
        atr,
        entries,
        horizon=8,
        n_permutations=20,
        seed=1,
    )

    assert result["n_signals"] == 2
    assert result["observed_hit_rate"] == 1.0


def test_permutation_excludes_invalid_signal_horizons_and_atr() -> None:
    dates = pd.date_range("2024-01-01", periods=12, freq="15min", tz="UTC")
    close = np.arange(12, dtype=float)
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
    atr.iloc[1] = np.nan
    entries = [
        {"bar_index": 0, "direction": "LONG"},
        {"bar_index": 1, "direction": "SHORT"},
        {"bar_index": 10, "direction": "LONG"},
    ]

    result = _direction_aware_permutation_test(
        data,
        atr,
        entries,
        horizon=2,
        n_permutations=20,
        seed=1,
    )

    assert result["n_signals"] == 1
    assert np.isfinite(result["observed_hit_rate"])
