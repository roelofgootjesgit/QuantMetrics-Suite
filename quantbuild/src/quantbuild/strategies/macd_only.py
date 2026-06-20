"""MACD cross-only strategy logic (EXP-MACD-MECH-001)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.quantbuild.indicators.atr import atr as compute_atr
from src.quantbuild.indicators.macd import macd as compute_macd
from src.quantbuild.strategies.bb_only import regime_at_signal_label, session_at_signal_label
from src.quantbuild.utils.signal_independence import signal_independence_mask


STRATEGY_ID = "macd_only"


def macd_only_strategy_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    strat = dict(cfg.get("strategy") or {})
    if cfg.get("exit"):
        strat.setdefault("exit", dict(cfg["exit"]))
    if cfg.get("risk"):
        strat.setdefault("risk", dict(cfg["risk"]))
    if cfg.get("guards"):
        strat.setdefault("guards", dict(cfg["guards"]))
    return strat


def compute_macd_frame(data: pd.DataFrame, macd_cfg: Dict[str, Any]) -> pd.DataFrame:
    return compute_macd(
        data["close"],
        fast=int(macd_cfg.get("fast", 12)),
        slow=int(macd_cfg.get("slow", 26)),
        signal=int(macd_cfg.get("signal", 9)),
    )


def macd_cross_velocity(macd_frame: pd.DataFrame, i: int) -> float:
    """Signed histogram change on cross bar (momentum into the cross)."""
    if i < 1:
        return 0.0
    h0 = float(macd_frame["histogram"].iloc[i])
    h1 = float(macd_frame["histogram"].iloc[i - 1])
    if not np.isfinite(h0) or not np.isfinite(h1):
        return 0.0
    return h0 - h1


def detect_macd_component_observations(
    macd_frame: pd.DataFrame,
) -> Tuple[pd.Series, pd.Series]:
    bull = macd_frame["bullish_cross"].fillna(False).astype(bool)
    bear = macd_frame["bearish_cross"].fillna(False).astype(bool)
    return bull, bear


def apply_independence_to_signals(
    signal: pd.Series,
    data: pd.DataFrame,
    atr_series: pd.Series,
    independence_cfg: Dict[str, Any],
) -> pd.Series:
    return signal_independence_mask(
        signal,
        data["close"],
        atr_series,
        min_bars_gap=int(independence_cfg.get("min_bars_gap", 4)),
        min_atr_distance=float(independence_cfg.get("min_atr_distance", 1.5)),
    )


def collect_macd_entry_signals(
    data: pd.DataFrame,
    strat_cfg: Dict[str, Any],
    session_mode: str = "extended",
    regime_series: Optional[pd.Series] = None,
) -> List[Dict[str, Any]]:
    macd_cfg = strat_cfg.get("macd") or {}
    indep_cfg = strat_cfg.get("signal_independence") or {}
    macd_frame = compute_macd_frame(data, macd_cfg)
    atr_series = compute_atr(data, period=14)

    bull_raw, bear_raw = detect_macd_component_observations(macd_frame)
    independent_any = apply_independence_to_signals(bull_raw | bear_raw, data, atr_series, indep_cfg)
    bull_ind = bull_raw & independent_any
    bear_ind = bear_raw & independent_any

    entries: List[Dict[str, Any]] = []
    for i in range(len(data)):
        if not bull_ind.iloc[i] and not bear_ind.iloc[i]:
            continue
        direction = "LONG" if bull_ind.iloc[i] else "SHORT"
        component_type = "MACD_BULL_CROSS" if direction == "LONG" else "MACD_BEAR_CROSS"
        ts = data.index[i]
        regime_val = (
            regime_series.iloc[i] if regime_series is not None and i < len(regime_series) else None
        )
        velocity = macd_cross_velocity(macd_frame, i)
        entries.append(
            {
                "bar_index": i,
                "direction": direction,
                "component_type": component_type,
                "bar_timestamp": ts,
                "session_at_signal": session_at_signal_label(ts, session_mode),
                "regime_at_signal": regime_at_signal_label(regime_val),
                "macd_cross_bull": direction == "LONG",
                "macd_cross_bear": direction == "SHORT",
                "macd_cross_velocity": velocity,
            }
        )
    return entries


def simulate_macd_time_exit_trade(
    data: pd.DataFrame,
    entry_i: int,
    direction: str,
    *,
    atr_arr: np.ndarray,
    sl_atr_mult: float = 2.0,
    time_exit_bars: int = 8,
    _cache: Optional[dict] = None,
) -> dict:
    """Time-based exit at ``time_exit_bars``; SL checked intrabar before horizon."""
    from src.quantbuild.models.trade import calculate_rr

    if _cache is not None:
        close_arr, high_arr, low_arr, ts_arr = (
            _cache["close"],
            _cache["high"],
            _cache["low"],
            _cache["ts"],
        )
    else:
        close_arr = data["close"].values.astype(np.float64)
        high_arr = data["high"].values.astype(np.float64)
        low_arr = data["low"].values.astype(np.float64)
        ts_arr = data.index

    n = len(close_arr)
    entry_price = float(close_arr[entry_i])
    atr_v = float(atr_arr[entry_i])
    if not np.isfinite(atr_v) or atr_v <= 0:
        atr_v = entry_price * 0.001

    if direction == "LONG":
        sl = entry_price - sl_atr_mult * atr_v
    else:
        sl = entry_price + sl_atr_mult * atr_v

    risk = abs(entry_price - sl)
    exit_price = entry_price
    exit_ts = ts_arr[entry_i]
    exit_bar_idx = entry_i
    result = "TIMEOUT"
    exit_reason = "time_exit"
    max_favorable = 0.0
    max_adverse = 0.0
    bars_to_half_r_mae: Optional[int] = None

    end_j = min(entry_i + int(time_exit_bars), n - 1)
    for j in range(entry_i + 1, end_j + 1):
        lo, hi = float(low_arr[j]), float(high_arr[j])
        if direction == "LONG":
            favorable = hi - entry_price
            adverse = entry_price - lo
            sl_hit = lo <= sl
        else:
            favorable = entry_price - lo
            adverse = hi - entry_price
            sl_hit = hi >= sl

        max_favorable = max(max_favorable, favorable)
        max_adverse = max(max_adverse, adverse)
        if bars_to_half_r_mae is None and risk > 0 and adverse >= 0.5 * risk:
            bars_to_half_r_mae = j - entry_i

        if sl_hit:
            exit_price, exit_ts, exit_bar_idx = sl, ts_arr[j], j
            result, exit_reason = "LOSS", "sl"
            break
        if j == end_j:
            exit_price, exit_ts, exit_bar_idx = float(close_arr[j]), ts_arr[j], j
            result = "WIN" if (
                (direction == "LONG" and exit_price > entry_price)
                or (direction == "SHORT" and exit_price < entry_price)
            ) else ("LOSS" if exit_price != entry_price else "TIMEOUT")
            if result == "TIMEOUT":
                result = "TIMEOUT"
            exit_reason = "time_exit"

    mae_r = (max_adverse / risk) if risk else 0.0
    mfe_r = (max_favorable / risk) if risk else 0.0
    profit_usd = (exit_price - entry_price) if direction == "LONG" else (entry_price - exit_price)
    profit_r = calculate_rr(entry_price, exit_price, sl, direction)
    if result not in ("WIN", "LOSS", "TIMEOUT"):
        if profit_r > 0:
            result = "WIN"
        elif profit_r < 0:
            result = "LOSS"
        else:
            result = "TIMEOUT"

    return {
        "entry_price": entry_price,
        "exit_price": exit_price,
        "sl": sl,
        "tp": entry_price,
        "exit_ts": exit_ts,
        "exit_bar_idx": exit_bar_idx,
        "profit_usd": profit_usd,
        "profit_r": profit_r,
        "result": result,
        "exit_reason": exit_reason,
        "bars_held": exit_bar_idx - entry_i,
        "bars_to_midline": None,
        "hit_midline_before_sl": False,
        "mae_r": mae_r,
        "mfe_r": mfe_r,
        "atr": atr_v,
        "bars_to_half_r_mae": bars_to_half_r_mae,
    }
