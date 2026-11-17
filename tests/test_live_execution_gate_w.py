"""Issue #104 PR-A — wire negative tests W1–W5 / W4b (B1/B2 repair)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from quantbridge.execution.clients.ctrader_openapi_client import CTraderOpenApiClient
from quantbridge.safety.live_execution_gate import GATE_ENV_KEYS, LiveExecutionDenied

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def deny_env(monkeypatch):
    """Process env without authorization — SESSION/ORDERS must fail allowlist/auth."""
    for key in GATE_ENV_KEYS:
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
    client = CTraderOpenApiClient(
        "12345678", "token-token-token-token-token", environment="prod"
    )
    with pytest.raises(LiveExecutionDenied):
        client.connect()
    assert track_ctrader_client == []


def test_w2_submit_without_auth_zero_side_effects(deny_env, track_ctrader_client, monkeypatch):
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_ACCOUNT_IDS", "12345678")
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS", "demo")
    client = CTraderOpenApiClient(
        "12345678", "token-token-token-token-token", environment="demo"
    )
    client.connected = True
    with pytest.raises(LiveExecutionDenied):
        client.submit_market_order(direction="BUY", units=1)
    assert track_ctrader_client == []


def test_w3_close_modify_without_auth(deny_env, track_ctrader_client, monkeypatch):
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_ACCOUNT_IDS", "12345678")
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS", "demo")
    client = CTraderOpenApiClient(
        "12345678", "token-token-token-token-token", environment="demo"
    )
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


def test_w4b_oanda_close_modify_denied_no_api_request(deny_env, monkeypatch):
    """B2: Oanda close/modify denied; no endpoint request issued."""
    from src.quantbuild.execution.broker_oanda import OandaBroker

    monkeypatch.setenv("QUANTMETRICS_ALLOWED_ACCOUNT_IDS", "001-practice")
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS", "practice")

    requests: list[object] = []

    class FakeClient:
        def request(self, r):
            requests.append(r)
            raise AssertionError("request must not run")

    broker = OandaBroker(
        account_id="001-practice",
        token="tok",
        environment="practice",
    )
    broker._connected = True
    broker._client = FakeClient()

    with pytest.raises(LiveExecutionDenied):
        broker.close_trade("42")
    with pytest.raises(LiveExecutionDenied):
        broker.modify_trade("42", sl=1.0)
    assert requests == []


def test_w4c_run_live_sh_allows_clean_env_and_executes():
    """Clean orchestrator env passes snapshot/restore and reaches PYTHON."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        env_file = tmp / "orch.env"
        env_file.write_text("FOO=bar\n# no gate keys\n", encoding="utf-8")
        stub_py = tmp / "stub_python"
        stub_py.write_text("#!/bin/sh\necho STUB_RAN\nexit 0\n", encoding="utf-8")
        stub_py.chmod(0o755)
        script = ROOT / "quantbuild/scripts/vps/run_live.sh"
        clean = {k: v for k, v in os.environ.items() if k not in GATE_ENV_KEYS}
        proc = subprocess.run(
            ["bash", str(script), "live", "--dry-run"],
            cwd=str(ROOT / "quantbuild"),
            env={
                **clean,
                "QUANTBUILD_ROOT": str(ROOT / "quantbuild"),
                "QUANTBUILD_ORCHESTRATOR_ENV": str(env_file),
                "PYTHON": str(stub_py),
            },
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "STUB_RAN" in proc.stdout


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
        oanda_loader._get_oanda_client(
            token="tok", environment="practice", account_id="001"
        )
    assert api_calls == []
