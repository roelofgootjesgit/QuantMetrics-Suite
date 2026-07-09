"""Tests for EXP-MACD-MECH-001 analyzer safety helpers."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "analyze_exp_macd_mech_001.py"
_SPEC = importlib.util.spec_from_file_location("analyze_exp_macd_mech_001", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_ANALYZER = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_ANALYZER)

_load_matching_trade_closed_payloads = _ANALYZER._load_matching_trade_closed_payloads
_resolve_configured_quantlog_path = _ANALYZER._resolve_configured_quantlog_path


def test_resolve_configured_quantlog_path_requires_stable_run_id(tmp_path: Path) -> None:
    cfg = {
        "quantlog": {
            "base_path": str(tmp_path / "ql"),
            "consolidated_run_file": True,
        }
    }

    assert _resolve_configured_quantlog_path(cfg) is None


def test_resolve_configured_quantlog_path_uses_configured_run_id(tmp_path: Path) -> None:
    cfg = {
        "quantlog": {
            "base_path": str(tmp_path / "ql"),
            "consolidated_run_file": True,
            "run_id": "macd_mech_run",
        }
    }

    assert _resolve_configured_quantlog_path(cfg) == tmp_path / "ql" / "runs" / "macd_mech_run.jsonl"


def test_load_matching_trade_closed_payloads_filters_experiment_and_symbol(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    events = [
        {
            "event_type": "trade_closed",
            "strategy_id": "EXP-MACD-MECH-001",
            "symbol": "EURUSD",
            "payload": {"pnl_r": 0.5},
        },
        {
            "event_type": "trade_closed",
            "strategy_id": "EXP-BB-MECH-001",
            "symbol": "EURUSD",
            "payload": {"pnl_r": 99.0},
        },
        {
            "event_type": "trade_closed",
            "strategy_id": "EXP-MACD-MECH-001",
            "symbol": "XAUUSD",
            "payload": {"pnl_r": 88.0},
        },
    ]
    path.write_text("\n".join(json.dumps(ev) for ev in events), encoding="utf-8")

    closed = _load_matching_trade_closed_payloads(
        path,
        experiment_id="EXP-MACD-MECH-001",
        symbol="EURUSD",
    )

    assert closed == [{"pnl_r": 0.5}]
