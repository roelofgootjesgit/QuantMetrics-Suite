"""cTrader OpenAPI must fail closed on Spotware error payloads."""
from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

QB_SRC = Path(__file__).resolve().parents[2] / "quantbridge" / "src"
if str(QB_SRC) not in sys.path:
    sys.path.insert(0, str(QB_SRC))

from quantbridge.execution.brokers.ctrader_broker import CTraderBroker  # noqa: E402
from quantbridge.execution.clients.ctrader_openapi_client import (  # noqa: E402
    CTraderOpenApiClient,
    _error_message_from_response,
)
from quantbridge.execution.errors import BrokerError  # noqa: E402


def _install_ctrader_stubs(monkeypatch):
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
    api_mod.ProtoOAClosePositionReq = _Req
    api_mod.ProtoOAAmendPositionSLTPReq = _Req
    api_mod.ProtoOAReconcileReq = _Req
    messages_mod.OpenApiModelMessages_pb2 = model_mod

    monkeypatch.setitem(sys.modules, "ctrader_open_api", messages_pkg)
    monkeypatch.setitem(sys.modules, "ctrader_open_api.messages", messages_mod)
    monkeypatch.setitem(
        sys.modules, "ctrader_open_api.messages.OpenApiModelMessages_pb2", model_mod
    )
    monkeypatch.setitem(sys.modules, "ctrader_open_api.messages.OpenApiMessages_pb2", api_mod)


def test_error_message_from_proto_oa_error_res():
    class ProtoOAErrorRes:
        errorCode = "POSITION_NOT_FOUND"
        description = "Position not found"

    msg = _error_message_from_response(ProtoOAErrorRes())
    assert msg is not None
    assert "POSITION_NOT_FOUND" in msg


def test_error_message_from_order_error_event():
    class ProtoOAOrderErrorEvent:
        errorCode = "TRADING_DISABLED"
        description = "Trading disabled"

    msg = _error_message_from_response(ProtoOAOrderErrorEvent())
    assert msg is not None
    assert "TRADING_DISABLED" in msg


def test_send_message_raises_on_error_payload(monkeypatch):
    client = CTraderOpenApiClient(account_id="1", access_token="tok")
    client._client = object()
    client._reactor = object()

    class ProtoOAErrorRes:
        errorCode = "BAD_STOPS"
        description = "Invalid stop price"

    twisted_threads = ModuleType("twisted.internet.threads")
    twisted_threads.blockingCallFromThread = lambda reactor, fn: ProtoOAErrorRes()
    monkeypatch.setitem(sys.modules, "twisted.internet.threads", twisted_threads)

    with pytest.raises(BrokerError, match="BAD_STOPS"):
        client._send_message(SimpleNamespace())


def test_close_trade_returns_false_on_error_payload(monkeypatch):
    _install_ctrader_stubs(monkeypatch)
    client = CTraderOpenApiClient(account_id="1", access_token="tok")
    client.connected = True
    client._send_message = MagicMock(  # type: ignore[method-assign]
        side_effect=BrokerError(code="order_rejected", message="POSITION_LOCKED: locked")
    )
    assert client.close_trade("42") is False
    assert client.last_error is not None
    assert "POSITION_LOCKED" in client.last_error


def test_modify_trade_returns_false_on_error_payload(monkeypatch):
    _install_ctrader_stubs(monkeypatch)
    client = CTraderOpenApiClient(account_id="1", access_token="tok")
    client.connected = True
    client._send_message = MagicMock(  # type: ignore[method-assign]
        side_effect=BrokerError(code="order_rejected", message="BAD_STOPS: Invalid stop")
    )
    assert client.modify_trade("42", sl=1990.0, tp=2020.0) is False
    assert client.last_error is not None
    assert "BAD_STOPS" in client.last_error


def test_get_open_trades_raises_instead_of_empty_list(monkeypatch):
    _install_ctrader_stubs(monkeypatch)
    client = CTraderOpenApiClient(account_id="1", access_token="tok")
    client.connected = True
    client._resolve_symbol = MagicMock(return_value=("XAUUSD", 41))  # type: ignore[method-assign]
    client.get_current_price = MagicMock(  # type: ignore[method-assign]
        return_value={"bid": 1.0, "ask": 1.1, "spread": 0.1}
    )
    client._send_message = MagicMock(  # type: ignore[method-assign]
        side_effect=BrokerError(code="reconcile_failed", message="UNDER_MAINTENANCE")
    )
    with pytest.raises(BrokerError, match="reconcile_failed"):
        client.get_open_trades("XAUUSD")
    assert client.last_error is not None


def test_ctrader_broker_does_not_mask_reconcile_failure():
    broker = CTraderBroker(account_id="1", access_token="tok", mode="mock")
    broker.client = MagicMock()
    broker.client.get_open_trades.return_value = []
    broker.client.last_error = "reconcile_failed: network timeout"

    with pytest.raises(BrokerError, match="reconcile_failed"):
        broker.get_open_trades("XAUUSD")
    assert broker._last_error is not None
    assert "reconcile_failed" in broker._last_error
    health = broker.health_check()
    assert health.status == "degraded"
