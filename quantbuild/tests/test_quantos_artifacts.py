from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from src.quantbuild.integration import quantos_artifacts


def test_collect_run_artifacts_preserves_symbol_specific_role(tmp_path: Path, monkeypatch) -> None:
    qb_root = tmp_path / "quantbuild"
    qm_root = tmp_path / "quantmetrics_os"
    (qm_root / "scripts").mkdir(parents=True)
    (qm_root / "scripts" / "collect_run_artifact.py").write_text("# test stub\n", encoding="utf-8")

    monkeypatch.setattr(quantos_artifacts, "quantbuild_project_root", lambda: qb_root)

    captured: dict[str, list[str]] = {}

    def fake_run(cmd: list[str], **kwargs):
        captured["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout=str(qm_root / "runs" / "EXP-003" / "variant_xauusd"), stderr="")

    monkeypatch.setattr(quantos_artifacts.subprocess, "run", fake_run)

    quantos_artifacts.invoke_collect_run_artifacts(
        {
            "artifacts": {
                "enabled": True,
                "experiment_id": "EXP-003",
                "role": "variant_xauusd",
                "quantmetrics_os_root": str(qm_root),
                "bundle_analytics": False,
            }
        },
        SimpleNamespace(run_id="qb_run_test"),
    )

    role_idx = captured["cmd"].index("--role") + 1
    assert captured["cmd"][role_idx] == "variant_xauusd"
