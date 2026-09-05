"""QuantBuild cTrader wrapper must not accept a one-sided / zero quote."""
from unittest.mock import MagicMock

from src.quantbuild.execution.broker_ctrader import CTraderBroker


def test_real_bridge_zero_ask_is_treated_as_unavailable():
    broker = CTraderBroker(mock_mode=False, account_id="1", access_token="token")
    broker._connected = True
    broker._real_bridge = MagicMock()
    broker._real_bridge.get_current_price.return_value = {
        "bid": 2650.0,
        "ask": 0.0,
        "spread": -2650.0,
    }
    assert broker.get_current_price("XAUUSD") is None


def test_real_bridge_valid_quote_passes_through():
    broker = CTraderBroker(mock_mode=False, account_id="1", access_token="token")
    broker._connected = True
    broker._real_bridge = MagicMock()
    quote = {"bid": 2650.0, "ask": 2650.5, "spread": 0.5}
    broker._real_bridge.get_current_price.return_value = quote
    assert broker.get_current_price("XAUUSD") == quote
