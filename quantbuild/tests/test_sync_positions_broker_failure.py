"""LiveRunner broker sync must not wipe local state on query failure."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.quantbuild.execution.live_runner import LiveRunner
from src.quantbuild.models.trade import Position


def _cfg():
    return {
        "symbol": "XAUUSD",
        "timeframes": ["15m", "1h"],
        "data": {"base_path": "data/market_cache"},
        "backtest": {"tp_r": 2.0, "sl_r": 1.0, "session_mode": "extended"},
        "risk": {"max_daily_loss_r": 3.0, "max_position_pct": 1.0, "paper_equity": 10000},
        "strategy": {},
        "regime": {},
        "regime_profiles": {},
        "execution_guards": {"max_spread_pips": 5.0, "max_slippage_r": 0.15, "max_open_positions": 3},
        "execution": {"check_interval_seconds": 60, "regime_update_seconds": 900},
        "news": {"enabled": False},
        "broker": {"account_id": "", "token": "", "environment": "practice", "instrument": "XAU_USD"},
        "order_management": {
            "trailing_stop": {"enabled": False},
            "break_even": {"enabled": False},
            "partial_close": {"enabled": False},
        },
    }


def test_sync_keeps_local_positions_when_get_open_trades_raises():
    runner = LiveRunner(_cfg(), dry_run=False)
    runner.broker = MagicMock()
    runner.broker.is_connected = True
    runner.broker.get_open_trades.side_effect = RuntimeError("reconcile_failed: network timeout")

    pos = Position(
        trade_id="LIVE-1",
        instrument="XAUUSD",
        direction="LONG",
        entry_price=2000.0,
        units=10.0,
        sl=1990.0,
        tp=2020.0,
        open_time=datetime.now(timezone.utc),
        current_price=2005.0,
    )
    runner.position_monitor.add_position(pos)
    runner.order_manager.register_trade(
        trade_id="LIVE-1",
        instrument="XAUUSD",
        direction="LONG",
        entry_price=2000.0,
        units=10.0,
        sl=1990.0,
        tp=2020.0,
    )

    runner._sync_positions_from_broker()

    assert runner.position_monitor.get_position("LIVE-1") is not None
    assert "LIVE-1" in runner.order_manager.managed_orders


def test_sync_refreshes_units_after_partial_close():
    runner = LiveRunner(_cfg(), dry_run=False)
    runner.broker = MagicMock()
    runner.broker.is_connected = True

    pos = Position(
        trade_id="LIVE-2",
        instrument="XAUUSD",
        direction="LONG",
        entry_price=2000.0,
        units=10.0,
        sl=1990.0,
        tp=2020.0,
        open_time=datetime.now(timezone.utc),
        current_price=2010.0,
    )
    runner.position_monitor.add_position(pos)
    runner.order_manager.register_trade(
        trade_id="LIVE-2",
        instrument="XAUUSD",
        direction="LONG",
        entry_price=2000.0,
        units=10.0,
        sl=1990.0,
        tp=2020.0,
    )

    bt = MagicMock()
    bt.trade_id = "LIVE-2"
    bt.instrument = "XAUUSD"
    bt.direction = "LONG"
    bt.entry_price = 2000.0
    bt.units = 5.0
    bt.current_price = 2010.0
    bt.unrealized_pnl = 50.0
    bt.sl = 2000.02
    bt.tp = 2020.0
    bt.open_time = pos.open_time
    runner.broker.get_open_trades.return_value = [bt]

    runner._sync_positions_from_broker()

    assert runner.position_monitor.get_position("LIVE-2").units == 5.0
    assert runner.order_manager.managed_orders["LIVE-2"].units == 5.0
    assert runner.position_monitor.get_position("LIVE-2").sl == 2000.02
