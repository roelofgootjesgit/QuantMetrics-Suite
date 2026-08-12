"""Critical live safety: broker-aware position limit + pending flatten persistence."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.quantbuild.execution.live_runner import LiveRunner
from src.quantbuild.models.trade import Position, TradeDirection


def _minimal_cfg(tmp_path):
    return {
        "symbol": "XAUUSD",
        "timeframes": ["15m", "1h"],
        "data": {"base_path": str(tmp_path / "market_cache")},
        "backtest": {"tp_r": 2.0, "sl_r": 1.0, "session_mode": "extended"},
        "risk": {"max_daily_loss_r": 3.0, "max_position_pct": 1.0, "paper_equity": 10000},
        "strategy": {},
        "regime": {},
        "regime_profiles": {
            "trend": {"tp_r": 2.0, "sl_r": 1.0, "max_trades_per_session": 3},
            "compression": {"skip": True},
            "expansion": {
                "tp_r": 2.0,
                "sl_r": 1.0,
                "allowed_sessions": ["New York", "Overlap"],
                "min_hour_utc": 10,
            },
        },
        "execution_guards": {
            "max_spread_pips": 5.0,
            "max_slippage_r": 0.15,
            "max_open_positions": 1,
        },
        "execution": {"check_interval_seconds": 60, "regime_update_seconds": 900},
        "news": {"enabled": False},
        "broker": {
            "account_id": "",
            "token": "",
            "environment": "practice",
            "instrument": "XAU_USD",
        },
    }


def _position(trade_id: str, thesis_valid: bool = True) -> Position:
    return Position(
        trade_id=trade_id,
        instrument="XAU_USD",
        direction=TradeDirection.LONG,
        entry_price=2000.0,
        units=1.0,
        current_price=2001.0,
        unrealized_pnl=1.0,
        sl=1990.0,
        tp=2020.0,
        open_time=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc),
        thesis_valid=thesis_valid,
    )


def _broker_trade(trade_id: str):
    return SimpleNamespace(
        trade_id=trade_id,
        instrument="XAU_USD",
        direction="LONG",
        entry_price=2000.0,
        units=1.0,
        current_price=2001.0,
        unrealized_pnl=1.0,
        sl=1990.0,
        tp=2020.0,
        open_time=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc),
    )


class TestBrokerAwarePositionLimit:
    def test_thesis_invalid_still_counts_toward_limit(self, tmp_path):
        runner = LiveRunner(_minimal_cfg(tmp_path), dry_run=True)
        runner.position_monitor.add_position(_position("t1", thesis_valid=False))
        # Tip bug: open_positions ignored thesis_valid=False and allowed another entry.
        assert not runner._check_position_limit()

    def test_broker_open_count_blocks_when_local_empty(self, tmp_path):
        runner = LiveRunner(_minimal_cfg(tmp_path), dry_run=False)
        runner.broker = MagicMock()
        runner.broker.is_connected = True
        runner.broker.get_open_trades.return_value = [_broker_trade("broker-1")]
        assert not runner._check_position_limit()
        runner.broker.get_open_trades.assert_called_once_with(instrument=None)

    def test_broker_query_failure_fail_closed(self, tmp_path):
        runner = LiveRunner(_minimal_cfg(tmp_path), dry_run=False)
        runner.broker = MagicMock()
        runner.broker.is_connected = True
        runner.broker.get_open_trades.side_effect = RuntimeError("reconcile down")
        assert not runner._check_position_limit()

    def test_allows_entry_when_flat_locally_and_on_broker(self, tmp_path):
        runner = LiveRunner(_minimal_cfg(tmp_path), dry_run=False)
        runner.broker = MagicMock()
        runner.broker.is_connected = True
        runner.broker.get_open_trades.return_value = []
        assert runner._check_position_limit()


class TestPendingFlattenPersistence:
    def test_mark_thesis_invalid_persists_across_restart(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        runner = LiveRunner(cfg, dry_run=False)
        runner.position_monitor.add_position(_position("t42"))
        runner._mark_thesis_invalid("t42", "counter_news_exit")

        path = runner._pending_flatten_state_path()
        assert path.exists()
        assert "t42" in runner._pending_flatten_ids

        # Simulate process restart: fresh runner loads persisted flatten intent.
        restarted = LiveRunner(cfg, dry_run=False)
        restarted._load_pending_flatten_state()
        assert "t42" in restarted._pending_flatten_ids

        restarted.broker = MagicMock()
        restarted.broker.is_connected = True
        restarted.broker.get_open_trades.return_value = [_broker_trade("t42")]
        restarted._sync_positions_from_broker()

        synced = restarted.position_monitor.all_positions
        assert len(synced) == 1
        assert synced[0].trade_id == "t42"
        assert synced[0].thesis_valid is False

    def test_sync_clears_pending_flatten_when_broker_closed(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        runner = LiveRunner(cfg, dry_run=False)
        runner._pending_flatten_ids.add("t99")
        runner._save_pending_flatten_state()
        runner.position_monitor.add_position(_position("t99", thesis_valid=False))

        runner.broker = MagicMock()
        runner.broker.is_connected = True
        runner.broker.get_open_trades.return_value = []
        runner._sync_positions_from_broker()

        assert "t99" not in runner._pending_flatten_ids
        assert runner.position_monitor.all_positions == []

    def test_monitor_keeps_pending_flatten_when_close_fails(self, tmp_path):
        runner = LiveRunner(_minimal_cfg(tmp_path), dry_run=False)
        runner.position_monitor.add_position(_position("t7", thesis_valid=False))
        runner.broker = MagicMock()
        runner.broker.is_connected = True
        runner.broker.close_trade.return_value = False

        runner._monitor_positions()

        assert len(runner.position_monitor.all_positions) == 1
        assert "t7" in runner._pending_flatten_ids
        assert runner.position_monitor.all_positions[0].thesis_valid is False
