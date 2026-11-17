"""Broker factory for selecting execution provider from config."""
from __future__ import annotations

from typing import Any, Dict

from src.quantbuild.execution.broker_ctrader import CTraderBroker
from src.quantbuild.execution.broker_contract import BrokerContract
from src.quantbuild.execution.broker_oanda import OandaBroker
from src.quantbuild.execution.live_execution_preflight import preflight_live_execution
from src.quantbuild.suite_layout import validate_suite_layout


def create_broker(cfg: Dict[str, Any]) -> BrokerContract:
    broker_cfg = cfg.get("broker", {}) or {}
    provider = str(broker_cfg.get("provider", "ctrader")).lower()

    if provider == "ctrader":
        mock_mode = bool(broker_cfg.get("mock_mode", True))
        environment = str(broker_cfg.get("environment", "demo"))
        account_id = str(broker_cfg.get("account_id", "") or "")
        # PR-B #7: non-mock requires suite layout + SESSION before construction.
        if not mock_mode:
            validate_suite_layout()
            preflight_live_execution(
                provider="ctrader",
                environment=environment,
                account_id=account_id,
                intent="SESSION",
            )
        return CTraderBroker(
            account_id=account_id,
            access_token=broker_cfg.get("access_token", ""),
            client_id=broker_cfg.get("client_id", ""),
            client_secret=broker_cfg.get("client_secret", ""),
            environment=environment,
            instrument=broker_cfg.get("instrument", cfg.get("symbol", "XAUUSD")),
            mock_mode=mock_mode,
            initial_balance=float(broker_cfg.get("initial_balance", 10000)),
            mock_spread=float(broker_cfg.get("mock_spread", 0.2)),
            mock_price=float(broker_cfg.get("mock_price", 2500.0)),
        )

    if provider == "oanda":
        environment = str(broker_cfg.get("environment", "practice"))
        account_id = str(broker_cfg.get("account_id", "") or "")
        # PR-B #7: Oanda is always non-mock API surface — layout + SESSION.
        validate_suite_layout()
        preflight_live_execution(
            provider="oanda",
            environment=environment,
            account_id=account_id,
            intent="SESSION",
        )
        return OandaBroker(
            account_id=account_id,
            token=broker_cfg.get("token", ""),
            environment=environment,
            instrument=broker_cfg.get("instrument", "XAU_USD"),
        )

    raise ValueError(f"Unsupported broker provider: {provider}")
