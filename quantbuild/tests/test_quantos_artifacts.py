"""Tests for QuantOS artifact collection wiring."""
from __future__ import annotations

import subprocess
from types import SimpleNamespace

import src.quantbuild.integration.quantos_artifacts as quantos_artifacts


def test_collect_artifacts_falls_back_to_top_level_experiment_id(monkeypatch, tmp_path) -> None:
    qb_root = tmp_path / "quantbuild"
    runs_dir = qb_root / "data" / "quantlog_events" / "runs"
    runs_dir.mkdir(parents=True)
    qm_root = tmp_path / "quantmetrics_os"
    scripts_dir = qm_root / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "collect_run_artifact.py").write_text("# test marker\n", encoding="utf-8")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout=str(tmp_path / "dest") + "\n", stderr="")

    monkeypatch.setattr(quantos_artifacts, "quantbuild_project_root", lambda: qb_root)
    monkeypatch.setattr(quantos_artifacts, "discover_quantmetrics_os_root", lambda root: qm_root)
    monkeypatch.setattr(quantos_artifacts, "discover_quantanalytics_output_rapport", lambda root: None)
    monkeypatch.setattr(
        quantos_artifacts,
        "write_runtime_config_yaml",
        lambda cfg, path: path.write_text("experiment_id: EXP-MACD-MECH-001\n", encoding="utf-8"),
    )
    monkeypatch.setattr(quantos_artifacts.subprocess, "run", fake_run)

    quantos_artifacts.invoke_collect_run_artifacts(
        {
            "experiment_id": "EXP-MACD-MECH-001",
            "artifacts": {"enabled": True},
        },
        SimpleNamespace(run_id="run_20260531_abcdef1234567890"),
    )

    assert calls
    cmd = calls[0]
    assert cmd[cmd.index("--experiment-id") + 1] == "EXP-MACD-MECH-001"
