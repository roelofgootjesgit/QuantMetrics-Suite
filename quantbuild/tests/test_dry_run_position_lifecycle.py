"""Regression: dry-run must close SL/TP phantoms so position_limit can free slots."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.quantbuild.execution.live_runner import LiveRunner
from src.quantbuild.models.trade import Position


def _minimal_cfg(max_open: int = 3):
    return {
        "symbol": "XAUUSD",
        "timeframes": ["15m", "1h"],
        "data": {"base_path": "data/market_cache"},
        "backtest": {"tp_r": 2.0, "sl_r": 1.0, "session_mode": "extended"},
        "risk": {"max_daily_loss_r": 3.0, "max_position_pct": 1.0, "paper_equity": 10000},
        "strategy": {},
        "regime": {},
        "regime_profiles": {},
        "execution_guards": {
            "max_spread_pips": 5.0,
            "max_slippage_r": 0.15,
            "max_open_positions": max_open,
        },
        "execution": {"check_interval_seconds": 60, "regime_update_seconds": 900},
        "news": {"enabled": False},
        "broker": {
            "account_id": "",
            "token": "",
            "environment": "practice",
            "instrument": "XAU_USD",
        },
        "quantlog": {"enabled": False},
    }


def _bar(high: float, low: float, close: float) -> pd.DataFrame:
    idx = pd.DatetimeIndex([pd.Timestamp("2025-01-02 12:00", tz="UTC")])
    return pd.DataFrame(
        {"open": [close], "high": [high], "low": [low], "close": [close]},
        index=idx,
    )


def _add_long(runner: LiveRunner, trade_id: str, entry: float = 2000.0, sl: float = 1990.0, tp: float = 2020.0):
    runner.order_manager.register_trade(
        trade_id=trade_id,
        instrument="XAUUSD",
        direction="LONG",
        entry_price=entry,
        units=10.0,
        sl=sl,
        tp=tp,
        atr=10.0,
        regime="trend",
        requested_price=entry,
    )
    runner.position_monitor.add_position(
        Position(
            trade_id=trade_id,
            instrument="XAUUSD",
            direction="LONG",
            entry_price=entry,
            units=10.0,
            sl=sl,
            tp=tp,
            open_time=datetime(2025, 1, 2, 11, 0, tzinfo=timezone.utc),
            atr_at_entry=10.0,
            regime_at_entry="trend",
        )
    )


class TestDryRunPositionLifecycle:
    def test_phantoms_block_until_sl_frees_slot(self, tmp_path, monkeypatch):
        """Without exits, max_open phantoms mute entries; SL touch frees a slot."""
        monkeypatch.chdir(tmp_path)
        cfg = _minimal_cfg(max_open=2)
        runner = LiveRunner(cfg, dry_run=True)
        runner.order_manager.save_state = MagicMock()

        _add_long(runner, "DRY_A", entry=2000.0, sl=1990.0, tp=2020.0)
        _add_long(runner, "DRY_B", entry=2005.0, sl=1995.0, tp=2025.0)
        assert len(runner.position_monitor.open_positions) == 2
        assert not runner._check_position_limit()

        # Price still between SL/TP — phantoms remain, limit still full.
        runner._load_recent_data = MagicMock(return_value=(_bar(2010, 2000, 2005), "cache"))
        runner._monitor_positions()
        assert len(runner.position_monitor.open_positions) == 2
        assert not runner._check_position_limit()

        # Bar wicks through DRY_A stop — one slot frees.
        runner._load_recent_data = MagicMock(return_value=(_bar(2008, 1988, 1992), "cache"))
        runner._monitor_positions()
        assert "DRY_A" not in {p.trade_id for p in runner.position_monitor.all_positions}
        assert "DRY_B" in {p.trade_id for p in runner.position_monitor.all_positions}
        assert runner._check_position_limit()
        assert runner._daily_pnl_r == pytest.approx(-1.0)

    def test_take_profit_closes_and_credits_daily_pnl(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner = LiveRunner(_minimal_cfg(max_open=3), dry_run=True)
        runner.order_manager.save_state = MagicMock()
        _add_long(runner, "DRY_TP", entry=2000.0, sl=1990.0, tp=2020.0)

        runner._load_recent_data = MagicMock(return_value=(_bar(2021, 2001, 2018), "cache"))
        runner._monitor_positions()

        assert runner.position_monitor.open_positions == []
        assert runner._daily_pnl_r == pytest.approx(2.0)

    def test_short_stop_uses_high_touch(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner = LiveRunner(_minimal_cfg(max_open=3), dry_run=True)
        runner.order_manager.save_state = MagicMock()
        runner.order_manager.register_trade(
            trade_id="DRY_S",
            instrument="XAUUSD",
            direction="SHORT",
            entry_price=2000.0,
            units=5.0,
            sl=2010.0,
            tp=1980.0,
            atr=10.0,
            regime="trend",
        )
        runner.position_monitor.add_position(
            Position(
                trade_id="DRY_S",
                instrument="XAUUSD",
                direction="SHORT",
                entry_price=2000.0,
                units=5.0,
                sl=2010.0,
                tp=1980.0,
                open_time=datetime(2025, 1, 2, 11, 0, tzinfo=timezone.utc),
            )
        )

        runner._load_recent_data = MagicMock(return_value=(_bar(2012, 1995, 2008), "cache"))
        runner._monitor_positions()
        assert runner.position_monitor.open_positions == []
        assert runner._daily_pnl_r == pytest.approx(-1.0)

    def test_dual_touch_prefers_stop_loss(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner = LiveRunner(_minimal_cfg(), dry_run=True)
        runner.order_manager.save_state = MagicMock()
        _add_long(runner, "DRY_BOTH", entry=2000.0, sl=1990.0, tp=2020.0)

        runner._load_recent_data = MagicMock(return_value=(_bar(2025, 1985, 2010), "cache"))
        runner._monitor_positions()
        assert runner.position_monitor.open_positions == []
        assert runner._daily_pnl_r == pytest.approx(-1.0)

    def test_live_mode_does_not_simulate_exits(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner = LiveRunner(_minimal_cfg(), dry_run=False)
        runner.order_manager.save_state = MagicMock()
        _add_long(runner, "LIVE_1", entry=2000.0, sl=1990.0, tp=2020.0)
        runner._load_recent_data = MagicMock(return_value=(_bar(2025, 1985, 2010), "cache"))
        runner._monitor_positions()
        assert len(runner.position_monitor.open_positions) == 1
