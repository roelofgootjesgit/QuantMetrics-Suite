"""Regression tests for non-destructive market-data cache refreshes."""

import pandas as pd
import pytest

from src.quantbuild.io import parquet_loader


def _ohlcv(index: pd.DatetimeIndex, close: float) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 100.0,
        },
        index=index,
    )


def test_ensure_data_refresh_preserves_older_cache(tmp_path, monkeypatch):
    old_index = pd.date_range("2020-01-01", periods=120, freq="15min")
    old_data = _ohlcv(old_index, 1.0)
    parquet_loader.save_parquet(tmp_path, "XAUUSD", "15m", old_data)

    recent_index = pd.date_range(
        end=pd.Timestamp.now().floor("15min"),
        periods=119,
        freq="15min",
    )
    fetched = pd.concat(
        [_ohlcv(pd.DatetimeIndex([old_index[-1]]), 9.0), _ohlcv(recent_index, 2.0)]
    )
    monkeypatch.setattr(parquet_loader, "_fetch_dukascopy", lambda *args: fetched)

    result = parquet_loader.ensure_data(
        symbol="XAUUSD",
        timeframe="15m",
        base_path=tmp_path,
        period_days=60,
        source="dukascopy",
    )

    cached = parquet_loader.load_parquet(tmp_path, "XAUUSD", "15m")
    assert len(result) == len(recent_index)
    assert len(cached) == len(old_index) + len(recent_index)
    assert cached.index[0] == old_index[0]
    assert cached.loc[old_index[-1], "close"] == 9.0


@pytest.mark.parametrize("fetched_rows", [150, 200])
def test_ensure_live_data_refresh_preserves_older_cache(
    tmp_path,
    monkeypatch,
    fetched_rows,
):
    old_index = pd.date_range("2020-01-01", periods=120, freq="15min")
    old_data = _ohlcv(old_index, 1.0)
    parquet_loader.save_parquet(tmp_path, "XAUUSD", "15m", old_data)

    recent_index = pd.date_range(
        end=pd.Timestamp.now().floor("15min"),
        periods=fetched_rows,
        freq="15min",
    )
    fetched = _ohlcv(recent_index, 2.0)
    monkeypatch.setattr(parquet_loader, "_fetch_dukascopy", lambda *args: fetched)

    result = parquet_loader.ensure_live_data(
        symbol="XAUUSD",
        timeframe="15m",
        base_path=tmp_path,
        min_bars=200,
        source="dukascopy",
    )

    cached = parquet_loader.load_parquet(tmp_path, "XAUUSD", "15m")
    assert len(result) == fetched_rows
    assert len(cached) == len(old_index) + fetched_rows
    assert cached.index[0] == old_index[0]
