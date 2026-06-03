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

    def test_component_observed_records_macd_velocity_delta(self, tmp_path):
        from src.quantbuild.strategies.macd_only_engine import run_macd_only_backtest

        close = np.concatenate([np.linspace(1.10, 1.12, 60), np.linspace(1.12, 1.08, 60)])
        dates = pd.date_range("2024-01-01", periods=len(close), freq="15min", tz="UTC")
        df = pd.DataFrame(
            {"open": close, "high": close + 0.0001, "low": close - 0.0001, "close": close},
            index=dates,
        )
        macd_cfg = {"fast": 5, "slow": 10, "signal": 3}
        ql_file = tmp_path / "events.jsonl"
        cfg = {
            "experiment_id": "EXP-MACD-MECH-001-TEST",
            "symbol": "EURUSD",
            "broker": {"provider": "ctrader", "mock_spread": 0.00010},
            "strategy": {
                "macd": macd_cfg,
                "signal_independence": {"min_bars_gap": 4, "min_atr_distance": 1.5},
            },
            "exit": {"time_exit_bars": 8},
            "risk": {"sl_atr_mult": 2.0, "max_concurrent": 1, "max_daily_loss_r": 99.0},
            "guards": {"spread": {"enabled": False}},
            "quantlog": {
                "enabled": True,
                "environment": "backtest",
                "base_path": str(tmp_path / "ql"),
                "consolidated_run_file": str(ql_file),
            },
        }
        run_macd_only_backtest(cfg, df, symbol="EURUSD")

        events = [json.loads(line) for line in ql_file.read_text(encoding="utf-8").splitlines()]
        macd_frame = compute_macd_frame(df, macd_cfg)
        checked = False
        for component in [e["payload"] for e in events if e["event_type"] == "component_observed"]:
            bar_ts = pd.Timestamp(component["bar_timestamp"]).tz_convert("UTC")
            bar_i = int(df.index.get_loc(bar_ts))
            raw_histogram = float(macd_frame["histogram"].iloc[bar_i])
            expected_velocity = macd_cross_velocity(macd_frame, bar_i)
            if expected_velocity == raw_histogram:
                continue

            assert component["macd_cross_velocity"] == expected_velocity
            assert component["macd_cross_velocity"] != raw_histogram
            checked = True
            break
        assert checked
