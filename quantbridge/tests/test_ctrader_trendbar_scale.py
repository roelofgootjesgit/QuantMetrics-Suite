"""cTrader trendbar prices must use Spotware's fixed 1/100000 relative scale.

Dividing by 10**symbol.digits is correct only for 5-digit FX (EURUSD). Production
XAUUSD (digits=2) was decoded 1000x too high, so live ATR/SL/TP and the parquet
cache diverged from broker spots (which already use /100000).
"""
from types import SimpleNamespace

import pytest

from quantbridge.execution.clients.ctrader_openapi_client import (
    CTraderOpenApiClient,
    _from_relative_price,
)


def _client_with_digits(symbol_id: int, digits: int) -> CTraderOpenApiClient:
    client = CTraderOpenApiClient(account_id="1", access_token="test")
    client._symbol_digits_by_id[symbol_id] = digits
    return client


def _bar(*, low: int, delta_open: int = 0, delta_high: int = 0, delta_close: int = 0):
    return SimpleNamespace(
        utcTimestampInMinutes=28_000_000,
        low=low,
        deltaOpen=delta_open,
        deltaHigh=delta_high,
        deltaClose=delta_close,
        volume=12,
    )


class TestFromRelativePrice:
    def test_official_eurusd_example(self):
        # ProtoTrendbar docs: 107716 means 1.07716
        assert _from_relative_price(107716, 5) == 1.07716

    def test_official_gold_like_example(self):
        # ProtoTrendbar docs: 47452000 means 474.52
        assert _from_relative_price(47452000, 2) == 474.52

    def test_xauusd_not_scaled_by_digits(self):
        # digits=2 must NOT become /100 (that would yield 2_650_000)
        assert _from_relative_price(265_000_000, 2) == 2650.0


class TestTrendbarToOhlcv:
    def test_xauusd_digits_2_matches_spot_scale(self):
        client = _client_with_digits(42, 2)
        row = client._trendbar_to_ohlcv(
            _bar(low=265_000_000, delta_open=50_000, delta_high=150_000, delta_close=80_000),
            symbol_id=42,
            symbol_name="XAUUSD",
        )
        assert row is not None
        assert row["low"] == 2650.00
        assert row["open"] == 2650.50
        assert row["high"] == 2651.50
        assert row["close"] == 2650.80
        # Old 10**digits path produced ~2.65e6 — must not return
        assert row["high"] < 10_000

    def test_eurusd_digits_5_unchanged(self):
        client = _client_with_digits(7, 5)
        row = client._trendbar_to_ohlcv(
            _bar(low=107716, delta_open=3, delta_high=20, delta_close=10),
            symbol_id=7,
            symbol_name="EURUSD",
        )
        assert row is not None
        assert row["low"] == 1.07716
        assert row["open"] == 1.07719
        assert row["high"] == 1.07736
        assert row["close"] == 1.07726

    def test_missing_timestamp_skipped(self):
        client = _client_with_digits(1, 2)
        tb = _bar(low=265_000_000)
        tb.utcTimestampInMinutes = 0
        assert client._trendbar_to_ohlcv(tb, 1, "XAUUSD") is None

    def test_wrong_old_scale_would_invert_live_sl(self):
        """Regression: 1000x ATR vs correct spot makes a LONG SL go negative."""
        client = _client_with_digits(42, 2)
        row = client._trendbar_to_ohlcv(_bar(low=265_000_000), 42, "XAUUSD")
        assert row is not None
        close = row["close"]
        # Typical gold ATR ~$8; 1000x bar scale would look like ~$8000
        atr_correct = 8.0
        sl_correct = close - atr_correct
        sl_old_bug = close - (atr_correct * 1000.0)
        assert sl_correct > 0
        assert sl_old_bug < 0
        assert pytest.approx(close, rel=0, abs=0.01) == 2650.0
