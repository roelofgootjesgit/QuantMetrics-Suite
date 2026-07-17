"""Tests for EXP-MACD-MECH-001 post-run analyzer helpers."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from analyze_exp_macd_mech_001 import (  # noqa: E402
    _directional_permutation_test,
    _load_matching_trade_closed_payloads,
    _resolve_configured_quantlog_path,
)


def test_directional_permutation_scores_short_signals_as_short_outcomes() -> None:
    long_outcomes = np.zeros(20, dtype=float)
    short_outcomes = np.zeros(20, dtype=float)
    long_outcomes[3] = 1.0
    long_outcomes[7] = -1.0
    short_outcomes[7] = 1.0

    result = _directional_permutation_test(
        long_outcomes,
        short_outcomes,
        np.array([3], dtype=int),
        np.array([7], dtype=int),
        n_permutations=100,
        seed=1,
    )

    assert result["observed_hit_rate"] == 1.0
    assert result["n_signals"] == 2


def test_directional_permutation_ignores_invalid_horizon_signals() -> None:
    long_outcomes = np.full(10, np.nan, dtype=float)
    short_outcomes = np.full(10, np.nan, dtype=float)
    long_outcomes[2] = 0.5
    short_outcomes[4] = 0.25

    result = _directional_permutation_test(
        long_outcomes,
        short_outcomes,
        np.array([2, 9], dtype=int),
        np.array([4], dtype=int),
        n_permutations=20,
        seed=1,
    )

    assert result["observed_hit_rate"] == 0.375
    assert result["n_signals"] == 2


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


def test_load_matching_trade_closed_payloads_filters_experiment_and_symbol(
    tmp_path: Path,
) -> None:
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
