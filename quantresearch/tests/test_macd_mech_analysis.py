"""Regression tests for EXP-MACD-MECH-001 analytics wiring."""
from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.analyze_exp_macd_mech_001 import _directional_permutation_test


def test_directional_permutation_preserves_short_signal_edge() -> None:
    n = 160
    dates = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")
    close = np.full(n, 100.0)
    close[28] = 90.0
    close[68] = 110.0
    data = pd.DataFrame(
        {"open": close, "high": close, "low": close, "close": close},
        index=dates,
    )
    atr = pd.Series(np.ones(n), index=dates)

    result = _directional_permutation_test(
        data,
        atr,
        signal_indices=[20, 60],
        signal_directions=["SHORT", "LONG"],
        horizon=8,
        n_permutations=500,
        seed=7,
    )

    assert result["observed_hit_rate"] == 5.0
    assert result["p_value"] < 0.05
