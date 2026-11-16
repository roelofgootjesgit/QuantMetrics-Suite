"""Issue #104 PR-A — policy negative tests N1–N12 / N10* (no network)."""
from __future__ import annotations

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
    for bad in ("", "prod", "Practice", "practice"):
        with pytest.raises(LiveExecutionDenied):
            assert_live_execution_allowed(
                LiveExecutionRequest("ctrader", bad, "12345678", "SESSION"),
                environ=_allowed_demo(),
                env_file_paths=[],
            )
        with pytest.raises(LiveExecutionDenied):
            resolve_ctrader_host(bad, environ=_allowed_demo())


def test_n2_live_default_allowlist_denied():
    environ = _env(QUANTMETRICS_ALLOWED_ACCOUNT_IDS="12345678")  # default demo-only
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
    with pytest.raises(LiveExecutionDenied):
        assert_live_execution_allowed(
            LiveExecutionRequest("ctrader", "live", "12345678", "SESSION"),
            environ=environ,
            env_file_paths=[],
            enablement_path=Path("/nonexistent/execution_authorization"),
        )


def test_n3b_c3_live_allowlisted_auth_one_still_frozen():
    """C3: auth=1 + allowlist live still DENY while enablement file absent."""
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


def test_n10_dotenv_gate_keys_denied_c2(tmp_path, monkeypatch):
    """C2: scan exact find_dotenv path; presence of gate key => deny."""
    dotenv = tmp_path / ".env"
    dotenv.write_text("QUANTMETRICS_EXECUTION_AUTHORIZED=1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(LiveExecutionDenied):
        assert_dotenv_path_has_no_gate_keys(dotenv)

    # Process missing auth: dotenv file with key still denies via env_file scan.
    with pytest.raises(LiveExecutionDenied):
        assert_live_execution_allowed(
            LiveExecutionRequest("ctrader", "demo", "12345678", "ORDERS"),
            environ=_env(
                QUANTMETRICS_ALLOWED_ACCOUNT_IDS="12345678",
                QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS="demo",
            ),
            env_file_paths=[dotenv],
        )
    # Process explicitly 0: dotenv cannot override — file presence still denies.
    with pytest.raises(LiveExecutionDenied):
        assert_live_execution_allowed(
            LiveExecutionRequest("ctrader", "demo", "12345678", "ORDERS"),
            environ=_env(
                QUANTMETRICS_EXECUTION_AUTHORIZED="0",
                QUANTMETRICS_ALLOWED_ACCOUNT_IDS="12345678",
                QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS="demo",
            ),
            env_file_paths=[dotenv],
        )


def test_n10b_orchestrator_env_refuses_gate_keys(tmp_path):
    orch = tmp_path / "orchestrator"
    orch.mkdir()
    (orch / ".env").write_text("QUANTMETRICS_EXECUTION_AUTHORIZED=1\nFOO=bar\n", encoding="utf-8")
    script = textwrap.dedent(
        f"""
        import runpy, sys
        from pathlib import Path
        import quantmetrics_os.orchestrator.quantmetrics as qm
        qm._ORCHESTRATOR_DIR = Path({str(orch)!r})
        # Patch child spawn tracker
        calls = []
        def fake_call(*a, **k):
            calls.append(1)
            return 0
        import subprocess
        subprocess.call = fake_call
        try:
            qm._bootstrap_env()
        except SystemExit as e:
            print("EXIT", e.code)
            print("CALLS", len(calls))
            raise SystemExit(0)
        print("EXIT", 0)
        print("CALLS", len(calls))
        """
    )
    # Run inline by importing after path setup
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent(
                f"""
                import sys
                from pathlib import Path
                sys.path.insert(0, {str(ROOT)!r})
                # Load module file directly for _bootstrap_env
                import importlib.util
                path = Path({str(ROOT)!r}) / "quantmetrics_os/orchestrator/quantmetrics.py"
                spec = importlib.util.spec_from_file_location("qm_orch", path)
                mod = importlib.util.module_from_spec(spec)
                # Provide directory override via monkeypatch after load
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


def test_n10c_run_live_sh_refuses_gate_keys(tmp_path):
    env_file = tmp_path / "orch.env"
    env_file.write_text("QUANTMETRICS_EXECUTION_AUTHORIZED=1\n", encoding="utf-8")
    stub_py = tmp_path / "stub_python"
    stub_py.write_text("#!/bin/sh\necho STUB_RAN\nexit 0\n", encoding="utf-8")
    stub_py.chmod(0o755)
    script = ROOT / "quantbuild/scripts/vps/run_live.sh"
    proc = subprocess.run(
        ["bash", str(script), "live", "--dry-run"],
        cwd=str(ROOT / "quantbuild"),
        env={
            **os.environ,
            "QUANTBUILD_ROOT": str(ROOT / "quantbuild"),
            "QUANTBUILD_ORCHESTRATOR_ENV": str(env_file),
            "PYTHON": str(stub_py),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "STUB_RAN" not in proc.stdout
    assert "gate key" in proc.stderr.lower() or "refuse" in proc.stderr.lower()


def test_n10d_bridge_local_env_gate_key_denies_hydrate(tmp_path, monkeypatch):
    """R1/d: bridge local.env with gate keys denies before real-client hydration."""
    bridge_root = tmp_path / "quantbridge"
    bridge_root.mkdir()
    (bridge_root / "local.env").write_text(
        "QUANTMETRICS_ALLOWED_ACCOUNT_IDS=123\nCTRADER_ACCOUNT_ID=999\n",
        encoding="utf-8",
    )
    # Exercise the same deny path as broker_ctrader._hydrate_credentials_from_dotenv
    # without importing the full QuantBuild config stack (yaml optional in root CI).
    from quantbridge.safety.live_execution_gate import (
        LiveExecutionDenied,
        default_bridge_env_files,
        env_file_contains_gate_keys,
    )

    hits = [
        p for p in default_bridge_env_files(root=bridge_root) if env_file_contains_gate_keys(p)
    ]
    assert hits, "expected local.env gate-key detection"
    with pytest.raises(LiveExecutionDenied):
        assert_live_execution_allowed(
            LiveExecutionRequest("ctrader", "demo", "12345678", "SESSION"),
            environ=_allowed_demo(),
            env_file_paths=hits,
        )

    # Bind-check the broker hydrate path still references the gate helpers.
    broker_src = (
        ROOT / "quantbuild/src/quantbuild/execution/broker_ctrader.py"
    ).read_text(encoding="utf-8")
    assert "env_file_contains_gate_keys" in broker_src
    assert "gate_key_present_in_env_file" in broker_src


def test_n10e_c1_openapi_connect_and_close_deny_with_local_env(tmp_path, monkeypatch):
    """C1: direct OpenAPI client denies when bridge local.env has gate keys (no QB)."""
    local_env = tmp_path / "local.env"
    local_env.write_text("QUANTMETRICS_EXECUTION_AUTHORIZED=1\n", encoding="utf-8")
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
    # Even with process auth present, local.env gate key must deny (C1).
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
