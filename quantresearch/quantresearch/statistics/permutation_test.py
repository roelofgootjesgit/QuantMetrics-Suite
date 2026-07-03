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
    long_signal_indices: np.ndarray,
    short_signal_indices: np.ndarray,
    *,
    n_permutations: int = 1000,
    seed: int = 42,
) -> dict[str, float | int | bool]:
    """Permutation test for directional signals.

    LONG and SHORT signals have opposite return signs, so the null sample must
    preserve the observed direction mix instead of indexing one long-only
    outcome array for every signal.
    """
    long_out = np.asarray(long_outcomes, dtype=float)
    short_out = np.asarray(short_outcomes, dtype=float)
    long_idx = np.asarray(long_signal_indices, dtype=int)
    short_idx = np.asarray(short_signal_indices, dtype=int)

    if long_out.ndim != 1 or short_out.ndim != 1:
        raise ValueError("outcomes must be 1-D")
    if len(long_out) != len(short_out):
        raise ValueError("long and short outcomes must have the same length")
    if long_idx.ndim != 1 or short_idx.ndim != 1:
        raise ValueError("signal_indices must be 1-D")

    n_bars = len(long_out)
    if n_bars == 0:
        raise ValueError("outcomes must not be empty")
    if (long_idx < 0).any() or (long_idx >= n_bars).any():
        raise ValueError("long signal_indices out of range")
    if (short_idx < 0).any() or (short_idx >= n_bars).any():
        raise ValueError("short signal_indices out of range")

    valid_long = np.flatnonzero(np.isfinite(long_out))
    valid_short = np.flatnonzero(np.isfinite(short_out))
    long_idx = long_idx[np.isfinite(long_out[long_idx])]
    short_idx = short_idx[np.isfinite(short_out[short_idx])]

    n_long = len(long_idx)
    n_short = len(short_idx)
    n_signals = n_long + n_short
    if n_signals == 0:
        return {
            "observed_hit_rate": 0.0,
            "baseline_mean_hit_rate": 0.0,
            "p_value": 1.0,
            "significant": False,
            "n_signals": 0,
            "n_long_signals": 0,
            "n_short_signals": 0,
            "n_permutations": n_permutations,
            "seed": seed,
        }
    if n_long > len(valid_long) or n_short > len(valid_short):
        raise ValueError("not enough valid outcomes for directional signal counts")

    observed_values = []
    if n_long:
        observed_values.append(long_out[long_idx])
    if n_short:
        observed_values.append(short_out[short_idx])
    observed = float(np.mean(np.concatenate(observed_values)))

    rng = np.random.default_rng(seed)
    perm_rates = np.empty(n_permutations, dtype=float)
    for i in range(n_permutations):
        samples = []
        if n_long:
            long_random_idx = rng.choice(valid_long, size=n_long, replace=False)
            samples.append(long_out[long_random_idx])
        if n_short:
            short_random_idx = rng.choice(valid_short, size=n_short, replace=False)
            samples.append(short_out[short_random_idx])
        perm_rates[i] = float(np.mean(np.concatenate(samples)))

    baseline_mean = float(np.mean(perm_rates))
    p_value = float(np.mean(perm_rates >= observed))

    return {
        "observed_hit_rate": observed,
        "baseline_mean_hit_rate": baseline_mean,
        "p_value": p_value,
        "significant": p_value < 0.05,
        "n_signals": n_signals,
        "n_long_signals": n_long,
        "n_short_signals": n_short,
        "n_permutations": n_permutations,
        "seed": seed,
    }
