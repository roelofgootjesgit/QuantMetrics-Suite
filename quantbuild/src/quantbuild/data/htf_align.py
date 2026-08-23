"""Align higher-timeframe series onto lower-timeframe bars without look-ahead.

HTF OHLCV is indexed at bar *open*. A 14:00 H1 candle is not complete until 15:00,
so M15 bars at 14:00–14:45 must not see that hour's label.
"""
from __future__ import annotations

import pandas as pd


def infer_htf_bar_duration(index: pd.Index) -> pd.Timedelta:
    """Median spacing of HTF timestamps, defaulting to 1 hour."""
    if index is None or len(index) < 2:
        return pd.Timedelta(hours=1)
    diffs = pd.Series(index).diff().dropna()
    if diffs.empty:
        return pd.Timedelta(hours=1)
    median = diffs.median()
    if pd.isna(median) or median <= pd.Timedelta(0):
        return pd.Timedelta(hours=1)
    return pd.Timedelta(median)


def align_completed_htf(
    htf: pd.Series,
    ltf_index: pd.Index,
    bar_duration: pd.Timedelta | None = None,
) -> pd.Series:
    """Forward-fill HTF values onto ``ltf_index`` using only *completed* HTF candles.

    Shifts the HTF index to each bar's close, then ``ffill``. Early LTF bars that
    precede the first completed HTF candle remain NaN (caller fill policy).
    """
    if htf is None or htf.empty:
        return pd.Series(index=ltf_index, dtype=getattr(htf, "dtype", object))
    duration = bar_duration if bar_duration is not None else infer_htf_bar_duration(htf.index)
    shifted = htf.copy()
    shifted.index = pd.DatetimeIndex(shifted.index) + duration
    if shifted.index.has_duplicates:
        shifted = shifted[~shifted.index.duplicated(keep="last")]
    return shifted.reindex(ltf_index, method="ffill")
