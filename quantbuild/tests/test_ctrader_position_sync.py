"""cTrader reconcile failures must not look like a flat account."""
from datetime import datetime, timezone
from pathlib import Path
import sys
from unittest.mock import MagicMock

import pytest

_QB_SRC = Path(__file__).resolve().parents[2] / "quantbridge" / "src"
if str(_QB_SRC) not in sys.path:
    sys.path.insert(0, str(_QB_SRC))

from quantbridge.execution.brokers.ctrader_broker import CTraderBroker as BridgeBroker
from src.quantbuild.execution.broker_ctrader import CTraderBroker
from src.quantbuild.execution.broker_errors import BrokerQueryError
from src.quantbuild.execution.live_runner import LiveRunner
from src.quantbuild.models.trade import Position, TradeDirection


def _runner_cfg():
    return {
        "symbol": "XAUUSD",
        "timeframes": ["15m", "1h"],
        "data": {"base_path": "data/market_cache"},
        "backtest": {"tp_r": 2.0, "sl_r": 1.0, "session_mode": "extended"},
        "risk": {"max_daily_loss_r": 3.0, "max_position_pct": 1.0, "paper_equity": 10000},
        "strategy": {},
        "regime": {},
        "regime_profiles": {},
        "execution_guards": {"max_open_positions": 3},
        "execution": {"check_interval_seconds": 60},
        "news": {"enabled": False},
        "broker": {"provider": "ctrader", "mock_mode": True, "instrument": "XAUUSD"},
        "quantlog": {"enabled": False},
    }


def _open_position() -> Position:
    return Position(
        trade_id="pos-1",
        instrument="XAUUSD",
        direction=TradeDirection.LONG,
        entry_price=2650.0,
        units=10.0,
        current_price=2652.0,
        sl=2640.0,
        tp=2670.0,
        open_time=datetime.now(timezone.utc),
    )


class TestBridgeReconcileFailure:
    def test_empty_list_with_client_error_is_not_a_flat_book(self):
        broker = BridgeBroker(
            account_id="1",
            access_token="token",
            mode="mock",
        )
        client = MagicMock()
        client.last_error = "reconcile_failed: openapi_request_timeout"
        client.get_open_trades.return_value = []
        broker.client = client

        with pytest.raises(RuntimeError, match="get_open_trades failed"):
            broker.get_open_trades()

        assert broker._last_error == "reconcile_failed: openapi_request_timeout"

    def test_genuine_empty_book_is_returned(self):
        broker = BridgeBroker(
            account_id="1",
            access_token="token",
            mode="mock",
        )
        client = MagicMock()
        client.last_error = None
        client.get_open_trades.return_value = []
        broker.client = client

        assert broker.get_open_trades() == []
        assert broker._last_error is None


class TestQuantBuildWrapper:
    def test_query_failure_raises_broker_query_error(self):
        broker = CTraderBroker(mock_mode=False, account_id="1", access_token="x" * 24)
        broker._connected = True
        bridge = MagicMock()
        bridge.get_open_trades.side_effect = RuntimeError(
            "get_open_trades failed: reconcile_failed: openapi_request_timeout"
        )
        broker._real_bridge = bridge

        with pytest.raises(BrokerQueryError, match="cTrader get_open_trades failed"):
            broker.get_open_trades()

    def test_close_does_not_send_when_volume_lookup_fails(self):
        broker = CTraderBroker(mock_mode=False, account_id="1", access_token="x" * 24)
        broker._connected = True
        bridge = MagicMock()
        bridge.get_open_trades.side_effect = RuntimeError("get_open_trades failed: timeout")
        broker._real_bridge = bridge

        assert broker.close_trade("pos-1") is False
        bridge.close_trade.assert_not_called()


class TestLiveRunnerSync:
    def test_failed_reconcile_keeps_open_position_and_order_state(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "src.quantbuild.execution.order_manager.STATE_FILE",
            tmp_path / "state.json",
        )
        runner = LiveRunner(_runner_cfg(), dry_run=False)
        runner.broker = MagicMock()
        runner.broker.is_connected = True
        runner.broker.get_open_trades.side_effect = BrokerQueryError(
            "cTrader get_open_trades failed: reconcile_failed: openapi_request_timeout"
        )
        runner._emit_trade_closed = MagicMock()

        pos = _open_position()
        runner.position_monitor.add_position(pos)
        runner.order_manager.register_trade(
            trade_id=pos.trade_id,
            instrument="XAUUSD",
            direction="LONG",
            entry_price=2650.0,
            units=10.0,
            sl=2640.0,
            tp=2670.0,
        )
        runner.order_manager.managed_orders[pos.trade_id].break_even_set = True
        runner.order_manager.managed_orders[pos.trade_id].peak_price = 2660.0

        runner._sync_positions_from_broker()

        assert pos.trade_id in {p.trade_id for p in runner.position_monitor.all_positions}
        managed = runner.order_manager.managed_orders[pos.trade_id]
        assert managed.break_even_set is True
        assert managed.peak_price == 2660.0
        runner._emit_trade_closed.assert_not_called()

    def test_confirmed_flat_book_still_drops_local_position(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "src.quantbuild.execution.order_manager.STATE_FILE",
            tmp_path / "state.json",
        )
        runner = LiveRunner(_runner_cfg(), dry_run=False)
        runner.broker = MagicMock()
        runner.broker.is_connected = True
        runner.broker.get_open_trades.return_value = []
        runner._emit_trade_closed = MagicMock()

        pos = _open_position()
        runner.position_monitor.add_position(pos)
        runner.order_manager.register_trade(
            trade_id=pos.trade_id,
            instrument="XAUUSD",
            direction="LONG",
            entry_price=2650.0,
            units=10.0,
            sl=2640.0,
            tp=2670.0,
        )

        runner._sync_positions_from_broker()

        assert runner.position_monitor.all_positions == []
        assert pos.trade_id not in runner.order_manager.managed_orders
        runner._emit_trade_closed.assert_called_once()
