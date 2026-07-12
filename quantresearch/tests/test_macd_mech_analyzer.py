"""Regression tests for EXP-MACD-MECH-001 post-run analyzer helpers."""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.analyze_exp_macd_mech_001 import (
    _collect_trade_stats,
    _direction_aware_permutation_test,
    _find_latest_run_jsonl,
)


def _event(event_type: str, strategy_id: str, symbol: str, payload: dict) -> str:
    return json.dumps(
        {
            "event_type": event_type,
            "strategy_id": strategy_id,
            "symbol": symbol,
            "payload": payload,
        }
    )


def test_direction_aware_permutation_scores_short_signals_with_short_returns() -> None:
    dates = pd.date_range("2024-01-01", periods=12, freq="15min", tz="UTC")
    close = np.full(12, 100.0)
    close[8] = 102.0
    close[9] = 98.0
    data = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.1,
            "low": close - 0.1,
            "close": close,
        },
        index=dates,
    )
    atr = pd.Series(np.ones(12), index=dates)
    entries = [
        {"bar_index": 0, "direction": "LONG"},
        {"bar_index": 1, "direction": "SHORT"},
    ]

    result = _direction_aware_permutation_test(
        data,
        atr,
        entries,
        horizon=8,
        n_permutations=20,
        seed=1,
    )

    assert result["n_signals"] == 2
    assert result["observed_hit_rate"] == 1.0


def test_find_latest_run_jsonl_skips_newer_unrelated_experiment(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    macd = runs / "macd.jsonl"
    bb = runs / "bb.jsonl"
    macd.write_text(
        _event(
            "trade_closed",
            "EXP-MACD-MECH-001",
            "EURUSD",
            {"trade_id": "macd", "pnl_r": 1.0},
        )
        + "\n",
        encoding="utf-8",
    )
    bb.write_text(
        _event(
            "trade_closed",
            "EXP-BB-MECH-001",
            "EURUSD",
            {"trade_id": "bb", "pnl_r": -1.0},
        )
        + "\n",
        encoding="utf-8",
    )
    os.utime(macd, (1_000_000, 1_000_000))
    os.utime(bb, (2_000_000, 2_000_000))

    selected = _find_latest_run_jsonl(tmp_path, "EXP-MACD-MECH-001", "EURUSD")

    assert selected == macd


def test_collect_trade_stats_filters_experiment_and_symbol(tmp_path: Path) -> None:
    path = tmp_path / "mixed.jsonl"
    path.write_text(
        "\n".join(
            [
                _event(
                    "trade_closed",
                    "EXP-BB-MECH-001",
                    "EURUSD",
                    {"trade_id": "bb", "pnl_r": -5.0},
                ),
                _event(
                    "trade_closed",
                    "EXP-MACD-MECH-001",
                    "GBPUSD",
                    {"trade_id": "gbp", "pnl_r": -3.0},
                ),
                _event(
                    "trade_closed",
                    "EXP-MACD-MECH-001",
                    "EURUSD",
                    {"trade_id": "macd_1", "pnl_r": 1.0},
                ),
                _event(
                    "trade_closed",
                    "EXP-MACD-MECH-001",
                    "EURUSD",
                    {"trade_id": "macd_2", "pnl_r": -0.5},
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    stats = _collect_trade_stats(
        path,
        experiment_id="EXP-MACD-MECH-001",
        symbol="EURUSD",
    )

    assert stats["n_trades"] == 2
    assert stats["expectancy_r"] == 0.25
