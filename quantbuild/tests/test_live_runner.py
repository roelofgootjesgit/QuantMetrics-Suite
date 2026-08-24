"""Unit tests for LiveRunner — decision kernel wiring."""
import logging

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

import src.quantbuild.execution.live_runner as live_runner_mod
from src.quantbuild.execution.live_runner import LiveRunner
from src.quantbuild.execution.quantlog_ids import resolve_quantlog_run_id, resolve_quantlog_session_id


def _minimal_cfg():
    return {
        "symbol": "XAUUSD",
        "timeframes": ["15m", "1h"],
        "data": {"base_path": "data/market_cache"},
        "backtest": {"tp_r": 2.0, "sl_r": 1.0, "session_mode": "extended"},
        "risk": {"max_daily_loss_r": 3.0, "max_position_pct": 1.0, "paper_equity": 10000},
        "strategy": {},
        "regime": {},
        "regime_profiles": {
            "trend": {"tp_r": 2.0, "sl_r": 1.0, "max_trades_per_session": 3},
            "compression": {"skip": True},
            "expansion": {
                "tp_r": 2.0, "sl_r": 1.0,
                "allowed_sessions": ["New York", "Overlap"],
                "min_hour_utc": 10,
            },
        },
        "execution_guards": {"max_spread_pips": 5.0, "max_slippage_r": 0.15, "max_open_positions": 3},
        "execution": {"check_interval_seconds": 60, "regime_update_seconds": 900},
        "news": {"enabled": False},
        "broker": {"account_id": "", "token": "", "environment": "practice", "instrument": "XAU_USD"},
    }


def _make_ohlc(n=200):
    np.random.seed(42)
    close = 2000 + np.cumsum(np.random.randn(n) * 2)
    high = close + np.abs(np.random.randn(n)) * 3
    low = close - np.abs(np.random.randn(n)) * 3
    opn = close + np.random.randn(n)
    return pd.DataFrame(
        {"open": opn, "high": high, "low": low, "close": close},
        index=pd.date_range("2025-01-01 10:00", periods=n, freq="15min", tz="UTC"),
    )


class TestQuantLogRunSessionIds:
    @pytest.fixture(autouse=True)
    def _clear_quantlog_run_env(self, monkeypatch):
        """GitHub Actions (and systemd) set INVOCATION_ID; tests need deterministic defaults."""
        monkeypatch.delenv("INVOCATION_ID", raising=False)
        monkeypatch.delenv("QUANTBUILD_RUN_ID", raising=False)

    def test_empty_config_run_id_uses_default_prefix(self):
        rid = resolve_quantlog_run_id({})
        assert rid.startswith("qb_run_")
        assert len(rid) > len("qb_run_")

    def test_whitespace_run_id_falls_through_to_default(self):
        rid = resolve_quantlog_run_id({"run_id": "  "})
        assert rid.startswith("qb_run_")

    def test_explicit_run_id_preserved(self):
        assert resolve_quantlog_run_id({"run_id": "my_run"}) == "my_run"

    def test_env_quantbuild_run_id_when_config_empty(self, monkeypatch):
        monkeypatch.delenv("INVOCATION_ID", raising=False)
        monkeypatch.setenv("QUANTBUILD_RUN_ID", "from_env")
        rid = resolve_quantlog_run_id({"run_id": ""})
        assert rid == "from_env"

    def test_invocation_id_when_no_config(self, monkeypatch):
        monkeypatch.delenv("QUANTBUILD_RUN_ID", raising=False)
        monkeypatch.setenv("INVOCATION_ID", "systemd-abc")
        rid = resolve_quantlog_run_id({})
        assert rid == "systemd-abc"

    def test_empty_session_id_gets_default_prefix(self):
        sid = resolve_quantlog_session_id({"session_id": ""})
        assert sid.startswith("qb_session_")

    def test_quantlog_emitter_non_empty_ids_with_empty_yaml(self):
        cfg = {
            **_minimal_cfg(),
            "quantlog": {"enabled": True, "run_id": "", "session_id": ""},
        }
        runner = LiveRunner(cfg, dry_run=True)
        assert runner._quantlog is not None
        assert runner._quantlog.run_id.startswith("qb_run_")
        assert runner._quantlog.session_id.startswith("qb_session_")

    def test_quantlog_warns_when_cli_repo_not_found(self, monkeypatch, caplog):
        monkeypatch.setattr(live_runner_mod, "resolve_quantlog_repo_path", lambda: None)
        cfg = {**_minimal_cfg(), "quantlog": {"enabled": True}}
        with caplog.at_level(logging.WARNING):
            LiveRunner(cfg, dry_run=True)
        assert any("QuantLog JSONL is on" in r.message for r in caplog.records)


class TestLiveRunnerInit:
    def test_creates_with_dry_run(self):
        runner = LiveRunner(_minimal_cfg(), dry_run=True)
        assert runner.dry_run
        assert runner._current_regime is None
        assert runner._current_atr == 0.0

    def test_news_layer_disabled(self):
        runner = LiveRunner(_minimal_cfg(), dry_run=True)
        assert runner._news_gate is None
        assert runner._news_poller is None


class TestRegimeUpdate:
    def test_updates_regime_from_data(self):
        runner = LiveRunner(_minimal_cfg(), dry_run=True)
        data = _make_ohlc(200)
        runner._update_regime(data)
        assert runner._current_regime is not None
        assert runner._current_regime in ("trend", "expansion", "compression")
        assert runner._current_atr > 0

    def test_effective_regime_without_override(self):
        runner = LiveRunner(_minimal_cfg(), dry_run=True)
        runner._current_regime = "trend"
        assert runner.get_effective_regime() == "trend"

    def test_effective_regime_with_override(self):
        runner = LiveRunner(_minimal_cfg(), dry_run=True)
        runner._current_regime = "trend"
        runner._news_regime_override = "expansion"
        assert runner.get_effective_regime() == "expansion"

    def test_empty_data_does_not_crash(self):
        runner = LiveRunner(_minimal_cfg(), dry_run=True)
        runner._update_regime(pd.DataFrame())
        assert runner._current_regime is None


class TestGuardrails:
    def test_position_limit(self):
        runner = LiveRunner(_minimal_cfg(), dry_run=True)
        assert runner._check_position_limit()

    def test_daily_loss_limit(self):
        runner = LiveRunner(_minimal_cfg(), dry_run=True)
        assert runner._check_daily_loss_limit()
        runner._daily_pnl_r = -4.0
        assert not runner._check_daily_loss_limit()

    def test_daily_tracking_reset(self):
        runner = LiveRunner(_minimal_cfg(), dry_run=True)
        runner._daily_pnl_r = -2.0
        runner._daily_date = "2025-01-01"
        now = datetime(2025, 1, 2, 10, 0, tzinfo=timezone.utc)
        runner._reset_daily_tracking(now)
        assert runner._daily_pnl_r == 0.0
        assert runner._daily_date == "2025-01-02"

    def test_spread_guard_dry_run(self):
        runner = LiveRunner(_minimal_cfg(), dry_run=True)
        assert runner._check_spread_guard() is None

    def test_calculate_units_dry_run(self):
        runner = LiveRunner(_minimal_cfg(), dry_run=True)
        units = runner._calculate_units(entry=2000, sl=1998, risk_pct=1.0)
        assert units > 0
        expected = round(10000 * 0.01 / 2.0)
        assert units == expected


class TestRegimeSkip:
    def test_compression_skipped(self):
        runner = LiveRunner(_minimal_cfg(), dry_run=True)
        runner._current_regime = "compression"
        now = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
        # Should skip silently (compression) before loading bars
        with patch.object(runner, "_load_recent_data", return_value=(pd.DataFrame(), "test")):
            runner._check_signals(now)
        # No error, no crash

    def test_expansion_blocked_in_london(self):
        """Expansion should be blocked outside NY/Overlap."""
        runner = LiveRunner(_minimal_cfg(), dry_run=True)
        runner._current_regime = "expansion"
        now = datetime(2025, 1, 1, 8, 0, tzinfo=timezone.utc)
        data = _ohlc_ending_at("2025-01-01 07:45", n=120)
        with patch.object(runner, "_load_recent_data", return_value=(data, "test")):
            runner._check_signals(now)
        # Should silently skip — no crash


def _ohlc_ending_at(end_ts: str, n: int = 120) -> pd.DataFrame:
    idx = pd.date_range(end=pd.Timestamp(end_ts, tz="UTC"), periods=n, freq="15min")
    close = np.full(n, 2000.0)
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": np.ones(n),
        },
        index=idx,
    )


class TestLiveSessionUsesBarTimestamp:
    """Session/hour gates must use the signal bar open time, not wall clock.

    Completed 15m bars are open-indexed: the 09:45 London bar first appears at 10:00
    when wall clock is already Overlap. Production expansion is NY/Overlap only.
    """

    def _runner(self) -> LiveRunner:
        cfg = {
            **_minimal_cfg(),
            "quantlog": {"enabled": False},
            "filters": {"cooldown": False},
        }
        runner = LiveRunner(cfg, dry_run=True)
        runner._current_regime = "expansion"
        return runner

    def test_expansion_london_bar_blocked_after_overlap_clock(self):
        runner = self._runner()
        data = _ohlc_ending_at("2025-01-02 09:45", n=120)
        now = datetime(2025, 1, 2, 10, 5, tzinfo=timezone.utc)
        executed = []
        with patch.object(runner, "_load_recent_data", return_value=(data, "ctrader")):
            with patch.object(
                runner, "_evaluate_and_execute", side_effect=lambda *a, **k: executed.append(1) or ("enter", "ok")
            ):
                with patch.object(runner, "_compute_sqe_signal_state") as sqe:
                    runner._check_signals(now)
        assert executed == []
        sqe.assert_not_called()

    def test_naive_utc_index_london_bar_also_blocked(self):
        """Parquet cache strips tz; open-indexed 09:45 must still be London."""
        runner = self._runner()
        data = _ohlc_ending_at("2025-01-02 09:45", n=120)
        data.index = data.index.tz_localize(None)
        now = datetime(2025, 1, 2, 10, 5, tzinfo=timezone.utc)
        executed = []
        with patch.object(runner, "_load_recent_data", return_value=(data, "ctrader")):
            with patch.object(
                runner, "_evaluate_and_execute", side_effect=lambda *a, **k: executed.append(1) or ("enter", "ok")
            ):
                runner._check_signals(now)
        assert executed == []

    def test_expansion_overlap_bar_still_reaches_execution(self):
        runner = self._runner()
        data = _ohlc_ending_at("2025-01-02 10:00", n=120)
        now = datetime(2025, 1, 2, 10, 20, tzinfo=timezone.utc)
        last_idx = len(data) - 1
        dummy_df = data.copy()
        executed = []

        def _sqe(_data):
            return dummy_df, last_idx, {}, ["LONG"], True, False

        with patch.object(runner, "_load_recent_data", return_value=(data, "ctrader")):
            with patch.object(runner, "_compute_sqe_signal_state", side_effect=_sqe):
                with patch.object(
                    runner,
                    "_evaluate_and_execute",
                    side_effect=lambda *a, **k: executed.append(a[0]) or ("enter", "all_conditions_met"),
                ):
                    with patch(
                        "src.quantbuild.execution.live_runner.sqe_decision_context_at_bar",
                        return_value={},
                    ):
                        runner._check_signals(now)
        assert executed == ["LONG"]

    def test_should_evaluate_just_closed_ny_bar_after_asia_clock(self):
        runner = self._runner()
        at_close = datetime(2025, 1, 2, 16, 5, tzinfo=timezone.utc)
        later = datetime(2025, 1, 2, 16, 20, tzinfo=timezone.utc)
        assert runner._should_evaluate_entry_signals(at_close) is True
        assert runner._should_evaluate_entry_signals(later) is False

    def test_regime_session_gate_uses_bar_hour_not_wall_clock(self):
        runner = self._runner()
        london_bar = datetime(2025, 1, 2, 9, 45, tzinfo=timezone.utc)
        session, reason, extras = runner._regime_session_gate("expansion", london_bar)
        assert session == "London"
        assert reason == "outside_killzone"
        overlap_bar = datetime(2025, 1, 2, 10, 0, tzinfo=timezone.utc)
        session, reason, extras = runner._regime_session_gate("expansion", overlap_bar)
        assert session == "Overlap"
        assert reason is None
        assert extras["hour_utc"] == 10
