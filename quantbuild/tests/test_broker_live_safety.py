"""Regression tests for live broker safety: query failures and unprotected fills."""
from unittest.mock import MagicMock

import pytest

from src.quantbuild.execution.broker_ctrader import CTraderBroker
from src.quantbuild.execution.broker_oanda import BrokerQueryError, OandaBroker


def test_oanda_get_open_trades_raises_on_api_failure():
    broker = OandaBroker(account_id="acc", token="tok", instrument="XAU_USD")
    broker._connected = True
    broker._client = MagicMock()
    broker._client.request.side_effect = RuntimeError("network timeout")

    with pytest.raises(BrokerQueryError, match="get_open_trades failed"):
        broker.get_open_trades()


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
