"""Issue #104 PR-A — mutation proof on scratch copies (P2)."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _copy_sources(dst: Path) -> None:
    for pkg in (
        "quantbridge/src/quantbridge",
        "quantbridge/src/quantbridge/safety",
        "quantbridge/src/quantbridge/execution",
        "quantbridge/src/quantbridge/execution/clients",
        "quantbuild/src/quantbuild",
        "quantbuild/src/quantbuild/execution",
        "quantbuild/src/quantbuild/io",
    ):
        (dst / pkg).mkdir(parents=True, exist_ok=True)
        init = dst / pkg / "__init__.py"
        if not init.exists():
            init.write_text("", encoding="utf-8")

    mapping = [
        "quantbridge/src/quantbridge/safety/live_execution_gate.py",
        "quantbridge/src/quantbridge/safety/__init__.py",
        "quantbridge/src/quantbridge/execution/clients/ctrader_openapi_client.py",
        "quantbridge/src/quantbridge/execution/errors.py",
        "quantbridge/src/quantbridge/execution/models.py",
        "quantbuild/src/quantbuild/execution/broker_oanda.py",
        "quantbuild/src/quantbuild/io/oanda_loader.py",
    ]
    for rel in mapping:
        src = ROOT / rel
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)


def _pythonpath(scratch: Path) -> str:
    return (
        f"{scratch / 'quantbridge' / 'src'}:"
        f"{scratch / 'quantbuild' / 'src'}:"
        f"{scratch / 'quantbuild'}"
    )


def _run(scratch: Path, code: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = _pythonpath(scratch)
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(scratch),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


CONNECT_PROBE = textwrap.dedent(
    """
    from quantbridge.execution.clients.ctrader_openapi_client import CTraderOpenApiClient
    from quantbridge.safety import live_execution_gate as g
    g.default_bridge_env_files = lambda root=None: []
    import os
    os.environ.pop("QUANTMETRICS_EXECUTION_AUTHORIZED", None)
    os.environ["QUANTMETRICS_ALLOWED_ACCOUNT_IDS"] = "12345678"
    os.environ["QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS"] = "demo"
    c = CTraderOpenApiClient("12345678", "t"*40, environment="prod")
    try:
        c.connect()
        print("MUTATION_UNDETECTED")
        raise SystemExit(0)
    except Exception as e:
        print("DENIED", type(e).__name__, e)
        raise SystemExit(2)
    """
)

ORDERS_PROBES = {
    "place": 'c.submit_market_order(units=1)',
    "close": 'c.close_trade("1")',
    "modify": 'c.modify_trade("1", sl=1.0)',
}


def _orders_probe(call: str) -> str:
    return textwrap.dedent(
        f"""
        from quantbridge.execution.clients.ctrader_openapi_client import CTraderOpenApiClient
        from quantbridge.safety import live_execution_gate as g
        g.default_bridge_env_files = lambda root=None: []
        import os
        os.environ.pop("QUANTMETRICS_EXECUTION_AUTHORIZED", None)
        os.environ["QUANTMETRICS_ALLOWED_ACCOUNT_IDS"] = "12345678"
        os.environ["QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS"] = "demo"
        c = CTraderOpenApiClient("12345678", "t"*40, environment="demo")
        c.connected = True
        try:
            {call}
            print("MUTATION_UNDETECTED")
            raise SystemExit(0)
        except Exception as e:
            print("DENIED", type(e).__name__, e)
            raise SystemExit(2)
        """
    )


def test_control_unmutated_connect_denies(tmp_path):
    scratch = tmp_path / "ctrl"
    scratch.mkdir()
    _copy_sources(scratch)
    proc = _run(scratch, CONNECT_PROBE)
    assert proc.returncode == 2
    assert "MUTATION_UNDETECTED" not in proc.stdout


@pytest.mark.parametrize("kind,call", list(ORDERS_PROBES.items()))
def test_control_unmutated_orders_deny(tmp_path, kind, call):
    scratch = tmp_path / f"ctrl-{kind}"
    scratch.mkdir()
    _copy_sources(scratch)
    proc = _run(scratch, _orders_probe(call))
    assert proc.returncode == 2
    assert "MUTATION_UNDETECTED" not in proc.stdout


def test_mutation_remove_session_gate_connect(tmp_path):
    scratch = tmp_path / "mut-session"
    scratch.mkdir()
    _copy_sources(scratch)
    target = scratch / "quantbridge/src/quantbridge/execution/clients/ctrader_openapi_client.py"
    text = target.read_text(encoding="utf-8")
    mutated = text.replace("self._assert_session_gate()", "pass  # mutated-session", 1)
    assert "mutated-session" in mutated
    target.write_text(mutated, encoding="utf-8")
    proc = _run(scratch, CONNECT_PROBE)
    # Without session gate, typo env reaches SDK import / returns False — not LiveExecutionDenied.
    assert proc.returncode != 2 or "LiveExecutionDenied" not in proc.stdout


def test_mutation_remove_orders_gates(tmp_path):
    scratch = tmp_path / "mut-orders"
    scratch.mkdir()
    _copy_sources(scratch)
    target = scratch / "quantbridge/src/quantbridge/execution/clients/ctrader_openapi_client.py"
    text = target.read_text(encoding="utf-8")
    mutated = text.replace("self._assert_orders_gate()", "pass  # mutated-orders")
    assert mutated.count("mutated-orders") >= 3
    target.write_text(mutated, encoding="utf-8")
    for call in ORDERS_PROBES.values():
        proc = _run(scratch, _orders_probe(call))
        assert "MUTATION_UNDETECTED" in proc.stdout or "LiveExecutionDenied" not in proc.stdout


def test_mutation_restore_fail_open_host_selects_live(tmp_path):
    scratch = tmp_path / "mut-host"
    scratch.mkdir()
    _copy_sources(scratch)
    target = scratch / "quantbridge/src/quantbridge/execution/clients/ctrader_openapi_client.py"
    text = target.read_text(encoding="utf-8")
    text = text.replace("self._assert_session_gate()", "pass  # mutated-session", 1)
    # Inject fail-open ternary after EndPoints import by replacing resolve block.
    pattern = re.compile(
        r"from quantbridge\.safety\.live_execution_gate import resolve_ctrader_host\n"
        r"\n"
        r"        host_kind = resolve_ctrader_host\(str\(self\.environment\)\)\n"
        r"        host = \(\n"
        r"            EndPoints\.PROTOBUF_DEMO_HOST\n"
        r"            if host_kind == \"demo\"\n"
        r"            else EndPoints\.PROTOBUF_LIVE_HOST\n"
        r"        \)",
        re.M,
    )
    mutated, n = pattern.subn(
        'host = EndPoints.PROTOBUF_DEMO_HOST if self.environment.lower() == "demo" '
        "else EndPoints.PROTOBUF_LIVE_HOST",
        text,
        count=1,
    )
    assert n == 1, "host selection block not found for mutation"
    target.write_text(mutated, encoding="utf-8")

    probe = textwrap.dedent(
        """
        import sys
        from types import ModuleType
        from quantbridge.execution.clients.ctrader_openapi_client import CTraderOpenApiClient
        from quantbridge.safety import live_execution_gate as g
        g.default_bridge_env_files = lambda root=None: []
        import os
        os.environ["QUANTMETRICS_ALLOWED_ACCOUNT_IDS"] = "12345678"
        os.environ["QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS"] = "demo"
        chosen = {}
        fake = ModuleType("ctrader_open_api")
        class EndPoints:
            PROTOBUF_DEMO_HOST = "DEMO"
            PROTOBUF_LIVE_HOST = "LIVE"
            PROTOBUF_PORT = 1
        class TcpProtocol: pass
        class Client:
            def __init__(self, host, *a, **k):
                chosen["host"] = host
                raise RuntimeError("stop_after_host")
            def setMessageReceivedCallback(self, cb): pass
            def startService(self): pass
            def whenConnected(self, failAfterFailures=1): return None
        fake.Client = Client
        fake.EndPoints = EndPoints
        fake.TcpProtocol = TcpProtocol
        sys.modules["ctrader_open_api"] = fake
        pb = ModuleType("ctrader_open_api.messages.OpenApiMessages_pb2")
        for name in ("ProtoOAAccountAuthReq", "ProtoOAApplicationAuthReq", "ProtoOASymbolsListReq"):
            setattr(pb, name, lambda **k: None)
        sys.modules["ctrader_open_api.messages"] = ModuleType("ctrader_open_api.messages")
        sys.modules["ctrader_open_api.messages.OpenApiMessages_pb2"] = pb
        twisted = ModuleType("twisted")
        internet = ModuleType("twisted.internet")
        class reactor:
            running = True
            @staticmethod
            def run(*a, **k): pass
        threads = ModuleType("twisted.internet.threads")
        def blockingCallFromThread(r, f):
            return f()
        threads.blockingCallFromThread = blockingCallFromThread
        internet.reactor = reactor
        twisted.internet = internet
        sys.modules["twisted"] = twisted
        sys.modules["twisted.internet"] = internet
        sys.modules["twisted.internet.threads"] = threads
        c = CTraderOpenApiClient("12345678", "t"*40, environment="prod")
        try:
            c.connect()
        except Exception as e:
            print("ERR", e)
        print("HOST", chosen.get("host"))
        if chosen.get("host") == "LIVE":
            print("MUTATION_UNDETECTED_FAIL_OPEN")
            raise SystemExit(0)
        raise SystemExit(1)
        """
    )
    proc = _run(scratch, probe)
    assert "MUTATION_UNDETECTED_FAIL_OPEN" in proc.stdout, proc.stdout + proc.stderr


def test_mutation_oanda_gates_removed(tmp_path):
    scratch = tmp_path / "mut-oanda"
    scratch.mkdir()
    _copy_sources(scratch)
    target = scratch / "quantbuild/src/quantbuild/execution/broker_oanda.py"
    text = target.read_text(encoding="utf-8")
    mutated = text.replace(
        '_oanda_gate("SESSION", environment=self.environment, account_id=self.account_id)',
        "pass  # mutated-session",
    ).replace(
        '_oanda_gate("ORDERS", environment=self.environment, account_id=self.account_id)',
        "pass  # mutated-orders",
    )
    assert "mutated-session" in mutated and "mutated-orders" in mutated
    target.write_text(mutated, encoding="utf-8")

    connect_probe = textwrap.dedent(
        """
        import os
        os.environ.pop("QUANTMETRICS_EXECUTION_AUTHORIZED", None)
        os.environ.pop("QUANTMETRICS_ALLOWED_ACCOUNT_IDS", None)
        from src.quantbuild.execution.broker_oanda import OandaBroker
        b = OandaBroker(account_id="001", token="tok", environment="practice")
        try:
            b.connect()
        except Exception as e:
            print("ERR", type(e).__name__, e)
            if "LiveExecutionDenied" in type(e).__name__ or "gate" in str(e).lower():
                raise SystemExit(2)
        print("MUTATION_UNDETECTED")
        """
    )
    order_probe = textwrap.dedent(
        """
        import os
        os.environ.pop("QUANTMETRICS_EXECUTION_AUTHORIZED", None)
        os.environ["QUANTMETRICS_ALLOWED_ACCOUNT_IDS"] = "001"
        os.environ["QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS"] = "practice"
        from src.quantbuild.execution.broker_oanda import OandaBroker
        b = OandaBroker(account_id="001", token="tok", environment="practice")
        b._connected = True
        b._client = object()
        try:
            b.submit_market_order()
        except Exception as e:
            print("ERR", type(e).__name__, e)
            if "LiveExecutionDenied" in type(e).__name__ or "execution_not_authorized" in str(e):
                raise SystemExit(2)
        print("MUTATION_UNDETECTED")
        """
    )
    for probe in (connect_probe, order_probe):
        proc = _run(scratch, probe)
        assert "MUTATION_UNDETECTED" in proc.stdout, proc.stdout + proc.stderr
