"""Tests for BB-only strategy signal logic and midline simulator."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from src.quantbuild.strategies.bb_only import (
    apply_independence_to_signals,
    collect_bb_entry_signals,
    compute_bb_bands,
    detect_bb_component_observations,
    simulate_bb_midline_trade,
)


def _eurusd_df(n: int = 120, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-06-01", periods=n, freq="15min", tz="UTC")
    close = 1.10 + np.cumsum(rng.normal(0, 0.0002, n))
    high = close + rng.uniform(0.00005, 0.0003, n)
    low = close - rng.uniform(0.00005, 0.0003, n)
    return pd.DataFrame(
        {"open": close, "high": high, "low": low, "close": close},
        index=dates,
    )


def _trend_down_through_bands(n: int = 80) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")
    close = np.linspace(1.12, 1.08, n)
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 0.0002,
            "low": close - 0.0002,
            "close": close,
        },
        index=dates,
    )


class TestBBOnlySignals:
    def test_detect_lower_break(self):
        df = _eurusd_df(60, seed=1)
        bands = compute_bb_bands(df, {"length": 20, "stddev": 2.0})
        i = 30
        df.loc[df.index[i], "close"] = float(bands["lower"].iloc[i]) - 0.001
        bands = compute_bb_bands(df, {"length": 20, "stddev": 2.0})
        long_obs, short_obs = detect_bb_component_observations(df, bands)
        assert long_obs.iloc[i]
        assert not (long_obs & short_obs).any()

    def test_independence_filters_cluster(self):
        sig = pd.Series([False, True, True, False, True])
        close = pd.Series([1.0, 1.0, 1.01, 1.0, 1.2])
        atr = pd.Series([0.01] * 5)
        mask = apply_independence_to_signals(
            sig, pd.DataFrame({"close": close}), atr, {"min_bars_gap": 4, "min_atr_distance": 0.0}
        )
        assert mask.iloc[1]
        assert not mask.iloc[2]

    def test_collect_entries_respects_independence(self):
        df = _trend_down_through_bands(100)
        strat = {
            "bollinger": {"length": 20, "stddev": 2.0},
            "signal_independence": {"min_bars_gap": 4, "min_atr_distance": 1.5},
        }
        entries = collect_bb_entry_signals(df, strat)
        indices = [e["bar_index"] for e in entries]
        for a, b in zip(indices, indices[1:]):
            assert b - a >= 4


class TestBBMidlineSimulator:
    def test_long_hits_midline(self):
        n = 40
        dates = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")
        close = np.full(n, 1.0)
        close[10] = 0.95
        for j in range(11, 20):
            close[j] = 0.95 + (j - 10) * 0.01
        mid = np.linspace(1.0, 1.0, n)
        df = pd.DataFrame(
            {
                "open": close,
                "high": close + 0.001,
                "low": close - 0.001,
                "close": close,
            },
            index=dates,
        )
        atr = np.full(n, 0.01)
        res = simulate_bb_midline_trade(
            df, 10, "LONG", mid=mid, atr_arr=atr, sl_atr_mult=5.0, time_exit_bars=20
        )
        assert res["exit_reason"] == "midline"
        assert res["hit_midline_before_sl"] is True
        assert res["bars_to_midline"] is not None

    def test_sl_before_midline(self):
        n = 30
        dates = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")
        close = np.linspace(1.0, 0.90, n)
        low = close - 0.002
        high = close + 0.0001
        mid = np.full(n, 1.0)
        df = pd.DataFrame(
            {"open": close, "high": high, "low": low, "close": close},
            index=dates,
        )
        atr = np.full(n, 0.005)
        res = simulate_bb_midline_trade(
            df, 5, "LONG", mid=mid, atr_arr=atr, sl_atr_mult=2.0, time_exit_bars=20
        )
        assert res["exit_reason"] == "sl"
        assert res["hit_midline_before_sl"] is False


class TestBBOnlyBacktestEngine:
    def test_run_on_synthetic_data(self, tmp_path):
        from src.quantbuild.strategies.bb_only_engine import run_bb_only_backtest

        df = _trend_down_through_bands(150)
        cfg = {
            "experiment_id": "EXP-BB-MECH-001-TEST",
            "symbol": "EURUSD",
            "broker": {"mock_spread": 0.00010},
            "strategy": {
                "bollinger": {"length": 20, "stddev": 2.0},
                "signal_independence": {"min_bars_gap": 4, "min_atr_distance": 1.5},
            },
            "exit": {"time_exit_bars": 32},
            "risk": {"sl_atr_mult": 2.0, "max_concurrent": 1, "max_daily_loss_r": 99.0},
            "guards": {"spread": {"enabled": True, "max_spread_pips": 1.5}},
            "quantlog": {
                "enabled": True,
                "environment": "backtest",
                "base_path": str(tmp_path / "ql"),
                "consolidated_run_file": str(tmp_path / "events.jsonl"),
            },
        }
        trades = run_bb_only_backtest(cfg, df, symbol="EURUSD")
        assert isinstance(trades, list)
        ql_file = tmp_path / "events.jsonl"
        if trades and ql_file.is_file():
            lines = [ln for ln in ql_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
            assert len(lines) >= len(trades) * 2

    def test_quantlog_trade_closed_includes_regime_session(self, tmp_path, monkeypatch):
        from src.quantbuild.strategies import bb_only_engine as engine

        dates = pd.date_range("2024-06-03 08:00", periods=5, freq="15min", tz="UTC")
        close = np.array([1.1000, 1.0990, 1.0985, 1.0995, 1.1005])
        df = pd.DataFrame(
            {
                "open": close,
                "high": close + 0.0002,
                "low": close - 0.0002,
                "close": close,
            },
            index=dates,
        )
        entries = [
            {
                "bar_index": 2,
                "direction": "LONG",
                "component_type": "BB_LOWER_BREAK",
                "bar_timestamp": dates[2],
                "session_at_signal": "LONDON",
                "regime_at_signal": "COMPRESSION",
                "bb_lower_break": True,
                "bb_upper_break": False,
                "bb_extension_normalized_atr": 1.2,
                "bands_mid": 1.1000,
            }
        ]

        monkeypatch.setattr(
            engine,
            "collect_bb_entry_signals",
            lambda data, strat_cfg, session_mode="extended", regime_series=None: entries,
        )
        monkeypatch.setattr(
            engine,
            "simulate_bb_midline_trade",
            lambda *args, **kwargs: {
                "entry_price": float(close[2]),
                "exit_price": 1.1000,
                "sl": float(close[2] - 0.001),
                "tp": 1.1000,
                "exit_ts": dates[4],
                "exit_bar_idx": 4,
                "profit_usd": 0.0015,
                "profit_r": 1.5,
                "result": "WIN",
                "exit_reason": "midline",
                "bars_held": 2,
                "bars_to_midline": 2,
                "hit_midline_before_sl": True,
                "mae_r": 0.1,
                "mfe_r": 1.6,
                "atr": 0.001,
            },
        )

        ql_file = tmp_path / "events.jsonl"
        cfg = {
            "experiment_id": "EXP-BB-MECH-001-TEST",
            "symbol": "EURUSD",
            "broker": {"mock_spread": 0.00010},
            "strategy": {
                "bollinger": {"length": 2, "stddev": 2.0},
                "signal_independence": {"min_bars_gap": 4, "min_atr_distance": 1.5},
            },
            "exit": {"time_exit_bars": 32},
            "risk": {"sl_atr_mult": 2.0, "max_concurrent": 1, "max_daily_loss_r": 99.0},
            "guards": {"spread": {"enabled": True, "max_spread_pips": 1.5}},
            "quantlog": {
                "enabled": True,
                "environment": "backtest",
                "base_path": str(tmp_path / "ql"),
                "consolidated_run_file": str(ql_file),
            },
        }

        trades = engine.run_bb_only_backtest(cfg, df, symbol="EURUSD")

        assert len(trades) == 1
        events = [json.loads(ln) for ln in ql_file.read_text(encoding="utf-8").splitlines()]
        closed = [e for e in events if e["event_type"] == "trade_closed"]
        assert closed[0]["payload"]["regime"] == "compression"
        assert closed[0]["payload"]["session"] == "London"
