"""Live cache refresh must not delete older OHLC bars."""
from datetime import datetime, timedelta, timezone

import pandas as pd

from src.quantbuild.io import parquet_loader as pl


def _ohlcv(index: pd.DatetimeIndex, close: float) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1.0,
        },
        index=index,
    )


def test_save_parquet_keeps_older_bars_and_prefers_new_overlap(tmp_path):
    old_idx = pd.date_range("2020-01-01", periods=3, freq="h")
    pl.save_parquet(tmp_path, "XAUUSD", "15m", _ohlcv(old_idx, close=1000.0))

    overlap = pd.DatetimeIndex([old_idx[-1], old_idx[-1] + pd.Timedelta(hours=1)])
    pl.save_parquet(tmp_path, "XAUUSD", "15m", _ohlcv(overlap, close=2000.0))

    stored = pl.load_parquet(tmp_path, "XAUUSD", "15m")
    assert list(stored.index) == [old_idx[0], old_idx[1], overlap[0], overlap[1]]
    assert stored.loc[old_idx[0], "close"] == 1000.0
    assert stored.loc[overlap[0], "close"] == 2000.0


def test_ensure_live_data_does_not_replace_history_with_lookback(tmp_path, monkeypatch):
    history_idx = pd.date_range("2020-01-01", periods=48, freq="h")
    pl.save_parquet(tmp_path, "XAUUSD", "1h", _ohlcv(history_idx, close=1500.0))

    recent_end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    recent_idx = pd.date_range(recent_end - timedelta(hours=399), periods=400, freq="h", tz="UTC")
    recent_idx = recent_idx.tz_convert("UTC").tz_localize(None)
    recent = _ohlcv(recent_idx, close=2400.0)

    def _fake_dukascopy(symbol, timeframe, start, end):
        return recent.copy()

    monkeypatch.setattr(pl, "_fetch_dukascopy", _fake_dukascopy)

    out = pl.ensure_live_data(
        symbol="XAUUSD",
        timeframe="1h",
        base_path=tmp_path,
        min_bars=200,
        max_stale_minutes=30,
        source="dukascopy",
        broker=None,
    )

    assert len(out) >= 200
    stored = pl.load_parquet(tmp_path, "XAUUSD", "1h")
    assert history_idx[0] in stored.index
    assert recent_idx[-1] in stored.index
    assert len(stored) == len(history_idx) + len(recent_idx)
    assert stored.loc[history_idx[0], "close"] == 1500.0
