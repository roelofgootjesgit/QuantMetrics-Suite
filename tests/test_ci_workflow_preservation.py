"""Issue #106 V4 — root CI must keep #104 gate commands and demo fail-closed."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

REQUIRED_RUN_SNIPPETS = (
    "pytest tests -q",
    "pytest tests/test_live_execution_gate_n.py tests/test_live_execution_gate_w.py tests/test_live_execution_gate_mutation.py -q",
    "pytest tests/test_live_execution_gate_e.py tests/test_live_execution_gate_e_mutation.py -q",
    "python run_demo.py",
)

def _load_workflow() -> dict:
    assert WORKFLOW.is_file(), f"missing workflow: {WORKFLOW}"
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _all_steps(data: dict) -> list[dict]:
    jobs = data.get("jobs") or {}
    steps: list[dict] = []
    for job in jobs.values():
        steps.extend(job.get("steps") or [])
    return steps


def test_v4_ci_preserves_root_and_issue_104_commands():
    """Parse ci.yml: required #104 + demo run lines remain; no continue-on-error."""
    data = _load_workflow()
    steps = _all_steps(data)
    runs = [str(s.get("run") or "") for s in steps]

    for snippet in REQUIRED_RUN_SNIPPETS:
        assert any(snippet in run for run in runs), f"missing required CI command: {snippet!r}"

    for step in steps:
        assert step.get("continue-on-error") in (None, False), (
            f"continue-on-error not allowed on CI steps: {step.get('name')}"
        )


def test_v4_ci_includes_offline_module_suites_with_socket_guard():
    """#106 P1–P3 module steps must use pytest-socket offline flags."""
    data = _load_workflow()
    steps = _all_steps(data)
    runs = [str(s.get("run") or "") for s in steps]

    assert any("quantanalytics/tests" in r and "--disable-socket" in r for r in runs)
    assert any("quantbuild/tests" in r and "--disable-socket" in r for r in runs)

    # quantlog runs from its own cwd (fixture paths); command is `pytest tests ...`
    ql = [
        s
        for s in steps
        if s.get("working-directory") == "quantlog"
        and "pytest tests" in str(s.get("run") or "")
        and "--disable-socket" in str(s.get("run") or "")
    ]
    assert ql, "quantlog step must use working-directory: quantlog with socket guard"

    # QuantResearch must stay out of this PR's CI (V3).
    joined = "\n".join(runs)
    assert "quantresearch" not in joined.lower()


def test_v2_socket_guard_blocks_network():
    """Negative proof: with sockets disabled, AF_INET socket construction fails."""
    pytest.importorskip("pytest_socket")
    import socket

    from pytest_socket import SocketBlockedError, disable_socket, enable_socket

    disable_socket(allow_unix_socket=True)
    try:
        with pytest.raises(SocketBlockedError):
            socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    finally:
        enable_socket()
