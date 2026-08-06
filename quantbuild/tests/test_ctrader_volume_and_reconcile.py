"""Critical cTrader OpenAPI volume scaling + reconcile failure semantics."""
from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

QB_SRC = Path(__file__).resolve().parents[2] / "quantbridge" / "src"
if str(QB_SRC) not in sys.path:
    sys.path.insert(0, str(QB_SRC))

from quantbridge.execution.clients.ctrader_openapi_client import (  # noqa: E402
    CTraderOpenApiClient,
    from_api_volume,
    to_api_volume,
)
from quantbridge.execution.errors import BrokerError  # noqa: E402


def _install_ctrader_stubs(monkeypatch):
    """Minimal stubs so openapi client methods can run without the Spotware SDK."""
    model = SimpleNamespace(BUY=1, SELL=2, MARKET=1)

    class _Req:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    messages_pkg = ModuleType("ctrader_open_api")
    messages_mod = ModuleType("ctrader_open_api.messages")
    model_mod = ModuleType("ctrader_open_api.messages.OpenApiModelMessages_pb2")
    for name, value in (("BUY", 1), ("SELL", 2), ("MARKET", 1)):
        setattr(model_mod, name, value)
    api_mod = ModuleType("ctrader_open_api.messages.OpenApiMessages_pb2")
    api_mod.ProtoOANewOrderReq = _Req
    api_mod.ProtoOAReconcileReq = _Req
    api_mod.ProtoOAClosePositionReq = _Req
    messages_mod.OpenApiModelMessages_pb2 = model_mod

    monkeypatch.setitem(sys.modules, "ctrader_open_api", messages_pkg)
    monkeypatch.setitem(sys.modules, "ctrader_open_api.messages", messages_mod)
    monkeypatch.setitem(sys.modules, "ctrader_open_api.messages.OpenApiModelMessages_pb2", model_mod)
    monkeypatch.setitem(sys.modules, "ctrader_open_api.messages.OpenApiMessages_pb2", api_mod)
    return model


def test_api_volume_round_trip_matches_spotware_cents_convention():
    # Protocol docs: 1000 means 10.00 units; samples use human_units * 100.
    assert to_api_volume(10.0) == 1000
    assert to_api_volume(0.01) == 1
    assert from_api_volume(1000) == 10.0
    assert from_api_volume(1) == 0.01
    assert from_api_volume(to_api_volume(15.0)) == 15.0


def test_submit_market_order_sends_centivolume(monkeypatch):
    _install_ctrader_stubs(monkeypatch)
    client = CTraderOpenApiClient(account_id="1", access_token="tok")
    client.connected = True
    client._resolve_symbol = MagicMock(return_value=("XAUUSD", 41))  # type: ignore[method-assign]
    captured = {}

    def _send(req):
        captured["volume"] = int(req.volume)
        return SimpleNamespace(position=SimpleNamespace(positionId=99, price=2500.0), order=None)

    client._send_message = _send  # type: ignore[method-assign]
    result = client.submit_market_order(instrument="XAUUSD", direction="BUY", units=15.0)
    assert result.success is True
    assert captured["volume"] == 1500  # 15.00 units → 1500 cents


def test_close_trade_sends_centivolume(monkeypatch):
    _install_ctrader_stubs(monkeypatch)
    client = CTraderOpenApiClient(account_id="1", access_token="tok")
    client.connected = True
    captured = {}

    def _send(req):
        captured["volume"] = int(req.volume)
        return SimpleNamespace()

    client._send_message = _send  # type: ignore[method-assign]
    assert client.close_trade("7", units=7.5) is True
    assert captured["volume"] == 750


def test_get_open_trades_converts_protocol_volume_to_units(monkeypatch):
    _install_ctrader_stubs(monkeypatch)
    client = CTraderOpenApiClient(account_id="1", access_token="tok")
    client.connected = True
    client._resolve_symbol = MagicMock(return_value=("XAUUSD", 41))  # type: ignore[method-assign]
    client.get_current_price = MagicMock(  # type: ignore[method-assign]
        return_value={"bid": 2499.0, "ask": 2501.0, "spread": 2.0}
    )
    client._symbol_name_by_id = {41: "XAUUSD"}

    trade_data = SimpleNamespace(symbolId=41, tradeSide=1, volume=1500)  # cents
    position = SimpleNamespace(
        tradeData=trade_data, positionId=7, price=2500.0, stopLoss=0, takeProfit=0
    )
    client._send_message = MagicMock(return_value=SimpleNamespace(position=[position]))  # type: ignore[method-assign]

    trades = client.get_open_trades("XAUUSD")
    assert len(trades) == 1
    assert trades[0].units == 15.0


def test_get_open_trades_raises_on_reconcile_failure(monkeypatch):
    _install_ctrader_stubs(monkeypatch)
    client = CTraderOpenApiClient(account_id="1", access_token="tok")
    client.connected = True
    client._resolve_symbol = MagicMock(return_value=("XAUUSD", 41))  # type: ignore[method-assign]
    client.get_current_price = MagicMock(  # type: ignore[method-assign]
        return_value={"bid": 1.0, "ask": 1.1, "spread": 0.1}
    )
    client._send_message = MagicMock(side_effect=RuntimeError("network timeout"))  # type: ignore[method-assign]

    with pytest.raises(BrokerError, match="reconcile_failed"):
        client.get_open_trades("XAUUSD")
