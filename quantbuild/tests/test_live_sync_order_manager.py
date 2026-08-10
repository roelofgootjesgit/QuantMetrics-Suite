"""LiveRunner broker sync must keep OrderManager aligned with broker truth."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.quantbuild.execution.live_runner import LiveRunner
from src.quantbuild.execution.order_manager import ManagedOrder
from src.quantbuild.models.trade import Position


def _minimal_cfg():
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
        "broker": {
            "provider": "ctrader",
            "account_id": "demo",
            "mock_mode": True,
            "instrument": "XAUUSD",
        },
        "order_management": {
            "trailing_stop": {"enabled": False},
            "break_even": {"enabled": False},
            "partial_close": {"enabled": False},
        },
    }


def _broker_trade(trade_id="BRK-1", sl=2490.0, tp=2520.0):
    return MagicMock(
        trade_id=trade_id,
        instrument="XAUUSD",
        direction="LONG",
        units=100.0,
        entry_price=2500.0,
        current_price=2501.0,
        unrealized_pnl=100.0,
        sl=sl,
        tp=tp,
        open_time=datetime.now(timezone.utc),
    )


def test_sync_registers_broker_position_into_order_manager():
    runner = LiveRunner(_minimal_cfg(), dry_run=False)
    runner.broker = MagicMock()
    runner.broker.is_connected = True
    runner.broker.get_open_trades.return_value = [_broker_trade()]

    assert runner.order_manager.managed_orders == {}
    runner._sync_positions_from_broker()

    assert "BRK-1" in runner.order_manager.managed_orders
    assert any(p.trade_id == "BRK-1" for p in runner.position_monitor.all_positions)
    order = runner.order_manager.managed_orders["BRK-1"]
    assert order.units == 100.0
    assert order.original_sl == 2490.0


def test_sync_prunes_stale_order_manager_entries_not_on_broker():
    runner = LiveRunner(_minimal_cfg(), dry_run=False)
    runner.broker = MagicMock()
    runner.broker.is_connected = True
    runner.broker.get_open_trades.return_value = []

    runner.order_manager.managed_orders["GHOST"] = ManagedOrder(
        trade_id="GHOST",
        instrument="XAUUSD",
        direction="LONG",
        entry_price=2500.0,
        units=50.0,
        original_sl=2490.0,
        original_tp=2520.0,
        current_sl=2490.0,
        current_tp=2520.0,
        open_time=datetime.now(timezone.utc),
        peak_price=2500.0,
    )

    runner._sync_positions_from_broker()
    assert "GHOST" not in runner.order_manager.managed_orders


def test_sync_skips_om_register_when_broker_sl_missing():
    runner = LiveRunner(_minimal_cfg(), dry_run=False)
    runner.broker = MagicMock()
    runner.broker.is_connected = True
    runner.broker.get_open_trades.return_value = [_broker_trade(sl=None)]

    runner._sync_positions_from_broker()
    assert any(p.trade_id == "BRK-1" for p in runner.position_monitor.all_positions)
    assert "BRK-1" not in runner.order_manager.managed_orders


def test_order_manager_save_state_atomic(tmp_path, monkeypatch):
    from src.quantbuild.execution import order_manager as om_mod

    state_file = tmp_path / "state.json"
    monkeypatch.setattr(om_mod, "STATE_FILE", state_file)

    om = om_mod.OrderManager(broker=None, config={
        "trailing_stop": {"enabled": False},
        "break_even": {"enabled": False},
        "partial_close": {"enabled": False},
    })
    om.register_trade(
        trade_id="T1",
        instrument="XAUUSD",
        direction="LONG",
        entry_price=2500.0,
        units=10.0,
        sl=2490.0,
        tp=2520.0,
    )
    assert state_file.exists()
    assert not state_file.with_suffix(".json.tmp").exists()
    loaded = om_mod.OrderManager(broker=None)
    monkeypatch.setattr(om_mod, "STATE_FILE", state_file)
    assert loaded.load_state() == 1
    assert "T1" in loaded.managed_orders
