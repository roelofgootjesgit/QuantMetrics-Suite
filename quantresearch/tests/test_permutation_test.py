"""Tests for signal timestamp permutation test."""
import numpy as np
import pytest

from quantresearch.statistics.permutation_test import directional_permutation_test, permutation_test


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


def test_directional_permutation_scores_short_signals_with_short_outcomes() -> None:
    long_outcomes = np.array([0.1, -2.0, 0.2, 0.3, 0.4], dtype=float)
    short_outcomes = -long_outcomes

    result = directional_permutation_test(
        long_outcomes,
        short_outcomes,
        np.array([1], dtype=int),
        ["SHORT"],
        n_permutations=20,
        seed=7,
    )

    assert result["observed_hit_rate"] == 2.0


def test_directional_permutation_rejects_invalid_signal_outcomes() -> None:
    long_outcomes = np.array([0.1, np.nan, 0.2], dtype=float)
    short_outcomes = np.array([-0.1, np.nan, -0.2], dtype=float)

    with pytest.raises(ValueError, match="without finite directional outcomes"):
        directional_permutation_test(
            long_outcomes,
            short_outcomes,
            np.array([1], dtype=int),
            ["LONG"],
            n_permutations=20,
            seed=7,
        )
