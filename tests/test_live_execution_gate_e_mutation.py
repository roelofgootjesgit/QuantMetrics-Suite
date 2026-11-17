"""Issue #104 PR-B — scratch-copy mutation proofs for entrypoint preflights."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _copy(dst: Path, rel: str) -> Path:
    src = ROOT / rel
    target = dst / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, target)
    return target


def _prep_pkgs(dst: Path) -> None:
    for pkg in (
        "quantbridge/src/quantbridge",
        "quantbridge/src/quantbridge/safety",
        "quantbridge/src/quantbridge/execution",
        "quantbridge/src/quantbridge/execution/brokers",
        "quantbridge/src/quantbridge/execution/clients",
        "quantbuild/src/quantbuild",
        "quantbuild/src/quantbuild/execution",
        "quantbuild/src/quantbuild/alerts",
    ):
        (dst / pkg).mkdir(parents=True, exist_ok=True)
        init = dst / pkg / "__init__.py"
        if not init.exists():
            init.write_text("", encoding="utf-8")


def _pythonpath(scratch: Path) -> str:
    return (
        f"{scratch / 'quantbridge' / 'src'}:"
        f"{scratch / 'quantbuild' / 'src'}:"
        f"{scratch / 'quantbuild'}:"
        f"{scratch}"
    )


def _run(scratch: Path, code: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for k in (
        "QUANTMETRICS_EXECUTION_AUTHORIZED",
        "QUANTMETRICS_ALLOWED_ACCOUNT_IDS",
        "QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS",
    ):
        env.pop(k, None)
    env["PYTHONPATH"] = _pythonpath(scratch)
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(scratch),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _seed_core(scratch: Path) -> None:
    _prep_pkgs(scratch)
    for rel in (
        "quantbridge/src/quantbridge/safety/live_execution_gate.py",
        "quantbridge/src/quantbridge/safety/__init__.py",
        "quantbuild/src/quantbuild/execution/live_execution_preflight.py",
        "quantbuild/src/quantbuild/execution/broker_factory.py",
        "quantbuild/src/quantbuild/suite_layout.py",
        "quantbuild/src/quantbuild/app.py",
        "quantbridge/src/quantbridge/execution/brokers/ctrader_broker.py",
    ):
        _copy(scratch, rel)
    # Minimal stubs so imports succeed without full tree
    (scratch / "quantbuild/src/quantbuild/config.py").write_text(
        "def load_config(path=None):\n"
        "    return {'symbol':'XAUUSD','broker':{'provider':'ctrader',"
        "'environment':'demo','account_id':'12345678','mock_mode':False},"
        "'data':{'source':'yfinance'},'system_mode':'PRODUCTION'}\n"
        "def quantbuild_repo_root():\n"
        "    from pathlib import Path\n"
        "    return Path('.').resolve()\n",
        encoding="utf-8",
    )
    (scratch / "quantbuild/src/quantbuild/version.py").write_text(
        "__version__='0'\ndef git_revision_short():\n    return 'x'\n",
        encoding="utf-8",
    )
    (scratch / "quantbuild/src/quantbuild/logging_config.py").write_text(
        "def setup_logging(*a, **k): pass\n",
        encoding="utf-8",
    )
    (scratch / "quantbridge/src/quantbridge/execution/broker_contract.py").write_text(
        "class BrokerContract: pass\n",
        encoding="utf-8",
    )
    (scratch / "quantbridge/src/quantbridge/execution/clients/ctrader_openapi_client.py").write_text(
        "class CTraderOpenApiClient:\n"
        "    def __init__(self, *a, **k):\n"
        "        raise AssertionError('openapi constructed')\n",
        encoding="utf-8",
    )
    (scratch / "quantbridge/src/quantbridge/execution/clients/ctrader_mock_client.py").write_text(
        "class CTraderMockClient:\n"
        "    def __init__(self, *a, **k): self.connected=False\n",
        encoding="utf-8",
    )
    for stub in (
        "quantbridge/src/quantbridge/execution/health.py",
        "quantbridge/src/quantbridge/execution/models.py",
        "quantbridge/src/quantbridge/execution/symbol_registry.py",
    ):
        p = scratch / stub
        if not p.exists():
            p.write_text(
                "class HealthReport:\n    def __init__(self, **k): pass\n"
                "class AccountState: pass\nclass OrderResult: pass\nclass Position: pass\n"
                "def map_symbol(*a, **k): return 'XAUUSD'\n"
                "def normalize_units(x): return x\n",
                encoding="utf-8",
            )


def test_mutation_remove_app_orders_preflight_killed(tmp_path):
    scratch = tmp_path / "mut-app"
    scratch.mkdir()
    _seed_core(scratch)
    target = scratch / "quantbuild/src/quantbuild/app.py"
    text = target.read_text(encoding="utf-8")
    # Comment out the ORDERS preflight block by neutralizing the condition
    mutated = text.replace(
        "if not args.dry_run:",
        "if False:  # mutated-app-preflight",
        1,
    )
    assert "mutated-app-preflight" in mutated
    target.write_text(mutated, encoding="utf-8")

    # Stub LiveRunner so success means preflight was skipped
    (scratch / "quantbuild/src/quantbuild/execution/live_runner.py").write_text(
        "class LiveRunner:\n"
        "    def __init__(self, cfg, dry_run=True): pass\n"
        "    def run(self): print('RUNNER_RAN')\n",
        encoding="utf-8",
    )
    (scratch / "quantbuild/src/quantbuild/suite_layout.py").write_text(
        "class SuiteLayoutError(Exception): pass\n"
        "def validate_suite_layout(): return {}\n",
        encoding="utf-8",
    )

    probe = textwrap.dedent(
        """
        import os
        os.environ.pop('QUANTMETRICS_EXECUTION_AUTHORIZED', None)
        os.environ['QUANTMETRICS_ALLOWED_ACCOUNT_IDS']='12345678'
        os.environ['QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS']='demo'
        from types import SimpleNamespace
        from src.quantbuild import app as app_mod
        args = SimpleNamespace(config=None, dry_run=False, command='live', real=True)
        rc = app_mod.cmd_live(args)
        print('RC', rc)
        if rc == 0:
            print('MUTATION_UNDETECTED')
        """
    )
    proc = _run(scratch, probe)
    assert "MUTATION_UNDETECTED" in proc.stdout, proc.stdout + proc.stderr


def test_mutation_remove_factory_session_preflight_killed(tmp_path):
    scratch = tmp_path / "mut-factory"
    scratch.mkdir()
    _seed_core(scratch)
    # Stub CTraderBroker in QB package
    (scratch / "quantbuild/src/quantbuild/execution/broker_ctrader.py").write_text(
        "class CTraderBroker:\n"
        "    def __init__(self, **k):\n"
        "        self.mock_mode=k.get('mock_mode', True)\n"
        "        print('BROKER_CTOR')\n",
        encoding="utf-8",
    )
    (scratch / "quantbuild/src/quantbuild/execution/broker_oanda.py").write_text(
        "class OandaBroker:\n    def __init__(self, **k): pass\n",
        encoding="utf-8",
    )
    (scratch / "quantbuild/src/quantbuild/execution/broker_contract.py").write_text(
        "class BrokerContract: pass\n",
        encoding="utf-8",
    )
    (scratch / "quantbuild/src/quantbuild/suite_layout.py").write_text(
        "def validate_suite_layout(): return {}\n",
        encoding="utf-8",
    )
    target = scratch / "quantbuild/src/quantbuild/execution/broker_factory.py"
    text = target.read_text(encoding="utf-8")
    mutated = text.replace(
        "if not mock_mode:",
        "if False:  # mutated-factory",
        1,
    )
    assert "mutated-factory" in mutated
    target.write_text(mutated, encoding="utf-8")

    probe = textwrap.dedent(
        """
        import os
        os.environ.pop('QUANTMETRICS_EXECUTION_AUTHORIZED', None)
        os.environ.pop('QUANTMETRICS_ALLOWED_ACCOUNT_IDS', None)
        from src.quantbuild.execution.broker_factory import create_broker
        cfg = {'broker': {'provider':'ctrader','environment':'demo','account_id':'12345678','mock_mode':False}}
        try:
            create_broker(cfg)
            print('MUTATION_UNDETECTED')
        except Exception as e:
            print('DENIED', type(e).__name__, e)
            raise SystemExit(2)
        """
    )
    proc = _run(scratch, probe)
    assert "MUTATION_UNDETECTED" in proc.stdout, proc.stdout + proc.stderr


def test_mutation_remove_bridge_openapi_session_killed(tmp_path):
    scratch = tmp_path / "mut-bridge"
    scratch.mkdir()
    _seed_core(scratch)
    target = scratch / "quantbridge/src/quantbridge/execution/brokers/ctrader_broker.py"
    text = target.read_text(encoding="utf-8")
    mutated = text.replace(
        'if mode == "openapi":',
        'if mode == "openapi":\n            if False:  # mutated-bridge-session\n'
        "                pass\n            elif True:",
        1,
    )
    # Simpler: remove assert_live_execution_allowed call
    mutated = text.replace(
        "assert_live_execution_allowed(",
        "False and assert_live_execution_allowed(",
        1,
    )
    assert "False and assert_live_execution_allowed" in mutated
    target.write_text(mutated, encoding="utf-8")

    # Allow OpenAPI ctor
    (scratch / "quantbridge/src/quantbridge/execution/clients/ctrader_openapi_client.py").write_text(
        "class CTraderOpenApiClient:\n"
        "    def __init__(self, *a, **k):\n"
        "        print('OPENAPI_CTOR')\n"
        "        self.connected=False\n",
        encoding="utf-8",
    )
    probe = textwrap.dedent(
        """
        import os
        os.environ.pop('QUANTMETRICS_EXECUTION_AUTHORIZED', None)
        os.environ.pop('QUANTMETRICS_ALLOWED_ACCOUNT_IDS', None)
        from quantbridge.execution.brokers.ctrader_broker import CTraderBroker
        try:
            CTraderBroker(account_id='12345678', access_token='t'*40, environment='demo', mode='openapi')
            print('MUTATION_UNDETECTED')
        except Exception as e:
            print('DENIED', type(e).__name__, e)
            raise SystemExit(2)
        """
    )
    proc = _run(scratch, probe)
    assert "MUTATION_UNDETECTED" in proc.stdout, proc.stdout + proc.stderr


def test_mutation_remove_launch_orders_preflight_killed(tmp_path):
    scratch = tmp_path / "mut-launch"
    scratch.mkdir()
    _seed_core(scratch)
    _copy(scratch, "quantbuild/scripts/launch_live_safe.py")
    target = scratch / "quantbuild/scripts/launch_live_safe.py"
    text = target.read_text(encoding="utf-8")
    mutated = text.replace(
        "preflight_live_execution(",
        "False and preflight_live_execution(",
        1,
    )
    assert "False and preflight_live_execution" in mutated
    target.write_text(mutated, encoding="utf-8")

    probe = textwrap.dedent(
        f"""
        import importlib.util, os, sys
        from pathlib import Path
        from types import SimpleNamespace
        os.environ.pop('QUANTMETRICS_EXECUTION_AUTHORIZED', None)
        os.environ['QUANTMETRICS_ALLOWED_ACCOUNT_IDS']='12345678'
        os.environ['QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS']='demo'
        path = Path({str(scratch / 'quantbuild/scripts/launch_live_safe.py')!r})
        spec = importlib.util.spec_from_file_location('lls', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # Force early return path with no errors before ORDERS — call only the ORDERS block via monkey
        # Simulate: empty errors list and invoke the ORDERS section by calling _preflight with stubs
        cfg = {{'broker': {{'provider':'ctrader','environment':'demo','mock_mode':False,'account_id':'12345678'}}}}
        mod.load_config = lambda p: cfg
        mod._read_bridge_env = lambda root: {{}}
        mod._resolve_credentials = lambda cfg, env: {{
            'account_id':'12345678','access_token':'t'*40,'client_id':'c','client_secret':'s'
        }}
        bridge = Path({str(scratch / 'quantbridge')!r})
        (bridge / 'src').mkdir(parents=True, exist_ok=True)
        args = SimpleNamespace(
            config='x.yaml', bridge_root=str(bridge), require_unpaused=False,
            run_recovery_first=False, recovery_config='r.yaml', account_state_file='a.json',
        )
        # Make bridge import succeed
        import types
        pkg = types.ModuleType('quantbridge.execution.brokers.ctrader_broker')
        sys.modules['quantbridge'] = types.ModuleType('quantbridge')
        sys.modules['quantbridge.execution'] = types.ModuleType('quantbridge.execution')
        sys.modules['quantbridge.execution.brokers'] = types.ModuleType('quantbridge.execution.brokers')
        sys.modules['quantbridge.execution.brokers.ctrader_broker'] = pkg
        ok, errors, warnings, creds, loaded = mod._preflight(args)
        print('OK', ok, 'ERRORS', errors)
        if ok:
            print('MUTATION_UNDETECTED')
        else:
            # If still failing for other reasons, check ORDERS not among errors
            if not any('denied' in e.lower() for e in errors):
                print('MUTATION_UNDETECTED')
            else:
                raise SystemExit(2)
        """
    )
    proc = _run(scratch, probe)
    assert "MUTATION_UNDETECTED" in proc.stdout, proc.stdout + proc.stderr
