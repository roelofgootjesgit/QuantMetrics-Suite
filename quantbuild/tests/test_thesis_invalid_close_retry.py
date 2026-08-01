"""Regression: thesis-invalid exit must not drop local state when broker close fails."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.quantbuild.execution.live_runner import LiveRunner
from src.quantbuild.models.trade import Position
from tests.test_live_runner import _minimal_cfg


def _open_position(trade_id: str = "t1") -> Position:
    return Position(
        trade_id=trade_id,
        instrument="XAU_USD",
        direction="LONG",
        entry_price=2000.0,
        units=10.0,
        current_price=1995.0,
        unrealized_pnl=-50.0,
        sl=1990.0,
        tp=2020.0,
        open_time=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc),
        thesis_valid=False,
    )


class TestThesisInvalidCloseRetry:
    def test_failed_close_retains_invalid_thesis_for_retry(self):
        runner = LiveRunner(_minimal_cfg(), dry_run=False)
        runner.broker = MagicMock()
        runner.broker.is_connected = True
        runner.broker.close_trade.return_value = False
        runner._emit_trade_closed = MagicMock()

        runner.position_monitor.add_position(_open_position())
        runner.order_manager.unregister_trade = MagicMock()

        runner._monitor_positions()

        retained = runner.position_monitor.all_positions
        assert len(retained) == 1
        assert retained[0].trade_id == "t1"
        assert retained[0].thesis_valid is False
        runner.broker.close_trade.assert_called_once_with("t1")
        runner.order_manager.unregister_trade.assert_not_called()
        runner._emit_trade_closed.assert_not_called()

    def test_successful_close_removes_and_emits(self):
        runner = LiveRunner(_minimal_cfg(), dry_run=False)
        runner.broker = MagicMock()
        runner.broker.is_connected = True
        runner.broker.close_trade.return_value = True
        runner._emit_trade_closed = MagicMock()
        runner.order_manager.unregister_trade = MagicMock()

        runner.position_monitor.add_position(_open_position())
        runner._monitor_positions()

        assert runner.position_monitor.all_positions == []
        runner.order_manager.unregister_trade.assert_called_once_with(
            "t1", reason="thesis_invalid"
        )
        runner._emit_trade_closed.assert_called_once()
        assert runner._emit_trade_closed.call_args.kwargs["outcome"] == "thesis_invalid"

    def test_disconnected_broker_retains_position(self):
        runner = LiveRunner(_minimal_cfg(), dry_run=False)
        runner.broker = MagicMock()
        runner.broker.is_connected = False
        runner._emit_trade_closed = MagicMock()
        runner.order_manager.unregister_trade = MagicMock()

        runner.position_monitor.add_position(_open_position())
        runner._monitor_positions()

        retained = runner.position_monitor.all_positions
        assert len(retained) == 1
        assert retained[0].thesis_valid is False
        runner.broker.close_trade.assert_not_called()
        runner._emit_trade_closed.assert_not_called()

    def test_sync_after_failed_close_does_not_revive_valid_thesis(self):
        """Even if sync runs, retained invalid thesis must not be overwritten."""
        runner = LiveRunner(_minimal_cfg(), dry_run=False)
        runner.broker = MagicMock()
        runner.broker.is_connected = True
        runner.broker.close_trade.return_value = False

        local = _open_position()
        runner.position_monitor.add_position(local)

        # Failed close keeps local invalid thesis.
        runner._monitor_positions()
        assert runner.position_monitor.all_positions[0].thesis_valid is False

        # Broker still shows the trade open — sync must not replace/revive it.
        bt = MagicMock()
        bt.trade_id = "t1"
        bt.instrument = "XAU_USD"
        bt.direction = "LONG"
        bt.entry_price = 2000.0
        bt.units = 10.0
        bt.current_price = 1994.0
        bt.unrealized_pnl = -60.0
        bt.sl = 1990.0
        bt.tp = 2020.0
        bt.open_time = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
        runner.broker.get_open_trades.return_value = [bt]

        runner._sync_positions_from_broker()
        retained = runner.position_monitor.all_positions
        assert len(retained) == 1
        assert retained[0].thesis_valid is False
