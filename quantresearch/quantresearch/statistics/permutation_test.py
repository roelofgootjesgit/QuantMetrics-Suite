"""Permutation test: signal timestamps vs random timestamps on bar outcomes."""
from __future__ import annotations

import numpy as np


def permutation_test(
    outcomes: np.ndarray,
    signal_indices: np.ndarray,
    *,
    n_permutations: int = 1000,
    seed: int = 42,
) -> dict[str, float | int | bool]:
    """Test H0: random bar timestamps achieve the same hit rate as signal timestamps.

    ``outcomes`` is a 1-D array (per bar): binary hit=1/0 or continuous score.
    ``signal_indices`` are integer positions into ``outcomes`` (0-based).

    Returns dict with observed/baseline hit rates, one-sided p-value, and metadata.
    """
    out = np.asarray(outcomes, dtype=float)
    sig_idx = np.asarray(signal_indices, dtype=int)
    if out.ndim != 1:
        raise ValueError("outcomes must be 1-D")
    if sig_idx.ndim != 1:
        raise ValueError("signal_indices must be 1-D")
    n_bars = len(out)
    if n_bars == 0:
        raise ValueError("outcomes must not be empty")
    if len(sig_idx) == 0:
        return {
            "observed_hit_rate": 0.0,
            "baseline_mean_hit_rate": 0.0,
            "p_value": 1.0,
            "significant": False,
            "n_signals": 0,
            "n_permutations": n_permutations,
            "seed": seed,
        }
    if (sig_idx < 0).any() or (sig_idx >= n_bars).any():
        raise ValueError("signal_indices out of range")

    n_signals = len(sig_idx)
    observed = float(np.mean(out[sig_idx]))
    rng = np.random.default_rng(seed)
    perm_rates = np.empty(n_permutations, dtype=float)
    for i in range(n_permutations):
        random_idx = rng.choice(n_bars, size=n_signals, replace=False)
        perm_rates[i] = float(np.mean(out[random_idx]))

    baseline_mean = float(np.mean(perm_rates))
    p_value = float(np.mean(perm_rates >= observed))

    return {
        "observed_hit_rate": observed,
        "baseline_mean_hit_rate": baseline_mean,
        "p_value": p_value,
        "significant": p_value < 0.05,
        "n_signals": n_signals,
        "n_permutations": n_permutations,
        "seed": seed,
    }


def directional_permutation_test(
    long_outcomes: np.ndarray,
    short_outcomes: np.ndarray,
    signal_indices: np.ndarray,
    signal_directions: np.ndarray,
    *,
    n_permutations: int = 1000,
    seed: int = 42,
) -> dict[str, float | int | bool]:
    """Test directional signal outcomes against random timestamps.

    ``long_outcomes`` and ``short_outcomes`` are per-bar scores for taking a
    LONG or SHORT at that bar. The null preserves the observed LONG/SHORT mix
    while randomizing timestamps.
    """
    long_arr = np.asarray(long_outcomes, dtype=float)
    short_arr = np.asarray(short_outcomes, dtype=float)
    sig_idx = np.asarray(signal_indices, dtype=int)
    sig_dir = np.asarray(signal_directions)
    if long_arr.ndim != 1 or short_arr.ndim != 1:
        raise ValueError("directional outcomes must be 1-D")
    if len(long_arr) != len(short_arr):
        raise ValueError("directional outcomes must have matching length")
    if sig_idx.ndim != 1 or sig_dir.ndim != 1:
        raise ValueError("signal_indices and signal_directions must be 1-D")
    if len(sig_idx) != len(sig_dir):
        raise ValueError("signal_indices and signal_directions length mismatch")
    n_bars = len(long_arr)
    if n_bars == 0:
        raise ValueError("outcomes must not be empty")
    if len(sig_idx) == 0:
        return {
            "observed_hit_rate": 0.0,
            "baseline_mean_hit_rate": 0.0,
            "p_value": 1.0,
            "significant": False,
            "n_signals": 0,
            "n_permutations": n_permutations,
            "seed": seed,
        }
    if (sig_idx < 0).any() or (sig_idx >= n_bars).any():
        raise ValueError("signal_indices out of range")

    observed_values: list[float] = []
    n_long = 0
    n_short = 0
    for idx, direction in zip(sig_idx, sig_dir):
        direction_u = str(direction).upper()
        if direction_u == "LONG":
            value = float(long_arr[idx])
            if np.isfinite(value):
                observed_values.append(value)
                n_long += 1
        elif direction_u == "SHORT":
            value = float(short_arr[idx])
            if np.isfinite(value):
                observed_values.append(value)
                n_short += 1
        else:
            raise ValueError(f"invalid signal direction: {direction!r}")

    n_signals = len(observed_values)
    if n_signals == 0:
        return {
            "observed_hit_rate": 0.0,
            "baseline_mean_hit_rate": 0.0,
            "p_value": 1.0,
            "significant": False,
            "n_signals": 0,
            "n_permutations": n_permutations,
            "seed": seed,
        }

    long_pool = long_arr[np.isfinite(long_arr)]
    short_pool = short_arr[np.isfinite(short_arr)]
    if n_long > len(long_pool) or n_short > len(short_pool):
        raise ValueError("not enough valid bars for directional permutation")

    observed = float(np.mean(observed_values))
    rng = np.random.default_rng(seed)
    perm_rates = np.empty(n_permutations, dtype=float)
    for i in range(n_permutations):
        samples: list[np.ndarray] = []
        if n_long:
            samples.append(rng.choice(long_pool, size=n_long, replace=False))
        if n_short:
            samples.append(rng.choice(short_pool, size=n_short, replace=False))
        perm_rates[i] = float(np.mean(np.concatenate(samples)))

    baseline_mean = float(np.mean(perm_rates))
    p_value = float(np.mean(perm_rates >= observed))

    return {
        "observed_hit_rate": observed,
        "baseline_mean_hit_rate": baseline_mean,
        "p_value": p_value,
        "significant": p_value < 0.05,
        "n_signals": n_signals,
        "n_permutations": n_permutations,
        "seed": seed,
    }
