"""Issue #104 PR-B — entrypoint E1–E9 behavioral deny-first tests."""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml

from quantbridge.safety.live_execution_gate import GATE_ENV_KEYS, LiveExecutionDenied

ROOT = Path(__file__).resolve().parents[1]


def _stub_filelock_if_missing() -> None:
    """Root CI installs suite requirements without quantbuild extras (filelock)."""
    try:
        import filelock  # noqa: F401
        return
    except ModuleNotFoundError:
        pass
    stub = ModuleType("filelock")

    class FileLock:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def acquire(self, *a, **k):
            return True

        def release(self, *a, **k):
            return None

    class Timeout(Exception):
        pass

    stub.FileLock = FileLock
    stub.Timeout = Timeout
    sys.modules["filelock"] = stub


@pytest.fixture
def deny_env(monkeypatch):
    for key in GATE_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(
        "quantbridge.safety.live_execution_gate.default_bridge_env_files",
        lambda root=None: [],
    )


def _minimal_cfg(**broker_extra: Any) -> dict:
    broker = {
        "provider": "ctrader",
        "environment": "demo",
        "account_id": "12345678",
        "mock_mode": True,
        "access_token": "x" * 40,
    }
    broker.update(broker_extra)
    return {
        "symbol": "XAUUSD",
        "broker": broker,
        "data": {"source": "yfinance"},
        "risk": {},
        "execution_guards": {},
        "order_management": {},
        "regime": {},
    }


def test_e1_app_live_real_without_auth_denied(deny_env, monkeypatch, tmp_path):
    """E1: app.py live --real without auth → nonzero before LiveRunner."""
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(
        yaml.safe_dump(
            _minimal_cfg(mock_mode=False, account_id="12345678"),
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_ACCOUNT_IDS", "12345678")
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS", "demo")
    # AUTH missing

    import src.quantbuild.app as app_mod

    runner_ctor: list[int] = []

    class BoomRunner:
        def __init__(self, *a, **k):
            runner_ctor.append(1)
            raise AssertionError("LiveRunner must not construct")

        def run(self):
            raise AssertionError("must not run")

    stub = ModuleType("src.quantbuild.execution.live_runner")
    stub.LiveRunner = BoomRunner
    monkeypatch.setitem(sys.modules, "src.quantbuild.execution.live_runner", stub)
    monkeypatch.setattr(app_mod, "validate_suite_layout", lambda: {})
    monkeypatch.setattr(app_mod, "setup_logging", lambda *a, **k: None)
    monkeypatch.setattr(app_mod, "load_config", lambda path: yaml.safe_load(cfg_path.read_text()))

    args = SimpleNamespace(config=str(cfg_path), dry_run=False, command="live", real=True)
    rc = app_mod.cmd_live(args)
    assert rc == 2
    assert runner_ctor == []


def test_e2_create_broker_non_mock_without_auth(deny_env, monkeypatch):
    """E2: create_broker non-mock without SESSION auth → deny; no broker."""
    from src.quantbuild.execution import broker_factory as bf

    monkeypatch.setattr(bf, "validate_suite_layout", lambda: {})
    ctor: list[int] = []

    class Boom:
        def __init__(self, *a, **k):
            ctor.append(1)
            raise AssertionError("must not construct")

    monkeypatch.setattr(bf, "CTraderBroker", Boom)
    with pytest.raises((LiveExecutionDenied, RuntimeError)):
        bf.create_broker(_minimal_cfg(mock_mode=False))
    assert ctor == []


def test_e3_bridge_openapi_broker_init_denied(deny_env, monkeypatch):
    """E3: QuantBridge CTraderBroker(mode=openapi) denied at init before client."""
    from quantbridge.execution.brokers import ctrader_broker as mod

    ctor: list[int] = []

    class BoomClient:
        def __init__(self, *a, **k):
            ctor.append(1)
            raise AssertionError("OpenAPI client must not construct")

    monkeypatch.setattr(mod, "CTraderOpenApiClient", BoomClient)
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_ACCOUNT_IDS", "12345678")
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS", "demo")
    with pytest.raises(LiveExecutionDenied):
        mod.CTraderBroker(
            account_id="12345678",
            access_token="t" * 40,
            environment="prod",  # typo env
            mode="openapi",
        )
    assert ctor == []


def test_e4_live_runner_real_without_auth(deny_env, monkeypatch):
    """E4: invoke real LiveRunner.run — ORDERS deny before broker.connect."""
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_ACCOUNT_IDS", "12345678")
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS", "demo")
    # AUTH missing
    _stub_filelock_if_missing()

    from src.quantbuild.execution.live_runner import LiveRunner

    connects: list[int] = []

    class FakeBroker:
        mock_mode = True
        is_connected = False

        def connect(self):
            connects.append(1)
            return True

        def disconnect(self):
            return None

    # Behavioral: construct via __new__ to avoid heavy __init__, then call real run().
    runner = object.__new__(LiveRunner)
    runner.cfg = _minimal_cfg(mock_mode=True, account_id="12345678")
    runner.dry_run = False
    runner._account_id = "12345678"
    runner.broker = FakeBroker()

    with pytest.raises((LiveExecutionDenied, RuntimeError)) as exc:
        runner.run()
    msg = str(exc.value).lower()
    assert "execution_not_authorized" in msg or "liveexecutiondenied" in type(exc.value).__name__.lower()
    assert connects == []


def test_e5_launch_live_safe_preflight_no_subprocess(deny_env, monkeypatch, tmp_path):
    """E5: launch_live_safe ORDERS deny → EXIT_PREFLIGHT; Popen never started."""
    cfg_path = tmp_path / "cfg.yaml"
    cfg = _minimal_cfg(mock_mode=False, account_id="12345678")
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    bridge = tmp_path / "quantbridge"
    (bridge / "src").mkdir(parents=True)
    (bridge / "src" / "quantbridge").mkdir()
    (bridge / "src" / "quantbridge" / "__init__.py").write_text("", encoding="utf-8")
    (bridge / "src" / "quantbridge" / "execution").mkdir()
    (bridge / "src" / "quantbridge" / "execution" / "__init__.py").write_text("", encoding="utf-8")
    (bridge / "src" / "quantbridge" / "execution" / "brokers").mkdir()
    (bridge / "src" / "quantbridge" / "execution" / "brokers" / "__init__.py").write_text(
        "", encoding="utf-8"
    )
    (bridge / "src" / "quantbridge" / "execution" / "brokers" / "ctrader_broker.py").write_text(
        "class CTraderBroker: pass\n", encoding="utf-8"
    )

    monkeypatch.setenv("QUANTMETRICS_ALLOWED_ACCOUNT_IDS", "12345678")
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS", "demo")
    monkeypatch.setenv("CTRADER_ACCOUNT_ID", "12345678")
    monkeypatch.setenv("CTRADER_ACCESS_TOKEN", "t" * 40)
    monkeypatch.setenv("CTRADER_CLIENT_ID", "cid")
    monkeypatch.setenv("CTRADER_CLIENT_SECRET", "sec")

    script = ROOT / "quantbuild/scripts/launch_live_safe.py"
    spec = importlib.util.spec_from_file_location("launch_live_safe", script)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    pops: list[int] = []

    def boom_popen(*a, **k):
        pops.append(1)
        raise AssertionError("Popen must not start")

    monkeypatch.setattr(mod.subprocess, "Popen", boom_popen)
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    args = SimpleNamespace(
        config=str(cfg_path),
        bridge_root=str(bridge),
        require_unpaused=False,
        run_recovery_first=False,
        recovery_config="configs/x.yaml",
        account_state_file="x.json",
        max_runtime_seconds=1,
        heartbeat_seconds=1,
        log_file=str(tmp_path / "launch.log"),
    )
    # Patch load_config used inside preflight
    monkeypatch.setattr(mod, "load_config", lambda p: cfg)
    ok, errors, warnings, creds, loaded = mod._preflight(args)
    assert ok is False
    assert any("live execution denied" in e.lower() or "denied" in e.lower() for e in errors)
    assert pops == []


def test_e6_mock_and_dry_run_succeed_without_auth(deny_env, monkeypatch):
    """E6: mock create_broker and dry_run LiveRunner path do not require ORDERS auth."""
    from src.quantbuild.execution.broker_factory import create_broker

    broker = create_broker(_minimal_cfg(mock_mode=True))
    assert getattr(broker, "mock_mode", True) is True

    # dry_run cmd_live path: preflight skipped when dry_run True
    import src.quantbuild.app as app_mod

    ran: list[int] = []

    class OkRunner:
        def __init__(self, cfg, dry_run=True):
            assert dry_run is True

        def run(self):
            ran.append(1)

    stub = ModuleType("src.quantbuild.execution.live_runner")
    stub.LiveRunner = OkRunner
    monkeypatch.setitem(sys.modules, "src.quantbuild.execution.live_runner", stub)
    monkeypatch.setattr(app_mod, "setup_logging", lambda *a, **k: None)
    monkeypatch.setattr(app_mod, "load_config", lambda path: _minimal_cfg())
    args = SimpleNamespace(config=None, dry_run=True, command="live", real=False)
    assert app_mod.cmd_live(args) == 0
    assert ran == [1]


def test_e7_root_demo_unchanged():
    """E7: run_demo still succeeds (smoke that PR-B did not break demo)."""
    proc = subprocess.run(
        [sys.executable, str(ROOT / "run_demo.py")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "VALIDATION_REQUIRED" in proc.stdout


def test_e8_create_broker_gate_import_fail(deny_env, monkeypatch):
    """E8: create_broker(non-mock) when gate import fails → deny."""
    from src.quantbuild.execution import broker_factory as bf
    from src.quantbuild.execution import live_execution_preflight as pref

    monkeypatch.setattr(bf, "validate_suite_layout", lambda: {})

    def boom(**kwargs):
        raise RuntimeError("LiveExecutionDenied: gate_import_failed: simulated")

    monkeypatch.setattr(bf, "preflight_live_execution", boom)
    with pytest.raises(RuntimeError) as exc:
        bf.create_broker(_minimal_cfg(mock_mode=False))
    assert "gate_import_failed" in str(exc.value)


def test_e9_oanda_connect_gate_import_fail_still_denied(deny_env, monkeypatch):
    """E9: OandaBroker.connect when gate import fails → deny (PR-A invariant)."""
    import src.quantbuild.execution.broker_oanda as mod

    real_import = __import__

    def blocked(name, *args, **kwargs):
        if name.startswith("quantbridge.safety"):
            raise ImportError("simulated_missing_gate")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", blocked)
    with pytest.raises(RuntimeError) as exc:
        mod._oanda_gate("SESSION", environment="practice", account_id="001")
    assert "gate_import_failed" in str(exc.value)


def test_e_orchestrator_real_no_spawn(deny_env, monkeypatch, tmp_path):
    """Orchestrator build --real denies before subprocess.call."""
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(yaml.safe_dump(_minimal_cfg(mock_mode=False)), encoding="utf-8")

    orch = ROOT / "quantmetrics_os/orchestrator/quantmetrics.py"
    spec = importlib.util.spec_from_file_location("qm_orch_e", orch)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # Avoid running module-level side effects beyond defs — file only defines funcs at import
    spec.loader.exec_module(mod)

    calls: list[int] = []

    def boom_call(*a, **k):
        calls.append(1)
        raise AssertionError("subprocess must not spawn")

    monkeypatch.setattr(mod.subprocess, "call", boom_call)
    monkeypatch.setenv("QUANTBUILD_ROOT", str(ROOT / "quantbuild"))
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_ACCOUNT_IDS", "12345678")
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS", "demo")

    args = SimpleNamespace(
        config=str(cfg_path),
        real=True,
        dry_run=False,
        notify_start=False,
        notify_components="build",
    )
    # load_config inside cmd_build — point at our yaml via absolute path
    rc = mod.cmd_build(args)
    assert rc == 2
    assert calls == []


def test_e_diagnose_non_mock_denied(deny_env, monkeypatch, tmp_path):
    """diagnose_ctrader_connect non-mock without account allowlist denies before create_broker."""
    script = ROOT / "quantbuild/scripts/diagnose_ctrader_connect.py"
    spec = importlib.util.spec_from_file_location("diag_e", script)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    # Missing account allowlist ⇒ SESSION deny (AUTH not required for SESSION).
    cfg = _minimal_cfg(mock_mode=False, environment="demo")
    monkeypatch.setattr(mod, "load_config", lambda p: cfg)
    for key in GATE_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    ctor: list[int] = []

    def boom_create(c):
        ctor.append(1)
        raise AssertionError("create_broker must not run")

    monkeypatch.setattr(mod, "create_broker", boom_create)
    monkeypatch.setattr(
        sys,
        "argv",
        ["diagnose_ctrader_connect.py", "-c", "configs/x.yaml"],
    )
    with pytest.raises((LiveExecutionDenied, RuntimeError, SystemExit)):
        mod.main()
    assert ctor == []


def test_e_oanda_create_broker_denied_zero_ctor(deny_env, monkeypatch):
    """Oanda create_broker without SESSION allowlist — deny; zero OandaBroker ctor."""
    from src.quantbuild.execution import broker_factory as bf

    monkeypatch.setattr(bf, "validate_suite_layout", lambda: {})
    ctor: list[int] = []

    class Boom:
        def __init__(self, *a, **k):
            ctor.append(1)
            raise AssertionError("OandaBroker must not construct")

    monkeypatch.setattr(bf, "OandaBroker", Boom)
    cfg = {
        "broker": {
            "provider": "oanda",
            "environment": "practice",
            "account_id": "001-practice",
            "token": "tok",
        }
    }
    with pytest.raises((LiveExecutionDenied, RuntimeError)):
        bf.create_broker(cfg)
    assert ctor == []


@pytest.mark.parametrize("provider_cfg", [
    {"provider": "ctrader", "environment": "demo", "account_id": "12345678", "mock_mode": False},
    {"provider": "oanda", "environment": "practice", "account_id": "001", "token": "tok"},
])
def test_e_validate_suite_layout_mandatory_before_broker(deny_env, monkeypatch, provider_cfg):
    """validate_suite_layout failure denies before any broker constructor."""
    from src.quantbuild.execution import broker_factory as bf
    from src.quantbuild.suite_layout import SuiteLayoutError

    layout_calls: list[int] = []
    ctor: list[int] = []

    def boom_layout():
        layout_calls.append(1)
        raise SuiteLayoutError("layout_invalid_for_test")

    class Boom:
        def __init__(self, *a, **k):
            ctor.append(1)
            raise AssertionError("broker must not construct")

    monkeypatch.setattr(bf, "validate_suite_layout", boom_layout)
    monkeypatch.setattr(bf, "CTraderBroker", Boom)
    monkeypatch.setattr(bf, "OandaBroker", Boom)
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_ACCOUNT_IDS", provider_cfg["account_id"])
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS", provider_cfg["environment"])
    monkeypatch.setenv("QUANTMETRICS_EXECUTION_AUTHORIZED", "1")

    with pytest.raises(SuiteLayoutError):
        bf.create_broker({"broker": provider_cfg, "symbol": "XAUUSD"})
    assert layout_calls == [1]
    assert ctor == []


def test_e_qb_ctrader_smoke_non_mock_denied(deny_env, monkeypatch, tmp_path):
    """QuantBuild ctrader_smoke non-mock without ORDERS auth — no create_broker."""
    script = ROOT / "quantbuild/scripts/ctrader_smoke.py"
    spec = importlib.util.spec_from_file_location("qb_smoke_e", script)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    cfg = _minimal_cfg(mock_mode=False, account_id="12345678")
    monkeypatch.setattr(mod, "load_config", lambda p: cfg)
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_ACCOUNT_IDS", "12345678")
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS", "demo")
    # AUTH missing

    ctor: list[int] = []

    def boom_create(c):
        ctor.append(1)
        raise AssertionError("create_broker must not run")

    monkeypatch.setattr(mod, "create_broker", boom_create)
    monkeypatch.setattr(sys, "argv", ["ctrader_smoke.py", "--config", "x.yaml"])
    with pytest.raises((LiveExecutionDenied, RuntimeError, SystemExit)):
        mod.main()
    assert ctor == []


def test_e_bridge_ctrader_smoke_openapi_denied(deny_env, monkeypatch, tmp_path):
    """Bridge ctrader_smoke openapi without ORDERS — no CTraderBroker ctor."""
    script = ROOT / "quantbridge/scripts/ctrader_smoke.py"
    spec = importlib.util.spec_from_file_location("bridge_smoke_e", script)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    monkeypatch.setattr(mod, "load_local_env", lambda: None)
    monkeypatch.setattr(
        mod,
        "load_config",
        lambda p: {
            "broker": {"environment": "demo", "mode": "openapi", "account_id": "12345678"},
            "symbol": {"internal": "XAUUSD"},
            "execution": {},
        },
    )
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_ACCOUNT_IDS", "12345678")
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS", "demo")
    monkeypatch.setenv("CTRADER_ACCOUNT_ID", "12345678")
    monkeypatch.setenv("CTRADER_ACCESS_TOKEN", "t" * 40)

    ctor: list[int] = []

    class Boom:
        def __init__(self, *a, **k):
            ctor.append(1)
            raise AssertionError("CTraderBroker must not construct")

    monkeypatch.setattr(mod, "CTraderBroker", Boom)
    monkeypatch.setattr(sys, "argv", ["ctrader_smoke.py", "--mode", "openapi", "--config", "x.yaml"])
    with pytest.raises((LiveExecutionDenied, RuntimeError, SystemExit)):
        mod.main()
    assert ctor == []


@pytest.mark.parametrize(
    "line",
    [
        "QUANTMETRICS_EXECUTION_AUTHORIZED=1",
        "export QUANTMETRICS_EXECUTION_AUTHORIZED=1",
        "QUANTMETRICS_EXECUTION_AUTHORIZED = 1",
    ],
)
def test_e_bridge_smoke_dotenv_gate_key_denied(deny_env, monkeypatch, tmp_path, line):
    """Bridge smoke load_local_env denies dotenv/export gate-key variants."""
    script = ROOT / "quantbridge/scripts/ctrader_smoke.py"
    # Point ROOT used by script via chdir + env file in tmp — import and call loader with patched ROOT
    spec = importlib.util.spec_from_file_location("bridge_smoke_dotenv", script)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    monkeypatch.setattr(mod, "ROOT", tmp_path)
    (tmp_path / "local.env").write_text(line + "\nCTRADER_ACCOUNT_ID=12345678\n", encoding="utf-8")
    with pytest.raises(LiveExecutionDenied):
        mod.load_local_env()


def test_e_order_lifecycle_openapi_denied(deny_env, monkeypatch):
    """run_order_lifecycle_check openapi without ORDERS — no CTraderBroker."""
    script = ROOT / "quantbridge/scripts/run_order_lifecycle_check.py"
    spec = importlib.util.spec_from_file_location("lifecycle_e", script)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    monkeypatch.setattr(mod, "load_env_files", lambda: None)
    monkeypatch.setattr(
        mod,
        "load_config",
        lambda p: {
            "broker": {"environment": "demo", "mode": "openapi", "account_id": "12345678"},
            "symbol": {"internal": "XAUUSD"},
            "execution": {"units": 1.0},
        },
    )
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_ACCOUNT_IDS", "12345678")
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS", "demo")
    monkeypatch.setenv("CTRADER_ACCOUNT_ID", "12345678")
    monkeypatch.setenv("CTRADER_ACCESS_TOKEN", "t" * 40)

    ctor: list[int] = []

    class Boom:
        def __init__(self, *a, **k):
            ctor.append(1)
            raise AssertionError("must not construct")

    monkeypatch.setattr(mod, "CTraderBroker", Boom)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_order_lifecycle_check.py", "--mode", "openapi", "--config", "x.yaml"],
    )
    with pytest.raises((LiveExecutionDenied, RuntimeError, SystemExit)):
        mod.main()
    assert ctor == []


@pytest.mark.parametrize(
    "line",
    [
        "export QUANTMETRICS_ALLOWED_ACCOUNT_IDS=12345678",
        "QUANTMETRICS_EXECUTION_AUTHORIZED=1",
    ],
)
def test_e_lifecycle_dotenv_gate_key_denied(deny_env, monkeypatch, tmp_path, line):
    script = ROOT / "quantbridge/scripts/run_order_lifecycle_check.py"
    spec = importlib.util.spec_from_file_location("lifecycle_dotenv", script)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    (tmp_path / ".env").write_text(line + "\n", encoding="utf-8")
    with pytest.raises(LiveExecutionDenied):
        mod.load_env_files()


def test_e_runtime_control_openapi_orders_denied(deny_env, monkeypatch):
    """run_runtime_control openapi + close_on_failsafe without ORDERS — no broker."""
    script = ROOT / "quantbridge/scripts/run_runtime_control.py"
    spec = importlib.util.spec_from_file_location("runtime_e", script)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    monkeypatch.setattr(mod, "load_env_files", lambda: None)
    monkeypatch.setattr(
        mod,
        "load_config",
        lambda p: {
            "broker": {"environment": "demo", "mode": "openapi", "account_id": "12345678"},
            "symbol": {"internal": "XAUUSD"},
        },
    )
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_ACCOUNT_IDS", "12345678")
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS", "demo")
    monkeypatch.setenv("CTRADER_ACCOUNT_ID", "12345678")
    monkeypatch.setenv("CTRADER_ACCESS_TOKEN", "t" * 40)

    ctor: list[int] = []

    class Boom:
        def __init__(self, *a, **k):
            ctor.append(1)
            raise AssertionError("must not construct")

    monkeypatch.setattr(mod, "CTraderBroker", Boom)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_runtime_control.py", "--mode", "openapi", "--config", "x.yaml", "--max-iterations", "1"],
    )
    with pytest.raises((LiveExecutionDenied, RuntimeError, SystemExit)):
        mod.main()
    assert ctor == []


@pytest.mark.parametrize(
    "line",
    [
        "export QUANTMETRICS_EXECUTION_AUTHORIZED=1",
        "QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS=demo",
    ],
)
def test_e_runtime_dotenv_gate_key_denied(deny_env, monkeypatch, tmp_path, line):
    script = ROOT / "quantbridge/scripts/run_runtime_control.py"
    spec = importlib.util.spec_from_file_location("runtime_dotenv", script)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    (tmp_path / "local.env").write_text(line + "\n", encoding="utf-8")
    with pytest.raises(LiveExecutionDenied):
        mod.load_env_files()


def test_e_qb_init_real_bridge_session_denied(deny_env, monkeypatch, tmp_path):
    """QB CTraderBroker._init_real_bridge SESSION deny before OpenAPI construction."""
    from src.quantbuild.execution.broker_ctrader import CTraderBroker

    monkeypatch.setenv("QUANTMETRICS_ALLOWED_ACCOUNT_IDS", "12345678")
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS", "demo")
    # Missing AUTH is OK for SESSION — use missing account instead
    monkeypatch.delenv("QUANTMETRICS_ALLOWED_ACCOUNT_IDS", raising=False)

    bridge_src = tmp_path / "quantbridge" / "src"
    bridge_src.mkdir(parents=True)
    monkeypatch.setenv("QUANTBRIDGE_SRC_PATH", str(bridge_src))
    # Make path exist so _init_real_bridge enters the loop
    (bridge_src / "quantbridge").mkdir()
    (bridge_src / "quantbridge" / "__init__.py").write_text("", encoding="utf-8")

    broker = CTraderBroker(
        account_id="12345678",
        access_token="t" * 40,
        environment="demo",
        mock_mode=False,
    )
    monkeypatch.setattr(broker, "_hydrate_credentials_from_dotenv", lambda root: None)
    with pytest.raises((LiveExecutionDenied, RuntimeError)):
        broker._init_real_bridge()
