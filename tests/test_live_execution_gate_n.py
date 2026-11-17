"""Issue #104 PR-A — policy negative tests N1–N12 / N10* (B1/B2 repair)."""
from __future__ import annotations

import importlib
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from quantbridge.safety.live_execution_gate import (
    GATE_ENV_KEYS,
    LiveExecutionDenied,
    LiveExecutionRequest,
    assert_dotenv_path_has_no_gate_keys,
    assert_live_execution_allowed,
    canonicalize_ctrader_account_id,
    env_file_contains_gate_keys,
    resolve_ctrader_host,
)

ROOT = Path(__file__).resolve().parents[1]


def _env(**kwargs: str) -> dict[str, str]:
    base = {k: v for k, v in os.environ.items() if k not in GATE_ENV_KEYS}
    base.update(kwargs)
    return base


def _allowed_demo(**extra: str) -> dict[str, str]:
    return _env(
        QUANTMETRICS_ALLOWED_ACCOUNT_IDS="12345678",
        QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS="demo",
        **extra,
    )


def test_n1_unknown_environments_denied():
    for bad in ("", "prod", "Practice"):
        with pytest.raises(LiveExecutionDenied):
            assert_live_execution_allowed(
                LiveExecutionRequest("ctrader", bad, "12345678", "SESSION"),
                environ=_allowed_demo(),
                env_file_paths=[],
            )
        with pytest.raises(LiveExecutionDenied):
            resolve_ctrader_host(bad, environ=_allowed_demo())


def test_n2_live_default_allowlist_denied():
    environ = _env(QUANTMETRICS_ALLOWED_ACCOUNT_IDS="12345678")
    with pytest.raises(LiveExecutionDenied):
        assert_live_execution_allowed(
            LiveExecutionRequest("ctrader", "live", "12345678", "SESSION"),
            environ=environ,
            env_file_paths=[],
        )


def test_n3a_live_allowlisted_auth_missing_denied():
    environ = _env(
        QUANTMETRICS_ALLOWED_ACCOUNT_IDS="12345678",
        QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS="demo,live",
    )
    with pytest.raises(LiveExecutionDenied):
        assert_live_execution_allowed(
            LiveExecutionRequest("ctrader", "live", "12345678", "ORDERS"),
            environ=environ,
            env_file_paths=[],
            enablement_path=Path("/nonexistent/execution_authorization"),
        )


def test_n3b_c3_live_allowlisted_auth_one_still_frozen():
    environ = _env(
        QUANTMETRICS_EXECUTION_AUTHORIZED="1",
        QUANTMETRICS_ALLOWED_ACCOUNT_IDS="12345678",
        QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS="demo,live",
    )
    with pytest.raises(LiveExecutionDenied) as exc:
        assert_live_execution_allowed(
            LiveExecutionRequest("ctrader", "live", "12345678", "ORDERS"),
            environ=environ,
            env_file_paths=[],
            enablement_path=Path("/nonexistent/execution_authorization"),
        )
    assert "live_host_enablement_frozen" in str(exc.value)


@pytest.mark.parametrize("bad", [None, "0", "true", "yes", "on", " 1", "1 ", "01", ""])
def test_n4_authorization_rejects_non_exact_one(bad):
    environ = _allowed_demo()
    if bad is None:
        environ.pop("QUANTMETRICS_EXECUTION_AUTHORIZED", None)
    else:
        environ["QUANTMETRICS_EXECUTION_AUTHORIZED"] = bad
    with pytest.raises(LiveExecutionDenied):
        assert_live_execution_allowed(
            LiveExecutionRequest("ctrader", "demo", "12345678", "ORDERS"),
            environ=environ,
            env_file_paths=[],
        )


def test_n5_missing_or_empty_account_allowlist():
    for environ in (
        _env(QUANTMETRICS_EXECUTION_AUTHORIZED="1"),
        _env(QUANTMETRICS_EXECUTION_AUTHORIZED="1", QUANTMETRICS_ALLOWED_ACCOUNT_IDS=""),
    ):
        with pytest.raises(LiveExecutionDenied):
            assert_live_execution_allowed(
                LiveExecutionRequest("ctrader", "demo", "12345678", "ORDERS"),
                environ=environ,
                env_file_paths=[],
            )


def test_n6_wrong_account_denied():
    environ = _env(
        QUANTMETRICS_EXECUTION_AUTHORIZED="1",
        QUANTMETRICS_ALLOWED_ACCOUNT_IDS="111",
        QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS="demo",
    )
    with pytest.raises(LiveExecutionDenied):
        assert_live_execution_allowed(
            LiveExecutionRequest("ctrader", "demo", "222", "ORDERS"),
            environ=environ,
            env_file_paths=[],
        )


def test_n7_demo_orders_allowed_when_policy_ok():
    environ = _env(
        QUANTMETRICS_EXECUTION_AUTHORIZED="1",
        QUANTMETRICS_ALLOWED_ACCOUNT_IDS="111",
        QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS="demo",
    )
    assert_live_execution_allowed(
        LiveExecutionRequest("ctrader", "demo", "111", "ORDERS"),
        environ=environ,
        env_file_paths=[],
    )


def test_n8_oanda_live_default_denied():
    environ = _env(QUANTMETRICS_ALLOWED_ACCOUNT_IDS="001-practice")
    with pytest.raises(LiveExecutionDenied):
        assert_live_execution_allowed(
            LiveExecutionRequest("oanda", "live", "001-practice", "SESSION"),
            environ=environ,
            env_file_paths=[],
        )


def test_n9_oanda_practice_orders_ok():
    environ = _env(
        QUANTMETRICS_EXECUTION_AUTHORIZED="1",
        QUANTMETRICS_ALLOWED_ACCOUNT_IDS="001-practice",
        QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS="practice",
    )
    assert_live_execution_allowed(
        LiveExecutionRequest("oanda", "practice", "001-practice", "ORDERS"),
        environ=environ,
        env_file_paths=[],
    )


@pytest.mark.parametrize(
    "line",
    [
        "QUANTMETRICS_EXECUTION_AUTHORIZED=1",
        "export QUANTMETRICS_EXECUTION_AUTHORIZED=1",
        "export\tQUANTMETRICS_EXECUTION_AUTHORIZED=1",
        "QUANTMETRICS_EXECUTION_AUTHORIZED = 1",
        "'QUANTMETRICS_EXECUTION_AUTHORIZED'=1",
    ],
)
def test_n10_dotenv_parser_forms_detected(tmp_path, line):
    """B1: dotenv_values detects export/tabs/quotes/spaced assignment."""
    dotenv = tmp_path / ".env"
    dotenv.write_text(line + "\n", encoding="utf-8")
    assert env_file_contains_gate_keys(dotenv) is True
    with pytest.raises(LiveExecutionDenied):
        assert_dotenv_path_has_no_gate_keys(dotenv)
    with pytest.raises(LiveExecutionDenied):
        assert_live_execution_allowed(
            LiveExecutionRequest("ctrader", "demo", "12345678", "ORDERS"),
            environ=_allowed_demo(QUANTMETRICS_EXECUTION_AUTHORIZED="1"),
            env_file_paths=[dotenv],
        )


def test_n10_behavioral_config_import_subprocess(tmp_path):
    """B2: real import of quantbuild.config with malicious .env denies; keys not retained."""
    dotenv = tmp_path / ".env"
    dotenv.write_text("export QUANTMETRICS_EXECUTION_AUTHORIZED=1\nFOO=bar\n", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in GATE_ENV_KEYS}
    env["PYTHONPATH"] = (
        f"{ROOT / 'quantbridge' / 'src'}:"
        f"{ROOT / 'quantbuild' / 'src'}:"
        f"{ROOT / 'quantbuild'}:"
        f"{ROOT}"
    )
    code = textwrap.dedent(
        f"""
        import os, sys
        os.chdir({str(tmp_path)!r})
        for k in {list(GATE_ENV_KEYS)!r}:
            os.environ.pop(k, None)
        try:
            import quantbuild.config as cfg  # noqa: F401
            print("IMPORT_OK")
            print("AUTH", repr(os.environ.get("QUANTMETRICS_EXECUTION_AUTHORIZED")))
            raise SystemExit(0)
        except Exception as e:
            print("DENIED", type(e).__name__, e)
            print("AUTH", repr(os.environ.get("QUANTMETRICS_EXECUTION_AUTHORIZED")))
            raise SystemExit(2)
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "IMPORT_OK" not in proc.stdout
    assert "LiveExecutionDenied" in proc.stdout or "gate_key" in proc.stdout.lower()
    # Gate key must not remain set after denial/restore
    assert "AUTH '1'" not in proc.stdout
    assert "AUTH None" in proc.stdout


def test_n10b_orchestrator_env_refuses_gate_keys(tmp_path):
    orch = tmp_path / "orchestrator"
    orch.mkdir()
    (orch / ".env").write_text(
        "export QUANTMETRICS_EXECUTION_AUTHORIZED=1\nFOO=bar\n", encoding="utf-8"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ROOT / 'quantbridge' / 'src'}:{ROOT}"
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent(
                f"""
                import sys
                from pathlib import Path
                import importlib.util
                path = Path({str(ROOT)!r}) / "quantmetrics_os/orchestrator/quantmetrics.py"
                spec = importlib.util.spec_from_file_location("qm_orch", path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                mod._ORCHESTRATOR_DIR = Path({str(orch)!r})
                try:
                    mod._bootstrap_env()
                    print("EXIT", 0)
                except SystemExit as e:
                    print("EXIT", int(e.code or 0))
                """
            ),
        ],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert "EXIT 2" in proc.stdout, proc.stdout + proc.stderr


@pytest.mark.parametrize(
    "body",
    [
        "QUANTMETRICS_EXECUTION_AUTHORIZED=1\n",
        "export QUANTMETRICS_EXECUTION_AUTHORIZED=1\n",
        "true; QUANTMETRICS_EXECUTION_AUTHORIZED=1\n",
        "declare -x QUANTMETRICS_EXECUTION_AUTHORIZED=1\n",
    ],
)
def test_n10c_run_live_sh_snapshot_denies_gate_mutation(tmp_path, body):
    env_file = tmp_path / "orch.env"
    env_file.write_text(body, encoding="utf-8")
    stub_py = tmp_path / "stub_python"
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
    assert proc.returncode == 2
    assert "STUB_RAN" not in proc.stdout
    assert "mutated gate keys" in proc.stderr.lower() or "refuse" in proc.stderr.lower()


def test_n10d_behavioral_hydrate_real_method(tmp_path):
    """B2: invoke real CTraderBroker._hydrate_credentials_from_dotenv and deny."""
    bridge_root = tmp_path / "quantbridge"
    bridge_root.mkdir()
    (bridge_root / "local.env").write_text(
        "export QUANTMETRICS_ALLOWED_ACCOUNT_IDS=123\nCTRADER_ACCOUNT_ID=99999999\n",
        encoding="utf-8",
    )
    # Ensure imports resolve
    sys.path.insert(0, str(ROOT / "quantbridge" / "src"))
    sys.path.insert(0, str(ROOT / "quantbuild" / "src"))
    sys.path.insert(0, str(ROOT / "quantbuild"))
    from src.quantbuild.execution.broker_ctrader import CTraderBroker

    broker = CTraderBroker(account_id="", access_token="x" * 40, mock_mode=True)
    with pytest.raises((LiveExecutionDenied, RuntimeError)) as exc:
        broker._hydrate_credentials_from_dotenv(bridge_root)
    msg = str(exc.value).lower()
    assert "gate_key" in msg or "liveexecutiondenied" in type(exc.value).__name__.lower()


def test_n10e_c1_openapi_connect_and_close_deny_with_local_env(tmp_path, monkeypatch):
    local_env = tmp_path / "local.env"
    local_env.write_text("export QUANTMETRICS_EXECUTION_AUTHORIZED=1\n", encoding="utf-8")
    from quantbridge.execution.clients.ctrader_openapi_client import CTraderOpenApiClient

    client = CTraderOpenApiClient(
        account_id="12345678",
        access_token="x" * 40,
        environment="demo",
    )
    monkeypatch.setattr(
        "quantbridge.safety.live_execution_gate.default_bridge_env_files",
        lambda root=None: [local_env],
    )
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_ACCOUNT_IDS", "12345678")
    monkeypatch.setenv("QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS", "demo")
    monkeypatch.setenv("QUANTMETRICS_EXECUTION_AUTHORIZED", "1")

    client_ctor_calls: list[object] = []
    fake = type(sys)("ctrader_open_api")

    class BoomClient:
        def __init__(self, *a, **k):
            client_ctor_calls.append(1)
            raise AssertionError("Client must not be constructed")

    fake.Client = BoomClient
    monkeypatch.setitem(sys.modules, "ctrader_open_api", fake)

    with pytest.raises(LiveExecutionDenied):
        client.connect()
    assert client_ctor_calls == []
    with pytest.raises(LiveExecutionDenied):
        client.close_trade("1")
    assert client_ctor_calls == []


@pytest.mark.parametrize("bad", ["0123", "12 3", "12a", " 123", "123 "])
def test_n11_ctrader_account_canonicalization(bad):
    with pytest.raises(LiveExecutionDenied):
        canonicalize_ctrader_account_id(bad)


def test_n12_gate_import_failure_denies_oanda(monkeypatch):
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


def test_b2_explicit_empty_env_allowlist_denies():
    environ = _env(
        QUANTMETRICS_EXECUTION_AUTHORIZED="1",
        QUANTMETRICS_ALLOWED_ACCOUNT_IDS="12345678",
        QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS="",
    )
    with pytest.raises(LiveExecutionDenied) as exc:
        assert_live_execution_allowed(
            LiveExecutionRequest("ctrader", "demo", "12345678", "ORDERS"),
            environ=environ,
            env_file_paths=[],
        )
    assert "environment_not_allowlisted" in str(exc.value)


def test_b2_ctrader_practice_denied_even_if_allowlisted():
    environ = _env(
        QUANTMETRICS_EXECUTION_AUTHORIZED="1",
        QUANTMETRICS_ALLOWED_ACCOUNT_IDS="12345678",
        QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS="demo,practice",
    )
    with pytest.raises(LiveExecutionDenied) as exc:
        assert_live_execution_allowed(
            LiveExecutionRequest("ctrader", "practice", "12345678", "SESSION"),
            environ=environ,
            env_file_paths=[],
        )
    assert "ctrader_practice_environment_rejected" in str(exc.value)
