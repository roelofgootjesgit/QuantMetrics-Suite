"""MACD — moving average convergence/divergence with cross flags."""
import pandas as pd

from src.quantbuild.indicators.ma import ema


def macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """MACD indicator on close prices.

    Returns columns: ``macd_line``, ``signal_line``, ``histogram``,
    ``bullish_cross``, ``bearish_cross``.
    Cross flags are True only on the bar where the cross occurs (no lookahead).
    """
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line

    prev_macd = macd_line.shift(1)
    prev_signal = signal_line.shift(1)
    bullish_cross = (macd_line > signal_line) & (prev_macd <= prev_signal)
    bearish_cross = (macd_line < signal_line) & (prev_macd >= prev_signal)

    return pd.DataFrame(
        {
            "macd_line": macd_line,
            "signal_line": signal_line,
            "histogram": histogram,
            "bullish_cross": bullish_cross.fillna(False),
            "bearish_cross": bearish_cross.fillna(False),
        },
        index=close.index,
    )
