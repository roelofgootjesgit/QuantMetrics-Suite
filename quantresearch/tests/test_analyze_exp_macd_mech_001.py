import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.analyze_exp_macd_mech_001 import (
    _directional_permutation_test,
    _executable_macd_entries,
    _find_latest_matching_run_jsonl,
    _load_trade_stats,
)


def _ohlc(close: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=len(close), freq="15min", tz="UTC")
    return pd.DataFrame(
        {
            "open": close,
            "high": [c + 0.1 for c in close],
            "low": [c - 0.1 for c in close],
            "close": close,
        },
        index=idx,
    )


def test_directional_permutation_scores_short_signals_with_short_return() -> None:
    data = _ohlc([10.0, 9.0, 8.0, 8.0, 8.0])
    atr = pd.Series(np.ones(len(data)), index=data.index)
    entries = [{"bar_index": 0, "direction": "SHORT"}]

    result = _directional_permutation_test(
        data,
        atr,
        entries,
        horizon=2,
        n_permutations=20,
        seed=1,
    )

    assert result["observed_hit_rate"] == 1.0
    assert result["n_short_signals"] == 1
    assert result["n_long_signals"] == 0


def test_executable_entries_match_single_position_backtest_admission() -> None:
    data = _ohlc([10.0] * 12)
    atr = pd.Series(np.ones(len(data)), index=data.index)
    entries = [
        {"bar_index": 0, "direction": "LONG"},
        {"bar_index": 2, "direction": "SHORT"},
        {"bar_index": 6, "direction": "LONG"},
    ]
    strat_cfg = {
        "exit": {"time_exit_bars": 4},
        "risk": {"sl_atr_mult": 2.0, "max_concurrent": 1, "max_daily_loss_r": 99.0},
    }

    executable = _executable_macd_entries(data, entries, strat_cfg, atr)

    assert [int(sig["bar_index"]) for sig in executable] == [0, 6]


def test_latest_quantlog_selection_requires_matching_strategy(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    macd_path = runs / "macd.jsonl"
    other_path = runs / "other.jsonl"
    macd_path.write_text(
        json.dumps({"event_type": "trade_closed", "strategy_id": "EXP-MACD-MECH-001"}) + "\n",
        encoding="utf-8",
    )
    other_path.write_text(
        json.dumps({"event_type": "trade_closed", "strategy_id": "OTHER-EXP"}) + "\n",
        encoding="utf-8",
    )
    os.utime(macd_path, (1000, 1000))
    os.utime(other_path, (2000, 2000))

    selected = _find_latest_matching_run_jsonl(tmp_path, {"EXP-MACD-MECH-001"})

    assert selected == macd_path


def test_trade_stats_ignore_events_from_other_strategies(tmp_path: Path) -> None:
    path = tmp_path / "run.jsonl"
    events = [
        {
            "event_type": "trade_closed",
            "strategy_id": "OTHER-EXP",
            "payload": {"pnl_r": 100.0},
        },
        {
            "event_type": "trade_closed",
            "strategy_id": "EXP-MACD-MECH-001",
            "payload": {"pnl_r": -1.0},
        },
        {
            "event_type": "trade_closed",
            "strategy_id": "EXP-MACD-MECH-001",
            "payload": {"pnl_r": 2.0},
        },
    ]
    path.write_text("\n".join(json.dumps(ev) for ev in events) + "\n", encoding="utf-8")

    stats = _load_trade_stats(path, {"EXP-MACD-MECH-001"})

    assert stats["n_trades"] == 2
    assert stats["expectancy_r"] == 0.5
    assert stats["win_rate_pct"] == 50.0
