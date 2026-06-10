"""Backtest engine for MACD-cross-only strategy (EXP-MACD-MECH-001)."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

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
from src.quantbuild.strategies.bb_only import regime_at_signal_label, session_at_signal_label
from src.quantbuild.strategies.bb_only_engine import _pip_size, _spread_ok
from src.quantbuild.strategies.macd_only import (
    STRATEGY_ID,
    collect_macd_entry_signals,
    compute_macd_frame,
    detect_macd_component_observations,
    macd_only_strategy_cfg,
    simulate_macd_time_exit_trade,
)

logger = logging.getLogger(__name__)


def run_macd_only_backtest(
    cfg: Dict[str, Any],
    data: pd.DataFrame,
    *,
    symbol: str,
    session_mode: str = "extended",
    regime_series: Optional[pd.Series] = None,
) -> List[Trade]:
    strat_cfg = macd_only_strategy_cfg(cfg)
    exit_cfg = strat_cfg.get("exit") or {}
    risk_cfg = strat_cfg.get("risk") or {}
    sl_atr_mult = float(risk_cfg.get("sl_atr_mult", 2.0))
    time_exit_bars = int(exit_cfg.get("time_exit_bars", 8))
    max_concurrent = int(risk_cfg.get("max_concurrent", 1))
    max_daily_loss_r = float(risk_cfg.get("max_daily_loss_r", 2.0))

    macd_frame = compute_macd_frame(data, strat_cfg.get("macd") or {})
    bull_raw, bear_raw = detect_macd_component_observations(macd_frame)
    sim_cache = _prepare_sim_cache(data)

    ql_emitter = _init_backtest_quantlog(cfg)
    assert_quantlog_inference_policy(cfg)
    account_id = str(cfg.get("broker", {}).get("account_id") or "backtest")
    strategy_id = str(cfg.get("experiment_id") or STRATEGY_ID)

    if ql_emitter:
        for i in range(len(data)):
            ts = data.index[i]
            ts_iso = _bar_timestamp_utc_iso(ts)
            regime_lbl = regime_at_signal_label(
                regime_series.iloc[i] if regime_series is not None and i < len(regime_series) else None
            )
            sess_lbl = session_at_signal_label(ts, session_mode)
            if bull_raw.iloc[i]:
                ql_emitter.emit(
                    event_type="component_observed",
                    trace_id=str(uuid4()),
                    timestamp_utc=ts_iso,
                    account_id=account_id,
                    strategy_id=strategy_id,
                    symbol=symbol,
                    payload=build_component_observed_payload(
                        component_type="MACD_BULL_CROSS",
                        bar_timestamp=ts_iso,
                        session_at_signal=sess_lbl,
                        regime_at_signal=regime_lbl,
                        macd_cross_bull=True,
                        macd_cross_velocity=float(macd_frame["histogram"].iloc[i]),
                    ),
                )
            if bear_raw.iloc[i]:
                ql_emitter.emit(
                    event_type="component_observed",
                    trace_id=str(uuid4()),
                    timestamp_utc=ts_iso,
                    account_id=account_id,
                    strategy_id=strategy_id,
                    symbol=symbol,
                    payload=build_component_observed_payload(
                        component_type="MACD_BEAR_CROSS",
                        bar_timestamp=ts_iso,
                        session_at_signal=sess_lbl,
                        regime_at_signal=regime_lbl,
                        macd_cross_bear=True,
                        macd_cross_velocity=float(macd_frame["histogram"].iloc[i]),
                    ),
                )

    entry_signals = collect_macd_entry_signals(
        data, strat_cfg, session_mode=session_mode, regime_series=regime_series
    )
    raw_count = int(bull_raw.sum() + bear_raw.sum())
    logger.info(
        "MACD-only raw crosses: %d | independent entry signals: %d",
        raw_count,
        len(entry_signals),
    )

    trades: List[Trade] = []
    trade_order_refs: List[str] = []
    daily_pnl_r: Dict[Any, float] = {}
    open_until_bar = -1

    for sig in entry_signals:
        i = int(sig["bar_index"])
        if i <= open_until_bar and max_concurrent <= 1:
            continue

        entry_ts = data.index[i]
        trade_date = entry_ts.date()
        if daily_pnl_r.get(trade_date, 0.0) <= -max_daily_loss_r:
            continue

        if not _spread_ok(cfg, symbol):
            if ql_emitter:
                dcid = new_decision_cycle_id(prefix="dc_macd")
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

        direction = sig["direction"]
        ts_iso = _bar_timestamp_utc_iso(entry_ts)
        trace_id = str(uuid4())
        decision_cycle_id = new_decision_cycle_id(prefix="dc_macd")
        trade_ref = f"BT-{trace_id[:8]}"

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
                    macd_cross_bull=sig["macd_cross_bull"],
                    macd_cross_bear=sig["macd_cross_bear"],
                    macd_cross_velocity=sig["macd_cross_velocity"],
                ),
            )
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
                    "type": "macd_cross",
                    "direction": direction,
                    "strength": 1.0,
                    "bar_timestamp": ts_iso,
                    "session": session_from_timestamp(entry_ts, mode=session_mode),
                    "regime": sig["regime_at_signal"].lower(),
                    "component_type": sig["component_type"],
                    "macd_cross_bull": sig["macd_cross_bull"],
                    "macd_cross_bear": sig["macd_cross_bear"],
                    "macd_cross_velocity": sig["macd_cross_velocity"],
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
                    "reason": "macd_cross_entry",
                    "trade_id": trade_ref,
                    "side": "BUY" if direction == "LONG" else "SELL",
                },
            )

        result = simulate_macd_time_exit_trade(
            data,
            i,
            direction,
            atr_arr=sim_cache["atr"],
            sl_atr_mult=sl_atr_mult,
            time_exit_bars=time_exit_bars,
            _cache=sim_cache,
        )

        open_until_bar = int(result["exit_bar_idx"])

        if ql_emitter:
            extra: Dict[str, Any] = {}
            if result.get("bars_to_half_r_mae") is not None:
                extra["bars_to_half_r_mae"] = result["bars_to_half_r_mae"]
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
                    mfe_r=float(result["mfe_r"]),
                    mae_r=float(result["mae_r"]),
                    direction=direction,
                    outcome=str(result["result"]),
                    regime=sig["regime_at_signal"].lower(),
                    regime_at_signal=sig["regime_at_signal"],
                    session=sig["session_at_signal"].lower(),
                    session_at_signal=sig["session_at_signal"],
                    **extra,
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

    logger.info("MACD-only backtest %s: %d trades", symbol, len(trades))
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
