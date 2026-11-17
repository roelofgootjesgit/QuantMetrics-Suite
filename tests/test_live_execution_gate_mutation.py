"""Issue #104 PR-A — scratch-copy mutation proofs (B2): every wire must be KILLED."""
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
        "quantbuild/src/quantbuild/execution/broker_ctrader.py",
        "quantbuild/src/quantbuild/io/oanda_loader.py",
        "quantbuild/src/quantbuild/config.py",
        "quantbuild/src/quantbuild/suite_layout.py",
        "quantmetrics_os/orchestrator/quantmetrics.py",
        "quantbuild/scripts/vps/run_live.sh",
    ]
    for rel in mapping:
        src = ROOT / rel
        if not src.exists():
            continue
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)


def _pythonpath(scratch: Path) -> str:
    return (
        f"{scratch / 'quantbridge' / 'src'}:"
        f"{scratch / 'quantbuild' / 'src'}:"
        f"{scratch / 'quantbuild'}:"
        f"{scratch}"
    )


def _run(scratch: Path, code: str, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for k in (
        "QUANTMETRICS_EXECUTION_AUTHORIZED",
        "QUANTMETRICS_ALLOWED_ACCOUNT_IDS",
        "QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS",
    ):
        env.pop(k, None)
    env["PYTHONPATH"] = _pythonpath(scratch)
    if extra_env:
        env.update(extra_env)
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
    "place": "c.submit_market_order(units=1)",
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


def test_mutation_remove_session_gate_connect_killed(tmp_path):
    """Removing session gate must allow connect path past LiveExecutionDenied (KILLED)."""
    scratch = tmp_path / "mut-session"
    scratch.mkdir()
    _copy_sources(scratch)
    target = scratch / "quantbridge/src/quantbridge/execution/clients/ctrader_openapi_client.py"
    text = target.read_text(encoding="utf-8")
    mutated = text.replace("self._assert_session_gate()", "pass  # mutated-session", 1)
    assert "mutated-session" in mutated
    target.write_text(mutated, encoding="utf-8")
    proc = _run(scratch, CONNECT_PROBE)
    assert proc.returncode != 2 or "LiveExecutionDenied" not in proc.stdout, proc.stdout


def test_mutation_remove_orders_gates_killed(tmp_path):
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


def test_mutation_restore_fail_open_host_selects_live_killed(tmp_path):
    scratch = tmp_path / "mut-host"
    scratch.mkdir()
    _copy_sources(scratch)
    target = scratch / "quantbridge/src/quantbridge/execution/clients/ctrader_openapi_client.py"
    text = target.read_text(encoding="utf-8")
    text = text.replace("self._assert_session_gate()", "pass  # mutated-session", 1)
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
            print("MUTATION_KILLED_FAIL_OPEN")
            raise SystemExit(0)
        raise SystemExit(1)
        """
    )
    proc = _run(scratch, probe)
    assert "MUTATION_KILLED_FAIL_OPEN" in proc.stdout, proc.stdout + proc.stderr


def test_mutation_oanda_gates_removed_killed(tmp_path):
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

    probes = {
        "connect": textwrap.dedent(
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
        ),
        "submit": textwrap.dedent(
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
        ),
        "close": textwrap.dedent(
            """
            import os
            os.environ.pop("QUANTMETRICS_EXECUTION_AUTHORIZED", None)
            os.environ["QUANTMETRICS_ALLOWED_ACCOUNT_IDS"] = "001"
            os.environ["QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS"] = "practice"
            from src.quantbuild.execution.broker_oanda import OandaBroker
            b = OandaBroker(account_id="001", token="tok", environment="practice")
            b._connected = True
            class C:
                def request(self, r):
                    print("REQUEST_FIRED")
                    return {}
            b._client = C()
            try:
                b.close_trade("1")
            except Exception as e:
                print("ERR", type(e).__name__, e)
                if "LiveExecutionDenied" in type(e).__name__:
                    raise SystemExit(2)
            print("MUTATION_UNDETECTED")
            """
        ),
        "modify": textwrap.dedent(
            """
            import os
            os.environ.pop("QUANTMETRICS_EXECUTION_AUTHORIZED", None)
            os.environ["QUANTMETRICS_ALLOWED_ACCOUNT_IDS"] = "001"
            os.environ["QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS"] = "practice"
            from src.quantbuild.execution.broker_oanda import OandaBroker
            b = OandaBroker(account_id="001", token="tok", environment="practice")
            b._connected = True
            class C:
                def request(self, r):
                    print("REQUEST_FIRED")
                    return {}
            b._client = C()
            try:
                b.modify_trade("1", sl=1.0)
            except Exception as e:
                print("ERR", type(e).__name__, e)
                if "LiveExecutionDenied" in type(e).__name__:
                    raise SystemExit(2)
            print("MUTATION_UNDETECTED")
            """
        ),
    }
    for name, probe in probes.items():
        proc = _run(scratch, probe)
        assert "MUTATION_UNDETECTED" in proc.stdout, f"{name}: {proc.stdout}\n{proc.stderr}"


def test_mutation_loader_gate_removed_killed(tmp_path):
    scratch = tmp_path / "mut-loader"
    scratch.mkdir()
    _copy_sources(scratch)
    target = scratch / "quantbuild/src/quantbuild/io/oanda_loader.py"
    text = target.read_text(encoding="utf-8")
    # Remove assert_live_execution_allowed call block by replacing with pass
    mutated = text.replace(
        "assert_live_execution_allowed(",
        "False and assert_live_execution_allowed(",
        1,
    )
    assert "False and assert_live_execution_allowed" in mutated
    target.write_text(mutated, encoding="utf-8")
    probe = textwrap.dedent(
        """
        import os, sys
        from types import ModuleType
        os.environ.pop("QUANTMETRICS_EXECUTION_AUTHORIZED", None)
        os.environ.pop("QUANTMETRICS_ALLOWED_ACCOUNT_IDS", None)
        fake = ModuleType("oandapyV20")
        class API:
            def __init__(self, *a, **k):
                print("API_CTOR")
        fake.API = API
        sys.modules["oandapyV20"] = fake
        from src.quantbuild.io.oanda_loader import _get_oanda_client
        try:
            _get_oanda_client(token="tok", environment="practice", account_id="001")
            print("MUTATION_UNDETECTED")
        except Exception as e:
            print("ERR", type(e).__name__, e)
            if "LiveExecutionDenied" in type(e).__name__ or "account_allowlist" in str(e):
                raise SystemExit(2)
            print("MUTATION_UNDETECTED")
        """
    )
    proc = _run(scratch, probe)
    assert "MUTATION_UNDETECTED" in proc.stdout, proc.stdout + proc.stderr


def test_mutation_dotenv_scan_noop_killed(tmp_path):
    """If env_file_contains_gate_keys always returns False, malicious dotenv loads."""
    scratch = tmp_path / "mut-scan"
    scratch.mkdir()
    _copy_sources(scratch)
    target = scratch / "quantbridge/src/quantbridge/safety/live_execution_gate.py"
    text = target.read_text(encoding="utf-8")
    mutated = text.replace(
        "def env_file_contains_gate_keys(path: Path | str) -> bool:",
        "def env_file_contains_gate_keys(path: Path | str) -> bool:\n"
        "    return False  # mutated-scan\n"
        "def _env_file_contains_gate_keys_orig(path: Path | str) -> bool:",
        1,
    )
    assert "mutated-scan" in mutated
    target.write_text(mutated, encoding="utf-8")
    dotenv = scratch / "evil.env"
    dotenv.write_text("export QUANTMETRICS_EXECUTION_AUTHORIZED=1\n", encoding="utf-8")
    probe = textwrap.dedent(
        f"""
        from pathlib import Path
        from quantbridge.safety.live_execution_gate import (
            LiveExecutionDenied,
            assert_dotenv_path_has_no_gate_keys,
            env_file_contains_gate_keys,
            load_dotenv_refusing_gate_keys,
        )
        p = Path({str(dotenv)!r})
        assert env_file_contains_gate_keys(p) is False
        try:
            assert_dotenv_path_has_no_gate_keys(p)
            print("SCAN_MUTATION_UNDETECTED")
        except LiveExecutionDenied:
            print("STILL_DENIED")
            raise SystemExit(2)
        """
    )
    proc = _run(scratch, probe)
    assert "SCAN_MUTATION_UNDETECTED" in proc.stdout, proc.stdout + proc.stderr


def test_mutation_truthy_auth_coercion_killed(tmp_path):
    """If ORDERS auth accepts truthy 'true', mutation is KILLED by probe seeing allow."""
    scratch = tmp_path / "mut-truthy"
    scratch.mkdir()
    _copy_sources(scratch)
    target = scratch / "quantbridge/src/quantbridge/safety/live_execution_gate.py"
    text = target.read_text(encoding="utf-8")
    mutated = text.replace(
        'if environ.get("QUANTMETRICS_EXECUTION_AUTHORIZED") != "1":',
        'if str(environ.get("QUANTMETRICS_EXECUTION_AUTHORIZED", "")).lower() not in {"1", "true", "yes"}:',
        1,
    )
    assert 'not in {"1", "true", "yes"}' in mutated
    target.write_text(mutated, encoding="utf-8")
    probe = textwrap.dedent(
        """
        from quantbridge.safety.live_execution_gate import (
            LiveExecutionDenied, LiveExecutionRequest, assert_live_execution_allowed,
        )
        environ = {
            "QUANTMETRICS_EXECUTION_AUTHORIZED": "true",
            "QUANTMETRICS_ALLOWED_ACCOUNT_IDS": "12345678",
            "QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS": "demo",
        }
        try:
            assert_live_execution_allowed(
                LiveExecutionRequest("ctrader", "demo", "12345678", "ORDERS"),
                environ=environ, env_file_paths=[],
            )
            print("MUTATION_UNDETECTED")
        except LiveExecutionDenied as e:
            print("DENIED", e)
            raise SystemExit(2)
        """
    )
    proc = _run(scratch, probe)
    assert "MUTATION_UNDETECTED" in proc.stdout, proc.stdout + proc.stderr


def test_mutation_live_freeze_bypass_killed(tmp_path):
    scratch = tmp_path / "mut-freeze"
    scratch.mkdir()
    _copy_sources(scratch)
    target = scratch / "quantbridge/src/quantbridge/safety/live_execution_gate.py"
    text = target.read_text(encoding="utf-8")
    mutated = text.replace(
        'if env == "live" and not live_host_enablement_satisfied(enablement_path=enablement_path):',
        'if False and env == "live" and not live_host_enablement_satisfied(enablement_path=enablement_path):',
        1,
    )
    assert "if False and env" in mutated
    target.write_text(mutated, encoding="utf-8")
    probe = textwrap.dedent(
        """
        from pathlib import Path
        from quantbridge.safety.live_execution_gate import (
            LiveExecutionDenied, LiveExecutionRequest, assert_live_execution_allowed,
        )
        environ = {
            "QUANTMETRICS_EXECUTION_AUTHORIZED": "1",
            "QUANTMETRICS_ALLOWED_ACCOUNT_IDS": "12345678",
            "QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS": "demo,live",
        }
        try:
            assert_live_execution_allowed(
                LiveExecutionRequest("ctrader", "live", "12345678", "SESSION"),
                environ=environ, env_file_paths=[],
                enablement_path=Path("/nonexistent/execution_authorization"),
            )
            print("MUTATION_UNDETECTED")
        except LiveExecutionDenied as e:
            print("DENIED", e)
            raise SystemExit(2)
        """
    )
    proc = _run(scratch, probe)
    assert "MUTATION_UNDETECTED" in proc.stdout, proc.stdout + proc.stderr


def test_mutation_leading_zero_accepted_killed(tmp_path):
    scratch = tmp_path / "mut-zero"
    scratch.mkdir()
    _copy_sources(scratch)
    target = scratch / "quantbridge/src/quantbridge/safety/live_execution_gate.py"
    text = target.read_text(encoding="utf-8")
    mutated = text.replace(
        'if text.startswith("0"):\n        raise LiveExecutionDenied("ctrader_account_id_leading_zero_rejected")',
        "if False:\n        raise LiveExecutionDenied('ctrader_account_id_leading_zero_rejected')",
        1,
    )
    assert "if False:" in mutated
    target.write_text(mutated, encoding="utf-8")
    probe = textwrap.dedent(
        """
        from quantbridge.safety.live_execution_gate import (
            LiveExecutionDenied, canonicalize_ctrader_account_id,
        )
        try:
            canonicalize_ctrader_account_id("0123")
            print("MUTATION_UNDETECTED")
        except LiveExecutionDenied:
            raise SystemExit(2)
        """
    )
    proc = _run(scratch, probe)
    assert "MUTATION_UNDETECTED" in proc.stdout, proc.stdout + proc.stderr


def test_mutation_empty_env_allowlist_fail_open_killed(tmp_path):
    scratch = tmp_path / "mut-empty-env"
    scratch.mkdir()
    _copy_sources(scratch)
    target = scratch / "quantbridge/src/quantbridge/safety/live_execution_gate.py"
    text = target.read_text(encoding="utf-8")
    mutated = text.replace(
        'if raw is None or str(raw).strip() == "":\n        return []',
        'if raw is None or str(raw).strip() == "":\n        return _default_env_allowlist(provider)  # mutated-empty',
        1,
    )
    assert "mutated-empty" in mutated
    target.write_text(mutated, encoding="utf-8")
    probe = textwrap.dedent(
        """
        from quantbridge.safety.live_execution_gate import (
            LiveExecutionDenied, LiveExecutionRequest, assert_live_execution_allowed,
        )
        environ = {
            "QUANTMETRICS_EXECUTION_AUTHORIZED": "1",
            "QUANTMETRICS_ALLOWED_ACCOUNT_IDS": "12345678",
            "QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS": "",
        }
        try:
            assert_live_execution_allowed(
                LiveExecutionRequest("ctrader", "demo", "12345678", "ORDERS"),
                environ=environ, env_file_paths=[],
            )
            print("MUTATION_UNDETECTED")
        except LiveExecutionDenied as e:
            print("DENIED", e)
            raise SystemExit(2)
        """
    )
    proc = _run(scratch, probe)
    assert "MUTATION_UNDETECTED" in proc.stdout, proc.stdout + proc.stderr


def test_mutation_ctrader_practice_allowed_killed(tmp_path):
    scratch = tmp_path / "mut-practice"
    scratch.mkdir()
    _copy_sources(scratch)
    target = scratch / "quantbridge/src/quantbridge/safety/live_execution_gate.py"
    text = target.read_text(encoding="utf-8")
    mutated = text.replace(
        'if provider.strip().lower() == "ctrader" and env == "practice":\n'
        '        raise LiveExecutionDenied("ctrader_practice_environment_rejected")',
        "if False:\n        raise LiveExecutionDenied('ctrader_practice_environment_rejected')",
        1,
    )
    assert "if False:" in mutated
    target.write_text(mutated, encoding="utf-8")
    probe = textwrap.dedent(
        """
        from quantbridge.safety.live_execution_gate import (
            LiveExecutionDenied, LiveExecutionRequest, assert_live_execution_allowed,
        )
        environ = {
            "QUANTMETRICS_EXECUTION_AUTHORIZED": "1",
            "QUANTMETRICS_ALLOWED_ACCOUNT_IDS": "12345678",
            "QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS": "demo,practice",
        }
        try:
            assert_live_execution_allowed(
                LiveExecutionRequest("ctrader", "practice", "12345678", "SESSION"),
                environ=environ, env_file_paths=[],
            )
            print("MUTATION_UNDETECTED")
        except LiveExecutionDenied as e:
            print("DENIED", e)
            raise SystemExit(2)
        """
    )
    proc = _run(scratch, probe)
    assert "MUTATION_UNDETECTED" in proc.stdout, proc.stdout + proc.stderr


def test_mutation_hydrate_scan_removed_killed(tmp_path):
    scratch = tmp_path / "mut-hydrate"
    scratch.mkdir()
    _copy_sources(scratch)
    target = scratch / "quantbuild/src/quantbuild/execution/broker_ctrader.py"
    text = target.read_text(encoding="utf-8")
    mutated = text.replace(
        "if env_file_contains_gate_keys(env_path):\n"
        "                raise LiveExecutionDenied(\n"
        '                    f"gate_key_present_in_env_file:{env_path.resolve()}"\n'
        "                )",
        "if False:\n                raise LiveExecutionDenied('skip')",
        1,
    )
    assert "if False:" in mutated
    target.write_text(mutated, encoding="utf-8")
    bridge = scratch / "bridge"
    bridge.mkdir()
    (bridge / "local.env").write_text(
        "export QUANTMETRICS_EXECUTION_AUTHORIZED=1\nCTRADER_ACCOUNT_ID=99999999\n",
        encoding="utf-8",
    )
    probe = textwrap.dedent(
        f"""
        from pathlib import Path
        from src.quantbuild.execution.broker_ctrader import CTraderBroker
        from quantbridge.safety.live_execution_gate import LiveExecutionDenied
        b = CTraderBroker(account_id="", access_token="x"*40, mock_mode=True)
        try:
            b._hydrate_credentials_from_dotenv(Path({str(bridge)!r}))
            print("MUTATION_UNDETECTED", "acct", b.account_id)
        except LiveExecutionDenied as e:
            print("DENIED", e)
            raise SystemExit(2)
        """
    )
    proc = _run(scratch, probe)
    assert "MUTATION_UNDETECTED" in proc.stdout, proc.stdout + proc.stderr


def test_mutation_config_skip_refuse_killed(tmp_path):
    scratch = tmp_path / "mut-config"
    scratch.mkdir()
    _copy_sources(scratch)
    target = scratch / "quantbuild/src/quantbuild/config.py"
    text = target.read_text(encoding="utf-8")
    # Replace refuse loader with plain load_dotenv
    mutated = text.replace(
        "load_dotenv_refusing_gate_keys(dotenv_path, override=True)",
        "from dotenv import load_dotenv; load_dotenv(dotenv_path, override=True)  # mutated",
        1,
    )
    assert "mutated" in mutated
    target.write_text(mutated, encoding="utf-8")
    work = scratch / "cwd"
    work.mkdir()
    (work / ".env").write_text("export QUANTMETRICS_EXECUTION_AUTHORIZED=1\n", encoding="utf-8")
    probe = textwrap.dedent(
        f"""
        import os, sys
        os.chdir({str(work)!r})
        for k in ("QUANTMETRICS_EXECUTION_AUTHORIZED", "QUANTMETRICS_ALLOWED_ACCOUNT_IDS",
                  "QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS"):
            os.environ.pop(k, None)
        try:
            import quantbuild.config  # noqa: F401
            auth = os.environ.get("QUANTMETRICS_EXECUTION_AUTHORIZED")
            print("AUTH", auth)
            if auth == "1":
                print("MUTATION_UNDETECTED")
                raise SystemExit(0)
            print("NO_AUTH")
            raise SystemExit(1)
        except Exception as e:
            print("ERR", type(e).__name__, e)
            raise SystemExit(2)
        """
    )
    proc = _run(scratch, probe)
    assert "MUTATION_UNDETECTED" in proc.stdout, proc.stdout + proc.stderr


def test_mutation_run_live_sh_skip_snapshot_killed(tmp_path):
    scratch = tmp_path / "mut-shell"
    scratch.mkdir()
    _copy_sources(scratch)
    script = scratch / "quantbuild/scripts/vps/run_live.sh"
    text = script.read_text(encoding="utf-8")
    mutated = text.replace(
        "if _gate_keys_changed; then",
        "if false; then  # mutated-shell",
        1,
    )
    assert "mutated-shell" in mutated
    script.write_text(mutated, encoding="utf-8")
    env_file = scratch / "evil.env"
    env_file.write_text("export QUANTMETRICS_EXECUTION_AUTHORIZED=1\n", encoding="utf-8")
    stub = scratch / "stub_py"
    stub.write_text(
        "#!/bin/sh\necho STUB_RAN AUTH=$QUANTMETRICS_EXECUTION_AUTHORIZED\nexit 0\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    clean = {
        k: v
        for k, v in os.environ.items()
        if k
        not in {
            "QUANTMETRICS_EXECUTION_AUTHORIZED",
            "QUANTMETRICS_ALLOWED_ACCOUNT_IDS",
            "QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS",
        }
    }
    proc = subprocess.run(
        ["bash", str(script), "live", "--dry-run"],
        cwd=str(scratch / "quantbuild"),
        env={
            **clean,
            "QUANTBUILD_ROOT": str(scratch / "quantbuild"),
            "QUANTBUILD_ORCHESTRATOR_ENV": str(env_file),
            "PYTHON": str(stub),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "STUB_RAN" in proc.stdout
    assert "AUTH=1" in proc.stdout
