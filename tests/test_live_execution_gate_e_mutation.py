"""Issue #104 PR-B — 17 single-site scratch mutations; each must be KILLED.

KILLED = removing the enforcement lets a deny-first probe proceed (MUTATION_UNDETECTED).
Unmutated code is covered by behavioral E-tests in test_live_execution_gate_e.py.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def _copy(scratch: Path, rel: str) -> Path:
    src = ROOT / rel
    dst = scratch / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def _pp(*roots: Path) -> str:
    """Build PYTHONPATH. For ``src.quantbuild.*`` put ``.../quantbuild`` (repo root), not ``.../src``."""
    parts = [str(r) for r in roots]
    # Fallbacks after scratch roots
    parts.extend(
        [
            str(ROOT / "quantbridge" / "src"),
            str(ROOT / "quantbuild"),
            str(ROOT),
        ]
    )
    return ":".join(parts)


def _mirror_qb(scratch: Path) -> Path:
    """Copy full quantbuild package tree into scratch; return scratch quantbuild repo root."""
    dst = scratch / "quantbuild" / "src" / "quantbuild"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(ROOT / "quantbuild" / "src" / "quantbuild", dst)
    (scratch / "quantbuild" / "src").mkdir(parents=True, exist_ok=True)
    return scratch / "quantbuild"


def _mirror_bridge(scratch: Path) -> Path:
    dst = scratch / "quantbridge" / "src" / "quantbridge"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(ROOT / "quantbridge" / "src" / "quantbridge", dst)
    return scratch / "quantbridge" / "src"


def _run(code: str, *, pythonpath: str, extra_env: dict | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for k in (
        "QUANTMETRICS_EXECUTION_AUTHORIZED",
        "QUANTMETRICS_ALLOWED_ACCOUNT_IDS",
        "QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS",
    ):
        env.pop(k, None)
    env["PYTHONPATH"] = pythonpath
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _killed(proc: subprocess.CompletedProcess[str], label: str) -> None:
    assert "MUTATION_UNDETECTED" in proc.stdout, (
        f"{label} SURVIVED or probe error\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )


def _seed_pkgs(scratch: Path) -> None:
    for pkg in (
        "quantbridge/src/quantbridge",
        "quantbridge/src/quantbridge/safety",
        "quantbridge/src/quantbridge/execution",
        "quantbridge/src/quantbridge/execution/brokers",
        "quantbridge/src/quantbridge/execution/clients",
        "quantbuild/src/quantbuild",
        "quantbuild/src/quantbuild/execution",
    ):
        (scratch / pkg).mkdir(parents=True, exist_ok=True)
        p = scratch / pkg / "__init__.py"
        if not p.exists():
            p.write_text("", encoding="utf-8")
    for rel in (
        "quantbridge/src/quantbridge/safety/live_execution_gate.py",
        "quantbridge/src/quantbridge/safety/__init__.py",
        "quantbuild/src/quantbuild/execution/live_execution_preflight.py",
        "quantbuild/src/quantbuild/suite_layout.py",
    ):
        _copy(scratch, rel)
    stubs = {
        "quantbridge/src/quantbridge/execution/broker_contract.py": "class BrokerContract: pass\n",
        "quantbridge/src/quantbridge/execution/clients/ctrader_openapi_client.py": (
            "class CTraderOpenApiClient:\n    def __init__(self,*a,**k):\n"
            "        print('OPENAPI_CTOR'); self.connected=False\n"
        ),
        "quantbridge/src/quantbridge/execution/clients/ctrader_mock_client.py": (
            "class CTraderMockClient:\n    def __init__(self,*a,**k): self.connected=False\n"
        ),
        "quantbridge/src/quantbridge/execution/health.py": "class HealthReport:\n    def __init__(self,**k): pass\n",
        "quantbridge/src/quantbridge/execution/models.py": "class AccountState: pass\nclass OrderResult: pass\nclass Position: pass\n",
        "quantbridge/src/quantbridge/execution/symbol_registry.py": (
            "def map_symbol(*a,**k): return 'XAUUSD'\ndef normalize_units(x): return x\n"
        ),
    }
    for rel, body in stubs.items():
        p = scratch / rel
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")


# --- m01 app ORDERS ---
def test_m01_app_orders_removed_killed(tmp_path):
    scratch = tmp_path / "m01"
    scratch.mkdir()
    qb = _mirror_qb(scratch)
    app = qb / "src/quantbuild/app.py"
    text = app.read_text(encoding="utf-8")
    app.write_text(text.replace("if not args.dry_run:", "if False:  # m01", 1), encoding="utf-8")
    (qb / "src/quantbuild/execution/live_runner.py").write_text(
        "class LiveRunner:\n  def __init__(self,cfg,dry_run=True): print('RUNNER_CTOR')\n  def run(self): print('RUNNER_RAN')\n",
        encoding="utf-8",
    )
    code = textwrap.dedent(
        """
        import os
        from types import SimpleNamespace
        os.environ.pop('QUANTMETRICS_EXECUTION_AUTHORIZED', None)
        os.environ['QUANTMETRICS_ALLOWED_ACCOUNT_IDS']='12345678'
        os.environ['QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS']='demo'
        from src.quantbuild import app as m
        m.validate_suite_layout = lambda: {}
        m.setup_logging = lambda *a, **k: None
        m.load_config = lambda path: {'symbol':'XAUUSD','broker':{'provider':'ctrader','environment':'demo','account_id':'12345678','mock_mode':False},'data':{},'system_mode':'PRODUCTION'}
        rc = m.cmd_live(SimpleNamespace(config=None, dry_run=False, command='live', real=True))
        print('RC', rc)
        if rc == 0:
            print('MUTATION_UNDETECTED')
        """
    )
    _killed(_run(code, pythonpath=_pp(qb, ROOT / "quantbridge" / "src")), "m01")


# --- m02 LiveRunner ORDERS ---
def test_m02_live_runner_orders_removed_killed(tmp_path):
    scratch = tmp_path / "m02"
    scratch.mkdir()
    qb = _mirror_qb(scratch)
    lr = qb / "src/quantbuild/execution/live_runner.py"
    text = lr.read_text(encoding="utf-8")
    lr.write_text(text.replace("if not self.dry_run:", "if False:  # m02", 1), encoding="utf-8")
    # Avoid root-CI missing filelock via quantlog_emitter import chain.
    (qb / "src/quantbuild/execution/quantlog_emitter.py").write_text(
        "class QuantLogEmitter:\n  def __init__(self, *a, **k): pass\n",
        encoding="utf-8",
    )
    code = textwrap.dedent(
        """
        import os, sys, types
        os.environ.pop('QUANTMETRICS_EXECUTION_AUTHORIZED', None)
        os.environ['QUANTMETRICS_ALLOWED_ACCOUNT_IDS']='12345678'
        os.environ['QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS']='demo'
        if 'filelock' not in sys.modules:
            fl = types.ModuleType('filelock')
            class FileLock:
                def __init__(self, *a, **k): pass
                def __enter__(self): return self
                def __exit__(self, *a): return False
            class Timeout(Exception): pass
            fl.FileLock = FileLock; fl.Timeout = Timeout
            sys.modules['filelock'] = fl
        from src.quantbuild.execution.live_runner import LiveRunner
        connects=[]
        class B:
            is_connected=False
            def connect(self):
                connects.append(1); return True
            def disconnect(self): pass
        r = object.__new__(LiveRunner)
        r.cfg={'broker':{'provider':'ctrader','environment':'demo','account_id':'12345678','mock_mode':True},'data':{'source':'yfinance'}}
        r.dry_run=False
        r._account_id='12345678'
        r.broker=B()
        try:
            r.run()
        except Exception as e:
            print('ERR', type(e).__name__, e)
        print('CONNECTS', connects)
        if connects:
            print('MUTATION_UNDETECTED')
        """
    )
    _killed(_run(code, pythonpath=_pp(qb, ROOT / "quantbridge" / "src")), "m02")


# --- m03 factory ctrader SESSION ---
def test_m03_factory_ctrader_session_removed_killed(tmp_path):
    scratch = tmp_path / "m03"
    scratch.mkdir()
    qb = _mirror_qb(scratch)
    bf = qb / "src/quantbuild/execution/broker_factory.py"
    text = bf.read_text(encoding="utf-8")
    text = text.replace(
        "preflight_live_execution(\n"
        '                provider="ctrader",\n'
        "                environment=environment,\n"
        "                account_id=account_id,\n"
        '                intent="SESSION",\n'
        "            )",
        "pass  # m03",
        1,
    )
    bf.write_text(text, encoding="utf-8")
    (qb / "src/quantbuild/suite_layout.py").write_text(
        "def validate_suite_layout(): return {}\nclass SuiteLayoutError(Exception): pass\n",
        encoding="utf-8",
    )
    (qb / "src/quantbuild/execution/broker_ctrader.py").write_text(
        "class CTraderBroker:\n  def __init__(self,**k):\n    print('CTOR'); self.mock_mode=k.get('mock_mode',True)\n",
        encoding="utf-8",
    )
    code = textwrap.dedent(
        """
        import os
        os.environ.pop('QUANTMETRICS_EXECUTION_AUTHORIZED', None)
        os.environ.pop('QUANTMETRICS_ALLOWED_ACCOUNT_IDS', None)
        from src.quantbuild.execution.broker_factory import create_broker
        create_broker({'broker':{'provider':'ctrader','environment':'demo','account_id':'12345678','mock_mode':False}})
        print('MUTATION_UNDETECTED')
        """
    )
    _killed(_run(code, pythonpath=_pp(qb, ROOT / "quantbridge" / "src")), "m03")


# --- m04 factory oanda SESSION ---
def test_m04_factory_oanda_session_removed_killed(tmp_path):
    scratch = tmp_path / "m04"
    scratch.mkdir()
    qb = _mirror_qb(scratch)
    bf = qb / "src/quantbuild/execution/broker_factory.py"
    text = bf.read_text(encoding="utf-8")
    text = text.replace(
        "preflight_live_execution(\n"
        '            provider="oanda",\n'
        "            environment=environment,\n"
        "            account_id=account_id,\n"
        '            intent="SESSION",\n'
        "        )",
        "pass  # m04",
        1,
    )
    bf.write_text(text, encoding="utf-8")
    (qb / "src/quantbuild/suite_layout.py").write_text(
        "def validate_suite_layout(): return {}\nclass SuiteLayoutError(Exception): pass\n",
        encoding="utf-8",
    )
    (qb / "src/quantbuild/execution/broker_oanda.py").write_text(
        "class AccountInfo: pass\n"
        "class OandaPosition: pass\n"
        "class OrderResult: pass\n"
        "class OandaBroker:\n"
        "  def __init__(self,**k):\n"
        "    print('OANDA_CTOR')\n",
        encoding="utf-8",
    )
    # Avoid real broker_ctrader importing the stubbed oanda symbols at factory import time.
    (qb / "src/quantbuild/execution/broker_ctrader.py").write_text(
        "class CTraderBroker:\n  def __init__(self,**k):\n    print('CTRADER_CTOR')\n",
        encoding="utf-8",
    )
    code = textwrap.dedent(
        """
        import os
        os.environ.pop('QUANTMETRICS_ALLOWED_ACCOUNT_IDS', None)
        from src.quantbuild.execution.broker_factory import create_broker
        create_broker({'broker':{'provider':'oanda','environment':'practice','account_id':'001','token':'t'}})
        print('MUTATION_UNDETECTED')
        """
    )
    _killed(_run(code, pythonpath=_pp(qb, ROOT / "quantbridge" / "src")), "m04")


# --- m05 factory ctrader layout ---
def test_m05_factory_ctrader_layout_removed_killed(tmp_path):
    scratch = tmp_path / "m05"
    scratch.mkdir()
    qb = _mirror_qb(scratch)
    bf = qb / "src/quantbuild/execution/broker_factory.py"
    text = bf.read_text(encoding="utf-8")
    text = text.replace(
        "if not mock_mode:\n            validate_suite_layout()\n            preflight_live_execution(",
        "if not mock_mode:\n            # m05 layout removed\n            preflight_live_execution(",
        1,
    )
    bf.write_text(text, encoding="utf-8")
    (qb / "src/quantbuild/suite_layout.py").write_text(
        "class SuiteLayoutError(Exception): pass\n"
        "def validate_suite_layout():\n"
        "    raise SuiteLayoutError('should_have_been_called')\n",
        encoding="utf-8",
    )
    (qb / "src/quantbuild/execution/broker_ctrader.py").write_text(
        "class CTraderBroker:\n  def __init__(self,**k):\n    print('CTOR')\n", encoding="utf-8"
    )
    code = textwrap.dedent(
        """
        import os
        os.environ['QUANTMETRICS_ALLOWED_ACCOUNT_IDS']='12345678'
        os.environ['QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS']='demo'
        from src.quantbuild.execution.broker_factory import create_broker
        try:
            create_broker({'broker':{'provider':'ctrader','environment':'demo','account_id':'12345678','mock_mode':False}})
            print('MUTATION_UNDETECTED')
        except Exception as e:
            print('ERR', type(e).__name__, e)
            if 'should_have_been_called' in str(e):
                raise SystemExit(2)
            print('MUTATION_UNDETECTED')
        """
    )
    _killed(_run(code, pythonpath=_pp(qb, ROOT / "quantbridge" / "src")), "m05")


# --- m06 factory oanda layout ---
def test_m06_factory_oanda_layout_removed_killed(tmp_path):
    scratch = tmp_path / "m06"
    scratch.mkdir()
    qb = _mirror_qb(scratch)
    bf = qb / "src/quantbuild/execution/broker_factory.py"
    text = bf.read_text(encoding="utf-8")
    needle = (
        'if provider == "oanda":\n'
        '        environment = str(broker_cfg.get("environment", "practice"))\n'
        '        account_id = str(broker_cfg.get("account_id", "") or "")\n'
        "        # PR-B #7: Oanda is always non-mock API surface — layout + SESSION.\n"
        "        validate_suite_layout()\n"
    )
    repl = needle.replace("        validate_suite_layout()\n", "        # m06 layout removed\n")
    assert needle in text
    bf.write_text(text.replace(needle, repl, 1), encoding="utf-8")
    (qb / "src/quantbuild/suite_layout.py").write_text(
        "class SuiteLayoutError(Exception): pass\n"
        "def validate_suite_layout():\n"
        "    raise SuiteLayoutError('should_have_been_called')\n",
        encoding="utf-8",
    )
    (qb / "src/quantbuild/execution/broker_oanda.py").write_text(
        "class AccountInfo: pass\n"
        "class OandaPosition: pass\n"
        "class OrderResult: pass\n"
        "class OandaBroker:\n"
        "  def __init__(self,**k):\n"
        "    print('CTOR')\n",
        encoding="utf-8",
    )
    (qb / "src/quantbuild/execution/broker_ctrader.py").write_text(
        "class CTraderBroker:\n  def __init__(self,**k):\n    print('CTRADER_CTOR')\n",
        encoding="utf-8",
    )
    code = textwrap.dedent(
        """
        import os
        os.environ['QUANTMETRICS_ALLOWED_ACCOUNT_IDS']='001'
        os.environ['QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS']='practice'
        from src.quantbuild.execution.broker_factory import create_broker
        try:
            create_broker({'broker':{'provider':'oanda','environment':'practice','account_id':'001','token':'t'}})
            print('MUTATION_UNDETECTED')
        except Exception as e:
            print('ERR', type(e).__name__, e)
            if 'should_have_been_called' in str(e):
                raise SystemExit(2)
            print('MUTATION_UNDETECTED')
        """
    )
    _killed(_run(code, pythonpath=_pp(qb, ROOT / "quantbridge" / "src")), "m06")


# --- m07 QB _init_real_bridge SESSION ---
def test_m07_qb_init_real_bridge_removed_killed(tmp_path):
    scratch = tmp_path / "m07"
    scratch.mkdir()
    qb = _mirror_qb(scratch)
    bc = qb / "src/quantbuild/execution/broker_ctrader.py"
    text = bc.read_text(encoding="utf-8")
    text = text.replace(
        "preflight_live_execution(\n"
        '                    provider="ctrader",\n'
        "                    environment=str(self.environment),\n"
        '                    account_id=str(self.account_id or ""),\n'
        '                    intent="SESSION",\n'
        "                )",
        "pass  # m07",
        1,
    )
    bc.write_text(text, encoding="utf-8")
    # QUANTBRIDGE_SRC_PATH must exist so _init_real_bridge enters the candidate loop.
    # Pre-seed a stub QB broker in sys.modules so removing QB SESSION is detectable
    # (otherwise the real bridge SESSION guard dominates after quantbridge is imported).
    bridge = scratch / "bridge_src"
    (bridge / "quantbridge" / "execution" / "brokers").mkdir(parents=True)
    (bridge / "quantbridge" / "__init__.py").write_text("", encoding="utf-8")
    (bridge / "quantbridge" / "execution" / "__init__.py").write_text("", encoding="utf-8")
    (bridge / "quantbridge" / "execution" / "brokers" / "__init__.py").write_text("", encoding="utf-8")
    (bridge / "quantbridge" / "execution" / "brokers" / "ctrader_broker.py").write_text(
        "class CTraderBroker:\n  def __init__(self,**k):\n    print('QB_BRIDGE_CTOR')\n",
        encoding="utf-8",
    )
    code = textwrap.dedent(
        f"""
        import os, sys, types
        os.environ.pop('QUANTMETRICS_ALLOWED_ACCOUNT_IDS', None)
        os.environ['QUANTBRIDGE_SRC_PATH']={str(bridge)!r}
        # Ensure package parents exist, then override the broker module with a gate-free stub.
        import quantbridge.execution.brokers as _brokers  # noqa: F401
        stub = types.ModuleType('quantbridge.execution.brokers.ctrader_broker')
        class _StubQB:
            def __init__(self, **k):
                print('QB_BRIDGE_CTOR')
        stub.CTraderBroker = _StubQB
        sys.modules['quantbridge.execution.brokers.ctrader_broker'] = stub
        from src.quantbuild.execution.broker_ctrader import CTraderBroker
        b=CTraderBroker(account_id='12345678', access_token='t'*40, environment='demo', mock_mode=False)
        b._hydrate_credentials_from_dotenv = lambda root: None
        ok = b._init_real_bridge()
        print('OK', ok, 'BRIDGE', b._real_bridge)
        if b._real_bridge is not None or ok:
            print('MUTATION_UNDETECTED')
        """
    )
    _killed(_run(code, pythonpath=_pp(qb, ROOT / "quantbridge" / "src")), "m07")


# --- m08 bridge openapi SESSION ---
def test_m08_bridge_openapi_session_removed_killed(tmp_path):
    scratch = tmp_path / "m08"
    scratch.mkdir()
    _seed_pkgs(scratch)
    br = _copy(scratch, "quantbridge/src/quantbridge/execution/brokers/ctrader_broker.py")
    text = br.read_text(encoding="utf-8")
    text = text.replace(
        "assert_live_execution_allowed(\n"
        "                LiveExecutionRequest(\n"
        '                    provider="ctrader",\n'
        "                    environment=str(environment),\n"
        "                    account_id=str(account_id),\n"
        '                    intent="SESSION",\n'
        "                )\n"
        "            )",
        "pass  # m08",
        1,
    )
    br.write_text(text, encoding="utf-8")
    code = textwrap.dedent(
        """
        import os
        os.environ.pop('QUANTMETRICS_ALLOWED_ACCOUNT_IDS', None)
        from quantbridge.execution.brokers.ctrader_broker import CTraderBroker
        CTraderBroker(account_id='12345678', access_token='t'*40, environment='demo', mode='openapi')
        print('MUTATION_UNDETECTED')
        """
    )
    _killed(_run(code, pythonpath=_pp(scratch / "quantbridge" / "src")), "m08")


# --- m09 launch_live_safe ORDERS ---
def test_m09_launch_orders_removed_killed(tmp_path):
    scratch = tmp_path / "m09"
    scratch.mkdir()
    script = _copy(scratch, "quantbuild/scripts/launch_live_safe.py")
    text = script.read_text(encoding="utf-8")
    text = text.replace(
        "preflight_live_execution(\n"
        '                provider="ctrader",\n'
        "                environment=environment,\n"
        "                account_id=account_id,\n"
        '                intent="ORDERS",\n'
        "            )",
        "pass  # m09",
        1,
    )
    script.write_text(text, encoding="utf-8")
    code = textwrap.dedent(
        f"""
        import importlib.util, sys, types, os
        from pathlib import Path
        from types import SimpleNamespace
        # Ensure src.quantbuild.config import succeeds during script load
        sys.path.insert(0, {str(ROOT / 'quantbuild')!r})
        path = Path({str(script)!r})
        spec = importlib.util.spec_from_file_location('lls', path)
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        cfg={{'broker':{{'provider':'ctrader','environment':'demo','mock_mode':False,'account_id':'12345678'}}}}
        mod.load_config=lambda p: cfg
        mod._read_bridge_env=lambda root: {{}}
        mod._resolve_credentials=lambda cfg,env: {{'account_id':'12345678','access_token':'t'*40,'client_id':'c','client_secret':'s'}}
        bridge=Path({str(scratch/'qb')!r}); (bridge/'src').mkdir(parents=True)
        sys.modules['quantbridge.execution.brokers.ctrader_broker']=types.ModuleType('x')
        args=SimpleNamespace(config='x', bridge_root=str(bridge), require_unpaused=False, run_recovery_first=False, recovery_config='r', account_state_file='a')
        os.environ['QUANTMETRICS_ALLOWED_ACCOUNT_IDS']='12345678'
        os.environ['QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS']='demo'
        os.environ.pop('QUANTMETRICS_EXECUTION_AUTHORIZED', None)
        ok, errors, *_ = mod._preflight(args)
        print('OK', ok, errors)
        if ok or not any('denied' in e.lower() for e in errors):
            print('MUTATION_UNDETECTED')
        """
    )
    _killed(
        _run(
            code,
            pythonpath=_pp(ROOT / "quantbuild", ROOT / "quantbridge" / "src"),
            extra_env={
                "QUANTMETRICS_ALLOWED_ACCOUNT_IDS": "12345678",
                "QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS": "demo",
            },
        ),
        "m09",
    )


# --- m10 orchestrator ORDERS ---
def test_m10_orchestrator_orders_removed_killed(tmp_path):
    scratch = tmp_path / "m10"
    scratch.mkdir()
    _seed_pkgs(scratch)
    orch = _copy(scratch, "quantmetrics_os/orchestrator/quantmetrics.py")
    text = orch.read_text(encoding="utf-8")
    # Neutralize only the ORDERS preflight block start
    text = text.replace(
        "    # PR-B #11: ORDERS preflight before spawning --real child (spawn UX).\n    if args.real:",
        "    # PR-B #11: ORDERS preflight before spawning --real child (spawn UX).\n    if False:  # m10",
        1,
    )
    orch.write_text(text, encoding="utf-8")
    code = textwrap.dedent(
        f"""
        import importlib.util, yaml, tempfile, os
        from pathlib import Path
        from types import SimpleNamespace
        path=Path({str(orch)!r})
        spec=importlib.util.spec_from_file_location('orch', path)
        mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        calls=[]
        mod.subprocess.call=lambda *a,**k: calls.append(1) or 0
        os.environ['QUANTBUILD_ROOT']={str(ROOT/'quantbuild')!r}
        cfg={{'broker':{{'provider':'ctrader','environment':'demo','account_id':'12345678','mock_mode':False}}}}
        cp=Path(tempfile.mkdtemp())/'c.yaml'; cp.write_text(yaml.safe_dump(cfg))
        rc=mod.cmd_build(SimpleNamespace(config=str(cp), real=True, dry_run=False, notify_start=False, notify_components='build'))
        print('RC', rc, 'CALLS', len(calls))
        if rc != 2:
            print('MUTATION_UNDETECTED')
        """
    )
    _killed(
        _run(
            code,
            pythonpath=_pp(scratch / "quantbridge" / "src", ROOT / "quantbuild" / "src", ROOT / "quantbuild"),
            extra_env={
                "QUANTMETRICS_ALLOWED_ACCOUNT_IDS": "12345678",
                "QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS": "demo",
                "QUANTBUILD_ROOT": str(ROOT / "quantbuild"),
            },
        ),
        "m10",
    )


def _stub_bridge_heavy_imports():
    """Return preamble that stubs heavy quantbridge modules before script import."""
    return textwrap.dedent(
        """
        import sys, types
        def _stub(name, **attrs):
            m = types.ModuleType(name)
            for k,v in attrs.items(): setattr(m,k,v)
            sys.modules[name]=m
            return m
        _stub('quantbridge.execution.order_manager', OrderManager=type('OM',(),{}))
        _stub('quantbridge.execution.runtime_control', RuntimeControlLoop=type('R',(),{}), send_telegram_alert=lambda **k: None)
        _stub('quantbridge.accounts.account_state_machine', AccountStateMachine=type('A',(),{'__init__':lambda self,**k: None,'set_state':lambda *a,**k: None,'get_pause_reason':lambda *a,**k: None}))
        _stub('quantbridge.risk.account_limits', AccountLimits=type('L',(),{'__init__':lambda self,**k: None}))
        _stub('quantbridge.risk.prop_guard', PropGuard=type('P',(),{'__init__':lambda self,**k: None,'evaluate':lambda *a,**k: None}))
        _stub('quantbridge.risk.risk_engine', RiskSnapshot=type('S',(),{}), TradeIntent=type('T',(),{}))
        _stub('quantbridge.ops.observability', JsonlEventSink=type('J',(),{'__init__':lambda self,**k: None,'emit':lambda *a,**k: None}))
        """
    )


# --- m11 QB smoke ORDERS ---
def test_m11_qb_smoke_orders_removed_killed(tmp_path):
    scratch = tmp_path / "m11"
    scratch.mkdir()
    script = _copy(scratch, "quantbuild/scripts/ctrader_smoke.py")
    text = script.read_text(encoding="utf-8")
    script.write_text(text.replace("if not mock_mode:", "if False:  # m11", 1), encoding="utf-8")
    code = textwrap.dedent(
        f"""
        import importlib.util, sys, os
        from pathlib import Path
        path=Path({str(script)!r})
        spec=importlib.util.spec_from_file_location('s', path)
        mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        mod.load_config=lambda p: {{'broker':{{'provider':'ctrader','environment':'demo','account_id':'12345678','mock_mode':False}},'symbol':'XAUUSD'}}
        ctors=[]
        mod.create_broker=lambda c: ctors.append(1) or (_ for _ in ()).throw(SystemExit(0))
        os.environ['QUANTMETRICS_ALLOWED_ACCOUNT_IDS']='12345678'
        os.environ['QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS']='demo'
        os.environ.pop('QUANTMETRICS_EXECUTION_AUTHORIZED', None)
        sys.argv=['x','--config','x.yaml']
        try:
            mod.main()
        except SystemExit:
            pass
        if ctors:
            print('MUTATION_UNDETECTED')
        """
    )
    _killed(
        _run(
            code,
            pythonpath=_pp(ROOT / "quantbridge" / "src", ROOT / "quantbuild" / "src", ROOT / "quantbuild"),
            extra_env={
                "QUANTMETRICS_ALLOWED_ACCOUNT_IDS": "12345678",
                "QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS": "demo",
            },
        ),
        "m11",
    )


# --- m12 diagnose SESSION ---
def test_m12_diagnose_session_removed_killed(tmp_path):
    scratch = tmp_path / "m12"
    scratch.mkdir()
    script = _copy(scratch, "quantbuild/scripts/diagnose_ctrader_connect.py")
    text = script.read_text(encoding="utf-8")
    script.write_text(text.replace("if not mock_mode:", "if False:  # m12", 1), encoding="utf-8")
    code = textwrap.dedent(
        f"""
        import importlib.util, sys, os
        from pathlib import Path
        path=Path({str(script)!r})
        spec=importlib.util.spec_from_file_location('s', path)
        mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        mod.load_config=lambda p: {{'broker':{{'provider':'ctrader','environment':'demo','account_id':'12345678','mock_mode':False}}}}
        for k in ('QUANTMETRICS_ALLOWED_ACCOUNT_IDS','QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS','QUANTMETRICS_EXECUTION_AUTHORIZED'):
            os.environ.pop(k, None)
        ctors=[]
        class B:
            mock_mode=False; account_id=''; access_token=''
            def connect(self): return False
            def disconnect(self): pass
        mod.create_broker=lambda c: ctors.append(1) or B()
        sys.argv=['x','-c','x.yaml']
        try:
            mod.main()
        except Exception as e:
            print('ERR', e)
        if ctors:
            print('MUTATION_UNDETECTED')
        """
    )
    _killed(
        _run(code, pythonpath=_pp(ROOT / "quantbridge" / "src", ROOT / "quantbuild" / "src", ROOT / "quantbuild")),
        "m12",
    )


# --- m13 bridge smoke ORDERS ---
def test_m13_bridge_smoke_orders_removed_killed(tmp_path):
    scratch = tmp_path / "m13"
    scratch.mkdir()
    script = _copy(scratch, "quantbridge/scripts/ctrader_smoke.py")
    text = script.read_text(encoding="utf-8")
    # Neutralize ORDERS preflight by forcing the openapi branch condition false.
    script.write_text(
        text.replace('if effective_mode == "openapi":', 'if False:  # m13 openapi orders removed', 1),
        encoding="utf-8",
    )
    code = _stub_bridge_heavy_imports() + textwrap.dedent(
        f"""
        import importlib.util, sys, os
        from pathlib import Path
        path=Path({str(script)!r})
        spec=importlib.util.spec_from_file_location('s', path)
        mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        mod.load_local_env=lambda: None
        mod.load_config=lambda p: {{'broker':{{'environment':'demo','mode':'openapi','account_id':'12345678'}},'symbol':{{'internal':'XAUUSD'}},'execution':{{}}}}
        os.environ['QUANTMETRICS_ALLOWED_ACCOUNT_IDS']='12345678'
        os.environ['QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS']='demo'
        os.environ.pop('QUANTMETRICS_EXECUTION_AUTHORIZED', None)
        ctors=[]
        class Boom:
            def __init__(self,*a,**k):
                ctors.append(1); raise SystemExit(0)
        mod.CTraderBroker=Boom
        sys.argv=['x','--mode','openapi','--config','x.yaml']
        try:
            mod.main()
        except SystemExit:
            pass
        if ctors:
            print('MUTATION_UNDETECTED')
        """
    )
    _killed(
        _run(
            code,
            pythonpath=_pp(ROOT / "quantbridge" / "src"),
            extra_env={
                "QUANTMETRICS_ALLOWED_ACCOUNT_IDS": "12345678",
                "QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS": "demo",
            },
        ),
        "m13",
    )


# --- m14 lifecycle ORDERS ---
def test_m14_lifecycle_orders_removed_killed(tmp_path):
    scratch = tmp_path / "m14"
    scratch.mkdir()
    script = _copy(scratch, "quantbridge/scripts/run_order_lifecycle_check.py")
    text = script.read_text(encoding="utf-8")
    script.write_text(
        text.replace('if mode == "openapi":', 'if False:  # m14 lifecycle orders removed', 1),
        encoding="utf-8",
    )
    code = _stub_bridge_heavy_imports() + textwrap.dedent(
        f"""
        import importlib.util, sys, os
        from pathlib import Path
        path=Path({str(script)!r})
        spec=importlib.util.spec_from_file_location('s', path)
        mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        mod.load_env_files=lambda: None
        mod.load_config=lambda p: {{'broker':{{'environment':'demo','mode':'openapi','account_id':'12345678'}},'symbol':{{'internal':'XAUUSD'}},'execution':{{'units':1.0}}}}
        os.environ['QUANTMETRICS_ALLOWED_ACCOUNT_IDS']='12345678'
        os.environ['QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS']='demo'
        os.environ.pop('QUANTMETRICS_EXECUTION_AUTHORIZED', None)
        ctors=[]
        class Boom:
            def __init__(self,*a,**k):
                ctors.append(1); raise SystemExit(0)
        mod.CTraderBroker=Boom
        sys.argv=['x','--mode','openapi','--config','x.yaml']
        try:
            mod.main()
        except SystemExit:
            pass
        if ctors:
            print('MUTATION_UNDETECTED')
        """
    )
    _killed(
        _run(
            code,
            pythonpath=_pp(ROOT / "quantbridge" / "src"),
            extra_env={
                "QUANTMETRICS_ALLOWED_ACCOUNT_IDS": "12345678",
                "QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS": "demo",
            },
        ),
        "m14",
    )


# --- m15 runtime ORDERS ---
def test_m15_runtime_orders_removed_killed(tmp_path):
    scratch = tmp_path / "m15"
    scratch.mkdir()
    script = _copy(scratch, "quantbridge/scripts/run_runtime_control.py")
    text = script.read_text(encoding="utf-8")
    script.write_text(
        text.replace(
            'if mode == "openapi" and close_on_failsafe:',
            "if False:  # m15 runtime orders removed",
            1,
        ),
        encoding="utf-8",
    )
    code = _stub_bridge_heavy_imports() + textwrap.dedent(
        f"""
        import importlib.util, sys, os
        from pathlib import Path
        path=Path({str(script)!r})
        spec=importlib.util.spec_from_file_location('s', path)
        mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        mod.load_env_files=lambda: None
        mod.load_config=lambda p: {{'broker':{{'environment':'demo','mode':'openapi','account_id':'12345678'}},'symbol':{{'internal':'XAUUSD'}}}}
        os.environ['QUANTMETRICS_ALLOWED_ACCOUNT_IDS']='12345678'
        os.environ['QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS']='demo'
        os.environ.pop('QUANTMETRICS_EXECUTION_AUTHORIZED', None)
        ctors=[]
        class Boom:
            def __init__(self,*a,**k):
                ctors.append(1); raise SystemExit(0)
        mod.CTraderBroker=Boom
        sys.argv=['x','--mode','openapi','--config','x.yaml','--max-iterations','1']
        try:
            mod.main()
        except SystemExit:
            pass
        if ctors:
            print('MUTATION_UNDETECTED')
        """
    )
    _killed(
        _run(
            code,
            pythonpath=_pp(ROOT / "quantbridge" / "src"),
            extra_env={
                "QUANTMETRICS_ALLOWED_ACCOUNT_IDS": "12345678",
                "QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS": "demo",
            },
        ),
        "m15",
    )


# --- m16 bridge smoke dotenv ---
def test_m16_bridge_smoke_dotenv_removed_killed(tmp_path):
    scratch = tmp_path / "m16"
    scratch.mkdir()
    script = _copy(scratch, "quantbridge/scripts/ctrader_smoke.py")
    text = script.read_text(encoding="utf-8")
    text = text.replace("assert_dotenv_path_has_no_gate_keys(env_path)", "pass  # m16a", 1)
    text = text.replace(
        'if key in _GATE_ENV_KEYS:\n                raise LiveExecutionDenied(f"gate_key_present_in_dotenv:{env_path}")',
        "if False:\n                raise RuntimeError('m16')",
        1,
    )
    script.write_text(text, encoding="utf-8")
    code = textwrap.dedent(
        f"""
        import importlib.util, tempfile, os
        from pathlib import Path
        path=Path({str(script)!r})
        spec=importlib.util.spec_from_file_location('s', path)
        mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        td=Path(tempfile.mkdtemp()); mod.ROOT=td
        (td/'local.env').write_text('QUANTMETRICS_EXECUTION_AUTHORIZED=1\\nFOO=bar\\n')
        for k in ('QUANTMETRICS_EXECUTION_AUTHORIZED','QUANTMETRICS_ALLOWED_ACCOUNT_IDS','QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS'):
            os.environ.pop(k, None)
        mod.load_local_env()
        print('AUTH', os.environ.get('QUANTMETRICS_EXECUTION_AUTHORIZED'))
        if os.environ.get('QUANTMETRICS_EXECUTION_AUTHORIZED') == '1':
            print('MUTATION_UNDETECTED')
        """
    )
    _killed(_run(code, pythonpath=_pp(ROOT / "quantbridge" / "src")), "m16")


# --- m17 lifecycle dotenv ---
def test_m17_lifecycle_dotenv_removed_killed(tmp_path):
    scratch = tmp_path / "m17"
    scratch.mkdir()
    script = _copy(scratch, "quantbridge/scripts/run_order_lifecycle_check.py")
    text = script.read_text(encoding="utf-8")
    text = text.replace("assert_dotenv_path_has_no_gate_keys(env_path)", "pass  # m17a", 1)
    text = text.replace(
        'if key in _GATE_ENV_KEYS:\n                raise LiveExecutionDenied(f"gate_key_present_in_dotenv:{env_path}")',
        "if False:\n                raise RuntimeError('m17')",
        1,
    )
    script.write_text(text, encoding="utf-8")
    code = _stub_bridge_heavy_imports() + textwrap.dedent(
        f"""
        import importlib.util, tempfile, os
        from pathlib import Path
        path=Path({str(script)!r})
        spec=importlib.util.spec_from_file_location('s', path)
        mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        td=Path(tempfile.mkdtemp()); mod.ROOT=td
        (td/'.env').write_text('QUANTMETRICS_EXECUTION_AUTHORIZED=1\\n')
        for k in ('QUANTMETRICS_EXECUTION_AUTHORIZED','QUANTMETRICS_ALLOWED_ACCOUNT_IDS','QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS'):
            os.environ.pop(k, None)
        mod.load_env_files()
        print('AUTH', os.environ.get('QUANTMETRICS_EXECUTION_AUTHORIZED'))
        if os.environ.get('QUANTMETRICS_EXECUTION_AUTHORIZED') == '1':
            print('MUTATION_UNDETECTED')
        """
    )
    _killed(_run(code, pythonpath=_pp(ROOT / "quantbridge" / "src")), "m17")
