"""QuantResearch run bundle integration helpers."""

from __future__ import annotations

import json
from pathlib import Path

from src.quantbuild.execution.quantlog_emitter import QuantLogEmitter
from src.quantbuild.integration import quantresearch_runs


def test_bundle_copies_emitter_consolidated_path_with_custom_base(
    tmp_path: Path,
    monkeypatch,
) -> None:
    qroot = tmp_path / "quantresearch"
    qroot.mkdir()
    qb_root = tmp_path / "quantbuild"
    qb_root.mkdir()
    custom_base = tmp_path / "custom_quantlog_events"
    consolidated = custom_base / "runs" / "run_custom.jsonl"
    consolidated.parent.mkdir(parents=True)
    consolidated.write_text('{"event_type": "trade_closed"}\n', encoding="utf-8")

    monkeypatch.setenv("QUANTRESEARCH_ROOT", str(qroot))
    monkeypatch.setattr(quantresearch_runs, "quantbuild_project_root", lambda: qb_root)
    monkeypatch.setattr(quantresearch_runs, "discover_quantanalytics_output_rapport", lambda _root: None)

    emitter = QuantLogEmitter(
        base_path=custom_base,
        source_component="backtest_engine",
        environment="backtest",
        run_id="run_custom",
        session_id="sess_custom",
        consolidated_path=consolidated,
    )
    cfg = {"quantresearch_runs": {"enabled": True, "experiment_id": "EXP-CUSTOM-BASE"}}

    dest = quantresearch_runs.invoke_quantresearch_run_bundle(cfg, emitter, metrics={"trades": 1})

    assert dest == (qroot / "runs" / "EXP-CUSTOM-BASE").resolve()
    assert (dest / "quantlog_events.jsonl").read_text(encoding="utf-8") == consolidated.read_text(
        encoding="utf-8"
    )
    manifest = json.loads((dest / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["quantlog_consolidated"] == str(consolidated.resolve())
