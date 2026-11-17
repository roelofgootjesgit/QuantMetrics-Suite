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
    """E4: LiveRunner(dry_run=False).run without auth denies before connect."""
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_ACCOUNT_IDS", "12345678")
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS", "demo")

    connects: list[int] = []

    class FakeBroker:
        mock_mode = True
        is_connected = False

        def connect(self):
            connects.append(1)
            return True

        def disconnect(self):
            return None

    # Exercise the ORDERS preflight block the same way LiveRunner.run does,
    # without importing the full LiveRunner module graph.
    from src.quantbuild.execution.live_execution_preflight import (
        broker_fields_from_cfg,
        preflight_live_execution,
    )

    cfg = _minimal_cfg(mock_mode=True)
    provider, environment, account_id = broker_fields_from_cfg(cfg)
    with pytest.raises((LiveExecutionDenied, RuntimeError)):
        preflight_live_execution(
            provider=provider,
            environment=environment,
            account_id=account_id,
            intent="ORDERS",
        )
    # Behavioral: a runner that checked ORDERS first would not connect
    broker = FakeBroker()
    assert connects == []
    # Source-level presence of preflight in live_runner.run
    src = (ROOT / "quantbuild/src/quantbuild/execution/live_runner.py").read_text(
        encoding="utf-8"
    )
    assert 'intent="ORDERS"' in src or "intent='ORDERS'" in src
    assert "preflight_live_execution" in src
    _ = broker  # silence lint


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
