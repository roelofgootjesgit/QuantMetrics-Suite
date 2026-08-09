"""Critical cTrader equity (UPL) and fill-id correctness."""
from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

QB_SRC = Path(__file__).resolve().parents[2] / "quantbridge" / "src"
QB_ROOT = Path(__file__).resolve().parents[2] / "quantbuild"
for p in (QB_SRC, QB_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from quantbridge.execution.clients.ctrader_openapi_client import (  # noqa: E402
    CTraderOpenApiClient,
)
from src.quantbuild.execution.quantbridge import (  # noqa: E402
    CTraderAdapter,
    ExecutionRequest,
    OandaAdapter,
)


def _install_ctrader_stubs(monkeypatch):
    """Minimal stubs so openapi client methods can run without the Spotware SDK."""

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
    api_mod.ProtoOATraderReq = _Req
    api_mod.ProtoOAGetPositionUnrealizedPnLReq = _Req
    api_mod.ProtoOANewOrderReq = _Req
    api_mod.ProtoOAReconcileReq = _Req
    messages_mod.OpenApiModelMessages_pb2 = model_mod

    monkeypatch.setitem(sys.modules, "ctrader_open_api", messages_pkg)
    monkeypatch.setitem(sys.modules, "ctrader_open_api.messages", messages_mod)
    monkeypatch.setitem(sys.modules, "ctrader_open_api.messages.OpenApiModelMessages_pb2", model_mod)
    monkeypatch.setitem(sys.modules, "ctrader_open_api.messages.OpenApiMessages_pb2", api_mod)


def test_get_account_state_adds_net_unrealized_pnl_to_equity(monkeypatch):
    """Concrete trigger: open losing position → equity must be below balance for sizing."""
    _install_ctrader_stubs(monkeypatch)
    client = CTraderOpenApiClient(account_id="42", access_token="tok")
    client.connected = True

    trader = SimpleNamespace(balance=10_000_00, moneyDigits=2)  # $10,000.00
    upl_items = [
        SimpleNamespace(positionId=1, netUnrealizedPnL=-250_00, grossUnrealizedPnL=-240_00),
        SimpleNamespace(positionId=2, netUnrealizedPnL=-50_00, grossUnrealizedPnL=-45_00),
    ]
    responses = [
        SimpleNamespace(trader=trader),
        SimpleNamespace(moneyDigits=2, positionUnrealizedPnL=upl_items),
    ]

    def _send(req):
        assert responses, f"unexpected extra request: {req!r}"
        return responses.pop(0)

    client._send_message = _send  # type: ignore[method-assign]

    state = client.get_account_state()
    assert state is not None
    assert state.balance == pytest.approx(10000.0)
    assert state.unrealized_pnl == pytest.approx(-300.0)
    assert state.equity == pytest.approx(9700.0)
    assert state.open_trade_count == 2
    assert state.margin_available == pytest.approx(9700.0)


def test_get_account_state_fails_closed_when_upl_unavailable(monkeypatch):
    _install_ctrader_stubs(monkeypatch)
    client = CTraderOpenApiClient(account_id="42", access_token="tok")
    client.connected = True
    trader = SimpleNamespace(balance=10_000_00, moneyDigits=2)
    calls = {"n": 0}

    def _send(req):
        calls["n"] += 1
        if calls["n"] == 1:
            return SimpleNamespace(trader=trader)
        raise RuntimeError("upl timeout")

    client._send_message = _send  # type: ignore[method-assign]

    assert client.get_account_state() is None
    assert "unrealized_pnl_unavailable" in (client.last_error or "")


def test_submit_market_order_rejects_order_id_only_response(monkeypatch):
    """Concrete trigger: MARKET ack with orderId but empty positionId must not look filled."""
    _install_ctrader_stubs(monkeypatch)
    client = CTraderOpenApiClient(account_id="1", access_token="tok")
    client.connected = True
    client._resolve_symbol = MagicMock(return_value=("XAUUSD", 41))  # type: ignore[method-assign]

    def _send(req):
        return SimpleNamespace(
            position=None,
            order=SimpleNamespace(orderId=555),
        )

    client._send_message = _send  # type: ignore[method-assign]
    result = client.submit_market_order(instrument="XAUUSD", direction="BUY", units=1.0)
    assert result.success is False
    assert result.trade_id is None
    assert result.order_id == "555"
    assert "missing positionId" in (result.message or "")


def test_submit_market_order_requires_position_id_for_success(monkeypatch):
    _install_ctrader_stubs(monkeypatch)
    client = CTraderOpenApiClient(account_id="1", access_token="tok")
    client.connected = True
    client._resolve_symbol = MagicMock(return_value=("XAUUSD", 41))  # type: ignore[method-assign]

    def _send(req):
        return SimpleNamespace(
            position=SimpleNamespace(positionId=99, price=2500.0),
            order=SimpleNamespace(orderId=555),
        )

    client._send_message = _send  # type: ignore[method-assign]
    result = client.submit_market_order(instrument="XAUUSD", direction="BUY", units=1.0)
    assert result.success is True
    assert result.trade_id == "99"
    assert result.order_id == "555"


class _FakeBrokerResult:
    def __init__(self, success, trade_id=None, order_id=None, fill_price=None, message="", raw_response=None):
        self.success = success
        self.trade_id = trade_id
        self.order_id = order_id
        self.fill_price = fill_price
        self.message = message
        self.raw_response = raw_response


class _FakeBroker:
    def __init__(self, result):
        self._result = result

    def submit_market_order(self, **kwargs):
        return self._result


def _request() -> ExecutionRequest:
    return ExecutionRequest(
        symbol="XAUUSD",
        side="LONG",
        entry=2500.0,
        stop_loss=2490.0,
        take_profit=2520.0,
        risk_percent=1.0,
        account_id="acct",
        units=1.0,
    )


@pytest.mark.parametrize("adapter_cls", [CTraderAdapter, OandaAdapter])
def test_adapters_reject_missing_trade_id_even_if_order_id_present(adapter_cls):
    broker = _FakeBroker(
        _FakeBrokerResult(
            success=True,
            trade_id=None,
            order_id="ORD-9",
            fill_price=2500.0,
            message="order_accepted",
        )
    )
    result = adapter_cls(broker).place_order(_request())
    assert result.status == "rejected"
    assert result.broker_order_id == ""
    assert "missing trade_id" in result.message


@pytest.mark.parametrize("adapter_cls", [CTraderAdapter, OandaAdapter])
def test_adapters_use_trade_id_not_order_id_on_fill(adapter_cls):
    broker = _FakeBroker(
        _FakeBrokerResult(
            success=True,
            trade_id="POS-7",
            order_id="ORD-9",
            fill_price=2501.0,
            message="order_accepted",
        )
    )
    result = adapter_cls(broker).place_order(_request())
    assert result.status == "filled"
    assert result.broker_order_id == "POS-7"
