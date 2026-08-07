"""Regression: slippage flatten / thesis-invalid exits must honor broker close results."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.quantbuild.execution.live_runner import LiveRunner
from src.quantbuild.models.trade import Position
from tests.test_live_runner import _minimal_cfg


def _open_position(trade_id: str = "t1", *, thesis_valid: bool = False) -> Position:
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
        thesis_valid=thesis_valid,
    )


def _slippage_kwargs(runner: LiveRunner) -> dict:
    return {
        "trade_id": "slip1",
        "fill_price": 2010.0,  # 10 pts vs 10 pts risk → 1.0R > 0.15
        "entry_price": 2000.0,
        "sl": 1990.0,
        "tp": 2020.0,
        "units": 5.0,
        "direction": "LONG",
        "entry_atr": 10.0,
        "regime": "trend",
        "session": "London",
        "now": datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc),
        "trace_id": "trace_test",
        "decision_cycle_id": "dc_test",
        "signal_id": "sig1",
        "decision_context_builder": lambda extra: {"execution": extra},
    }


class TestSlippageFlattenCloseRetry:
    def test_successful_flatten_emits_closed_and_does_not_register(self):
        runner = LiveRunner(_minimal_cfg(), dry_run=False)
        runner.broker = MagicMock()
        runner.broker.is_connected = True
        runner.broker.close_trade.return_value = True
        runner._emit_trade_closed = MagicMock()
        runner._emit_guard_decision = MagicMock()
        runner._emit_trade_action = MagicMock()
        runner._emit_signal_filtered = MagicMock()
        runner.order_manager.register_trade = MagicMock()

        result = runner._handle_excessive_slippage_fill(**_slippage_kwargs(runner))

        assert result == ("no_trade", "slippage_block")
        runner.broker.close_trade.assert_called_once_with("slip1")
        runner._emit_trade_closed.assert_called_once()
        assert runner._emit_trade_closed.call_args.kwargs["outcome"] == "slippage_flatten"
        assert runner.position_monitor.all_positions == []
        runner.order_manager.register_trade.assert_not_called()

    def test_failed_flatten_registers_invalid_thesis_without_trade_closed(self):
        runner = LiveRunner(_minimal_cfg(), dry_run=False)
        runner.broker = MagicMock()
        runner.broker.is_connected = True
        runner.broker.close_trade.return_value = False
        runner._emit_trade_closed = MagicMock()
        runner._emit_guard_decision = MagicMock()
        runner._emit_trade_action = MagicMock()
        runner._emit_signal_filtered = MagicMock()
        runner._register_open_trade_quantlog = MagicMock()

        result = runner._handle_excessive_slippage_fill(**_slippage_kwargs(runner))

        assert result == ("no_trade", "slippage_flatten_pending")
        runner._emit_trade_closed.assert_not_called()
        retained = runner.position_monitor.all_positions
        assert len(retained) == 1
        assert retained[0].trade_id == "slip1"
        assert retained[0].thesis_valid is False
        # Pending flatten must still consume a position-limit slot.
        assert runner._check_position_limit() is True  # max_open=3, one pending
        runner.position_monitor.add_position(_open_position("t2", thesis_valid=True))
        runner.position_monitor.add_position(_open_position("t3", thesis_valid=True))
        assert runner._check_position_limit() is False

    def test_acceptable_slippage_returns_none(self):
        runner = LiveRunner(_minimal_cfg(), dry_run=False)
        runner.broker = MagicMock()
        kwargs = _slippage_kwargs(runner)
        kwargs["fill_price"] = 2001.0  # 0.1R < 0.15
        assert runner._handle_excessive_slippage_fill(**kwargs) is None
        runner.broker.close_trade.assert_not_called()


class TestThesisInvalidCloseRetry:
    def test_failed_close_retains_invalid_thesis_for_retry(self):
        runner = LiveRunner(_minimal_cfg(), dry_run=False)
        runner.broker = MagicMock()
        runner.broker.is_connected = True
        runner.broker.close_trade.return_value = False
        runner._emit_trade_closed = MagicMock()
        runner.order_manager.unregister_trade = MagicMock()

        runner.position_monitor.add_position(_open_position())
        runner._monitor_positions()

        retained = runner.position_monitor.all_positions
        assert len(retained) == 1
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

    def test_pending_slippage_flatten_retried_by_monitor(self):
        runner = LiveRunner(_minimal_cfg(), dry_run=False)
        runner.broker = MagicMock()
        runner.broker.is_connected = True
        runner.broker.close_trade.side_effect = [False, True]
        runner._emit_trade_closed = MagicMock()
        runner._emit_guard_decision = MagicMock()
        runner._emit_trade_action = MagicMock()
        runner._emit_signal_filtered = MagicMock()
        runner._register_open_trade_quantlog = MagicMock()

        result = runner._handle_excessive_slippage_fill(**_slippage_kwargs(runner))
        assert result == ("no_trade", "slippage_flatten_pending")
        assert len(runner.position_monitor.all_positions) == 1

        runner._monitor_positions()
        assert runner.position_monitor.all_positions == []
        assert runner._emit_trade_closed.call_args.kwargs["outcome"] == "thesis_invalid"


class TestPositionLimitCountsPendingCloses:
    def test_invalid_thesis_positions_consume_limit_slots(self):
        cfg = _minimal_cfg()
        cfg["execution_guards"]["max_open_positions"] = 2
        runner = LiveRunner(cfg, dry_run=False)

        runner.position_monitor.add_position(_open_position("a", thesis_valid=False))
        runner.position_monitor.add_position(_open_position("b", thesis_valid=True))
        assert runner._check_position_limit() is False
