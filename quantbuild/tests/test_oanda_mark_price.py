"""Regression: Oanda open trades must use live mark, not fill price."""
import sys
from types import ModuleType
from unittest.mock import MagicMock

from src.quantbuild.execution.broker_oanda import OandaBroker


def _ensure_fake_oandapy():
    """Install minimal oandapyV20 stubs so optional broker imports succeed in CI."""
    if "oandapyV20.endpoints.trades" in sys.modules:
        return

    root = ModuleType("oandapyV20")
    endpoints = ModuleType("oandapyV20.endpoints")
    trades = ModuleType("oandapyV20.endpoints.trades")
    pricing = ModuleType("oandapyV20.endpoints.pricing")

    class TradesList:
        def __init__(self, accountID, params=None):
            self.accountID = accountID
            self.params = params

    class PricingInfo:
        def __init__(self, accountID, params=None):
            self.accountID = accountID
            self.params = params

    trades.TradesList = TradesList
    pricing.PricingInfo = PricingInfo
    sys.modules["oandapyV20"] = root
    sys.modules["oandapyV20.endpoints"] = endpoints
    sys.modules["oandapyV20.endpoints.trades"] = trades
    sys.modules["oandapyV20.endpoints.pricing"] = pricing


def test_get_open_trades_uses_live_mid_not_fill_price():
    _ensure_fake_oandapy()
    broker = OandaBroker(account_id="acc", token="tok", instrument="XAU_USD")
    broker._connected = True
    broker._client = MagicMock()

    fill_price = 2000.0
    expected_mid = 2020.0
    broker._client.request.return_value = {
        "trades": [
            {
                "id": "T-1",
                "instrument": "XAU_USD",
                "currentUnits": "2",
                "price": str(fill_price),
                "unrealizedPL": "40.0",
                "stopLossOrder": {"price": "1990.0"},
                "takeProfitOrder": {"price": "2040.0"},
            }
        ]
    }
    broker.get_current_price = MagicMock(
        return_value={"bid": 2019.0, "ask": 2021.0, "spread": 2.0, "time": "t"}
    )

    positions = broker.get_open_trades()

    assert len(positions) == 1
    pos = positions[0]
    assert pos.entry_price == fill_price
    assert pos.current_price == expected_mid
    assert pos.current_price != pos.entry_price
    assert pos.unrealized_pnl == 40.0
    assert pos.sl == 1990.0
    assert pos.tp == 2040.0
    broker.get_current_price.assert_called_once_with("XAU_USD")


def test_get_open_trades_caches_one_price_fetch_per_instrument():
    _ensure_fake_oandapy()
    broker = OandaBroker(account_id="acc", token="tok", instrument="XAU_USD")
    broker._connected = True
    broker._client = MagicMock()
    broker._client.request.return_value = {
        "trades": [
            {
                "id": "T-1",
                "instrument": "XAU_USD",
                "currentUnits": "1",
                "price": "2000.0",
                "unrealizedPL": "10.0",
            },
            {
                "id": "T-2",
                "instrument": "XAU_USD",
                "currentUnits": "-1",
                "price": "2005.0",
                "unrealizedPL": "-5.0",
            },
        ]
    }
    broker.get_current_price = MagicMock(
        return_value={"bid": 2010.0, "ask": 2012.0, "spread": 2.0, "time": "t"}
    )

    positions = broker.get_open_trades()

    assert broker.get_current_price.call_count == 1
    assert len(positions) == 2
    assert all(p.current_price == 2011.0 for p in positions)


def test_get_open_trades_falls_back_to_fill_when_mark_unavailable():
    _ensure_fake_oandapy()
    broker = OandaBroker(account_id="acc", token="tok", instrument="XAU_USD")
    broker._connected = True
    broker._client = MagicMock()
    broker._client.request.return_value = {
        "trades": [
            {
                "id": "T-1",
                "instrument": "XAU_USD",
                "currentUnits": "1",
                "price": "2000.0",
                "unrealizedPL": "0.0",
            }
        ]
    }
    broker.get_current_price = MagicMock(return_value=None)

    positions = broker.get_open_trades()

    assert len(positions) == 1
    assert positions[0].current_price == 2000.0
