"""Tests for signal timestamp permutation test."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from quantresearch.statistics.permutation_test import permutation_test

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from analyze_exp_macd_mech_001 import _direction_aware_permutation_test


def test_seed_reproducible() -> None:
    out = np.random.default_rng(0).random(200)
    sig = np.array([10, 50, 120, 180])
    a = permutation_test(out, sig, n_permutations=500, seed=99)
    b = permutation_test(out, sig, n_permutations=500, seed=99)
    assert a["p_value"] == b["p_value"]
    assert a["baseline_mean_hit_rate"] == b["baseline_mean_hit_rate"]


def test_perfect_predictor_low_p_value() -> None:
    outcomes = np.zeros(100, dtype=float)
    outcomes[5] = 1.0
    outcomes[25] = 1.0
    outcomes[55] = 1.0
    signals = np.array([5, 25, 55])
    result = permutation_test(outcomes, signals, n_permutations=1000, seed=1)
    assert result["observed_hit_rate"] == 1.0
    assert result["p_value"] < 0.01


def test_random_labels_not_structurally_significant() -> None:
    """Across seeds, false-positive rate at alpha=0.05 should stay near nominal."""
    significant = 0
    for seed in range(40):
        rng = np.random.default_rng(seed)
        outcomes = rng.random(500)
        signals = rng.choice(500, size=30, replace=False)
        result = permutation_test(outcomes, signals, n_permutations=500, seed=seed + 100)
        if result["significant"]:
            significant += 1
    assert significant < 20


def test_empty_signals_returns_neutral() -> None:
    result = permutation_test(np.ones(50), np.array([], dtype=int), seed=1)
    assert result["n_signals"] == 0
    assert result["p_value"] == 1.0
    assert not result["significant"]


def test_direction_aware_permutation_preserves_short_returns() -> None:
    close = np.arange(100.0, 112.0)
    idx = pd.date_range("2024-01-01", periods=len(close), freq="15min", tz="UTC")
    data = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.25,
            "low": close - 0.25,
            "close": close,
        },
        index=idx,
    )
    atr = pd.Series(np.ones(len(close)), index=idx)

    result = _direction_aware_permutation_test(
        data,
        atr,
        signal_indices=[0, 1],
        signal_directions=["LONG", "SHORT"],
        horizon=2,
        n_permutations=100,
        seed=7,
    )

    assert result["n_signals"] == 2
    assert result["observed_hit_rate"] == 0.0
