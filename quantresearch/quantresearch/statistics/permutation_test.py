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
    signal_directions: list[str] | np.ndarray,
    *,
    n_permutations: int = 1000,
    seed: int = 42,
) -> dict[str, float | int | bool]:
    """Permutation test that preserves each signal's trade direction.

    ``long_outcomes`` and ``short_outcomes`` are per-bar scores for entering
    long or short at that timestamp. Random timestamps are sampled once per
    permutation, then scored with the original signal direction mix.
    """
    long_out = np.asarray(long_outcomes, dtype=float)
    short_out = np.asarray(short_outcomes, dtype=float)
    sig_idx = np.asarray(signal_indices, dtype=int)
    directions = np.asarray(signal_directions, dtype=str)

    if long_out.ndim != 1 or short_out.ndim != 1:
        raise ValueError("outcomes must be 1-D")
    if len(long_out) != len(short_out):
        raise ValueError("long_outcomes and short_outcomes must have the same length")
    if sig_idx.ndim != 1:
        raise ValueError("signal_indices must be 1-D")
    if directions.ndim != 1:
        raise ValueError("signal_directions must be 1-D")
    if len(sig_idx) != len(directions):
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

    directions = np.char.upper(directions)
    if ((directions != "LONG") & (directions != "SHORT")).any():
        raise ValueError("signal_directions must contain only LONG or SHORT")

    eligible = np.flatnonzero(np.isfinite(long_out) & np.isfinite(short_out))
    n_signals = len(sig_idx)
    if len(eligible) < n_signals:
        raise ValueError("not enough eligible outcome bars for permutation")

    observed_values = np.where(directions == "LONG", long_out[sig_idx], short_out[sig_idx])
    if not np.isfinite(observed_values).all():
        raise ValueError("signal_indices include bars without finite directional outcomes")
    observed = float(np.mean(observed_values))

    rng = np.random.default_rng(seed)
    perm_rates = np.empty(n_permutations, dtype=float)
    for i in range(n_permutations):
        random_idx = rng.choice(eligible, size=n_signals, replace=False)
        random_values = np.where(directions == "LONG", long_out[random_idx], short_out[random_idx])
        perm_rates[i] = float(np.mean(random_values))

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
