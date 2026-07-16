"""Tests for MACD-only strategy (EXP-MACD-MECH-001)."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from src.quantbuild.strategies import macd_only as macd_module
from src.quantbuild.strategies import macd_only_engine as macd_engine_module
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
        df = _ohlc(40, seed=3)
        hist = np.zeros(len(df))
        hist[19] = -0.02
        hist[20] = 0.01
        hist[21] = -0.01
        macd_frame = pd.DataFrame(
            {
                "histogram": hist,
                "bullish_cross": [False] * len(df),
                "bearish_cross": [False] * len(df),
            },
            index=df.index,
        )
        macd_frame.loc[df.index[20], "bullish_cross"] = True
        macd_frame.loc[df.index[21], "bearish_cross"] = True
        monkeypatch.setattr(macd_module, "compute_macd_frame", lambda data, cfg: macd_frame)
        monkeypatch.setattr(
            macd_module,
            "compute_atr",
            lambda data, period=14: pd.Series(0.001, index=data.index),
        )
        strat = {"signal_independence": {"min_bars_gap": 4, "min_atr_distance": 0.0}}

        entries = collect_macd_entry_signals(df, strat)

        assert [e["bar_index"] for e in entries] == [20]
        assert entries[0]["direction"] == "LONG"

    def test_component_observed_uses_histogram_delta_velocity(self, tmp_path, monkeypatch):
        df = _ohlc(5, seed=4)
        hist = np.array([0.0, -0.03, 0.02, 0.01, 0.0])
        macd_frame = pd.DataFrame(
            {
                "histogram": hist,
                "bullish_cross": [False, False, True, False, False],
                "bearish_cross": [False] * len(df),
            },
            index=df.index,
        )
        monkeypatch.setattr(macd_engine_module, "compute_macd_frame", lambda data, cfg: macd_frame)
        monkeypatch.setattr(macd_engine_module, "collect_macd_entry_signals", lambda *args, **kwargs: [])
        out = tmp_path / "events.jsonl"
        cfg = {
            "experiment_id": "EXP-MACD-MECH-001",
            "broker": {"account_id": "backtest", "mock_spread": 0.0001},
            "quantlog": {
                "enabled": True,
                "environment": "backtest",
                "base_path": str(tmp_path / "ql"),
                "consolidated_run_file": str(out),
            },
            "risk": {"max_daily_loss_r": 99.0},
        }

        trades = macd_engine_module.run_macd_only_backtest(cfg, df, symbol="EURUSD")

        assert trades == []
        events = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
        component = [ev for ev in events if ev["event_type"] == "component_observed"][0]
        assert component["payload"]["macd_cross_velocity"] == 0.05

    def test_spread_block_preserves_candidate_funnel(self, tmp_path):
        close = np.concatenate([np.linspace(1.10, 1.12, 60), np.linspace(1.12, 1.08, 60)])
        dates = pd.date_range("2024-01-01", periods=len(close), freq="15min", tz="UTC")
        df = pd.DataFrame(
            {"open": close, "high": close + 0.0001, "low": close - 0.0001, "close": close},
            index=dates,
        )
        strategy = {
            "macd": {"fast": 5, "slow": 10, "signal": 3},
            "signal_independence": {"min_bars_gap": 4, "min_atr_distance": 0.0},
        }
        expected_candidates = collect_macd_entry_signals(df, strategy)
        assert expected_candidates
        out = tmp_path / "events.jsonl"
        cfg = {
            "experiment_id": "EXP-MACD-MECH-001-TEST",
            "broker": {"mock_spread": 0.00010},
            "strategy": strategy,
            "exit": {"time_exit_bars": 8},
            "risk": {"sl_atr_mult": 2.0, "max_concurrent": 1, "max_daily_loss_r": 99.0},
            "guards": {"spread": {"enabled": True, "max_spread_pips": 0.1}},
            "quantlog": {
                "enabled": True,
                "environment": "backtest",
                "base_path": str(tmp_path / "ql"),
                "consolidated_run_file": str(out),
            },
        }

        trades = macd_engine_module.run_macd_only_backtest(cfg, df, symbol="EURUSD")

        assert trades == []
        events = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
        candidates = [ev for ev in events if ev["event_type"] == "candidate_signal"]
        no_actions = [
            ev
            for ev in events
            if ev["event_type"] == "trade_action"
            and ev["payload"]["decision"] == "NO_ACTION"
            and ev["payload"]["reason"] == "spread_too_high"
        ]
        assert len(candidates) == len(expected_candidates)
        assert len(no_actions) == len(expected_candidates)
