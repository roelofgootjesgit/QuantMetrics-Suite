"""QuantBuild cTrader adapter must not close with omitted/zero volume."""
from unittest.mock import MagicMock

from src.quantbuild.execution.broker_ctrader import CTraderBroker


def _live_adapter(bridge) -> CTraderBroker:
    broker = CTraderBroker(mock_mode=False, instrument="XAUUSD")
    broker._connected = True
    broker._real_bridge = bridge
    return broker


def test_close_without_units_looks_up_position_volume():
    pos = MagicMock(trade_id="42", units=100.0)
    bridge = MagicMock()
    bridge.get_open_trades.return_value = [pos]
    bridge.close_trade.return_value = True
    broker = _live_adapter(bridge)

    assert broker.close_trade("42") is True
    bridge.close_trade.assert_called_once_with("42", units=100.0)


def test_close_without_units_fails_closed_when_position_missing():
    bridge = MagicMock()
    bridge.get_open_trades.return_value = []
    broker = _live_adapter(bridge)

    assert broker.close_trade("42") is False
    bridge.close_trade.assert_not_called()


def test_close_without_units_fails_closed_when_reconcile_raises():
    bridge = MagicMock()
    bridge.get_open_trades.side_effect = RuntimeError("reconcile_failed")
    broker = _live_adapter(bridge)

    assert broker.close_trade("42") is False
    bridge.close_trade.assert_not_called()


def test_close_rejects_zero_units_without_broker_call():
    bridge = MagicMock()
    broker = _live_adapter(bridge)

    assert broker.close_trade("42", units=0) is False
    bridge.close_trade.assert_not_called()
    bridge.get_open_trades.assert_not_called()
