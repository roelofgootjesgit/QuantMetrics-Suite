"""Regression: primary_backup must not open backup after primary has exposure."""
from __future__ import annotations

from pathlib import Path

from quantbridge.accounts.account_policy import AccountPolicy
from quantbridge.accounts.account_state_machine import AccountStateMachine
from quantbridge.execution.brokers.ctrader_broker import CTraderBroker
from quantbridge.execution.order_manager import OrderLifecycleResult, OrderManager
from quantbridge.execution.models import OrderResult, Position
from quantbridge.router.account_selector import AccountSelector
from quantbridge.router.execution_orchestrator import MultiAccountExecutionOrchestrator
from quantbridge.router.execution_plan_builder import ExecutionPlanBuilder, TradeRequest


class _StubBroker:
    """Minimal broker surface used by OrderManager.place_and_validate tests."""

    def __init__(
        self,
        *,
        fill_units: float,
        submitted_units: float | None = None,
        expected_trade_id: str = "T1",
    ):
        self.fill_units = fill_units
        self.submitted_units = submitted_units
        self.expected_trade_id = expected_trade_id
        self._price = {"bid": 2500.0, "ask": 2500.2, "spread": 0.2}

    def get_current_price(self, instrument=None):
        return dict(self._price)

    def submit_market_order(self, **kwargs):
        # Mirror CTraderBroker: surface the size actually submitted.
        submitted = (
            float(self.submitted_units)
            if self.submitted_units is not None
            else float(kwargs.get("units", self.fill_units))
        )
        return OrderResult(
            success=True,
            order_id="O1",
            trade_id=self.expected_trade_id,
            fill_price=2500.2,
            message="accepted",
            raw_response={"submitted_units": submitted},
        )

    def sync_positions(self, instrument=None):
        return [
            Position(
                trade_id=self.expected_trade_id,
                instrument=str(instrument or "XAUUSD"),
                direction="LONG",
                units=float(self.fill_units),
                entry_price=2500.2,
                current_price=2500.2,
                unrealized_pnl=0.0,
                sl=2490.0,
                tp=2520.0,
            )
        ]

    def modify_trade(self, **kwargs):
        return True


def _policies():
    return [
        AccountPolicy(account_id="DEMO_A", priority=1, routing_mode="primary"),
        AccountPolicy(account_id="DEMO_B", priority=2, routing_mode="backup"),
    ]


def test_primary_backup_stops_on_partial_fill_exposure(tmp_path: Path):
    """Primary partial fill must block backup — previously opened both accounts."""
    sm = AccountStateMachine(path=tmp_path / "states.json")
    builder = ExecutionPlanBuilder(AccountSelector(sm))
    calls: list[str] = []

    def factory(account_id: str):
        calls.append(account_id)

        class _Mgr:
            def place_and_validate(self, **kwargs):
                return OrderLifecycleResult(
                    success=False,
                    status="fill_unconfirmed",
                    order_id="O1",
                    trade_id=f"T-{account_id}",
                    fill_confirmed=False,
                    filled_units=50.0,
                    message="partial_fill_detected",
                    error="partial_fill_detected",
                )

        return _Mgr()

    orch = MultiAccountExecutionOrchestrator(builder, factory)
    agg = orch.execute(
        request=TradeRequest(
            instrument="XAUUSD",
            direction="BUY",
            units=100.0,
            sl=2490.0,
            tp=2520.0,
            routing_mode="primary_backup",
            account_group="default",
        ),
        policies=_policies(),
    )

    assert calls == ["DEMO_A"]
    assert len(agg.results) == 2
    assert agg.results[0].attempted is True
    assert agg.results[0].status == "fill_unconfirmed"
    assert agg.results[1].attempted is False
    assert agg.results[1].status == "not_attempted_after_open_exposure"
    assert agg.overall_success is False


def test_primary_backup_still_failovers_on_clean_reject(tmp_path: Path):
    sm = AccountStateMachine(path=tmp_path / "states.json")
    builder = ExecutionPlanBuilder(AccountSelector(sm))
    calls: list[str] = []

    def factory(account_id: str):
        calls.append(account_id)

        class _Mgr:
            def place_and_validate(self, **kwargs):
                if account_id == "DEMO_A":
                    return OrderLifecycleResult(
                        success=False,
                        status="rejected",
                        message="order_rejected",
                        error="order_rejected",
                    )
                return OrderLifecycleResult(
                    success=True,
                    status="validated",
                    order_id="O2",
                    trade_id="T-B",
                    fill_confirmed=True,
                    protection_confirmed=True,
                    filled_units=100.0,
                    message="order_validated",
                )

        return _Mgr()

    orch = MultiAccountExecutionOrchestrator(builder, factory)
    agg = orch.execute(
        request=TradeRequest(
            instrument="XAUUSD",
            direction="BUY",
            units=100.0,
            routing_mode="primary_backup",
        ),
        policies=_policies(),
    )
    assert calls == ["DEMO_A", "DEMO_B"]
    assert agg.results[1].success is True
    assert agg.overall_success is True


def test_confirm_fill_uses_submitted_units_and_reports_filled_units():
    """Normalized submit size must not look like a partial fill."""
    # Intent 100.4, broker submits/fills normalized 100.0 via submitted_units.
    broker = _StubBroker(fill_units=100.0, submitted_units=100.0)
    mgr = OrderManager(
        broker=broker,
        default_fill_timeout_seconds=0.4,
        default_poll_interval_seconds=0.05,
    )
    result = mgr.place_and_validate(
        instrument="XAUUSD",
        direction="BUY",
        units=100.4,
        sl=2490.0,
        tp=2520.0,
        enforce_protection=True,
    )
    assert result.success is True
    assert result.filled_units == 100.0


def test_fill_unconfirmed_includes_filled_units_on_true_partial():
    # Submitted full size but only half filled — true residual exposure.
    broker = _StubBroker(fill_units=50.0, submitted_units=100.0)
    mgr = OrderManager(
        broker=broker,
        default_fill_timeout_seconds=0.3,
        default_poll_interval_seconds=0.05,
    )
    result = mgr.place_and_validate(
        instrument="XAUUSD",
        direction="BUY",
        units=100.0,
        sl=2490.0,
        tp=2520.0,
        enforce_protection=True,
    )
    assert result.success is False
    assert result.status == "fill_unconfirmed"
    assert result.error == "partial_fill_detected"
    assert result.filled_units == 50.0
    assert result.trade_id == "T1"


def test_ctrader_broker_normalize_units_does_not_false_partial():
    broker = CTraderBroker(
        account_id="A",
        access_token="t",
        mode="mock",
        instrument="XAUUSD",
    )
    assert broker.connect()
    mgr = OrderManager(
        broker=broker,
        default_fill_timeout_seconds=2.0,
        default_poll_interval_seconds=0.1,
    )
    result = mgr.place_and_validate(
        instrument="XAUUSD",
        direction="BUY",
        units=100.4,
        sl=2490.0,
        tp=2520.0,
    )
    assert result.success is True
    assert result.filled_units == 100.0
