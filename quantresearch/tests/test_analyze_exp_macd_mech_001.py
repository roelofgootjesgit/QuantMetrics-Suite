"""Tests for EXP-MACD-MECH-001 analytics helpers."""
from __future__ import annotations

import numpy as np

from scripts.analyze_exp_macd_mech_001 import direction_aware_permutation_test


def test_direction_aware_permutation_scores_short_signals_as_short_returns() -> None:
    long_returns = np.array([1.0, 0.2, -1.0, 0.1])
    short_returns = -long_returns

    result = direction_aware_permutation_test(
        long_returns,
        short_returns,
        np.array([], dtype=int),
        np.array([2]),
        n_permutations=200,
        seed=7,
    )

    assert result["observed_hit_rate"] == 1.0
    assert result["n_signals"] == 1
