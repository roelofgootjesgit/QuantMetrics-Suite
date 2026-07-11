"""Tests for EXP-MACD-MECH-001 post-run analyzer helpers."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from analyze_exp_macd_mech_001 import _directional_permutation_test  # noqa: E402


def test_directional_permutation_scores_short_signals_as_short_outcomes() -> None:
    long_outcomes = np.zeros(20, dtype=float)
    short_outcomes = np.zeros(20, dtype=float)
    long_outcomes[3] = 1.0
    long_outcomes[7] = -1.0
    short_outcomes[7] = 1.0

    result = _directional_permutation_test(
        long_outcomes,
        short_outcomes,
        np.array([3], dtype=int),
        np.array([7], dtype=int),
        n_permutations=100,
        seed=1,
    )

    assert result["observed_hit_rate"] == 1.0
    assert result["n_signals"] == 2


def test_directional_permutation_ignores_invalid_horizon_signals() -> None:
    long_outcomes = np.full(10, np.nan, dtype=float)
    short_outcomes = np.full(10, np.nan, dtype=float)
    long_outcomes[2] = 0.5
    short_outcomes[4] = 0.25

    result = _directional_permutation_test(
        long_outcomes,
        short_outcomes,
        np.array([2, 9], dtype=int),
        np.array([4], dtype=int),
        n_permutations=20,
        seed=1,
    )

    assert result["observed_hit_rate"] == 0.375
    assert result["n_signals"] == 2
