"""Issue #106 — root CI preservation (V4) + A1/N2 hardening.

A1: reject job/step continue-on-error and soft-fail shells on mandatory runs.
N2: pytest-socket is a hard requirement (no importorskip).
"""
from __future__ import annotations

import re
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

# Soft-fail / fail-open shell patterns banned in mandatory CI run scripts (A1).
SOFT_FAIL_PATTERNS = (
    re.compile(r"\|\|\s*true\b"),
    re.compile(r"\|\|\s*:"),
    re.compile(r";\s*true\b"),
    re.compile(r"\bset\s+\+e\b"),
)


def _load_workflow_text(text: str) -> dict:
    data = yaml.safe_load(text)
    assert isinstance(data, dict)
    return data


def _load_workflow() -> dict:
    assert WORKFLOW.is_file(), f"missing workflow: {WORKFLOW}"
    return _load_workflow_text(WORKFLOW.read_text(encoding="utf-8"))


def _jobs(data: dict) -> dict:
    jobs = data.get("jobs") or {}
    assert isinstance(jobs, dict)
    return jobs


def _all_steps(data: dict) -> list[dict]:
    steps: list[dict] = []
    for job in _jobs(data).values():
        steps.extend(job.get("steps") or [])
    return steps


def _assert_no_continue_on_error(data: dict) -> None:
    """A1: continue-on-error forbidden at job and step level for mandatory CI."""
    for job_name, job in _jobs(data).items():
        assert job.get("continue-on-error") in (None, False), (
            f"continue-on-error not allowed on CI job: {job_name}"
        )
        for step in job.get("steps") or []:
            assert step.get("continue-on-error") in (None, False), (
                f"continue-on-error not allowed on CI step: {step.get('name')} (job={job_name})"
            )


def _assert_no_soft_fail_in_runs(data: dict) -> None:
    """A1: reject || true / || : / ; true / set +e in any run script."""
    for step in _all_steps(data):
        run = str(step.get("run") or "")
        if not run.strip():
            continue
        for pat in SOFT_FAIL_PATTERNS:
            assert not pat.search(run), (
                f"soft-fail pattern {pat.pattern!r} banned in CI run "
                f"(step={step.get('name')!r}): {run!r}"
            )


def _assert_required_commands_present(data: dict) -> None:
    runs = [str(s.get("run") or "") for s in _all_steps(data)]
    for snippet in REQUIRED_RUN_SNIPPETS:
        assert any(snippet in run for run in runs), f"missing required CI command: {snippet!r}"


def _assert_module_socket_guards(data: dict) -> None:
    steps = _all_steps(data)
    runs = [str(s.get("run") or "") for s in steps]
    assert any("quantanalytics/tests" in r and "--disable-socket" in r for r in runs)
    assert any("quantbuild/tests" in r and "--disable-socket" in r for r in runs)
    ql = [
        s
        for s in steps
        if s.get("working-directory") == "quantlog"
        and "pytest tests" in str(s.get("run") or "")
        and "--disable-socket" in str(s.get("run") or "")
    ]
    assert ql, "quantlog step must use working-directory: quantlog with socket guard"
    joined = "\n".join(runs)
    assert "quantresearch" not in joined.lower()


def assert_workflow_fail_closed(data: dict) -> None:
    """Full fail-closed CI contract used by live tests and A1 mutations."""
    _assert_required_commands_present(data)
    _assert_no_continue_on_error(data)
    _assert_no_soft_fail_in_runs(data)
    _assert_module_socket_guards(data)


def test_v4_ci_preserves_root_and_issue_104_commands():
    """Parse ci.yml: required #104 + demo remain; no soft-fail / continue-on-error."""
    assert_workflow_fail_closed(_load_workflow())


def test_v4_ci_includes_offline_module_suites_with_socket_guard():
    """#106 P1–P3 module steps must use pytest-socket offline flags."""
    _assert_module_socket_guards(_load_workflow())


def test_n2_socket_guard_blocks_network_hard_requirement():
    """N2: pytest_socket is mandatory; AF_INET socket construction must fail when disabled."""
    import pytest_socket  # noqa: F401 — hard fail if missing (no importorskip)
    import socket

    from pytest_socket import SocketBlockedError, disable_socket, enable_socket

    disable_socket(allow_unix_socket=True)
    try:
        with pytest.raises(SocketBlockedError):
            socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    finally:
        enable_socket()


# --- A1 mutation proofs (scratch workflow text; must be KILLED) ---


def test_a1_m01_demo_or_true_soft_fail_killed():
    """Mutant: `python run_demo.py || true` — previously SURVIVED; must now fail assert."""
    text = WORKFLOW.read_text(encoding="utf-8")
    mutated = text.replace("python run_demo.py", "python run_demo.py || true", 1)
    assert "|| true" in mutated
    data = _load_workflow_text(mutated)
    with pytest.raises(AssertionError, match="soft-fail|\\|\\|"):
        assert_workflow_fail_closed(data)


def test_a1_m02_job_continue_on_error_killed():
    """Mutant: job-level continue-on-error: true — previously SURVIVED; must now fail."""
    text = WORKFLOW.read_text(encoding="utf-8")
    # Insert under the primary job key.
    needle = "  test-and-demo:\n    runs-on: ubuntu-latest\n"
    repl = "  test-and-demo:\n    continue-on-error: true\n    runs-on: ubuntu-latest\n"
    assert needle in text
    mutated = text.replace(needle, repl, 1)
    data = _load_workflow_text(mutated)
    with pytest.raises(AssertionError, match="continue-on-error"):
        assert_workflow_fail_closed(data)


def test_a1_m03_missing_issue_104_nw_step_killed():
    """Mutant: remove N/W/mutation gate command — must fail required-command assert."""
    text = WORKFLOW.read_text(encoding="utf-8")
    snippet = (
        "pytest tests/test_live_execution_gate_n.py "
        "tests/test_live_execution_gate_w.py "
        "tests/test_live_execution_gate_mutation.py -q"
    )
    mutated = text.replace(snippet, "pytest tests/test_live_execution_gate_n.py -q  # mutated-drop-nw", 1)
    assert snippet not in mutated
    data = _load_workflow_text(mutated)
    with pytest.raises(AssertionError, match="missing required CI command"):
        assert_workflow_fail_closed(data)


def test_a1_m04_removed_socket_guard_killed():
    """Mutant: strip --disable-socket from module steps — must fail socket-guard assert."""
    text = WORKFLOW.read_text(encoding="utf-8")
    mutated = text.replace(" --disable-socket --allow-unix-socket", "", 3)
    assert "--disable-socket" not in mutated
    data = _load_workflow_text(mutated)
    with pytest.raises(AssertionError):
        assert_workflow_fail_closed(data)
