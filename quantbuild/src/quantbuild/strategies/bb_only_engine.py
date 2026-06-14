"""Backtest engine for BB-only extension strategy (EXP-BB-MECH-001)."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

import numpy as np
import pandas as pd

from src.quantbuild.backtest.engine import (
    _bar_timestamp_utc_iso,
    _init_backtest_quantlog,
    _prepare_sim_cache,
)
from src.quantbuild.data.sessions import session_from_timestamp
from src.quantbuild.execution.quantlog_no_action import canonical_no_action_reason
from src.quantbuild.execution.signal_evaluated_payload import new_decision_cycle_id
from src.quantbuild.export.trade_r_series import assert_quantlog_inference_policy, maybe_write_trade_r_series_fallback
from src.quantbuild.indicators.atr import atr as compute_atr
from src.quantbuild.models.trade import Trade, TradeDirection, TradeResult
from src.quantbuild.research.signal_research_quantlog import (
    build_candidate_signal_payload,
    build_component_observed_payload,
    build_trade_closed_research_payload,
)
from src.quantbuild.strategies.bb_only import (
    STRATEGY_ID,
    bb_only_strategy_cfg,
    collect_bb_entry_signals,
    compute_bb_bands,
    detect_bb_component_observations,
    regime_at_signal_label,
    session_at_signal_label,
    simulate_bb_midline_trade,
)

logger = logging.getLogger(__name__)


def _pip_size(symbol: str) -> float:
    s = symbol.upper()
    if "JPY" in s:
        return 0.01
    return 0.0001


def _spread_ok(cfg: Dict[str, Any], symbol: str) -> bool:
    guards = (cfg.get("guards") or {}).get("spread") or {}
    if not bool(guards.get("enabled", False)):
        return True
    broker = cfg.get("broker") or {}
    mock_spread = float(broker.get("mock_spread", 0.0))
    max_pips = float(guards.get("max_spread_pips", 1.5))
    spread_pips = mock_spread / _pip_size(symbol) if mock_spread > 0 else 0.0
    return spread_pips <= max_pips


def run_bb_only_backtest(
    cfg: Dict[str, Any],
    data: pd.DataFrame,
    *,
    symbol: str,
    session_mode: str = "extended",
    regime_series: Optional[pd.Series] = None,
) -> List[Trade]:
    strat_cfg = bb_only_strategy_cfg(cfg)
    exit_cfg = strat_cfg.get("exit") or {}
    risk_cfg = strat_cfg.get("risk") or {}
    sl_atr_mult = float(risk_cfg.get("sl_atr_mult", 2.0))
    time_exit_bars = int(exit_cfg.get("time_exit_bars", 32))
    max_concurrent = int(risk_cfg.get("max_concurrent", 1))
    max_daily_loss_r = float(
        risk_cfg.get("max_daily_loss_r", risk_cfg.get("daily_dd_limit_pct", 2.0))
    )

    bands = compute_bb_bands(data, strat_cfg.get("bollinger") or {})
    atr_series = compute_atr(data, period=14)
    sim_cache = _prepare_sim_cache(data)
    sim_cache["mid"] = bands["mid"].values.astype(np.float64)

    long_raw, short_raw = detect_bb_component_observations(data, bands)
    ql_emitter = _init_backtest_quantlog(cfg)
    assert_quantlog_inference_policy(cfg)
    account_id = str(cfg.get("broker", {}).get("account_id") or "backtest")
    strategy_id = str(cfg.get("experiment_id") or STRATEGY_ID)

    for i in range(len(data)):
        if not ql_emitter:
            break
        ts = data.index[i]
        ts_iso = _bar_timestamp_utc_iso(ts)
        regime_lbl = regime_at_signal_label(
            regime_series.iloc[i] if regime_series is not None and i < len(regime_series) else None
        )
        sess_lbl = session_at_signal_label(ts, session_mode)
        trace = str(uuid4())
        if long_raw.iloc[i]:
            ql_emitter.emit(
                event_type="component_observed",
                trace_id=trace,
                timestamp_utc=ts_iso,
                account_id=account_id,
                strategy_id=strategy_id,
                symbol=symbol,
                payload=build_component_observed_payload(
                    component_type="BB_LOWER_BREAK",
                    bar_timestamp=ts_iso,
                    session_at_signal=sess_lbl,
                    regime_at_signal=regime_lbl,
                    bb_lower_break=True,
                ),
            )
        if short_raw.iloc[i]:
            ql_emitter.emit(
                event_type="component_observed",
                trace_id=str(uuid4()),
                timestamp_utc=ts_iso,
                account_id=account_id,
                strategy_id=strategy_id,
                symbol=symbol,
                payload=build_component_observed_payload(
                    component_type="BB_UPPER_BREAK",
                    bar_timestamp=ts_iso,
                    session_at_signal=sess_lbl,
                    regime_at_signal=regime_lbl,
                    bb_upper_break=True,
                ),
            )

    entry_signals = collect_bb_entry_signals(
        data, strat_cfg, session_mode=session_mode, regime_series=regime_series
    )
    logger.info("BB-only independent entry signals: %d", len(entry_signals))

    trades: List[Trade] = []
    trade_order_refs: List[str] = []
    daily_pnl_r: Dict[Any, float] = {}
    open_until_bar = -1

    for sig in entry_signals:
        i = int(sig["bar_index"])
        entry_ts = data.index[i]
        direction = sig["direction"]
        ts_iso = _bar_timestamp_utc_iso(entry_ts)
        trace_id = str(uuid4())
        if ql_emitter:
            ql_emitter.emit(
                event_type="candidate_signal",
                trace_id=trace_id,
                timestamp_utc=ts_iso,
                account_id=account_id,
                strategy_id=strategy_id,
                symbol=symbol,
                payload=build_candidate_signal_payload(
                    component_type=sig["component_type"],
                    bar_timestamp=ts_iso,
                    session_at_signal=sig["session_at_signal"],
                    regime_at_signal=sig["regime_at_signal"],
                    direction=direction,
                    signal_is_independent=True,
                    bb_lower_break=sig["bb_lower_break"],
                    bb_upper_break=sig["bb_upper_break"],
                    bb_extension_normalized_atr=sig["bb_extension_normalized_atr"],
                ),
            )

        if i <= open_until_bar and max_concurrent <= 1:
            continue

        trade_date = entry_ts.date()
        if daily_pnl_r.get(trade_date, 0.0) <= -max_daily_loss_r:
            continue

        if not _spread_ok(cfg, symbol):
            if ql_emitter:
                dcid = new_decision_cycle_id(prefix="dc_bb")
                eff = canonical_no_action_reason("spread_block")
                ql_emitter.emit(
                    event_type="trade_action",
                    trace_id=str(uuid4()),
                    timestamp_utc=_bar_timestamp_utc_iso(entry_ts),
                    account_id=account_id,
                    strategy_id=strategy_id,
                    symbol=symbol,
                    decision_cycle_id=dcid,
                    payload={"decision": "NO_ACTION", "reason": eff},
                )
            continue

        decision_cycle_id = new_decision_cycle_id(prefix="dc_bb")
        trade_ref = f"BT-{trace_id[:8]}"

        if ql_emitter:
            ql_emitter.emit(
                event_type="signal_detected",
                trace_id=trace_id,
                timestamp_utc=ts_iso,
                account_id=account_id,
                strategy_id=strategy_id,
                symbol=symbol,
                decision_cycle_id=decision_cycle_id,
                payload={
                    "signal_id": trade_ref,
                    "type": "bb_extension",
                    "direction": direction,
                    "strength": 1.0,
                    "bar_timestamp": ts_iso,
                    "session": session_from_timestamp(entry_ts, mode=session_mode),
                    "regime": sig["regime_at_signal"].lower(),
                    "component_type": sig["component_type"],
                    "bb_lower_break": sig["bb_lower_break"],
                    "bb_upper_break": sig["bb_upper_break"],
                    "bb_extension_normalized_atr": sig["bb_extension_normalized_atr"],
                    "regime_at_signal": sig["regime_at_signal"],
                    "session_at_signal": sig["session_at_signal"],
                    "signal_is_independent": True,
                },
            )
            ql_emitter.emit(
                event_type="trade_action",
                trace_id=trace_id,
                timestamp_utc=ts_iso,
                account_id=account_id,
                strategy_id=strategy_id,
                symbol=symbol,
                order_ref=trade_ref,
                decision_cycle_id=decision_cycle_id,
                payload={
                    "decision": "ENTER",
                    "reason": "bb_extension_entry",
                    "trade_id": trade_ref,
                    "side": "BUY" if direction == "LONG" else "SELL",
                },
            )

        result = simulate_bb_midline_trade(
            data,
            i,
            direction,
            mid=sim_cache["mid"],
            atr_arr=sim_cache["atr"],
            sl_atr_mult=sl_atr_mult,
            time_exit_bars=time_exit_bars,
            _cache=sim_cache,
        )

        open_until_bar = int(result["exit_bar_idx"])

        if ql_emitter:
            ql_emitter.emit(
                event_type="trade_closed",
                trace_id=trace_id,
                timestamp_utc=_bar_timestamp_utc_iso(result["exit_ts"]),
                account_id=account_id,
                strategy_id=strategy_id,
                symbol=symbol,
                order_ref=trade_ref,
                decision_cycle_id=decision_cycle_id,
                payload=build_trade_closed_research_payload(
                    trade_id=trade_ref,
                    exit_price=float(result["exit_price"]),
                    pnl_r=float(result["profit_r"]),
                    exit_reason=str(result["exit_reason"]),
                    bars_held=int(result["bars_held"]),
                    hit_midline_before_sl=bool(result["hit_midline_before_sl"]),
                    bars_to_midline=result.get("bars_to_midline"),
                    mfe_r=float(result["mfe_r"]),
                    mae_r=float(result["mae_r"]),
                    direction=direction,
                    outcome=str(result["result"]),
                ),
            )

        tr_res = str(result["result"]).upper()
        trade_result = getattr(TradeResult, tr_res, TradeResult.TIMEOUT)
        trades.append(
            Trade(
                timestamp_open=entry_ts,
                timestamp_close=result["exit_ts"],
                symbol=symbol,
                direction=TradeDirection.LONG if direction == "LONG" else TradeDirection.SHORT,
                entry_price=float(result["entry_price"]),
                exit_price=float(result["exit_price"]),
                sl=float(result["sl"]),
                tp=float(result["tp"]),
                profit_usd=float(result["profit_usd"]),
                profit_r=float(result["profit_r"]),
                result=trade_result,
                regime=sig["regime_at_signal"],
                session=sig["session_at_signal"],
            )
        )
        trade_order_refs.append(trade_ref)
        daily_pnl_r[trade_date] = daily_pnl_r.get(trade_date, 0.0) + float(result["profit_r"])

    logger.info("BB-only backtest %s: %d trades", symbol, len(trades))
    maybe_write_trade_r_series_fallback(cfg, trades, trade_order_refs)

    try:
        from src.quantbuild.integration.quantanalytics_post_run import invoke_quantanalytics_after_quantlog
        from src.quantbuild.integration.quantos_artifacts import invoke_collect_run_artifacts
        from src.quantbuild.integration.quantresearch_runs import invoke_quantresearch_run_bundle

        metrics_out = None
        if trades:
            from src.quantbuild.backtest.metrics import compute_metrics

            metrics_out = dict(compute_metrics(trades))
        invoke_quantanalytics_after_quantlog(cfg, ql_emitter)
        invoke_collect_run_artifacts(cfg, ql_emitter)
        invoke_quantresearch_run_bundle(cfg, ql_emitter, metrics_out)
    except Exception:
        logger.debug("Post-run hooks skipped", exc_info=True)

    return trades
