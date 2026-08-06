"""OrderManager live risk defaults and break-even pip sizing."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.quantbuild.execution.order_manager import (
    DEFAULT_ORDER_CONFIG,
    OrderManager,
    _merge_order_config,
    _pip_size_for_instrument,
)


def test_default_management_features_are_disabled():
    assert DEFAULT_ORDER_CONFIG["trailing_stop"]["enabled"] is False
    assert DEFAULT_ORDER_CONFIG["break_even"]["enabled"] is False
    assert DEFAULT_ORDER_CONFIG["partial_close"]["enabled"] is False
    mgr = OrderManager(broker=None, config=None)
    assert mgr.config["break_even"]["enabled"] is False
    assert mgr.config["partial_close"]["enabled"] is False
    assert mgr.config["trailing_stop"]["enabled"] is False


def test_merge_preserves_nested_defaults_when_partial_override():
    merged = _merge_order_config({"break_even": {"enabled": True}})
    assert merged["break_even"]["enabled"] is True
    assert merged["break_even"]["trigger_r"] == 1.0
    assert merged["break_even"]["offset_pips"] == 2
    assert merged["trailing_stop"]["enabled"] is False


def test_pip_size_uses_symbol_registry():
    assert _pip_size_for_instrument("XAUUSD") == 0.01
    assert _pip_size_for_instrument("EURUSD") == 0.0001
    assert _pip_size_for_instrument("EUR_USD") == 0.0001


def test_break_even_offset_uses_instrument_pip_size_not_hardcoded_gold():
    broker = MagicMock()
    broker.modify_trade.return_value = True
    mgr = OrderManager(
        broker=broker,
        config={"break_even": {"enabled": True, "trigger_r": 1.0, "offset_pips": 2}},
    )
    mgr.register_trade(
        trade_id="T1",
        instrument="EURUSD",
        direction="LONG",
        entry_price=1.1000,
        units=1000,
        sl=1.0990,  # 10 pips risk
        tp=1.1020,
    )
    # Clearly above +1R (avoid float edge at exactly 1.0R)
    mgr.update_price("T1", 1.1015)
    assert mgr.managed_orders["T1"].break_even_set is True
    # 2 pips * 0.0001 = 0.0002 above entry (NOT 2 * 0.01 = 0.02)
    assert mgr.managed_orders["T1"].current_sl == pytest.approx(1.1002)
    broker.modify_trade.assert_called()
    assert broker.modify_trade.call_args.kwargs["sl"] == pytest.approx(1.1002)


def test_disabled_defaults_do_not_partial_or_trail_without_config():
    broker = MagicMock()
    broker.modify_trade.return_value = True
    broker.close_trade.return_value = True
    mgr = OrderManager(broker=broker, config=None)
    mgr.register_trade(
        trade_id="T2",
        instrument="XAUUSD",
        direction="LONG",
        entry_price=2000.0,
        units=10,
        sl=1990.0,
        tp=2020.0,
    )
    mgr.update_price("T2", 2015.0)  # +1.5R
    assert mgr.managed_orders["T2"].break_even_set is False
    assert mgr.managed_orders["T2"].partial_closed is False
    assert mgr.managed_orders["T2"].trailing_active is False
    broker.close_trade.assert_not_called()
