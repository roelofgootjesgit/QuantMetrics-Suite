"""Live equity kill switch: peak-to-current closed-trade R drawdown must halt entries."""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from src.quantbuild.execution.live_runner import LiveRunner


def _cfg(tmp_path, **risk_extra):
    cfg = {
        "symbol": "XAUUSD",
        "timeframes": ["15m", "1h"],
        "data": {"base_path": str(tmp_path)},
        "backtest": {"tp_r": 2.0, "sl_r": 1.0, "session_mode": "extended"},
        "risk": {
            "max_daily_loss_r": 3.0,
            "max_position_pct": 1.0,
            "paper_equity": 10000,
            "equity_kill_switch_pct": 10.0,
        },
        "strategy": {},
        "regime": {},
        "regime_profiles": {
            "trend": {"tp_r": 2.0, "sl_r": 1.0, "max_trades_per_session": 3},
        },
        "execution_guards": {"max_spread_pips": 5.0, "max_slippage_r": 0.15, "max_open_positions": 3},
        "execution": {"check_interval_seconds": 60, "regime_update_seconds": 900},
        "news": {"enabled": False},
        "quantlog": {"enabled": False},
        "broker": {"account_id": "", "token": "", "environment": "practice", "instrument": "XAU_USD"},
    }
    cfg["risk"].update(risk_extra)
    return cfg


class TestEquityKillSwitch:
    def test_allows_entries_before_threshold(self, tmp_path):
        runner = LiveRunner(_cfg(tmp_path), dry_run=True)
        assert runner._check_equity_kill_switch()
        runner._record_closed_trade_r(2.0)
        runner._record_closed_trade_r(-3.0)  # peak 2, cum -1, dd 3 < 10
        assert runner._check_equity_kill_switch()
        assert not runner._equity_kill_latched

    def test_trips_at_peak_to_current_r_drawdown(self, tmp_path):
        runner = LiveRunner(_cfg(tmp_path), dry_run=True)
        runner._record_closed_trade_r(5.0)
        runner._record_closed_trade_r(-6.0)
        runner._record_closed_trade_r(-9.0)  # peak 5, cum -10, dd 15 >= 10
        assert runner._equity_kill_latched
        assert not runner._check_equity_kill_switch()

    def test_zero_threshold_disables(self, tmp_path):
        runner = LiveRunner(_cfg(tmp_path, equity_kill_switch_pct=0.0), dry_run=True)
        runner._record_closed_trade_r(-50.0)
        assert runner._check_equity_kill_switch()
        assert not runner._equity_kill_latched

    def test_stays_latched_after_recovery(self, tmp_path):
        runner = LiveRunner(_cfg(tmp_path), dry_run=True)
        runner._record_closed_trade_r(2.0)
        runner._record_closed_trade_r(-12.0)  # dd 12 >= 10
        assert not runner._check_equity_kill_switch()
        runner._record_closed_trade_r(20.0)  # equity recovers
        assert not runner._check_equity_kill_switch()
        assert runner._equity_kill_latched

    def test_persists_across_restart(self, tmp_path):
        cfg = _cfg(tmp_path)
        first = LiveRunner(cfg, dry_run=True)
        first._record_closed_trade_r(4.0)
        first._record_closed_trade_r(-15.0)
        assert first._equity_kill_latched

        second = LiveRunner(cfg, dry_run=True)
        assert second._equity_kill_latched
        assert second._cumulative_r == pytest.approx(-11.0)
        assert second._peak_r == pytest.approx(4.0)
        assert not second._check_equity_kill_switch()

    def test_emit_trade_closed_records_r_without_quantlog(self, tmp_path):
        runner = LiveRunner(_cfg(tmp_path), dry_run=True)
        runner._emit_trade_closed(
            trade_id="t1",
            exit_price=2000.0,
            pnl_r=-10.0,
            outcome="closed_external",
            exit_tag="broker_sync",
        )
        assert runner._cumulative_r == pytest.approx(-10.0)
        assert runner._equity_kill_latched

    def test_check_signals_blocks_new_entries(self, tmp_path):
        runner = LiveRunner(_cfg(tmp_path), dry_run=True)
        runner._record_closed_trade_r(-10.0)
        now = datetime(2025, 1, 1, 14, 0, tzinfo=timezone.utc)  # NY session
        with patch.object(runner, "_load_recent_data") as load_data, patch.object(
            runner, "_emit_trade_action"
        ) as emit_action:
            runner._check_signals(now)
            load_data.assert_not_called()
            reasons = [c.kwargs.get("reason") for c in emit_action.call_args_list]
            assert "equity_kill_switch_block" in reasons
