"""Tests for QuantBuild -> QuantMetrics OS artifact collection."""

from __future__ import annotations

import subprocess
from pathlib import Path

from src.quantbuild.integration import quantos_artifacts


class _Emitter:
    run_id = "qb_run_test_1234"


def test_custom_artifact_role_is_passed_to_collector(monkeypatch, tmp_path: Path) -> None:
    qb_root = tmp_path / "quantbuild"
    qmos_root = tmp_path / "quantmetrics_os"
    runs_dir = qb_root / "data" / "quantlog_events" / "runs"
    scripts_dir = qmos_root / "scripts"
    runs_dir.mkdir(parents=True)
    scripts_dir.mkdir(parents=True)
    config_path = qb_root / "config.yaml"
    config_path.write_text("symbol: XAUUSD\n", encoding="utf-8")
    (scripts_dir / "collect_run_artifact.py").write_text("pass\n", encoding="utf-8")

    monkeypatch.setattr(quantos_artifacts, "quantbuild_project_root", lambda: qb_root)

    captured: dict[str, list[str]] = {}

    def fake_run(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="/tmp/artifacts\n", stderr="")

    monkeypatch.setattr(quantos_artifacts.subprocess, "run", fake_run)

    quantos_artifacts.invoke_collect_run_artifacts(
        {
            "_quantbuild_config_path": str(config_path),
            "artifacts": {
                "enabled": True,
                "experiment_id": "EXP-003",
                "role": "variant_xauusd",
                "quantmetrics_os_root": str(qmos_root),
                "bundle_analytics": False,
            },
        },
        _Emitter(),
    )

    cmd = captured["cmd"]
    role_arg = cmd[cmd.index("--role") + 1]
    assert role_arg == "variant_xauusd"
