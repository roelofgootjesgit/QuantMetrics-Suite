"""Bollinger Band extension-only strategy logic (EXP-BB-MECH-001)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.quantbuild.indicators.atr import atr as compute_atr
from src.quantbuild.indicators.bollinger import bollinger_bands
from src.quantbuild.utils.signal_independence import signal_independence_mask


STRATEGY_ID = "bb_only"


def bb_only_strategy_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Merge top-level exit/risk/guards with ``strategy`` block (YAML plan layout)."""
    strat = dict(cfg.get("strategy") or {})
    if cfg.get("exit"):
        strat.setdefault("exit", dict(cfg["exit"]))
    if cfg.get("risk"):
        strat.setdefault("risk", dict(cfg["risk"]))
    if cfg.get("guards"):
        strat.setdefault("guards", dict(cfg["guards"]))
    return strat


def session_at_signal_label(ts: Any, session_mode: str = "extended") -> str:
    from src.quantbuild.data.sessions import (
        SESSION_LONDON,
        SESSION_NY,
        SESSION_OVERLAP,
        session_from_timestamp,
    )

    s = session_from_timestamp(ts, mode=session_mode)
    if s == SESSION_LONDON:
        return "LONDON"
    if s == SESSION_NY:
        return "NEW_YORK"
    if s == SESSION_OVERLAP:
        return "OVERLAP"
    return "OFF_HOURS"


def regime_at_signal_label(regime: Any) -> str:
    if regime is None or (isinstance(regime, float) and not np.isfinite(regime)):
        return "UNKNOWN"
    r = str(regime).strip().upper()
    if r in {"TREND", "EXPANSION", "COMPRESSION", "UNKNOWN"}:
        return r
    if "TREND" in r:
        return "TREND"
    if "EXPANS" in r:
        return "EXPANSION"
    if "COMPRESS" in r:
        return "COMPRESSION"
    return "UNKNOWN"


def bb_extension_normalized_atr(
    close: float,
    band: float,
    atr_val: float,
    direction: str,
) -> float:
    if atr_val <= 0 or not np.isfinite(atr_val):
        return 0.0
    if direction == "LONG":
        return max(0.0, (band - close) / atr_val)
    return max(0.0, (close - band) / atr_val)


def compute_bb_bands(data: pd.DataFrame, bollinger_cfg: Dict[str, Any]) -> pd.DataFrame:
    length = int(bollinger_cfg.get("length", 20))
    stddev = float(bollinger_cfg.get("stddev", 2.0))
    return bollinger_bands(data["close"], length=length, stddev=stddev)


def detect_bb_component_observations(
    data: pd.DataFrame,
    bands: pd.DataFrame,
) -> Tuple[pd.Series, pd.Series]:
    """Raw BB extension hits (before independence filter)."""
    close = data["close"]
    long_obs = close < bands["lower"]
    short_obs = close > bands["upper"]
    valid = bands["mid"].notna()
    return (long_obs & valid).fillna(False), (short_obs & valid).fillna(False)


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


def collect_bb_entry_signals(
    data: pd.DataFrame,
    strat_cfg: Dict[str, Any],
    session_mode: str = "extended",
    regime_series: Optional[pd.Series] = None,
) -> List[Dict[str, Any]]:
    """Build independent BB entry candidates with research metadata per bar."""
    bollinger_cfg = strat_cfg.get("bollinger") or {}
    indep_cfg = strat_cfg.get("signal_independence") or {}
    atr_series = compute_atr(data, period=14)
    bands = compute_bb_bands(data, bollinger_cfg)
    long_raw, short_raw = detect_bb_component_observations(data, bands)
    independent_any = apply_independence_to_signals(long_raw | short_raw, data, atr_series, indep_cfg)
    long_ind = long_raw & independent_any
    short_ind = short_raw & independent_any

    entries: List[Dict[str, Any]] = []
    for i in range(len(data)):
        if not long_ind.iloc[i] and not short_ind.iloc[i]:
            continue
        direction = "LONG" if long_ind.iloc[i] else "SHORT"
        component_type = "BB_LOWER_BREAK" if direction == "LONG" else "BB_UPPER_BREAK"
        ts = data.index[i]
        regime_val = None
        if regime_series is not None and i < len(regime_series):
            regime_val = regime_series.iloc[i]
        atr_v = float(atr_series.iloc[i]) if pd.notna(atr_series.iloc[i]) else 0.0
        close_v = float(data["close"].iloc[i])
        band_v = float(bands["lower"].iloc[i] if direction == "LONG" else bands["upper"].iloc[i])
        ext_atr = bb_extension_normalized_atr(close_v, band_v, atr_v, direction)
        entries.append(
            {
                "bar_index": i,
                "direction": direction,
                "component_type": component_type,
                "bar_timestamp": ts,
                "session_at_signal": session_at_signal_label(ts, session_mode),
                "regime_at_signal": regime_at_signal_label(regime_val),
                "bb_lower_break": direction == "LONG",
                "bb_upper_break": direction == "SHORT",
                "bb_extension_normalized_atr": ext_atr,
                "bands_mid": float(bands["mid"].iloc[i]),
            }
        )
    return entries


def simulate_bb_midline_trade(
    data: pd.DataFrame,
    entry_i: int,
    direction: str,
    *,
    mid: np.ndarray,
    atr_arr: np.ndarray,
    sl_atr_mult: float = 2.0,
    time_exit_bars: int = 32,
    _cache: Optional[dict] = None,
) -> dict:
    """Simulate exit at BB midline, ATR stop, or time stop."""
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

    exit_price = entry_price
    exit_ts = ts_arr[entry_i]
    exit_bar_idx = entry_i
    result = "TIMEOUT"
    exit_reason = "time_exit"
    bars_to_midline: Optional[int] = None
    hit_midline_before_sl = False
    max_favorable = 0.0
    max_adverse = 0.0

    end_j = min(entry_i + int(time_exit_bars), n - 1)
    for j in range(entry_i + 1, end_j + 1):
        lo, hi = float(low_arr[j]), float(high_arr[j])
        mid_v = float(mid[j])

        if direction == "LONG":
            favorable = hi - entry_price
            adverse = entry_price - lo
            sl_hit = lo <= sl
            mid_hit = np.isfinite(mid_v) and close_arr[j] >= mid_v
        else:
            favorable = entry_price - lo
            adverse = hi - entry_price
            sl_hit = hi >= sl
            mid_hit = np.isfinite(mid_v) and close_arr[j] <= mid_v

        max_favorable = max(max_favorable, favorable)
        max_adverse = max(max_adverse, adverse)

        if sl_hit:
            exit_price, exit_ts, exit_bar_idx = sl, ts_arr[j], j
            result, exit_reason = "LOSS", "sl"
            break
        if mid_hit:
            exit_price, exit_ts, exit_bar_idx = mid_v, ts_arr[j], j
            result, exit_reason = "WIN", "midline"
            bars_to_midline = j - entry_i
            hit_midline_before_sl = True
            break

        if j == end_j:
            exit_price, exit_ts, exit_bar_idx = float(close_arr[j]), ts_arr[j], j
            result, exit_reason = "TIMEOUT", "time_exit"

    risk = abs(entry_price - sl)
    mae_r = (max_adverse / risk) if risk else 0.0
    mfe_r = (max_favorable / risk) if risk else 0.0
    profit_usd = (exit_price - entry_price) if direction == "LONG" else (entry_price - exit_price)
    profit_r = calculate_rr(entry_price, exit_price, sl, direction)
    bars_held = exit_bar_idx - entry_i

    return {
        "entry_price": entry_price,
        "exit_price": exit_price,
        "sl": sl,
        "tp": float(mid[entry_i]) if np.isfinite(mid[entry_i]) else entry_price,
        "exit_ts": exit_ts,
        "exit_bar_idx": exit_bar_idx,
        "profit_usd": profit_usd,
        "profit_r": profit_r,
        "result": result,
        "exit_reason": exit_reason,
        "bars_held": bars_held,
        "bars_to_midline": bars_to_midline,
        "hit_midline_before_sl": hit_midline_before_sl,
        "mae_r": mae_r,
        "mfe_r": mfe_r,
        "atr": atr_v,
    }
