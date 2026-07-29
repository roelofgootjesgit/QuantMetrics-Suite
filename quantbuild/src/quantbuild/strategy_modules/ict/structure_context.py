"""Market structure context: HH/HL (bullish), LH/LL (bearish), or RANGE."""
from typing import Dict

import numpy as np
import pandas as pd

from src.quantbuild.strategy_modules.ict.structure_labels import (
    BULLISH_STRUCTURE, BEARISH_STRUCTURE, RANGE,
)


def compute_structure_labels(
    data: pd.DataFrame, lookback: int = 30, pivot_bars: int = 2,
) -> pd.Series:
    """Per bar: BULLISH_STRUCTURE (HH/HL), BEARISH_STRUCTURE (LH/LL), or RANGE.

    Pivot highs/lows require ``pivot_bars`` bars on each side. Labels at bar ``i``
    only consume pivots whose right-side confirmation is fully known by ``i``,
    so the series is causal (no look-ahead into bars after ``i``).
    """
    n = len(data)
    window = 2 * pivot_bars + 1
    # Full window required: partial centered windows would still be non-causal
    # if stamped early, and are unused once we gate on confirmation below.
    high_roll = data["high"].rolling(window, center=True, min_periods=window).max()
    low_roll = data["low"].rolling(window, center=True, min_periods=window).min()
    is_pivot_high = ((data["high"] == high_roll) & high_roll.notna()).values
    is_pivot_low = ((data["low"] == low_roll) & low_roll.notna()).values

    high_arr = data["high"].values.astype(np.float64)
    low_arr = data["low"].values.astype(np.float64)
    out_arr = np.full(n, 0, dtype=np.int8)

    for i in range(lookback, n):
        start = max(0, i - lookback)
        # Pivot at j is confirmed only once bars j..j+pivot_bars are known.
        confirm_end = i - pivot_bars + 1
        if confirm_end <= start:
            continue
        ph_vals = high_arr[start:confirm_end][is_pivot_high[start:confirm_end]]
        pl_vals = low_arr[start:confirm_end][is_pivot_low[start:confirm_end]]

        if len(ph_vals) < 2 or len(pl_vals) < 2:
            continue

        sh2, sh1 = ph_vals[-1], ph_vals[-2]
        sl2, sl1 = pl_vals[-1], pl_vals[-2]

        if sh2 > sh1 and sl2 > sl1:
            out_arr[i] = 1
        elif sh2 < sh1 and sl2 < sl1:
            out_arr[i] = -1

    label_map = {0: RANGE, 1: BULLISH_STRUCTURE, -1: BEARISH_STRUCTURE}
    return pd.Series([label_map[v] for v in out_arr], index=data.index, dtype=object)


def add_structure_context(df: pd.DataFrame, config: Dict, inplace: bool = False) -> pd.DataFrame:
    lookback = config.get("lookback", 30)
    pivot_bars = config.get("pivot_bars", 2)
    if not inplace:
        df = df.copy()
    df["structure_label"] = compute_structure_labels(df, lookback=lookback, pivot_bars=pivot_bars)
    df["in_bullish_structure"] = df["structure_label"] == BULLISH_STRUCTURE
    df["in_bearish_structure"] = df["structure_label"] == BEARISH_STRUCTURE
    return df
