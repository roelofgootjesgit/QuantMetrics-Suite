"""Tests for QuantBuild -> QuantOS artifact collection."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import yaml

from src.quantbuild.integration import quantos_artifacts


def test_custom_artifact_role_is_preserved(monkeypatch, tmp_path: Path) -> None:
    qb_root = tmp_path / "quantbuild"
    (qb_root / "data" / "quantlog_events" / "runs").mkdir(parents=True)
    qmos_root = tmp_path / "quantmetrics_os"
    (qmos_root / "scripts").mkdir(parents=True)
    (qmos_root / "scripts" / "collect_run_artifact.py").write_text("# test helper\n", encoding="utf-8")
    config_path = tmp_path / "XAUUSD.yaml"
    config_path.write_text("symbol: XAUUSD\n", encoding="utf-8")

    monkeypatch.setattr(quantos_artifacts, "quantbuild_project_root", lambda: qb_root)
    monkeypatch.setattr(quantos_artifacts, "discover_quantmetrics_os_root", lambda _root: qmos_root)
    monkeypatch.setattr(
        quantos_artifacts,
        "write_runtime_config_yaml",
        lambda _cfg, path: Path(path).write_text("symbol: XAUUSD\n", encoding="utf-8"),
    )

    captured: dict[str, list[str]] = {}

    def fake_run(cmd: list[str], **_kwargs: object) -> SimpleNamespace:
        captured["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout=str(tmp_path / "artifact") + "\n", stderr="")

    monkeypatch.setattr(quantos_artifacts.subprocess, "run", fake_run)

    cfg = {
        "_quantbuild_config_path": str(config_path),
        "artifacts": {
            "enabled": True,
            "experiment_id": "EXP-003",
            "role": "xauusd",
            "bundle_analytics": False,
        },
    }
    ql_emitter = SimpleNamespace(run_id="qb_run_custom")

    quantos_artifacts.invoke_collect_run_artifacts(cfg, ql_emitter)

    cmd = captured["cmd"]
    role_idx = cmd.index("--role")
    assert cmd[role_idx + 1] == "xauusd"


def test_exp003_artifact_roles_are_unique_per_instrument() -> None:
    config_dir = Path(__file__).resolve().parents[1] / "configs" / "experiments" / "exp003_overlap_breakout"
    roles = {}
    for path in sorted(config_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        roles[path.stem] = data["artifacts"]["role"]

    assert roles == {
        "EURUSD": "eurusd",
        "GBPUSD": "gbpusd",
        "NAS100": "nas100",
        "US30": "us30",
        "XAUUSD": "xauusd",
    }
    assert len(set(roles.values())) == len(roles)
