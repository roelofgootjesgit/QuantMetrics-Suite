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
    """Permutation test for signal timestamps while preserving trade direction.

    LONG signals are scored against ``long_outcomes`` and SHORT signals against
    ``short_outcomes``. Non-finite signal outcomes are excluded so unavailable
    forward windows do not silently count as zero-return trades.
    """
    long_out = np.asarray(long_outcomes, dtype=float)
    short_out = np.asarray(short_outcomes, dtype=float)
    sig_idx = np.asarray(signal_indices, dtype=int)
    dirs = np.asarray(signal_directions)
    if long_out.ndim != 1 or short_out.ndim != 1:
        raise ValueError("outcomes must be 1-D")
    if len(long_out) != len(short_out):
        raise ValueError("long_outcomes and short_outcomes must have the same length")
    if sig_idx.ndim != 1 or dirs.ndim != 1:
        raise ValueError("signal_indices and signal_directions must be 1-D")
    if len(sig_idx) != len(dirs):
        raise ValueError("signal_indices and signal_directions must have the same length")

    n_bars = len(long_out)
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
    for idx, direction in zip(sig_idx, dirs):
        d = str(direction).upper()
        if d == "LONG":
            value = long_out[idx]
        elif d == "SHORT":
            value = short_out[idx]
        else:
            raise ValueError(f"unsupported signal direction: {direction!r}")
        if not np.isfinite(value):
            continue
        observed_values.append(float(value))
        if d == "LONG":
            n_long += 1
        else:
            n_short += 1

    if not observed_values:
        return {
            "observed_hit_rate": 0.0,
            "baseline_mean_hit_rate": 0.0,
            "p_value": 1.0,
            "significant": False,
            "n_signals": 0,
            "n_permutations": n_permutations,
            "seed": seed,
        }

    long_pool = np.flatnonzero(np.isfinite(long_out))
    short_pool = np.flatnonzero(np.isfinite(short_out))
    if n_long > len(long_pool) or n_short > len(short_pool):
        raise ValueError("not enough finite outcomes for permutation sample")

    observed = float(np.mean(observed_values))
    rng = np.random.default_rng(seed)
    perm_rates = np.empty(n_permutations, dtype=float)
    for i in range(n_permutations):
        sampled: list[np.ndarray] = []
        if n_long:
            long_idx = rng.choice(long_pool, size=n_long, replace=False)
            sampled.append(long_out[long_idx])
        if n_short:
            short_idx = rng.choice(short_pool, size=n_short, replace=False)
            sampled.append(short_out[short_idx])
        perm_rates[i] = float(np.mean(np.concatenate(sampled)))

    baseline_mean = float(np.mean(perm_rates))
    p_value = float(np.mean(perm_rates >= observed))

    return {
        "observed_hit_rate": observed,
        "baseline_mean_hit_rate": baseline_mean,
        "p_value": p_value,
        "significant": p_value < 0.05,
        "n_signals": len(observed_values),
        "n_permutations": n_permutations,
        "seed": seed,
    }
