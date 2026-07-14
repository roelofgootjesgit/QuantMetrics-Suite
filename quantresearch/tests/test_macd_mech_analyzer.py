"""Regression tests for EXP-MACD-MECH-001 post-run analytics."""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from scripts.analyze_exp_macd_mech_001 import (
    _collect_trade_stats,
    _direction_aware_permutation_test,
    _find_latest_run_jsonl,
)


def _event(strategy_id: str, symbol: str, pnl_r: float) -> str:
    return json.dumps(
        {
            "event_type": "trade_closed",
            "strategy_id": strategy_id,
            "symbol": symbol,
            "payload": {"trade_id": f"{strategy_id}-{symbol}", "pnl_r": pnl_r},
        }
    )


def test_permutation_scores_mixed_signals_in_their_trade_direction() -> None:
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
    atr = pd.Series(np.ones(len(data)), index=data.index)
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


def test_permutation_excludes_invalid_signal_horizons_and_atr() -> None:
    dates = pd.date_range("2024-01-01", periods=12, freq="15min", tz="UTC")
    close = np.arange(12, dtype=float)
    data = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.1,
            "low": close - 0.1,
            "close": close,
        },
        index=dates,
    )
    atr = pd.Series(np.ones(len(data)), index=data.index)
    atr.iloc[1] = np.nan
    entries = [
        {"bar_index": 0, "direction": "LONG"},
        {"bar_index": 1, "direction": "SHORT"},
        {"bar_index": 10, "direction": "LONG"},
    ]

    result = _direction_aware_permutation_test(
        data,
        atr,
        entries,
        horizon=2,
        n_permutations=20,
        seed=1,
    )

    assert result["n_signals"] == 1
    assert np.isfinite(result["observed_hit_rate"])


def test_latest_quantlog_skips_newer_unrelated_experiment(tmp_path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    macd_run = runs / "macd.jsonl"
    bb_run = runs / "bb.jsonl"
    macd_run.write_text(
        _event("EXP-MACD-MECH-001", "EURUSD", 1.0) + "\n",
        encoding="utf-8",
    )
    bb_run.write_text(
        _event("EXP-BB-MECH-001", "EURUSD", -5.0) + "\n",
        encoding="utf-8",
    )
    os.utime(macd_run, (1_000_000, 1_000_000))
    os.utime(bb_run, (2_000_000, 2_000_000))

    selected = _find_latest_run_jsonl(
        tmp_path,
        experiment_id="EXP-MACD-MECH-001",
        symbol="EURUSD",
    )

    assert selected == macd_run


def test_trade_stats_exclude_other_experiments_and_symbols(tmp_path) -> None:
    path = tmp_path / "mixed.jsonl"
    path.write_text(
        "\n".join(
            [
                _event("EXP-BB-MECH-001", "EURUSD", -5.0),
                _event("EXP-MACD-MECH-001", "GBPUSD", -3.0),
                _event("EXP-MACD-MECH-001", "EURUSD", 1.0),
                _event("EXP-MACD-MECH-001", "EURUSD", -0.5),
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
