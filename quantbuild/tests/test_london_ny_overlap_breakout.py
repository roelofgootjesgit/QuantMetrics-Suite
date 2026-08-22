"""Unit tests for EXP-003 London/NY overlap breakout engine."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import pytest

from src.quantbuild.backtest.engine import _simulate_trade_price_levels
from src.quantbuild.strategies.london_ny_overlap_breakout import (
    _find_range_signal_entry,
    run_london_ny_overlap_breakout_backtest,
)


def _fake_emitter_bundle(monkeypatch: pytest.MonkeyPatch) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []

    class FakeEmitter:
        def emit(self, **kwargs: Any) -> None:
            events.append(kwargs)

    monkeypatch.setattr(
        "src.quantbuild.strategies.london_ny_overlap_breakout._init_backtest_quantlog",
        lambda _cfg: FakeEmitter(),
    )
    return events


def _base_cfg() -> dict:
    return {
        "broker": {"account_id": "bt-test", "mock_spread": 0.0},
        "quantlog": {"enabled": True, "inference_requires_quantlog": False},
        "backtest": {"session_mode": "extended"},
        "session_open_utc": "13:30",
        "tp_multiplier": 1.5,
        "major_news_filter": False,
    }


def test_range_candle_detection() -> None:
    """First bar with open time >= 13:30 UTC is the range candle."""
    from datetime import time

    idx = pd.DatetimeIndex(
        [
            "2026-01-05 13:00:00+00:00",
            "2026-01-05 13:30:00+00:00",
            "2026-01-05 14:30:00+00:00",
        ],
        tz="UTC",
    )
    df = pd.DataFrame(
        {
            "open": [99.0, 100.0, 101.0],
            "high": [100.0, 102.0, 103.0],
            "low": [98.0, 99.5, 100.0],
            "close": [99.5, 101.0, 102.0],
            "volume": [1, 1, 1],
        },
        index=idx,
    )
    r_i, s_i, e_i, err = _find_range_signal_entry(df, pd.Timestamp("2026-01-05").date(), time(13, 30))
    assert err == "no_entry_candle"
    assert r_i == 1
    assert df.index[r_i] == pd.Timestamp("2026-01-05 13:30:00+00:00")
    assert s_i == 2 and e_i is None
    assert float(df.iloc[r_i]["high"]) == 102.0 and float(df.iloc[r_i]["low"]) == 99.5


def test_ambiguous_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Signal close inside range → NO_ACTION ambiguous."""
    events = _fake_emitter_bundle(monkeypatch)
    idx = pd.date_range("2026-01-06 13:30", periods=3, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "open": [100.0, 101.0, 101.0],
            "high": [102.0, 101.5, 102.0],
            "low": [99.0, 100.5, 100.0],
            "close": [101.0, 101.0, 101.2],
            "volume": [1, 1, 1],
        },
        index=idx,
    )
    # range 13:30: H=102 L=99; signal 14:30 close 101 (inside) → ambiguous
    run_london_ny_overlap_breakout_backtest(
        _base_cfg(),
        df,
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 2, 1, tzinfo=timezone.utc),
        Path("."),
        "XAUUSD",
        "1h",
    )
    skips = [e for e in events if e.get("event_type") == "trade_action"]
    amb = [e for e in skips if e.get("payload", {}).get("reason") == "ambiguous"]
    assert len(amb) == 1
    assert amb[0]["payload"].get("trade_action") == "NO_ACTION"


def test_no_signal_candle_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Range candle is last bar of UTC day → no_signal_candle."""
    events = _fake_emitter_bundle(monkeypatch)
    idx = pd.DatetimeIndex(["2026-01-07 15:00:00+00:00"], tz="UTC")
    df = pd.DataFrame(
        {"open": [100.0], "high": [103.0], "low": [99.0], "close": [102.0], "volume": [1]},
        index=idx,
    )
    run_london_ny_overlap_breakout_backtest(
        _base_cfg(),
        df,
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 2, 1, tzinfo=timezone.utc),
        Path("."),
        "XAUUSD",
        "1h",
    )
    ranges = [e for e in events if e.get("event_type") == "range_detected"]
    assert len(ranges) == 1
    skips = [e for e in events if e.get("payload", {}).get("reason") == "no_signal_candle"]
    assert len(skips) == 1


def test_long_trade_pnl() -> None:
    """LONG hits TP; profit_r ≈ tp_multiplier (spread 0)."""
    cfg = _base_cfg()
    cfg["quantlog"] = {"enabled": False, "inference_requires_quantlog": False}
    cfg["broker"]["mock_spread"] = 0.0
    cfg["tp_multiplier"] = 1.5
    idx = pd.date_range("2026-01-08 13:30", periods=6, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0, 102.0, 102.0, 102.0],
            "high": [102.0, 103.0, 102.0, 106.0, 106.0, 106.0],
            "low": [100.0, 100.0, 101.5, 101.0, 101.0, 101.0],
            "close": [101.0, 103.0, 101.8, 105.5, 105.0, 105.0],
            "volume": [1] * 6,
        },
        index=idx,
    )
    # range 13:30: H=102 L=100 → size 2; signal 14:30 close 103 LONG; entry 15:30 open 102
    # entry_price 102, sl 100, tp 105, bar 16:30 high 106 → WIN at TP
    trades = run_london_ny_overlap_breakout_backtest(
        cfg,
        df,
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 2, 1, tzinfo=timezone.utc),
        Path("."),
        "XAUUSD",
        "1h",
    )
    assert len(trades) == 1
    assert trades[0].result.value == "WIN"
    assert abs(float(trades[0].profit_r) - 1.5) < 1e-6


def test_open_entry_same_bar_stop_not_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    """HYP-003 fills at the open of entry_i; SL on that H1 must not be ignored.

    Range 13:30 H=102 L=100 (size 2). Signal 14:30 close 103 → LONG.
    Entry 15:30 open 102, SL 100, TP 105. Entry bar low 99 hits SL; the next
    bar would print through TP. Skipping the fill bar would falsely WIN.
    """
    _fake_emitter_bundle(monkeypatch)
    cfg = _base_cfg()
    cfg["quantlog"] = {"enabled": False, "inference_requires_quantlog": False}
    idx = pd.date_range("2026-01-08 13:30", periods=4, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0, 102.0],
            "high": [102.0, 103.0, 103.0, 106.0],
            "low": [100.0, 100.0, 99.0, 101.0],
            "close": [101.0, 103.0, 100.5, 105.5],
            "volume": [1, 1, 1, 1],
        },
        index=idx,
    )
    trades = run_london_ny_overlap_breakout_backtest(
        cfg,
        df,
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 2, 1, tzinfo=timezone.utc),
        Path("."),
        "XAUUSD",
        "1h",
    )
    assert len(trades) == 1
    assert trades[0].result.value == "LOSS"
    assert abs(float(trades[0].exit_price) - 100.0) < 1e-9


def test_open_entry_same_bar_tp_not_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    """Open-of-bar fill must also honor TP printed on the fill H1."""
    _fake_emitter_bundle(monkeypatch)
    cfg = _base_cfg()
    cfg["quantlog"] = {"enabled": False, "inference_requires_quantlog": False}
    idx = pd.date_range("2026-01-08 13:30", periods=4, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0, 102.0],
            "high": [102.0, 103.0, 106.0, 101.0],
            "low": [100.0, 100.0, 101.5, 90.0],
            "close": [101.0, 103.0, 105.0, 95.0],
            "volume": [1, 1, 1, 1],
        },
        index=idx,
    )
    trades = run_london_ny_overlap_breakout_backtest(
        cfg,
        df,
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 2, 1, tzinfo=timezone.utc),
        Path("."),
        "XAUUSD",
        "1h",
    )
    assert len(trades) == 1
    assert trades[0].result.value == "WIN"
    assert abs(float(trades[0].exit_price) - 105.0) < 1e-9
    assert abs(float(trades[0].profit_r) - 1.5) < 1e-6


def test_sl_bar_mfe_exclusion() -> None:
    """MFE peak is not updated on the SL bar even if that bar prints a wide high."""
    idx = pd.date_range("2026-01-09 10:00", periods=4, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "open": [100.0, 100.5, 100.5, 100.5],
            "high": [101.0, 101.5, 999.0, 101.0],
            "low": [99.5, 100.0, 98.0, 99.0],
            "close": [100.0, 101.0, 98.5, 100.0],
            "volume": [1, 1, 1, 1],
        },
        index=idx,
    )
    entry_i = 0
    entry_price = 100.15
    sl = 99.5
    tp = 200.0
    out = _simulate_trade_price_levels(df, entry_i, "LONG", entry_price, sl, tp)
    assert out["result"] == "LOSS"
    assert out["exit_bar_idx"] == 2
    assert out["bars_to_mfe"] == 1
    assert out["mfe_peak_ts"] == idx[1]