"""Tests for MACD-only strategy (EXP-MACD-MECH-001)."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

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


class TestMacdOnlyBacktestEngine:
    def test_quantlog_preserves_research_funnel_and_metadata(self, tmp_path, monkeypatch):
        from src.quantbuild.strategies import macd_only_engine as engine

        dates = pd.date_range("2024-06-03 08:00", periods=5, freq="15min", tz="UTC")
        close = np.array([1.1000, 1.1002, 1.1006, 1.1009, 1.1012])
        df = pd.DataFrame(
            {
                "open": close,
                "high": close + 0.0002,
                "low": close - 0.0002,
                "close": close,
            },
            index=dates,
        )
        macd_frame = pd.DataFrame(
            {
                "histogram": [0.0, -0.5, 0.25, 0.10, 0.0],
                "bullish_cross": [False, False, True, True, False],
                "bearish_cross": [False, False, False, False, False],
            },
            index=dates,
        )
        entries = [
            {
                "bar_index": 2,
                "direction": "LONG",
                "component_type": "MACD_BULL_CROSS",
                "bar_timestamp": dates[2],
                "session_at_signal": "LONDON",
                "regime_at_signal": "TREND",
                "macd_cross_bull": True,
                "macd_cross_bear": False,
                "macd_cross_velocity": 0.75,
            },
            {
                "bar_index": 3,
                "direction": "LONG",
                "component_type": "MACD_BULL_CROSS",
                "bar_timestamp": dates[3],
                "session_at_signal": "LONDON",
                "regime_at_signal": "TREND",
                "macd_cross_bull": True,
                "macd_cross_bear": False,
                "macd_cross_velocity": -0.15,
            },
        ]

        monkeypatch.setattr(engine, "compute_macd_frame", lambda data, macd_cfg: macd_frame)
        monkeypatch.setattr(
            engine,
            "collect_macd_entry_signals",
            lambda data, strat_cfg, session_mode="extended", regime_series=None: entries,
        )
        monkeypatch.setattr(
            engine,
            "simulate_macd_time_exit_trade",
            lambda *args, **kwargs: {
                "entry_price": float(close[2]),
                "exit_price": float(close[4]),
                "sl": float(close[2] - 0.001),
                "tp": float(close[2]),
                "exit_ts": dates[4],
                "exit_bar_idx": 4,
                "profit_usd": float(close[4] - close[2]),
                "profit_r": 0.3,
                "result": "WIN",
                "exit_reason": "time_exit",
                "bars_held": 2,
                "bars_to_midline": None,
                "hit_midline_before_sl": False,
                "mae_r": 0.1,
                "mfe_r": 0.4,
                "atr": 0.001,
                "bars_to_half_r_mae": None,
            },
        )

        ql_file = tmp_path / "events.jsonl"
        cfg = {
            "experiment_id": "EXP-MACD-MECH-001-TEST",
            "symbol": "EURUSD",
            "broker": {"mock_spread": 0.00010},
            "strategy": {"signal_independence": {"min_bars_gap": 4, "min_atr_distance": 1.5}},
            "exit": {"time_exit_bars": 8},
            "risk": {"sl_atr_mult": 2.0, "max_concurrent": 1, "max_daily_loss_r": 99.0},
            "guards": {"spread": {"enabled": True, "max_spread_pips": 1.5}},
            "quantlog": {
                "enabled": True,
                "environment": "backtest",
                "base_path": str(tmp_path / "ql"),
                "consolidated_run_file": str(ql_file),
            },
        }

        trades = engine.run_macd_only_backtest(cfg, df, symbol="EURUSD")

        assert len(trades) == 1
        events = [json.loads(ln) for ln in ql_file.read_text(encoding="utf-8").splitlines()]
        component_events = [e for e in events if e["event_type"] == "component_observed"]
        candidate_events = [e for e in events if e["event_type"] == "candidate_signal"]
        trade_actions = [e for e in events if e["event_type"] == "trade_action"]
        closed = [e for e in events if e["event_type"] == "trade_closed"]

        assert component_events[0]["payload"]["macd_cross_velocity"] == 0.75
        assert len(candidate_events) == 2
        assert any(
            e["payload"]["decision"] == "NO_ACTION"
            and e["payload"]["reason"] == "position_limit_reached"
            for e in trade_actions
        )
        assert closed[0]["payload"]["regime"] == "trend"
        assert closed[0]["payload"]["session"] == "London"
