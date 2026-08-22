"""
EXP-003 / HYP-003 — London/NY overlap H1 range breakout (continuation).

Range: first same-day H1 bar with open time >= session_open_utc (default 13:30).
Signal: next same-day H1 close strictly outside range; entry: open of following same-day H1.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import pandas as pd

from src.quantbuild.backtest.engine import (
    _bar_timestamp_utc_iso,
    _exit_tag_from_simulator,
    _init_backtest_quantlog,
    _prepare_sim_cache,
    _simulate_trade_price_levels,
)
from src.quantbuild.export.trade_r_series import assert_quantlog_inference_policy, maybe_write_trade_r_series_fallback
from src.quantbuild.models.trade import Trade, TradeDirection, TradeResult
from src.quantbuild.data.sessions import session_from_timestamp
from src.quantbuild.execution.signal_evaluated_payload import new_decision_cycle_id

logger = logging.getLogger(__name__)

HYPOTHESIS_ID = "HYP-003"
STRATEGY_ID = "london_ny_overlap_breakout"


def _session_open_time(cfg: Dict[str, Any]) -> time:
    raw = (cfg.get("session_open_utc") or (cfg.get("backtest") or {}).get("session_open_utc") or "13:30")
    parts = str(raw).strip().split(":")
    h, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
    return time(h, m, 0)


def _exp003_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    return cfg.get("exp003") or {}


def _major_news_blocks_day(cfg: Dict[str, Any], d: date) -> bool:
    if not bool(cfg.get("major_news_filter", False)):
        return False
    ex = _exp003_cfg(cfg)
    blocked = ex.get("blocked_dates_utc") or ex.get("major_news_dates") or []
    ds = d.isoformat()
    for b in blocked:
        if str(b).strip()[:10] == ds:
            return True
    return False


def _utc_date(ts: Any) -> date:
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    else:
        t = t.tz_convert("UTC")
    return t.date()


def _bar_time_utc(ts: Any) -> time:
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    else:
        t = t.tz_convert("UTC")
    return t.time()


def _find_range_signal_entry(
    df: pd.DataFrame,
    day: date,
    session_open: time,
) -> Tuple[Optional[int], Optional[int], Optional[int], Optional[str]]:
    """
    Return (range_i, signal_i, entry_i) global indices or (None, None, None, reason).
    All three bars must be on the same UTC calendar day and consecutive in that day's bar list.
    """
    idxs = [i for i, ts in enumerate(df.index) if _utc_date(ts) == day]
    if not idxs:
        return None, None, None, "no_bars"
    range_i: Optional[int] = None
    for i in idxs:
        if _bar_time_utc(df.index[i]) >= session_open:
            range_i = i
            break
    if range_i is None:
        return None, None, None, "no_range_candle"
    pos = idxs.index(range_i)
    if pos + 1 >= len(idxs):
        return range_i, None, None, "no_signal_candle"
    signal_i = idxs[pos + 1]
    if pos + 2 >= len(idxs):
        return range_i, signal_i, None, "no_entry_candle"
    entry_i = idxs[pos + 2]
    return range_i, signal_i, entry_i, None


def _classify_signal(
    close: float,
    range_high: float,
    range_low: float,
) -> Optional[str]:
    if close > range_high:
        return "LONG"
    if close < range_low:
        return "SHORT"
    return None  # ambiguous / inside range


def run_london_ny_overlap_breakout_backtest(
    cfg: Dict[str, Any],
    data: pd.DataFrame,
    start: datetime,
    end: datetime,
    base_path: Path,
    symbol: str,
    tf: str,
    regime_series: Optional[pd.Series] = None,
) -> List[Trade]:
    _ = start, end, base_path, tf, regime_series  # reserved / API parity with other engines
    df = data.sort_index()
    if df.empty:
        return []

    session_open = _session_open_time(cfg)
    broker = cfg.get("broker") or {}
    spread = float(broker.get("mock_spread") or cfg.get("mock_spread") or 0.0)
    tp_mult = float(cfg.get("tp_multiplier") or (cfg.get("backtest") or {}).get("tp_multiplier") or 1.5)
    bt_mode = (cfg.get("backtest") or {}).get("session_mode", "extended")

    account_id = str(broker.get("account_id") or "backtest")
    ql_emitter = _init_backtest_quantlog(cfg)
    try:
        assert_quantlog_inference_policy(cfg)
    except ValueError:
        if bool((cfg.get("quantlog") or {}).get("enabled", True)):
            raise

    sim_cache = _prepare_sim_cache(df)
    unique_days = sorted({_utc_date(ts) for ts in df.index})
    trades: List[Trade] = []
    trade_order_refs: List[str] = []

    for d in unique_days:
        if _major_news_blocks_day(cfg, d):
            if ql_emitter is not None:
                _emit_skip(ql_emitter, account_id, symbol, d, "major_news_day", cfg)
            continue

        range_i, signal_i, entry_i, err = _find_range_signal_entry(df, d, session_open)
        date_str = d.isoformat()
        range_id = f"{symbol}_{date_str}"

        if err == "no_range_candle" or err == "no_bars":
            if ql_emitter is not None:
                _emit_skip(ql_emitter, account_id, symbol, d, "no_range_candle", cfg)
            continue

        rh = float(df.iloc[range_i]["high"])
        rl = float(df.iloc[range_i]["low"])
        rsize = rh - rl
        range_ts = df.index[range_i]

        if ql_emitter is not None:
            ql_emitter.emit(
                event_type="range_detected",
                trace_id=str(uuid4()),
                timestamp_utc=_bar_timestamp_utc_iso(range_ts),
                account_id=account_id,
                strategy_id=STRATEGY_ID,
                symbol=symbol,
                payload={
                    "range_id": range_id,
                    "range_candle_open_utc": _bar_timestamp_utc_iso(range_ts),
                    "range_high": rh,
                    "range_low": rl,
                    "range_size": float(rsize),
                    "symbol": symbol,
                    "session": "london_ny_overlap",
                    "hypothesis": HYPOTHESIS_ID,
                },
            )

        if err == "no_signal_candle":
            if ql_emitter is not None:
                _emit_skip(ql_emitter, account_id, symbol, d, "no_signal_candle", cfg)
            continue

        sig_close = float(df.iloc[signal_i]["close"])
        direction = _classify_signal(sig_close, rh, rl)
        signal_ts = df.index[signal_i]

        if ql_emitter is not None:
            ql_emitter.emit(
                event_type="breakout_signal",
                trace_id=str(uuid4()),
                timestamp_utc=_bar_timestamp_utc_iso(signal_ts),
                account_id=account_id,
                strategy_id=STRATEGY_ID,
                symbol=symbol,
                payload={
                    "range_id": range_id,
                    "direction": "long" if direction == "LONG" else ("short" if direction == "SHORT" else "none"),
                    "signal_close": sig_close,
                    "signal_candle_utc": _bar_timestamp_utc_iso(signal_ts),
                    "bars_since_range": 1,
                    "hypothesis": HYPOTHESIS_ID,
                },
            )

        if direction is None:
            if ql_emitter is not None:
                _emit_skip(ql_emitter, account_id, symbol, d, "ambiguous", cfg)
            continue

        if err == "no_entry_candle":
            if ql_emitter is not None:
                _emit_skip(ql_emitter, account_id, symbol, d, "no_entry_candle", cfg)
            continue

        entry_open = float(df.iloc[entry_i]["open"])
        entry_ts = df.index[entry_i]

        if direction == "LONG":
            entry_price = entry_open + spread
            sl_price = rl - spread
            tp_price = entry_price + tp_mult * rsize
            sim_dir = "LONG"
        else:
            entry_price = entry_open - spread
            sl_price = rh + spread
            tp_price = entry_price - tp_mult * rsize
            sim_dir = "SHORT"

        trace_id = str(uuid4())
        decision_cycle_id = new_decision_cycle_id(prefix="bt")
        trade_ref = f"BT-{trace_id[:8]}"

        if ql_emitter is not None:
            ts_iso = _bar_timestamp_utc_iso(entry_ts)
            ql_emitter.emit(
                event_type="trade_action",
                trace_id=trace_id,
                timestamp_utc=ts_iso,
                account_id=account_id,
                strategy_id=STRATEGY_ID,
                symbol=symbol,
                order_ref=trade_ref,
                decision_cycle_id=decision_cycle_id,
                payload={
                    "trade_action": "ENTER",
                    "decision": "ENTER",
                    "reason": STRATEGY_ID,
                    "side": sim_dir,
                    "range_id": range_id,
                    "hypothesis": HYPOTHESIS_ID,
                },
            )

        # Entry is the open of entry_i; remaining high/low of that H1 must be simulated.
        result = _simulate_trade_price_levels(
            df,
            entry_i,
            sim_dir,
            entry_price,
            sl_price,
            tp_price,
            _cache=sim_cache,
            include_entry_bar=True,
        )

        mfe_peak_iso = (
            _bar_timestamp_utc_iso(result["mfe_peak_ts"])
            if result.get("mfe_peak_ts") is not None
            else None
        )
        tex_dir = sim_dir
        regime_str = "none"
        try:
            regime_str = str(df.iloc[entry_i].get("regime", "none"))
        except Exception:
            pass
        current_session = session_from_timestamp(entry_ts, mode=bt_mode)

        exit_ts_iso = _bar_timestamp_utc_iso(result["exit_ts"])
        if ql_emitter is not None:
            ql_emitter.emit(
                event_type="trade_closed",
                trace_id=trace_id,
                timestamp_utc=exit_ts_iso,
                account_id=account_id,
                strategy_id=STRATEGY_ID,
                symbol=symbol,
                order_ref=trade_ref,
                decision_cycle_id=decision_cycle_id,
                payload={
                    "trade_id": trade_ref,
                    "order_ref": trade_ref,
                    "direction": tex_dir,
                    "range_id": range_id,
                    "symbol": symbol,
                    "entry_price": float(result["entry_price"]),
                    "exit_price": float(result["exit_price"]),
                    "pnl_abs": float(result["profit_usd"]),
                    "pnl_r": float(result["profit_r"]),
                    "mae_r": float(result["mae_r"]),
                    "mfe_r": float(result["mfe_r"]),
                    "mfe_peak_timestamp_utc": mfe_peak_iso,
                    "bars_to_mfe": result.get("bars_to_mfe"),
                    "range_size": float(rsize),
                    "tp_multiplier": float(tp_mult),
                    "mock_spread": float(spread),
                    "outcome": result["result"],
                    "exit": _exit_tag_from_simulator(result["result"]),
                    "session": current_session,
                    "regime": regime_str,
                    "decision_cycle_id": decision_cycle_id,
                    "hypothesis": HYPOTHESIS_ID,
                },
            )

        tr_res = str(result["result"]).upper()
        trade_result = getattr(TradeResult, tr_res, TradeResult.TIMEOUT)

        t = Trade(
            timestamp_open=entry_ts,
            timestamp_close=result["exit_ts"],
            symbol=symbol,
            direction=TradeDirection.LONG if tex_dir == "LONG" else TradeDirection.SHORT,
            entry_price=float(result["entry_price"]),
            exit_price=float(result["exit_price"]),
            sl=float(result["sl"]),
            tp=float(result["tp"]),
            profit_usd=float(result["profit_usd"]),
            profit_r=float(result["profit_r"]),
            result=trade_result,
            regime=regime_str,
            session=current_session,
        )
        trades.append(t)
        trade_order_refs.append(trade_ref)

    logger.info("%s %s HYP-003: %d trades", symbol, tf, len(trades))

    metrics_out: Optional[Dict[str, Any]] = None
    if trades:
        from src.quantbuild.backtest.metrics import compute_metrics

        metrics_out = dict(compute_metrics(trades))

    maybe_write_trade_r_series_fallback(cfg, trades, trade_order_refs)

    try:
        from src.quantbuild.integration.quantanalytics_post_run import invoke_quantanalytics_after_quantlog
        from src.quantbuild.integration.quantos_artifacts import invoke_collect_run_artifacts
        from src.quantbuild.integration.quantresearch_runs import invoke_quantresearch_run_bundle

        invoke_quantanalytics_after_quantlog(cfg, ql_emitter)
        invoke_collect_run_artifacts(cfg, ql_emitter)
        invoke_quantresearch_run_bundle(cfg, ql_emitter, metrics_out)
    except Exception:
        logger.debug("QuantAnalytics post-run skipped", exc_info=True)

    return trades


def _emit_skip(
    ql_emitter: Any,
    account_id: str,
    symbol: str,
    d: date,
    reason: str,
    cfg: Dict[str, Any],
) -> None:
    ts = pd.Timestamp(datetime(d.year, d.month, d.day, 13, 30, tzinfo=timezone.utc))
    hyp = cfg.get("experiment_id") or (cfg.get("artifacts") or {}).get("experiment_id") or ""
    dcid = new_decision_cycle_id(prefix="lnob_skip")
    ql_emitter.emit(
        event_type="trade_action",
        trace_id=str(uuid4()),
        timestamp_utc=_bar_timestamp_utc_iso(ts),
        account_id=account_id,
        strategy_id=STRATEGY_ID,
        symbol=symbol,
        decision_cycle_id=dcid,
        payload={
            "trade_action": "NO_ACTION",
            "decision": "NO_ACTION",
            "reason": reason,
            "range_id": f"{symbol}_{d.isoformat()}",
            "hypothesis": HYPOTHESIS_ID,
            "experiment_id": hyp,
        },
    )
