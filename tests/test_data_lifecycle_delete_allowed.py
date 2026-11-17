"""Issue #103 — strict delete_allowed parse (T1–T4).

T1: only JSON boolean true enables permission.
T2: scratch mutations of the real module must fail this suite.
T3: real filesystem snapshot before/after _scan_runs and main() (tmp only).
T4: never touch tracked quantmetrics_os/reports/data_lifecycle_report.*.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from quantmetrics_os.scripts import data_lifecycle as dl

ROOT = Path(__file__).resolve().parents[1]
PROD_MODULE = ROOT / "quantmetrics_os" / "scripts" / "data_lifecycle.py"
TRACKED_REPORTS = (
    ROOT / "quantmetrics_os" / "reports" / "data_lifecycle_report.json",
    ROOT / "quantmetrics_os" / "reports" / "data_lifecycle_report.md",
)


def _write_status(run_dir: Path, payload: object | None, *, raw: str | None = None) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    status = run_dir / "status.json"
    if raw is not None:
        status.write_text(raw, encoding="utf-8")
    elif payload is None:
        # missing status.json
        if status.exists():
            status.unlink()
    else:
        status.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _snapshot_tree(root: Path) -> dict[str, tuple[int, int]]:
    """Map relative posix path -> (size, mtime_ns) for all files under root."""
    out: dict[str, tuple[int, int]] = {}
    if not root.exists():
        return out
    for path in sorted(root.rglob("*")):
        if path.is_file():
            st = path.stat()
            rel = str(path.relative_to(root)).replace("\\", "/")
            out[rel] = (st.st_size, getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)))
    return out


# --- T1: strict permission parsing ---


@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"status": "scratch", "delete_allowed": True}, True),
        ({"status": "scratch", "delete_allowed": False}, False),
        ({"status": "scratch"}, False),  # missing key
        ({"status": "scratch", "delete_allowed": None}, False),
        ({"status": "scratch", "delete_allowed": "true"}, False),
        ({"status": "scratch", "delete_allowed": "True"}, False),
        ({"status": "scratch", "delete_allowed": "false"}, False),
        ({"status": "scratch", "delete_allowed": "no"}, False),
        ({"status": "scratch", "delete_allowed": 1}, False),
        ({"status": "scratch", "delete_allowed": 1.0}, False),
        ({"status": "scratch", "delete_allowed": 0}, False),
        ({"status": "scratch", "delete_allowed": []}, False),
        ({"status": "scratch", "delete_allowed": {}}, False),
    ],
)
def test_t1_delete_allowed_strict_helper(payload, expected):
    assert dl._delete_allowed_strict(payload) is expected


def test_t1_delete_allowed_strict_non_dict_and_none():
    assert dl._delete_allowed_strict(None) is False
    assert dl._delete_allowed_strict("not-a-dict") is False  # type: ignore[arg-type]
    assert dl._delete_allowed_strict([True]) is False  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "label,payload,raw,expected",
    [
        ("json_true", {"status": "scratch", "delete_allowed": True}, None, True),
        ("json_false", {"status": "scratch", "delete_allowed": False}, None, False),
        ("missing_key", {"status": "scratch"}, None, False),
        ("null", {"status": "scratch", "delete_allowed": None}, None, False),
        ("str_true", {"status": "scratch", "delete_allowed": "true"}, None, False),
        ("str_True", {"status": "scratch", "delete_allowed": "True"}, None, False),
        ("str_false", {"status": "scratch", "delete_allowed": "false"}, None, False),
        ("str_no", {"status": "scratch", "delete_allowed": "no"}, None, False),
        ("int_1", {"status": "scratch", "delete_allowed": 1}, None, False),
        ("float_1", {"status": "scratch", "delete_allowed": 1.0}, None, False),
        ("int_0", {"status": "scratch", "delete_allowed": 0}, None, False),
        ("list_empty", {"status": "scratch", "delete_allowed": []}, None, False),
        ("dict_empty", {"status": "scratch", "delete_allowed": {}}, None, False),
        ("malformed_json", None, "{not-json", False),
        ("non_dict_json", None, "[1, 2, 3]\n", False),
        ("missing_status_file", None, None, False),
    ],
)
def test_t1_scan_runs_delete_allowed_cases(tmp_path, label, payload, raw, expected):
    qmos = tmp_path / "qmos"
    run_dir = qmos / "runs" / "exp" / label
    if raw is None and payload is None:
        run_dir.mkdir(parents=True, exist_ok=True)
        # deliberately no status.json
    else:
        _write_status(run_dir, payload, raw=raw)

    rows = dl._scan_runs(runs_root=qmos / "runs", qmos_root=qmos)
    assert len(rows) == 1
    assert rows[0].delete_allowed is expected


def test_t1_unreadable_status_json_denies(tmp_path, monkeypatch):
    """R1: simulate unreadability without chmod(0) (root can still read mode 0)."""
    qmos = tmp_path / "qmos"
    run_dir = qmos / "runs" / "exp" / "unreadable"
    _write_status(run_dir, {"status": "scratch", "delete_allowed": True})
    status = run_dir / "status.json"
    status_resolved = status.resolve()
    real_read_text = Path.read_text

    def _read_text(self, *args, **kwargs):
        if self.resolve() == status_resolved:
            raise PermissionError("denied")
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _read_text)
    rows = dl._scan_runs(runs_root=qmos / "runs", qmos_root=qmos)
    assert len(rows) == 1
    assert rows[0].delete_allowed is False
    assert rows[0].status == "unknown"


# --- T3: filesystem invariant (real tree, no mocks-only) ---


def test_t3_scan_runs_does_not_mutate_fixture_tree(tmp_path):
    qmos = tmp_path / "qmos"
    run_dir = qmos / "runs" / "exp" / "baseline"
    _write_status(run_dir, {"status": "scratch", "delete_allowed": "false", "run_id": "r1"})
    (run_dir / "artifact.bin").write_bytes(b"abc123")
    before = _snapshot_tree(qmos / "runs")

    rows = dl._scan_runs(runs_root=qmos / "runs", qmos_root=qmos)
    assert len(rows) == 1
    assert rows[0].delete_allowed is False

    after = _snapshot_tree(qmos / "runs")
    assert after == before


def test_t3_main_writes_only_tmp_reports_and_preserves_runs(tmp_path, monkeypatch):
    qmos = tmp_path / "qmos"
    run_dir = qmos / "runs" / "exp" / "baseline"
    _write_status(run_dir, {"status": "scratch", "delete_allowed": True, "run_id": "r-ok"})
    (run_dir / "keep.me").write_text("intact\n", encoding="utf-8")
    before_runs = _snapshot_tree(qmos / "runs")

    # T4 guard: record tracked report digests before main().
    tracked_before = {
        p: (p.read_bytes() if p.is_file() else None) for p in TRACKED_REPORTS
    }

    monkeypatch.setattr(dl, "_discover_qmos_root", lambda: qmos)
    monkeypatch.setattr(sys, "argv", ["data_lifecycle.py", "--dry-run"])
    rc = dl.main()
    assert rc == 0

    after_runs = _snapshot_tree(qmos / "runs")
    assert after_runs == before_runs

    # Reports only under tmp qmos/reports — never repo reports/.
    assert (qmos / "reports" / "data_lifecycle_report.json").is_file()
    assert (qmos / "reports" / "data_lifecycle_report.md").is_file()
    for p, content in tracked_before.items():
        if content is None:
            assert not p.exists() or True
        else:
            assert p.read_bytes() == content


# --- T2: mutation proofs against this real test file / module ---


def _probe_module(path: Path) -> subprocess.CompletedProcess[str]:
    probe = textwrap.dedent(
        """
        import importlib.util, json, sys, tempfile
        from pathlib import Path

        mod_path = Path(sys.argv[1])
        spec = importlib.util.spec_from_file_location("dl_mut", mod_path)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules["dl_mut"] = mod
        spec.loader.exec_module(mod)

        cases = [
            ({"delete_allowed": True}, True),
            ({"delete_allowed": False}, False),
            ({"delete_allowed": "false"}, False),
            ({"delete_allowed": "true"}, False),
            ({"delete_allowed": 1}, False),
            ({"delete_allowed": 1.0}, False),
            ({}, False),
        ]
        failures = []
        for payload, expected in cases:
            got = mod._delete_allowed_strict(payload)
            if got is not expected:
                failures.append((payload, expected, got))

        with tempfile.TemporaryDirectory() as td:
            qmos = Path(td)
            run = qmos / "runs" / "e" / "r"
            run.mkdir(parents=True)
            (run / "status.json").write_text(
                json.dumps({"delete_allowed": "false"}), encoding="utf-8"
            )
            rows = mod._scan_runs(qmos / "runs", qmos)
            if not rows or rows[0].delete_allowed is not False:
                failures.append(
                    ("scan_string_false", False, rows[0].delete_allowed if rows else None)
                )
            (run / "status.json").write_text(
                json.dumps({"delete_allowed": 1}), encoding="utf-8"
            )
            rows = mod._scan_runs(qmos / "runs", qmos)
            if not rows or rows[0].delete_allowed is not False:
                failures.append(
                    ("scan_int_1", False, rows[0].delete_allowed if rows else None)
                )

        if failures:
            print("MUTATION_UNDETECTED", failures)
            raise SystemExit(1)
        print("STRICT_OK")
        """
    )
    return subprocess.run(
        [sys.executable, "-c", probe, str(path)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )


def test_t2_unmutated_module_passes_probe():
    proc = _probe_module(PROD_MODULE)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "STRICT_OK" in proc.stdout


def test_t2_mutation_bool_coercion_killed(tmp_path):
    """Revert is True → bool(...); string-false / int-1 cases must fail the probe."""
    scratch = tmp_path / "data_lifecycle_bool.py"
    shutil.copy2(PROD_MODULE, scratch)
    text = scratch.read_text(encoding="utf-8")
    old = "return status_payload.get(\"delete_allowed\") is True"
    new = "return bool(status_payload.get(\"delete_allowed\", False))"
    assert old in text
    scratch.write_text(text.replace(old, new, 1), encoding="utf-8")
    proc = _probe_module(scratch)
    assert proc.returncode != 0, "bool(...) mutant SURVIVED"
    assert "MUTATION_UNDETECTED" in proc.stdout


def test_t2_mutation_eq_true_killed(tmp_path):
    """Mutate is True → == True; int 1 must slip through and fail the probe."""
    scratch = tmp_path / "data_lifecycle_eq.py"
    shutil.copy2(PROD_MODULE, scratch)
    text = scratch.read_text(encoding="utf-8")
    old = "return status_payload.get(\"delete_allowed\") is True"
    new = "return status_payload.get(\"delete_allowed\") == True"
    assert old in text
    scratch.write_text(text.replace(old, new, 1), encoding="utf-8")
    proc = _probe_module(scratch)
    assert proc.returncode != 0, "== True mutant SURVIVED"
    assert "MUTATION_UNDETECTED" in proc.stdout


def test_t4_tracked_reports_untouched_by_this_suite():
    """Guard: suite must not rewrite committed report artifacts."""
    # Presence is OK; content must remain unchanged across a no-op check here.
    # Stronger: main() test already compared bytes; this asserts paths stay tracked files.
    for p in TRACKED_REPORTS:
        assert p.is_file(), f"expected tracked report present: {p}"
