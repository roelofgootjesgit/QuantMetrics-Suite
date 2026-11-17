"""Issue #106 / #119 — root CI preservation (V4) + A1/N2 hardening.

A1: reject job/step continue-on-error and soft-fail shells on mandatory runs.
N2: pytest-socket is a hard requirement (no importorskip).
#119 Impl-A: exact allowlist for mandatory runs; reject job/step if: and
shell: overrides on mandatory steps; kill V4-M01–M09 mutants.
#119 B1 repair: X1 step shell (existing), X2 defaults.run.shell, X3 pytest env
bypass keys, X4 push+pull_request triggers (YAML ``on`` → ``True``).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

# Exact step `run` strings (strip) for mandatory #104 + root + demo (#119 V4).
REQUIRED_EXACT_RUNS = (
    "pytest tests -q",
    "pytest tests/test_live_execution_gate_n.py tests/test_live_execution_gate_w.py tests/test_live_execution_gate_mutation.py -q",
    "pytest tests/test_live_execution_gate_e.py tests/test_live_execution_gate_e_mutation.py -q",
    "python run_demo.py",
)

# Soft-fail / fail-open shell patterns banned in mandatory CI run scripts (A1 + #119).
SOFT_FAIL_PATTERNS = (
    re.compile(r"\|\|\s*true\b"),
    re.compile(r"\|\|\s*:"),
    re.compile(r";\s*true\b"),
    re.compile(r"\bset\s+\+e\b"),
    re.compile(r"\|\|\s*exit\s+0\b"),
)

# #119 X3: env keys that can bypass exact pytest allowlist / plugin policy.
BANNED_PYTEST_ENV_KEYS = frozenset({"PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PYTHONPATH"})

# #119 X4: restrictive filters on required triggers (prefer disallow).
RESTRICTIVE_TRIGGER_FILTER_KEYS = frozenset(
    {"branches", "branches-ignore", "paths", "paths-ignore", "tags", "tags-ignore"}
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


def _workflow_on(data: dict):
    """Return workflow ``on:`` block.

    PyYAML 1.1 loaders map the key ``on`` to boolean ``True``.
    """
    if "on" in data:
        return data["on"]
    if True in data:
        return data[True]
    raise AssertionError("workflow missing on: triggers")


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
    """A1/#119: reject || true / || : / ; true / set +e / || exit 0 in any run script."""
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
    """#119 V4: each mandatory command must appear as an exact step run (strip)."""
    runs = [str(s.get("run") or "").strip() for s in _all_steps(data)]
    for required in REQUIRED_EXACT_RUNS:
        assert required in runs, f"missing required CI command (exact): {required!r}"


def _assert_no_if_on_jobs_or_steps(data: dict) -> None:
    """#119 O3: any job/step if: is forbidden (blocks if: false soft-skip)."""
    for job_name, job in _jobs(data).items():
        assert "if" not in job, f"if: not allowed on CI job: {job_name}"
        for step in job.get("steps") or []:
            assert "if" not in step, (
                f"if: not allowed on CI step: {step.get('name')!r} (job={job_name})"
            )


def _assert_no_shell_on_mandatory_steps(data: dict) -> None:
    """#119 O3 / X1: shell: override forbidden on steps carrying exact allowlisted runs."""
    allow = set(REQUIRED_EXACT_RUNS)
    for step in _all_steps(data):
        run = str(step.get("run") or "").strip()
        if run not in allow:
            continue
        assert "shell" not in step, (
            f"shell: override not allowed on mandatory step: {step.get('name')!r}"
        )


def _assert_no_defaults_run_shell(data: dict) -> None:
    """#119 X2: defaults.run.shell forbidden at workflow and job level."""
    defaults = data.get("defaults")
    if isinstance(defaults, dict):
        run_defaults = defaults.get("run")
        if isinstance(run_defaults, dict):
            assert "shell" not in run_defaults, (
                "defaults.run.shell not allowed at workflow level"
            )
    for job_name, job in _jobs(data).items():
        jdef = job.get("defaults")
        if not isinstance(jdef, dict):
            continue
        jrun = jdef.get("run")
        if isinstance(jrun, dict):
            assert "shell" not in jrun, (
                f"defaults.run.shell not allowed on CI job: {job_name}"
            )


def _env_mapping(raw) -> dict:
    if raw is None:
        return {}
    assert isinstance(raw, dict), f"env must be a mapping, got {type(raw)!r}"
    return raw


def _assert_env_no_banned_pytest_keys(env: dict, where: str) -> None:
    banned = sorted(BANNED_PYTEST_ENV_KEYS.intersection(env.keys()))
    assert not banned, (
        f"banned pytest env key(s) {banned} not allowed in {where} "
        f"(PYTEST_ADDOPTS/PYTEST_PLUGINS/PYTHONPATH)"
    )


def _assert_no_banned_pytest_env(data: dict) -> None:
    """#119 X3: reject PYTEST_ADDOPTS / PYTEST_PLUGINS / PYTHONPATH at workflow/job/mandatory step."""
    _assert_env_no_banned_pytest_keys(_env_mapping(data.get("env")), "workflow env")
    allow = set(REQUIRED_EXACT_RUNS)
    for job_name, job in _jobs(data).items():
        _assert_env_no_banned_pytest_keys(
            _env_mapping(job.get("env")), f"job env ({job_name})"
        )
        for step in job.get("steps") or []:
            run = str(step.get("run") or "").strip()
            if run not in allow:
                continue
            _assert_env_no_banned_pytest_keys(
                _env_mapping(step.get("env")),
                f"mandatory step env ({step.get('name')!r})",
            )


def _assert_required_triggers(data: dict) -> None:
    """#119 X4: require push + pull_request; reject restrictive filters on them."""
    on = _workflow_on(data)
    if isinstance(on, str):
        triggers = {on}
        configs: dict = {}
    elif isinstance(on, list):
        triggers = {str(x) for x in on}
        configs = {}
    elif isinstance(on, dict):
        triggers = {str(k) for k in on.keys()}
        configs = on
    else:
        raise AssertionError(f"unsupported on: value type {type(on)!r}")

    assert "push" in triggers, "workflow on: must include push"
    assert "pull_request" in triggers, "workflow on: must include pull_request"

    for name in ("push", "pull_request"):
        cfg = configs.get(name)
        if cfg is None:
            continue
        if not isinstance(cfg, dict):
            # bare / non-mapping value — treat as unrestricted trigger OK
            continue
        present = sorted(RESTRICTIVE_TRIGGER_FILTER_KEYS.intersection(cfg.keys()))
        assert not present, (
            f"restrictive on.{name} filter(s) {present} not allowed "
            "(must not exclude PRs to main / path-filter CI)"
        )


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
    # Impl-B will replace this ban with a positive QR requirement; keep for Impl-A.
    assert "quantresearch" not in joined.lower()


def assert_workflow_fail_closed(data: dict) -> None:
    """Full fail-closed CI contract used by live tests and V4/A1/X mutations."""
    _assert_required_triggers(data)
    _assert_required_commands_present(data)
    _assert_no_continue_on_error(data)
    _assert_no_soft_fail_in_runs(data)
    _assert_no_if_on_jobs_or_steps(data)
    _assert_no_shell_on_mandatory_steps(data)
    _assert_no_defaults_run_shell(data)
    _assert_no_banned_pytest_env(data)
    _assert_module_socket_guards(data)


def test_v4_ci_preserves_root_and_issue_104_commands():
    """Parse ci.yml: required #104 + demo remain; no soft-fail / continue-on-error / if / shell."""
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
    with pytest.raises(AssertionError, match="missing required CI command|soft-fail|\\|\\|"):
        assert_workflow_fail_closed(data)


def test_a1_m02_job_continue_on_error_killed():
    """Mutant: job-level continue-on-error: true — previously SURVIVED; must now fail."""
    text = WORKFLOW.read_text(encoding="utf-8")
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


# --- #119 V4-M01–M09 mutation proofs ---


def test_v4_m01_pytest_or_exit_0_killed():
    """V4-M01: `pytest tests -q || exit 0` must fail exact allowlist and/or soft-fail denylist."""
    text = WORKFLOW.read_text(encoding="utf-8")
    mutated = text.replace("pytest tests -q", "pytest tests -q || exit 0", 1)
    assert "|| exit 0" in mutated
    data = _load_workflow_text(mutated)
    with pytest.raises(AssertionError, match="missing required CI command|soft-fail|\\|\\|"):
        assert_workflow_fail_closed(data)


def test_v4_m02_demo_or_exit_0_killed():
    """V4-M02: `python run_demo.py || exit 0` must fail."""
    text = WORKFLOW.read_text(encoding="utf-8")
    mutated = text.replace("python run_demo.py", "python run_demo.py || exit 0", 1)
    assert "|| exit 0" in mutated
    data = _load_workflow_text(mutated)
    with pytest.raises(AssertionError, match="missing required CI command|soft-fail|\\|\\|"):
        assert_workflow_fail_closed(data)


def test_v4_m03_job_continue_on_error_killed():
    """V4-M03: job continue-on-error: true must fail."""
    text = WORKFLOW.read_text(encoding="utf-8")
    needle = "  test-and-demo:\n    runs-on: ubuntu-latest\n"
    repl = "  test-and-demo:\n    continue-on-error: true\n    runs-on: ubuntu-latest\n"
    assert needle in text
    data = _load_workflow_text(text.replace(needle, repl, 1))
    with pytest.raises(AssertionError, match="continue-on-error"):
        assert_workflow_fail_closed(data)


def test_v4_m04_step_continue_on_error_demo_killed():
    """V4-M04: step continue-on-error on demo must fail."""
    text = WORKFLOW.read_text(encoding="utf-8")
    needle = "      - name: Run deterministic demo\n        run: python run_demo.py\n"
    repl = (
        "      - name: Run deterministic demo\n"
        "        continue-on-error: true\n"
        "        run: python run_demo.py\n"
    )
    assert needle in text
    data = _load_workflow_text(text.replace(needle, repl, 1))
    with pytest.raises(AssertionError, match="continue-on-error"):
        assert_workflow_fail_closed(data)


def test_v4_m05_drop_nw_gate_killed():
    """V4-M05: drop N/W gate command must fail exact allowlist."""
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


def test_v4_m06_strip_socket_guard_killed():
    """V4-M06: strip --disable-socket from module steps must fail."""
    text = WORKFLOW.read_text(encoding="utf-8")
    mutated = text.replace(" --disable-socket --allow-unix-socket", "", 3)
    assert "--disable-socket" not in mutated
    data = _load_workflow_text(mutated)
    with pytest.raises(AssertionError):
        assert_workflow_fail_closed(data)


def test_v4_m07_step_if_false_killed():
    """V4-M07: mandatory step `if: false` must fail."""
    text = WORKFLOW.read_text(encoding="utf-8")
    needle = "      - name: Run tests\n        run: pytest tests -q\n"
    repl = "      - name: Run tests\n        if: false\n        run: pytest tests -q\n"
    assert needle in text
    data = _load_workflow_text(text.replace(needle, repl, 1))
    with pytest.raises(AssertionError, match=r"\bif:"):
        assert_workflow_fail_closed(data)


def test_v4_m08_job_if_false_killed():
    """V4-M08: job `if: false` must fail."""
    text = WORKFLOW.read_text(encoding="utf-8")
    needle = "  test-and-demo:\n    runs-on: ubuntu-latest\n"
    repl = "  test-and-demo:\n    if: false\n    runs-on: ubuntu-latest\n"
    assert needle in text
    data = _load_workflow_text(text.replace(needle, repl, 1))
    with pytest.raises(AssertionError, match=r"\bif:"):
        assert_workflow_fail_closed(data)


def test_v4_m09_shell_override_on_mandatory_killed():
    """V4-M09: shell: override on mandatory step must fail."""
    text = WORKFLOW.read_text(encoding="utf-8")
    needle = "      - name: Run tests\n        run: pytest tests -q\n"
    repl = "      - name: Run tests\n        shell: bash {0}\n        run: pytest tests -q\n"
    assert needle in text
    data = _load_workflow_text(text.replace(needle, repl, 1))
    with pytest.raises(AssertionError, match="shell:"):
        assert_workflow_fail_closed(data)


# --- #119 B1 repair: X1–X4 mutation proofs ---


def test_x1_mandatory_step_shell_killed():
    """X1: mandatory step shell: override must be KILLED (same contract as V4-M09)."""
    text = WORKFLOW.read_text(encoding="utf-8")
    needle = "      - name: Run tests\n        run: pytest tests -q\n"
    repl = "      - name: Run tests\n        shell: bash {0}\n        run: pytest tests -q\n"
    assert needle in text
    data = _load_workflow_text(text.replace(needle, repl, 1))
    with pytest.raises(AssertionError, match="shell:"):
        assert_workflow_fail_closed(data)


def test_x2_workflow_defaults_run_shell_killed():
    """X2: workflow defaults.run.shell (bash -c 'exit 0' {0}) must be KILLED."""
    data = _load_workflow()
    data["defaults"] = {"run": {"shell": "bash -c 'exit 0' {0}"}}
    with pytest.raises(AssertionError, match="defaults\\.run\\.shell"):
        assert_workflow_fail_closed(data)


def test_x2_job_defaults_run_shell_killed():
    """X2: job-level defaults.run.shell must be KILLED."""
    data = _load_workflow()
    job = _jobs(data)["test-and-demo"]
    job["defaults"] = {"run": {"shell": "bash -c 'exit 0' {0}"}}
    with pytest.raises(AssertionError, match="defaults\\.run\\.shell"):
        assert_workflow_fail_closed(data)


def test_x3_workflow_env_pytest_addopts_killed():
    """X3: workflow env PYTEST_ADDOPTS=--collect-only must be KILLED."""
    data = _load_workflow()
    data["env"] = {"PYTEST_ADDOPTS": "--collect-only"}
    with pytest.raises(AssertionError, match="PYTEST_ADDOPTS|banned pytest env"):
        assert_workflow_fail_closed(data)


def test_x3_job_env_pytest_plugins_killed():
    """X3: job env PYTEST_PLUGINS must be KILLED."""
    data = _load_workflow()
    _jobs(data)["test-and-demo"]["env"] = {"PYTEST_PLUGINS": "no:cacheprovider"}
    with pytest.raises(AssertionError, match="PYTEST_PLUGINS|banned pytest env"):
        assert_workflow_fail_closed(data)


def test_x3_mandatory_step_env_pythonpath_killed():
    """X3: PYTHONPATH on a mandatory allowlisted step must be KILLED."""
    data = _load_workflow()
    for step in _jobs(data)["test-and-demo"]["steps"]:
        if str(step.get("run") or "").strip() == "pytest tests -q":
            step["env"] = {"PYTHONPATH": "/tmp/evil"}
            break
    else:
        raise AssertionError("mandatory pytest tests -q step not found for X3 mutant")
    with pytest.raises(AssertionError, match="PYTHONPATH|banned pytest env"):
        assert_workflow_fail_closed(data)


def test_x4_workflow_dispatch_only_killed():
    """X4: on: workflow_dispatch only (no push/pull_request) must be KILLED."""
    data = _load_workflow()
    # Replace triggers; support PyYAML ``on`` → True key.
    if "on" in data:
        data["on"] = "workflow_dispatch"
    else:
        data[True] = "workflow_dispatch"
    with pytest.raises(AssertionError, match="push|pull_request"):
        assert_workflow_fail_closed(data)


def test_x4_pull_request_paths_filter_killed():
    """X4: restrictive pull_request paths filter must be KILLED."""
    data = _load_workflow()
    on_key = "on" if "on" in data else True
    data[on_key] = {
        "push": None,
        "pull_request": {"paths": ["docs/**"]},
    }
    with pytest.raises(AssertionError, match="restrictive|paths"):
        assert_workflow_fail_closed(data)
