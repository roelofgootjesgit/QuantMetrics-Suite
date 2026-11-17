"""Market structure context: HH/HL (bullish), LH/LL (bearish), or RANGE.

Pivots are confirmation-time only (see ``indicators.swing.pivot_*_prices``).
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from src.quantbuild.indicators.swing import pivot_high_prices, pivot_low_prices
from src.quantbuild.strategy_modules.ict.structure_labels import (
    BULLISH_STRUCTURE, BEARISH_STRUCTURE, RANGE,
)


def compute_structure_labels(
    data: pd.DataFrame, lookback: int = 30, pivot_bars: int = 2,
) -> pd.Series:
    """Per bar: BULLISH_STRUCTURE (HH/HL), BEARISH_STRUCTURE (LH/LL), or RANGE.

    Uses only pivot prices that have already been confirmed by the right-side
    window (flags/prices appear at confirmation bars, never back-written).
    """
    n = len(data)
    ph_price = pivot_high_prices(data, pivot_bars=pivot_bars).to_numpy(dtype=np.float64)
    pl_price = pivot_low_prices(data, pivot_bars=pivot_bars).to_numpy(dtype=np.float64)
    out_arr = np.full(n, 0, dtype=np.int8)

    for i in range(lookback, n):
        start = max(0, i - lookback)
        ph_vals = ph_price[start : i + 1]
        pl_vals = pl_price[start : i + 1]
        ph_vals = ph_vals[np.isfinite(ph_vals)]
        pl_vals = pl_vals[np.isfinite(pl_vals)]

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
