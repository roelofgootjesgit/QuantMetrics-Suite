"""Regression tests for parquet cache refresh safety."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from src.quantbuild.io import parquet_loader


def _ohlcv(index: pd.DatetimeIndex, base: float) -> pd.DataFrame:
    values = [base + float(i) for i in range(len(index))]
    return pd.DataFrame(
        {
            "open": values,
            "high": [v + 1.0 for v in values],
            "low": [v - 1.0 for v in values],
            "close": values,
            "volume": [1.0] * len(index),
        },
        index=index,
    )


def test_ensure_data_merges_refresh_with_existing_history(monkeypatch, tmp_path):
    symbol = "XAUUSD"
    timeframe = "5m"
    historical_index = pd.date_range("2022-01-03 00:00", periods=120, freq="5min")
    historical = _ohlcv(historical_index, 100.0)
    parquet_loader.save_parquet(tmp_path, symbol, timeframe, historical)

    recent_end = datetime.now().replace(second=0, microsecond=0)
    recent_start = recent_end - timedelta(minutes=5 * 119)
    recent_index = pd.date_range(recent_start, periods=120, freq="5min")
    recent = _ohlcv(recent_index, 200.0)

    def fake_fetch_yfinance(fetch_symbol: str, fetch_timeframe: str, period_days: int) -> pd.DataFrame:
        assert fetch_symbol == symbol
        assert fetch_timeframe == timeframe
        assert period_days == 2
        return recent

    monkeypatch.setattr(parquet_loader, "_fetch_yfinance", fake_fetch_yfinance)

    refreshed = parquet_loader.ensure_data(
        symbol=symbol,
        timeframe=timeframe,
        base_path=tmp_path,
        period_days=2,
        source="yfinance",
    )
    cached = parquet_loader.load_parquet(tmp_path, symbol, timeframe)

    assert len(refreshed) == len(recent)
    assert len(cached) == len(historical) + len(recent)
    assert cached.index[0] == historical.index[0]
    assert cached.index[-1] == recent.index[-1]
    assert cached.loc[historical.index[0], "close"] == historical.iloc[0]["close"]
    assert cached.loc[recent.index[-1], "close"] == recent.iloc[-1]["close"]
