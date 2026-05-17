"""Unit tests for Bollinger Bands indicator."""
import numpy as np
import pandas as pd
import pytest

from src.quantbuild.indicators.bollinger import bollinger_bands
from src.quantbuild.indicators.ma import sma


def _close_series(n: int = 50, seed: int = 0) -> pd.Series:
    np.random.seed(seed)
    values = 100.0 + np.cumsum(np.random.randn(n))
    return pd.Series(values, index=pd.RangeIndex(n), dtype=float)


class TestBollingerBands:
    def test_midline_equals_sma(self):
        close = _close_series(60)
        length = 20
        bands = bollinger_bands(close, length=length, stddev=2.0)
        expected_mid = sma(close, period=length, min_periods=length)
        pd.testing.assert_series_equal(bands["mid"], expected_mid, check_names=False)

    def test_band_order_after_warmup(self):
        close = _close_series(80, seed=1)
        length = 20
        bands = bollinger_bands(close, length=length, stddev=2.0)
        valid = bands.iloc[length - 1 :]
        assert (valid["upper"] >= valid["mid"]).all()
        assert (valid["mid"] >= valid["lower"]).all()

    def test_warmup_nan_count(self):
        close = _close_series(40)
        length = 20
        bands = bollinger_bands(close, length=length, stddev=2.0)
        warmup = bands.iloc[: length - 1]
        assert warmup.isna().all().all()
        assert bands.iloc[length - 1 :].notna().all().all()

    def test_no_lookahead(self):
        close = _close_series(100, seed=2)
        length = 20
        full = bollinger_bands(close, length=length, stddev=2.0)
        for i in range(length - 1, len(close)):
            partial = bollinger_bands(close.iloc[: i + 1], length=length, stddev=2.0)
            row_full = full.iloc[i]
            row_partial = partial.iloc[-1]
            assert row_full["mid"] == pytest.approx(row_partial["mid"])
            assert row_full["upper"] == pytest.approx(row_partial["upper"])
            assert row_full["lower"] == pytest.approx(row_partial["lower"])

    def test_constant_close_collapses_bands_to_mid(self):
        close = pd.Series([50.0] * 30)
        bands = bollinger_bands(close, length=10, stddev=2.0)
        valid = bands.dropna()
        pd.testing.assert_series_equal(valid["upper"], valid["mid"], check_names=False)
        pd.testing.assert_series_equal(valid["lower"], valid["mid"], check_names=False)
