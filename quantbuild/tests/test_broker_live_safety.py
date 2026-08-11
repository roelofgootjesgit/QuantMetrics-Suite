"""Regression tests for live broker safety: sync failures and unprotected fills."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.quantbuild.execution.broker_ctrader import CTraderBroker
from src.quantbuild.execution.live_runner import LiveRunner
from src.quantbuild.models.trade import Position


def _cfg():
    return {
        "symbol": "XAUUSD",
        "timeframes": ["15m", "1h"],
        "data": {"base_path": "data/market_cache"},
        "backtest": {"tp_r": 2.0, "sl_r": 1.0, "session_mode": "extended"},
        "risk": {
            "max_daily_loss_r": 3.0,
            "max_position_pct": 1.0,
            "paper_equity": 10000,
        },
        "strategy": {},
        "regime": {},
        "regime_profiles": {},
        "execution_guards": {
            "max_spread_pips": 5.0,
            "max_slippage_r": 0.15,
            "max_open_positions": 3,
        },
        "execution": {"check_interval_seconds": 60, "regime_update_seconds": 900},
        "news": {"enabled": False},
        "broker": {
            "account_id": "",
            "token": "",
            "environment": "practice",
            "instrument": "XAU_USD",
        },
        "order_management": {
            "trailing_stop": {"enabled": False},
            "break_even": {"enabled": False},
            "partial_close": {"enabled": False},
        },
    }


def test_ctrader_amend_failure_flattens_and_returns_failure():
    broker = CTraderBroker(mock_mode=False, instrument="XAUUSD")
    broker._connected = True
    bridge = MagicMock()
    bridge.submit_market_order.return_value = MagicMock(
        success=True,
        order_id="OID-1",
        trade_id="TID-1",
        fill_price=2000.0,
        message="filled",
        raw_response={"ok": True},
    )
    bridge.modify_trade.return_value = False
    bridge.close_trade.return_value = True
    broker._real_bridge = bridge

    result = broker.submit_market_order(
        instrument="XAUUSD",
        direction="BUY",
        units=1.0,
        sl=1990.0,
        tp=2020.0,
    )

    assert result.success is False
    assert "SL/TP amend failed" in result.message
    assert "flatten=ok" in result.message
    bridge.close_trade.assert_called_once_with("TID-1")


def test_sync_keeps_local_positions_when_get_open_trades_raises():
    runner = LiveRunner(_cfg(), dry_run=False)
    runner.broker = MagicMock()
    runner.broker.is_connected = True
    runner.broker.get_open_trades.side_effect = RuntimeError(
        "reconcile_failed: network timeout"
    )

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

    assert any(p.trade_id == "LIVE-1" for p in runner.position_monitor.all_positions)
    assert "LIVE-1" in runner.order_manager.managed_orders
