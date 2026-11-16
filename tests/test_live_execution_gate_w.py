"""Issue #104 PR-A — wire negative tests W1–W5 (zero network client construction)."""
from __future__ import annotations

import sys
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock

import pytest

from quantbridge.execution.clients.ctrader_openapi_client import CTraderOpenApiClient
from quantbridge.safety.live_execution_gate import LiveExecutionDenied


@pytest.fixture
def deny_env(monkeypatch):
    """Process env without authorization — SESSION/ORDERS must fail allowlist/auth."""
    for key in (
        "QUANTMETRICS_EXECUTION_AUTHORIZED",
        "QUANTMETRICS_ALLOWED_ACCOUNT_IDS",
        "QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(
        "quantbridge.safety.live_execution_gate.default_bridge_env_files",
        lambda root=None: [],
    )


@pytest.fixture
def track_ctrader_client(monkeypatch):
    calls: list[tuple] = []

    fake = ModuleType("ctrader_open_api")

    class Client:
        def __init__(self, *a, **k):
            calls.append(("Client", a, k))
            raise AssertionError("ctrader Client constructed on denied path")

    class EndPoints:
        PROTOBUF_DEMO_HOST = "demo-host"
        PROTOBUF_LIVE_HOST = "live-host"
        PROTOBUF_PORT = 5035

    class TcpProtocol:
        pass

    fake.Client = Client
    fake.EndPoints = EndPoints
    fake.TcpProtocol = TcpProtocol
    msgs = ModuleType("ctrader_open_api.messages")
    pb = ModuleType("ctrader_open_api.messages.OpenApiMessages_pb2")
    monkeypatch.setitem(sys.modules, "ctrader_open_api", fake)
    monkeypatch.setitem(sys.modules, "ctrader_open_api.messages", msgs)
    monkeypatch.setitem(sys.modules, "ctrader_open_api.messages.OpenApiMessages_pb2", pb)
    return calls


def test_w1_openapi_connect_typo_env_zero_client(deny_env, track_ctrader_client, monkeypatch):
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_ACCOUNT_IDS", "12345678")
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS", "demo")
    client = CTraderOpenApiClient("12345678", "token-token-token-token-token", environment="prod")
    with pytest.raises(LiveExecutionDenied):
        client.connect()
    assert track_ctrader_client == []


def test_w2_submit_without_auth_zero_side_effects(deny_env, track_ctrader_client, monkeypatch):
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_ACCOUNT_IDS", "12345678")
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS", "demo")
    client = CTraderOpenApiClient("12345678", "token-token-token-token-token", environment="demo")
    client.connected = True
    with pytest.raises(LiveExecutionDenied):
        client.submit_market_order(direction="BUY", units=1)
    assert track_ctrader_client == []


def test_w3_close_modify_without_auth(deny_env, track_ctrader_client, monkeypatch):
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_ACCOUNT_IDS", "12345678")
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS", "demo")
    client = CTraderOpenApiClient("12345678", "token-token-token-token-token", environment="demo")
    client.connected = True
    with pytest.raises(LiveExecutionDenied):
        client.close_trade("99")
    with pytest.raises(LiveExecutionDenied):
        client.modify_trade("99", sl=1.0)
    assert track_ctrader_client == []


def test_w4_oanda_connect_and_order_zero_api(deny_env, monkeypatch):
    api_calls: list[Any] = []
    fake = ModuleType("oandapyV20")

    class API:
        def __init__(self, *a, **k):
            api_calls.append(1)
            raise AssertionError("oandapyV20.API constructed on denied path")

    fake.API = API
    monkeypatch.setitem(sys.modules, "oandapyV20", fake)

    from src.quantbuild.execution.broker_oanda import OandaBroker

    broker = OandaBroker(account_id="001", token="tok", environment="practice")
    with pytest.raises(Exception):
        broker.connect()
    assert api_calls == []

    monkeypatch.setenv("QUANTMETRICS_ALLOWED_ACCOUNT_IDS", "001")
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS", "practice")
    broker._connected = True
    broker._client = object()
    with pytest.raises(Exception):
        broker.submit_market_order()
    assert api_calls == []


def test_w5_oanda_loader_unauthorized_zero_api(deny_env, monkeypatch):
    api_calls: list[Any] = []
    fake = ModuleType("oandapyV20")

    class API:
        def __init__(self, *a, **k):
            api_calls.append(1)
            raise AssertionError("oandapyV20.API constructed on denied path")

    fake.API = API
    monkeypatch.setitem(sys.modules, "oandapyV20", fake)

    from src.quantbuild.io import oanda_loader

    with pytest.raises(Exception):
        oanda_loader._get_oanda_client(token="tok", environment="live", account_id="001")
    assert api_calls == []

    with pytest.raises(Exception):
        oanda_loader._get_oanda_client(token="tok", environment="practice", account_id="001")
    assert api_calls == []
