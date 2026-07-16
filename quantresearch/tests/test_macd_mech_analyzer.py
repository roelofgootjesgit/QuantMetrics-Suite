from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from scripts.analyze_exp_macd_mech_001 import (
    _default_quantlog_path,
    _directional_t8_permutation_test,
    _load_matching_trade_closed,
)


def _ohlc_from_close(close: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=len(close), freq="15min", tz="UTC")
    arr = np.array(close, dtype=float)
    return pd.DataFrame(
        {
            "open": arr,
            "high": arr + 0.1,
            "low": arr - 0.1,
            "close": arr,
        },
        index=idx,
    )


def test_default_quantlog_path_requires_correlated_run_id(monkeypatch, tmp_path):
    monkeypatch.delenv("QUANTBUILD_RUN_ID", raising=False)
    monkeypatch.delenv("INVOCATION_ID", raising=False)

    assert _default_quantlog_path({}, tmp_path) is None

    monkeypatch.setenv("QUANTBUILD_RUN_ID", "run_exp_macd")
    assert _default_quantlog_path({}, tmp_path) == tmp_path / "runs" / "run_exp_macd.jsonl"


def test_load_matching_trade_closed_rejects_unrelated_trade_log(tmp_path):
    path = tmp_path / "wrong.jsonl"
    event = {
        "event_type": "trade_closed",
        "strategy_id": "EXP-OTHER",
        "symbol": "EURUSD",
        "payload": {"trade_id": "T1", "pnl_r": 1.0, "exit_price": 1.2},
    }
    path.write_text(json.dumps(event) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="none match"):
        _load_matching_trade_closed(
            path,
            experiment_id="EXP-MACD-MECH-001",
            symbol="EURUSD",
        )


def test_load_matching_trade_closed_filters_by_strategy_and_symbol(tmp_path):
    path = tmp_path / "mixed.jsonl"
    events = [
        {
            "event_type": "trade_closed",
            "strategy_id": "EXP-MACD-MECH-001",
            "symbol": "GBPUSD",
            "payload": {"trade_id": "T1", "pnl_r": 1.0, "exit_price": 1.2},
        },
        {
            "event_type": "trade_closed",
            "strategy_id": "EXP-MACD-MECH-001",
            "symbol": "EURUSD",
            "payload": {"trade_id": "T2", "pnl_r": -0.5, "exit_price": 1.1},
        },
    ]
    path.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")

    closed = _load_matching_trade_closed(
        path,
        experiment_id="EXP-MACD-MECH-001",
        symbol="EURUSD",
    )

    assert [c["trade_id"] for c in closed] == ["T2"]


def test_directional_permutation_uses_short_return_sign():
    df = _ohlc_from_close([10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 9.0, 9.0])
    atr = pd.Series(1.0, index=df.index)
    entries = [{"bar_index": 0, "direction": "SHORT"}]

    result = _directional_t8_permutation_test(
        df,
        atr,
        entries,
        horizon=8,
        n_permutations=20,
        seed=7,
    )

    assert result["observed_hit_rate"] == 0.5
    assert result["n_short_signals"] == 1
    assert result["n_long_signals"] == 0


def test_directional_permutation_excludes_invalid_horizon_signals():
    df = _ohlc_from_close([1.0] * 10)
    atr = pd.Series(1.0, index=df.index)
    entries = [{"bar_index": 9, "direction": "LONG"}]

    result = _directional_t8_permutation_test(
        df,
        atr,
        entries,
        horizon=8,
        n_permutations=20,
        seed=7,
    )

    assert result["n_signals"] == 0
    assert result["p_value"] == 1.0
