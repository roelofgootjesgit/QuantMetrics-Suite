"""Regression tests for EXP-MACD-MECH QuantLog run selection."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest


def _load_analyzer_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "analyze_exp_macd_mech_001.py"
    spec = importlib.util.spec_from_file_location("analyze_exp_macd_mech_001", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load analyzer script: {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def analyzer():
    return _load_analyzer_module()


def _write_trade_closed(path: Path, *, strategy_id: str, symbol: str, pnl_r: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event_type": "trade_closed",
        "strategy_id": strategy_id,
        "symbol": symbol,
        "payload": {"trade_id": f"{strategy_id}-trade", "exit_price": 1.1, "pnl_r": pnl_r},
    }
    path.write_text(json.dumps(event) + "\n", encoding="utf-8")


def test_default_quantlog_selection_skips_newer_unrelated_run(tmp_path, analyzer):
    ql_base = tmp_path / "quantlog_events"
    macd_run = ql_base / "runs" / "macd.jsonl"
    unrelated_run = ql_base / "runs" / "bb.jsonl"

    _write_trade_closed(
        macd_run, strategy_id="EXP-MACD-MECH-001", symbol="EURUSD", pnl_r=0.5
    )
    _write_trade_closed(
        unrelated_run, strategy_id="EXP-BB-MECH-001", symbol="EURUSD", pnl_r=-4.0
    )

    older = 1_700_000_000
    newer = older + 60
    os.utime(macd_run, (older, older))
    os.utime(unrelated_run, (newer, newer))

    selected = analyzer._find_latest_run_jsonl(
        ql_base, experiment_id="EXP-MACD-MECH-001", symbol="EURUSD"
    )

    assert selected == macd_run


def test_trade_stats_ignore_explicit_unrelated_quantlog_path(tmp_path, analyzer):
    macd_run = tmp_path / "macd.jsonl"
    unrelated_run = tmp_path / "bb.jsonl"

    _write_trade_closed(
        macd_run, strategy_id="EXP-MACD-MECH-001", symbol="EURUSD", pnl_r=1.0
    )
    _write_trade_closed(
        unrelated_run, strategy_id="EXP-BB-MECH-001", symbol="EURUSD", pnl_r=-9.0
    )

    assert (
        analyzer._trade_stats_from_quantlog(
            unrelated_run, experiment_id="EXP-MACD-MECH-001", symbol="EURUSD"
        )
        == {}
    )

    stats = analyzer._trade_stats_from_quantlog(
        macd_run, experiment_id="EXP-MACD-MECH-001", symbol="EURUSD"
    )
    assert stats["n_trades"] == 1
    assert stats["expectancy_r"] == pytest.approx(1.0)
