from __future__ import annotations

import json

from src.quantbuild.execution.quantlog_emitter import QuantLogEmitter
from src.quantbuild.integration import quantresearch_runs
from src.quantbuild.integration.quantresearch_runs import invoke_quantresearch_run_bundle


def test_bundle_copies_custom_consolidated_quantlog_path(tmp_path, monkeypatch):
    qroot = tmp_path / "quantresearch"
    qroot.mkdir()
    custom_jsonl = tmp_path / "custom-quantlog" / "runs" / "run-123.jsonl"
    custom_jsonl.parent.mkdir(parents=True)
    custom_jsonl.write_text('{"event_type":"trade_closed"}\n', encoding="utf-8")
    emitter = QuantLogEmitter(
        base_path=tmp_path / "custom-quantlog",
        source_component="backtest_engine",
        environment="backtest",
        run_id="run-123",
        session_id="session-123",
        consolidated_path=custom_jsonl,
    )
    monkeypatch.setenv("QUANTRESEARCH_ROOT", str(qroot))
    monkeypatch.setattr(quantresearch_runs, "discover_quantanalytics_output_rapport", lambda qb_root: None)

    dest = invoke_quantresearch_run_bundle(
        {"quantresearch_runs": {"enabled": True, "experiment_id": "EXP-CUSTOM-QL"}},
        emitter,
    )

    assert dest == qroot / "runs" / "EXP-CUSTOM-QL"
    assert (dest / "quantlog_events.jsonl").read_text(encoding="utf-8") == custom_jsonl.read_text(
        encoding="utf-8"
    )
    manifest = json.loads((dest / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["quantlog_consolidated"] == str(custom_jsonl.resolve())
