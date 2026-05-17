"""Bollinger Bands — SMA midline with rolling standard deviation bands."""
import pandas as pd

from src.quantbuild.indicators.ma import sma


def bollinger_bands(
    close: pd.Series,
    length: int = 20,
    stddev: float = 2.0,
) -> pd.DataFrame:
    """Bollinger Bands on a close price series.

    Returns DataFrame columns: ``mid``, ``upper``, ``lower``.
    Mid = SMA(close, length). Bands = mid ± stddev * rolling_std(ddof=0).
    First ``length - 1`` rows are NaN (full window required).
    """
    mid = sma(close, period=length, min_periods=length)
    std = close.rolling(length, min_periods=length).std(ddof=0)
    upper = mid + stddev * std
    lower = mid - stddev * std
    return pd.DataFrame(
        {"mid": mid, "upper": upper, "lower": lower},
        index=close.index,
    )
