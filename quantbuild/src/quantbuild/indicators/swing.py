"""Swing high/low and pivot detection (confirmation-time / causal)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def swing_highs(data: pd.DataFrame, lookback: int = 20, shift: bool = True) -> pd.Series:
    """Rolling highest high over lookback period.

    Args:
        shift: If True, uses previous bar's value (avoids look-ahead).
    """
    result = data["high"].rolling(lookback, center=False, min_periods=1).max()
    if shift:
        result = result.shift(1)
    return result


def swing_lows(data: pd.DataFrame, lookback: int = 20, shift: bool = True) -> pd.Series:
    """Rolling lowest low over lookback period.

    Args:
        shift: If True, uses previous bar's value (avoids look-ahead).
    """
    result = data["low"].rolling(lookback, center=False, min_periods=1).min()
    if shift:
        result = result.shift(1)
    return result


def pivot_highs(data: pd.DataFrame, pivot_bars: int = 2) -> pd.Series:
    """Pivot high confirmed only after the right-side window has closed.

    Origin bar ``i`` is a pivot high iff ``high[i]`` equals the max on
    ``[i - pivot_bars, i + pivot_bars]``. The boolean is written at confirmation
    index ``i + pivot_bars`` — never back-written onto ``i``.
    """
    high = data["high"].to_numpy(dtype=np.float64, copy=False)
    n = len(high)
    out = np.zeros(n, dtype=bool)
    pb = int(pivot_bars)
    if pb < 0:
        raise ValueError("pivot_bars must be >= 0")
    for c in range(2 * pb, n):
        i = c - pb
        window = high[i - pb : i + pb + 1]
        if window.size and np.isfinite(high[i]) and high[i] == np.max(window[np.isfinite(window)]):
            out[c] = True
    return pd.Series(out, index=data.index, dtype=bool)


def pivot_lows(data: pd.DataFrame, pivot_bars: int = 2) -> pd.Series:
    """Pivot low confirmed only after the right-side window has closed.

    See :func:`pivot_highs` for confirmation-time semantics.
    """
    low = data["low"].to_numpy(dtype=np.float64, copy=False)
    n = len(low)
    out = np.zeros(n, dtype=bool)
    pb = int(pivot_bars)
    if pb < 0:
        raise ValueError("pivot_bars must be >= 0")
    for c in range(2 * pb, n):
        i = c - pb
        window = low[i - pb : i + pb + 1]
        if window.size and np.isfinite(low[i]) and low[i] == np.min(window[np.isfinite(window)]):
            out[c] = True
    return pd.Series(out, index=data.index, dtype=bool)


def pivot_high_prices(data: pd.DataFrame, pivot_bars: int = 2) -> pd.Series:
    """At confirmation bar ``c``, the confirmed pivot-high **price** (origin high)."""
    high = data["high"].to_numpy(dtype=np.float64, copy=False)
    n = len(high)
    out = np.full(n, np.nan, dtype=np.float64)
    pb = int(pivot_bars)
    for c in range(2 * pb, n):
        i = c - pb
        window = high[i - pb : i + pb + 1]
        finite = window[np.isfinite(window)]
        if finite.size and np.isfinite(high[i]) and high[i] == np.max(finite):
            out[c] = high[i]
    return pd.Series(out, index=data.index)


def pivot_low_prices(data: pd.DataFrame, pivot_bars: int = 2) -> pd.Series:
    """At confirmation bar ``c``, the confirmed pivot-low **price** (origin low)."""
    low = data["low"].to_numpy(dtype=np.float64, copy=False)
    n = len(low)
    out = np.full(n, np.nan, dtype=np.float64)
    pb = int(pivot_bars)
    for c in range(2 * pb, n):
        i = c - pb
        window = low[i - pb : i + pb + 1]
        finite = window[np.isfinite(window)]
        if finite.size and np.isfinite(low[i]) and low[i] == np.min(finite):
            out[c] = low[i]
    return pd.Series(out, index=data.index)


def last_swing_low(
    high: np.ndarray, low: np.ndarray, close: np.ndarray,
    end_idx: int, pivot_n: int = 3, lookback: int = 50,
) -> float:
    """Most recent swing low with right-window confirmed by ``end_idx`` (inclusive)."""
    start = max(0, end_idx - lookback)
    best = float("nan")
    # Origin i needs i+pivot_n <= end_idx for confirmation-time causality.
    for i in range(start + pivot_n, end_idx - pivot_n + 1):
        is_pivot = True
        for j in range(i - pivot_n, i + pivot_n + 1):
            if j == i or j < 0 or j > end_idx:
                continue
            if low[j] < low[i]:
                is_pivot = False
                break
        if is_pivot:
            best = float(low[i])
    return best


def last_swing_high(
    high: np.ndarray, low: np.ndarray, close: np.ndarray,
    end_idx: int, pivot_n: int = 3, lookback: int = 50,
) -> float:
    """Most recent swing high with right-window confirmed by ``end_idx`` (inclusive)."""
    start = max(0, end_idx - lookback)
    best = float("nan")
    for i in range(start + pivot_n, end_idx - pivot_n + 1):
        is_pivot = True
        for j in range(i - pivot_n, i + pivot_n + 1):
            if j == i or j < 0 or j > end_idx:
                continue
            if high[j] > high[i]:
                is_pivot = False
                break
        if is_pivot:
            best = float(high[i])
    return best
