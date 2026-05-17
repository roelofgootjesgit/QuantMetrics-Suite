"""Unit tests for MACD indicator."""
import numpy as np
import pandas as pd
import pytest

from src.quantbuild.indicators.macd import macd


def _synthetic_cross_series() -> pd.Series:
    """Piecewise trend so MACD crosses signal on a known bar."""
    n = 80
    close = np.concatenate([
        np.linspace(100.0, 100.0, 30),
        np.linspace(100.0, 130.0, 25),
        np.linspace(130.0, 95.0, 25),
    ])
    return pd.Series(close, dtype=float)


class TestMACD:
    def test_output_columns(self):
        close = _synthetic_cross_series()
        result = macd(close, fast=12, slow=26, signal=9)
        assert list(result.columns) == [
            "macd_line",
            "signal_line",
            "histogram",
            "bullish_cross",
            "bearish_cross",
        ]
        assert len(result) == len(close)

    def test_histogram_equals_macd_minus_signal(self):
        close = _synthetic_cross_series()
        result = macd(close)
        valid = result[["macd_line", "signal_line", "histogram"]].dropna()
        expected = valid["macd_line"] - valid["signal_line"]
        pd.testing.assert_series_equal(
            valid["histogram"], expected, check_names=False
        )

    def test_bullish_and_bearish_never_same_bar(self):
        close = _synthetic_cross_series()
        result = macd(close)
        both = result["bullish_cross"] & result["bearish_cross"]
        assert not both.any()

    def test_cross_flags_are_boolean(self):
        close = _synthetic_cross_series()
        result = macd(close)
        assert result["bullish_cross"].dtype == bool
        assert result["bearish_cross"].dtype == bool

    def test_bullish_cross_definition_on_synthetic_step(self):
        """Engineered series: sharp rise after flat should produce at least one bull cross."""
        close = pd.Series(
            [100.0] * 40 + [100 + i * 2.5 for i in range(1, 41)],
            dtype=float,
        )
        result = macd(close, fast=5, slow=10, signal=3)
        assert result["bullish_cross"].sum() >= 1
        for idx in result.index[result["bullish_cross"]]:
            m = result.loc[idx, "macd_line"]
            s = result.loc[idx, "signal_line"]
            prev = result.shift(1).loc[idx]
            assert m > s
            assert prev["macd_line"] <= prev["signal_line"]

    def test_no_lookahead(self):
        close = _synthetic_cross_series()
        full = macd(close, fast=12, slow=26, signal=9)
        start = 30
        for i in range(start, len(close)):
            partial = macd(close.iloc[: i + 1], fast=12, slow=26, signal=9)
            row_full = full.iloc[i]
            row_partial = partial.iloc[-1]
            for col in ("macd_line", "signal_line", "histogram"):
                if pd.isna(row_full[col]) and pd.isna(row_partial[col]):
                    continue
                assert row_full[col] == pytest.approx(row_partial[col], rel=1e-9)
            assert row_full["bullish_cross"] == row_partial["bullish_cross"]
            assert row_full["bearish_cross"] == row_partial["bearish_cross"]

    def test_first_bar_has_no_cross_flags(self):
        close = _synthetic_cross_series()
        result = macd(close)
        assert not result["bullish_cross"].iloc[0]
        assert not result["bearish_cross"].iloc[0]
