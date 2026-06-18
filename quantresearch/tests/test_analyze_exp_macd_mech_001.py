"""Tests for EXP-MACD-MECH-001 post-run analytics helpers."""

from __future__ import annotations

import numpy as np

from scripts.analyze_exp_macd_mech_001 import (
    _direction_preserving_permutation_test,
    _directional_forward_return_universes,
)


def test_permutation_observed_score_preserves_signal_direction() -> None:
    close = np.array([100.0, 110.0, 90.0, 100.0])
    atr = np.array([5.0, 5.0, 5.0, 5.0])
    long_returns, short_returns = _directional_forward_return_universes(close, atr, horizon=1)

    result = _direction_preserving_permutation_test(
        long_returns,
        short_returns,
        np.array([0, 1], dtype=int),
        ["LONG", "SHORT"],
        n_permutations=20,
        seed=7,
    )

    assert result["observed_hit_rate"] == 1.5
    assert long_returns[1] == -2.0
    assert short_returns[1] == 2.0
