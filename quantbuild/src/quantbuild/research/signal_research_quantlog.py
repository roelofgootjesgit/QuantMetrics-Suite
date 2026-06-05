"""QuantLog payload builders for BB/MACD signal research (EXP-BB-MECH)."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

COMPONENT_TYPES = frozenset(
    {
        "BB_LOWER_BREAK",
        "BB_UPPER_BREAK",
        "MACD_BULL_CROSS",
        "MACD_BEAR_CROSS",
        "JOINT",
    }
)


def signal_research_metrics(
    *,
    bb_lower_break: bool = False,
    bb_upper_break: bool = False,
    macd_cross_bull: bool = False,
    macd_cross_bear: bool = False,
    bb_extension_normalized_atr: float = 0.0,
    macd_cross_velocity: float = 0.0,
    regime_at_signal: str = "UNKNOWN",
    session_at_signal: str = "OFF_HOURS",
    bars_since_last_signal: int = 0,
    price_distance_from_last_signal_atr: float = 0.0,
    signal_is_independent: bool = True,
) -> dict[str, Any]:
    """Optional research metrics shared across component/candidate/signal_detected payloads."""
    return {
        "bb_lower_break": bb_lower_break,
        "bb_upper_break": bb_upper_break,
        "macd_cross_bull": macd_cross_bull,
        "macd_cross_bear": macd_cross_bear,
        "bb_extension_normalized_atr": float(bb_extension_normalized_atr),
        "macd_cross_velocity": float(macd_cross_velocity),
        "regime_at_signal": regime_at_signal,
        "session_at_signal": session_at_signal,
        "bars_since_last_signal": int(bars_since_last_signal),
        "price_distance_from_last_signal_atr": float(price_distance_from_last_signal_atr),
        "signal_is_independent": signal_is_independent,
    }


def build_component_observed_payload(
    *,
    component_type: str,
    bar_timestamp: str,
    session_at_signal: str,
    regime_at_signal: str,
    observation_id: str | None = None,
    **metrics: Any,
) -> dict[str, Any]:
    if component_type not in COMPONENT_TYPES:
        raise ValueError(f"invalid component_type: {component_type!r}")
    payload: dict[str, Any] = {
        "observation_id": observation_id or str(uuid4()),
        "component_type": component_type,
        "bar_timestamp": bar_timestamp,
        "session_at_signal": session_at_signal,
        "regime_at_signal": regime_at_signal,
    }
    payload.update(
        signal_research_metrics(
            session_at_signal=session_at_signal,
            regime_at_signal=regime_at_signal,
            **metrics,
        )
    )
    return payload


def build_candidate_signal_payload(
    *,
    component_type: str,
    bar_timestamp: str,
    session_at_signal: str,
    regime_at_signal: str,
    direction: str,
    signal_is_independent: bool,
    signal_id: str | None = None,
    **metrics: Any,
) -> dict[str, Any]:
    if component_type not in COMPONENT_TYPES:
        raise ValueError(f"invalid component_type: {component_type!r}")
    direction_u = direction.upper()
    if direction_u not in {"LONG", "SHORT"}:
        raise ValueError(f"invalid direction: {direction!r}")
    payload: dict[str, Any] = {
        "signal_id": signal_id or str(uuid4()),
        "component_type": component_type,
        "bar_timestamp": bar_timestamp,
        "session_at_signal": session_at_signal,
        "regime_at_signal": regime_at_signal,
        "direction": direction_u,
        "signal_is_independent": signal_is_independent,
    }
    merged = signal_research_metrics(
        session_at_signal=session_at_signal,
        regime_at_signal=regime_at_signal,
        signal_is_independent=signal_is_independent,
        **metrics,
    )
    payload.update(merged)
    return payload


def build_trade_closed_research_payload(
    *,
    trade_id: str,
    exit_price: float,
    pnl_r: float,
    exit_reason: str,
    bars_held: int,
    hit_midline_before_sl: bool = False,
    bars_to_midline: int | None = None,
    mfe_r: float = 0.0,
    mae_r: float = 0.0,
    **extra: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "trade_id": trade_id,
        "exit_price": exit_price,
        "pnl_r": pnl_r,
        "exit_reason": exit_reason,
        "bars_held": bars_held,
        "hit_midline_before_sl": hit_midline_before_sl,
        "bars_to_midline": bars_to_midline,
        "mfe_r": float(mfe_r),
        "mae_r": float(mae_r),
    }
    payload.update(extra)
    return payload
