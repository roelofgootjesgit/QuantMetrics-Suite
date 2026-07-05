"""Tests for MACD-only strategy (EXP-MACD-MECH-001)."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from src.quantbuild.strategies.macd_only import (
    collect_macd_entry_signals,
    detect_macd_component_observations,
    compute_macd_frame,
    macd_cross_velocity,
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

    def test_collect_entries_applies_independence_across_directions(self, monkeypatch):
        import src.quantbuild.strategies.macd_only as macd_only

        n = 20
        dates = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")
        df = pd.DataFrame(
            {
                "open": np.full(n, 100.0),
                "high": np.full(n, 101.0),
                "low": np.full(n, 99.0),
                "close": np.linspace(100.0, 101.0, n),
            },
            index=dates,
        )
        macd_frame = pd.DataFrame(
            {
                "histogram": np.linspace(-1.0, 1.0, n),
                "bullish_cross": [False] * n,
                "bearish_cross": [False] * n,
            },
            index=dates,
        )
        macd_frame.loc[dates[10], "bullish_cross"] = True
        macd_frame.loc[dates[12], "bearish_cross"] = True
        monkeypatch.setattr(macd_only, "compute_macd_frame", lambda data, cfg: macd_frame)
        monkeypatch.setattr(macd_only, "compute_atr", lambda data, period=14: pd.Series(1.0, index=dates))

        entries = collect_macd_entry_signals(
            df,
            {
                "macd": {"fast": 8, "slow": 17, "signal": 5},
                "signal_independence": {"min_bars_gap": 4, "min_atr_distance": 0.0},
            },
        )

        assert [(e["bar_index"], e["direction"]) for e in entries] == [(10, "LONG")]

    def test_component_observed_uses_cross_velocity(self, tmp_path):
        from src.quantbuild.strategies.macd_only_engine import run_macd_only_backtest

        close = np.concatenate(
            [
                np.linspace(1.10, 1.12, 40),
                np.linspace(1.12, 1.08, 40),
                np.linspace(1.08, 1.13, 40),
            ]
        )
        dates = pd.date_range("2024-01-01", periods=len(close), freq="15min", tz="UTC")
        df = pd.DataFrame(
            {"open": close, "high": close + 0.0002, "low": close - 0.0002, "close": close},
            index=dates,
        )
        macd_cfg = {"fast": 5, "slow": 10, "signal": 3}
        cfg = {
            "experiment_id": "EXP-MACD-MECH-001-TEST",
            "symbol": "EURUSD",
            "broker": {"mock_spread": 0.00010},
            "strategy": {
                "macd": macd_cfg,
                "signal_independence": {"min_bars_gap": 1, "min_atr_distance": 0.0},
            },
            "exit": {"time_exit_bars": 8},
            "risk": {"sl_atr_mult": 2.0, "max_concurrent": 1, "max_daily_loss_r": 99.0},
            "guards": {"spread": {"enabled": False}},
            "quantlog": {
                "enabled": True,
                "environment": "backtest",
                "base_path": str(tmp_path / "ql"),
                "consolidated_run_file": str(tmp_path / "events.jsonl"),
            },
        }

        run_macd_only_backtest(cfg, df, symbol="EURUSD")

        mf = compute_macd_frame(df, macd_cfg)
        bull, bear = detect_macd_component_observations(mf)
        expected = []
        for i in range(len(df)):
            if bull.iloc[i]:
                expected.append(("MACD_BULL_CROSS", macd_cross_velocity(mf, i)))
            if bear.iloc[i]:
                expected.append(("MACD_BEAR_CROSS", macd_cross_velocity(mf, i)))
        lines = [
            json.loads(line)
            for line in (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        observed = [
            (event["payload"]["component_type"], event["payload"]["macd_cross_velocity"])
            for event in lines
            if event["event_type"] == "component_observed"
        ]

        assert expected
        assert observed == expected

    def test_quantlog_candidate_is_written_when_spread_blocks(self, tmp_path, monkeypatch):
        from src.quantbuild.strategies import macd_only_engine

        df = _ohlc(60)
        signal = {
            "bar_index": 30,
            "component_type": "MACD_BULL_CROSS",
            "session_at_signal": "NEW_YORK",
            "regime_at_signal": "TREND",
            "direction": "LONG",
            "macd_cross_bull": True,
            "macd_cross_bear": False,
            "macd_cross_velocity": 0.5,
        }
        monkeypatch.setattr(
            macd_only_engine,
            "collect_macd_entry_signals",
            lambda *args, **kwargs: [signal],
        )

        ql_file = tmp_path / "events.jsonl"
        cfg = {
            "experiment_id": "EXP-MACD-MECH-SPREAD-BLOCK-TEST",
            "symbol": "EURUSD",
            "broker": {"mock_spread": 0.0010},
            "strategy": {"macd": {"fast": 5, "slow": 10, "signal": 3}},
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

        trades = macd_only_engine.run_macd_only_backtest(cfg, df, symbol="EURUSD")

        assert trades == []
        events = [json.loads(line) for line in ql_file.read_text(encoding="utf-8").splitlines()]
        candidates = [event for event in events if event["event_type"] == "candidate_signal"]
        actions = [event for event in events if event["event_type"] == "trade_action"]
        assert len(candidates) == 1
        assert len(actions) == 1
        assert actions[0]["trace_id"] == candidates[0]["trace_id"]
        assert actions[0]["payload"] == {"decision": "NO_ACTION", "reason": "spread_too_high"}
