"""Unit tests for M5 sweep research detector."""

from __future__ import annotations

import math

import pandas as pd

from src.quantbuild.research.sweep_m5_xauusd import (
    SweepDetectorConfig,
    align_prev_daily_high_low,
    detect_sweep_events_m5,
    in_session_bucket_utc,
)


def test_in_session_bucket_utc():
    assert in_session_bucket_utc(pd.Timestamp("2024-06-01 07:30", tz="UTC")) == "london_open"
    assert in_session_bucket_utc(pd.Timestamp("2024-06-01 14:00", tz="UTC")) == "ny_open"
    assert in_session_bucket_utc(pd.Timestamp("2024-06-01 11:00", tz="UTC")) is None


def test_align_prev_daily_high_low():
    idx = pd.date_range("2024-01-01 22:00", periods=30, freq="5min", tz="UTC")
    df = pd.DataFrame(
        {"open": [1, 1, 1], "high": [2, 3, 2], "low": [0.5, 0.5, 1], "close": [1, 2, 1], "volume": [0, 0, 0]},
        index=idx[:3],
    )
    # extend to 30 rows crossing UTC midnight so prior-day OHLC exists
    rows = []
    for i, t in enumerate(idx):
        rows.append({"open": 1.0, "high": 2.0 + 0.01 * i, "low": 0.5, "close": 1.5, "volume": 0.0})
    df = pd.DataFrame(rows, index=idx)
    out = align_prev_daily_high_low(df)
    first_jan2 = min(i for i, ts in enumerate(out.index) if ts.date().isoformat() == "2024-01-02")
    assert math.isfinite(out["pdh"].iloc[first_jan2])
    assert math.isfinite(out["pdl"].iloc[first_jan2])


def test_pdl_sweep_synthetic():
    """PDL sweep + same-bar reclaim during London (07:00 UTC)."""
    idx1 = pd.date_range("2024-06-01 12:00", periods=40, freq="5min", tz="UTC")
    idx2 = pd.date_range("2024-06-02 06:30", periods=50, freq="5min", tz="UTC")
    idx = pd.DatetimeIndex(list(idx1) + list(idx2))

    row_flat = {"open": 100.5, "high": 101.5, "low": 100.0, "close": 101.0, "volume": 1.0}
    rows = [dict(row_flat) for _ in idx1]
    rows2 = []
    for t in idx2:
        if t.hour == 7 and t.minute == 0:
            rows2.append(
                {"open": 100.5, "high": 101.0, "low": 98.5, "close": 100.8, "volume": 1.0}
            )
        else:
            rows2.append({"open": 100.5, "high": 102.0, "low": 100.2, "close": 101.0, "volume": 1.0})

    df = pd.DataFrame(rows + rows2, index=idx)
    cfg = SweepDetectorConfig(
        min_sweep_depth_atr=0.15,
        max_reclaim_candles=3,
        median_range_window=15,
        atr_period=5,
    )
    ev = detect_sweep_events_m5(df, regime_series=None, cfg=cfg)
    pdl_events = [e for e in ev if e["payload"]["level_type"] == "PDL"]
    assert len(pdl_events) >= 1
    assert pdl_events[0]["payload"]["reclaimed_within_window"] is True
    assert pdl_events[0]["payload"]["session"] == "london_open"
