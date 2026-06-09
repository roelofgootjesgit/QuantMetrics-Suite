"""Regression tests for EXP-MACD-MECH-001 analysis helpers."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path


def _load_analysis_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "analyze_exp_macd_mech_001.py"
    spec = importlib.util.spec_from_file_location("analyze_exp_macd_mech_001", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_event(path: Path, strategy_id: str) -> None:
    path.write_text(
        json.dumps(
            {
                "event_type": "trade_closed",
                "strategy_id": strategy_id,
                "payload": {"pnl_r": 1.0},
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_find_latest_run_jsonl_ignores_newer_unrelated_experiment(tmp_path: Path) -> None:
    module = _load_analysis_module()
    runs = tmp_path / "runs"
    runs.mkdir()
    matching = runs / "macd.jsonl"
    unrelated = runs / "bb.jsonl"
    _write_event(matching, "EXP-MACD-MECH-001")
    _write_event(unrelated, "EXP-BB-MECH-001")
    os.utime(matching, (1000, 1000))
    os.utime(unrelated, (2000, 2000))

    assert module._find_latest_run_jsonl(tmp_path, "EXP-MACD-MECH-001") == matching
