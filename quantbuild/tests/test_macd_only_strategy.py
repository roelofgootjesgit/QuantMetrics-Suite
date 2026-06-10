"""Tests for MACD-only strategy (EXP-MACD-MECH-001)."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

import src.quantbuild.strategies.macd_only as macd_only_module
from src.quantbuild.strategies.macd_only import (
    collect_macd_entry_signals,
    detect_macd_component_observations,
    compute_macd_frame,
    simulate_macd_time_exit_trade,
)


def _ohlc(n: int = 120, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-06-01", periods=n, freq="15min", tz="UTC")
    close = 1.10 + np.cumsum(rng.normal(0, 0.0003, n))
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 0.0002,
            "low": close - 0.0002,
            "close": close,
        },
        index=dates,
    )


class TestMacdOnly:
    def test_detect_crosses_exist_on_trending_series(self):
        close = np.concatenate([np.linspace(1.10, 1.12, 60), np.linspace(1.12, 1.08, 60)])
        dates = pd.date_range("2024-01-01", periods=len(close), freq="15min", tz="UTC")
        df = pd.DataFrame(
            {"open": close, "high": close + 0.0001, "low": close - 0.0001, "close": close},
            index=dates,
        )
        mf = compute_macd_frame(df, {"fast": 5, "slow": 10, "signal": 3})
        bull, bear = detect_macd_component_observations(mf)
        assert (bull | bear).sum() >= 1

    def test_time_exit_within_horizon(self):
        df = _ohlc(50)
        atr = np.full(len(df), 0.001)
        res = simulate_macd_time_exit_trade(
            df, 10, "LONG", atr_arr=atr, sl_atr_mult=10.0, time_exit_bars=8
        )
        assert res["bars_held"] <= 8
        assert res["exit_reason"] in {"time_exit", "sl"}

    def test_tae_recorded_when_adverse_early(self):
        n = 30
        dates = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")
        close = np.linspace(1.10, 1.05, n)
        df = pd.DataFrame(
            {
                "open": close,
                "high": close + 0.00005,
                "low": close - 0.002,
                "close": close,
            },
            index=dates,
        )
        atr = np.full(n, 0.001)
        res = simulate_macd_time_exit_trade(
            df, 5, "LONG", atr_arr=atr, sl_atr_mult=2.0, time_exit_bars=12
        )
        assert res["bars_to_half_r_mae"] is not None
        assert res["bars_to_half_r_mae"] <= 3

    def test_collect_entries_independence_gap(self):
        df = _ohlc(150, seed=2)
        strat = {
            "macd": {"fast": 8, "slow": 17, "signal": 5},
            "signal_independence": {"min_bars_gap": 4, "min_atr_distance": 1.5},
        }
        entries = collect_macd_entry_signals(df, strat)
        idx = [e["bar_index"] for e in entries]
        for a, b in zip(idx, idx[1:]):
            assert b - a >= 4

    def test_collect_entries_filters_opposite_direction_cluster(self, monkeypatch):
        df = _ohlc(20)
        bull = pd.Series(False, index=df.index)
        bear = pd.Series(False, index=df.index)
        bull.iloc[5] = True
        bear.iloc[6] = True
        macd_frame = pd.DataFrame(
            {
                "histogram": np.linspace(-0.1, 0.1, len(df)),
                "bullish_cross": bull,
                "bearish_cross": bear,
            },
            index=df.index,
        )

        monkeypatch.setattr(macd_only_module, "compute_macd_frame", lambda data, cfg: macd_frame)
        monkeypatch.setattr(
            macd_only_module,
            "compute_atr",
            lambda data, period=14: pd.Series([0.01] * len(data), index=data.index),
        )

        entries = collect_macd_entry_signals(
            df,
            {"signal_independence": {"min_bars_gap": 4, "min_atr_distance": 0.0}},
        )

        assert [(e["bar_index"], e["direction"]) for e in entries] == [(5, "LONG")]

    def test_backtest_trade_closed_quantlog_includes_signal_regime(self, tmp_path, monkeypatch):
        from src.quantbuild.strategies import macd_only_engine

        df = _ohlc(12)
        ql_file = tmp_path / "events.jsonl"
        entry = {
            "bar_index": 2,
            "direction": "LONG",
            "component_type": "MACD_BULL_CROSS",
            "bar_timestamp": df.index[2],
            "session_at_signal": "NEW_YORK",
            "regime_at_signal": "TREND",
            "macd_cross_bull": True,
            "macd_cross_bear": False,
            "macd_cross_velocity": 0.25,
        }
        macd_frame = pd.DataFrame(
            {
                "histogram": np.zeros(len(df)),
                "bullish_cross": [False] * len(df),
                "bearish_cross": [False] * len(df),
            },
            index=df.index,
        )

        monkeypatch.setattr(macd_only_engine, "compute_macd_frame", lambda data, cfg: macd_frame)
        monkeypatch.setattr(
            macd_only_engine,
            "detect_macd_component_observations",
            lambda frame: (frame["bullish_cross"], frame["bearish_cross"]),
        )
        monkeypatch.setattr(macd_only_engine, "collect_macd_entry_signals", lambda *args, **kwargs: [entry])
        monkeypatch.setattr(macd_only_engine, "_spread_ok", lambda cfg, symbol: True)
        monkeypatch.setattr(
            macd_only_engine,
            "simulate_macd_time_exit_trade",
            lambda *args, **kwargs: {
                "entry_price": 1.1,
                "exit_price": 1.101,
                "sl": 1.09,
                "tp": 1.1,
                "exit_ts": df.index[4],
                "exit_bar_idx": 4,
                "profit_usd": 0.001,
                "profit_r": 0.1,
                "result": "WIN",
                "exit_reason": "time_exit",
                "bars_held": 2,
                "mfe_r": 0.2,
                "mae_r": 0.05,
                "bars_to_half_r_mae": None,
            },
        )

        trades = macd_only_engine.run_macd_only_backtest(
            {
                "experiment_id": "EXP-MACD-MECH-001-TEST",
                "broker": {"mock_spread": 0.0001},
                "risk": {"max_daily_loss_r": 99.0, "max_concurrent": 1, "sl_atr_mult": 2.0},
                "exit": {"time_exit_bars": 8},
                "quantlog": {
                    "enabled": True,
                    "environment": "backtest",
                    "base_path": str(tmp_path / "ql"),
                    "consolidated_run_file": str(ql_file),
                },
            },
            df,
            symbol="EURUSD",
        )

        assert len(trades) == 1
        closed = [
            json.loads(line)["payload"]
            for line in ql_file.read_text(encoding="utf-8").splitlines()
            if json.loads(line).get("event_type") == "trade_closed"
        ]
        assert closed[0]["regime"] == "trend"
        assert closed[0]["regime_at_signal"] == "TREND"
        assert closed[0]["session_at_signal"] == "NEW_YORK"
