"""Tests for QuantBuild -> QuantOS artifact collection integration."""
from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

from src.quantbuild.integration import quantos_artifacts


def test_collect_artifacts_falls_back_to_top_level_experiment_id(monkeypatch, tmp_path: Path) -> None:
    qb_root = tmp_path / "quantbuild"
    qb_root.mkdir()
    qm_root = tmp_path / "quantmetrics_os"
    script = qm_root / "scripts" / "collect_run_artifact.py"
    script.parent.mkdir(parents=True)
    script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

    captured: dict[str, list[str]] = {}

    def fake_write_runtime_config_yaml(cfg: dict, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("experiment_id: EXP-BB-MECH-001\n", encoding="utf-8")

    def fake_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="artifact-dir\n", stderr="")

    monkeypatch.delenv("QUANTMETRICS_ARTIFACTS", raising=False)
    monkeypatch.setattr(quantos_artifacts, "quantbuild_project_root", lambda: qb_root)
    monkeypatch.setattr(quantos_artifacts, "write_runtime_config_yaml", fake_write_runtime_config_yaml)
    monkeypatch.setattr(quantos_artifacts.subprocess, "run", fake_run)

    cfg = {
        "experiment_id": "EXP-BB-MECH-001",
        "artifacts": {
            "enabled": True,
            "quantmetrics_os_root": str(qm_root),
        },
    }
    emitter = SimpleNamespace(run_id="run_20260603_test")

    quantos_artifacts.invoke_collect_run_artifacts(cfg, emitter)

    cmd = captured["cmd"]
    assert cmd[cmd.index("--experiment-id") + 1] == "EXP-BB-MECH-001"
