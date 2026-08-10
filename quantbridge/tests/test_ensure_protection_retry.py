"""Regression: ensure_protection must poll through transient empty syncs."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from quantbridge.execution.models import OrderResult, Position
from quantbridge.execution.order_manager import OrderManager


class _SeqBroker:
    def __init__(self) -> None:
        self.calls = 0
        self.pos = Position(
            trade_id="T1",
            instrument="XAUUSD",
            direction="LONG",
            units=100.0,
            entry_price=2500.0,
            current_price=2500.0,
            unrealized_pnl=0.0,
            sl=None,
            tp=None,
            open_time=datetime.now(timezone.utc),
        )

    def sync_positions(self, instrument=None):
        self.calls += 1
        if self.calls == 1:
            return [self.pos]  # confirm_fill
        if self.calls == 2:
            return []  # transient empty during ensure_protection
        return [replace(self.pos, sl=2490.0, tp=2520.0)]

    def modify_trade(self, trade_id, sl=None, tp=None):
        self.pos = replace(self.pos, sl=sl, tp=tp)
        return True

    def submit_market_order(self, **kwargs):
        return OrderResult(success=True, order_id="O1", trade_id="T1", fill_price=2500.0)

    def get_current_price(self, instrument=None):
        return {"bid": 2499.9, "ask": 2500.1, "spread": 0.2}


def test_ensure_protection_retries_transient_position_not_found():
    broker = _SeqBroker()
    om = OrderManager(
        broker,
        default_fill_timeout_seconds=2.0,
        default_poll_interval_seconds=0.05,
    )
    result = om.place_and_validate(
        instrument="XAUUSD",
        direction="BUY",
        units=100,
        sl=2490,
        tp=2520,
    )
    assert result.success is True
    assert result.status == "validated"
    assert result.protection_confirmed is True
    assert broker.calls >= 3


def test_ensure_protection_direct_retries_then_succeeds():
    class Flaky:
        def __init__(self):
            self.n = 0
            self.pos = Position(
                trade_id="T1",
                instrument="XAUUSD",
                direction="LONG",
                units=100.0,
                entry_price=2500.0,
                current_price=2500.0,
                unrealized_pnl=0.0,
                sl=None,
                tp=None,
                open_time=datetime.now(timezone.utc),
            )

        def sync_positions(self, instrument=None):
            self.n += 1
            if self.n == 1:
                return []
            return [replace(self.pos, sl=2490.0, tp=2520.0)]

        def modify_trade(self, **kwargs):
            return True

    broker = Flaky()
    om = OrderManager(
        broker,
        default_fill_timeout_seconds=2.0,
        default_poll_interval_seconds=0.05,
    )
    ok, pos, err = om.ensure_protection(trade_id="T1", sl=2490, tp=2520)
    assert ok is True
    assert err is None
    assert pos is not None
    assert broker.n >= 2
