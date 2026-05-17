"""
M5 liquidity sweep detection for XAU/USD research (PDH/PDL, UTC sessions).

Rules implemented (aligned with sweep-reversal spec):
  - Sessions: London 07:00–10:00 UTC, NY 13:00–16:00 UTC (inclusive minute windows).
  - Levels: previous calendar day high (PDH) / low (PDL) from M5 history.
  - Penetration: price exceeds level by >= min_sweep_depth_atr * ATR(14) on M5.
  - Reclaim: first close back on the protected side within a window of
    ``max_reclaim_candles`` bars starting at the sweep bar (inclusive).
  - acceptance_failed: True iff reclaim exists and there were never 3 consecutive
    closes on the wrong side of the (per-bar) level before that reclaim.
  - displacement: first bullish/bearish impulse bar after reclaim with range >
    rolling median range (prior bars only); displacement_strength = range / median.
  - micro_structure_shift: displacement close breaks the prior 10-bar range extreme
    (causal, no lookahead).

news_nearby is not inferred here (defaults False in payload); wire a calendar in CLI later.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.quantbuild.indicators.atr import atr as compute_atr

STRATEGY_ID_DEFAULT = "xauusd_sweep_reversal_v1"


def _parse_hhmm(s: str) -> Tuple[int, int]:
    parts = str(s).strip().split(":")
    h = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    return h, m


def _minute_of_day_utc(ts: Any) -> int:
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    else:
        t = t.tz_convert("UTC")
    return int(t.hour * 60 + t.minute)


def in_session_bucket_utc(ts: Any) -> Optional[str]:
    """London / NY open windows from spec (UTC). Returns None if outside."""
    m = _minute_of_day_utc(ts)
    lo_l, hi_l = _parse_hhmm("07:00")[0] * 60 + _parse_hhmm("07:00")[1], _parse_hhmm("10:00")[0] * 60 + _parse_hhmm("10:00")[1]
    lo_n, hi_n = _parse_hhmm("13:00")[0] * 60 + _parse_hhmm("13:00")[1], _parse_hhmm("16:00")[0] * 60 + _parse_hhmm("16:00")[1]
    if lo_l <= m <= hi_l:
        return "london_open"
    if lo_n <= m <= hi_n:
        return "ny_open"
    return None


def align_prev_daily_high_low(df: pd.DataFrame) -> pd.DataFrame:
    """Add columns pdh, pdl = prior UTC calendar day high/low for each M5 row.

    Index is normalized to timezone-naive UTC wall time to match parquet caches
    and regime series alignment.
    """
    if df.empty:
        return df
    out = df.copy()
    idx = pd.DatetimeIndex(pd.to_datetime(out.index, utc=True))
    if idx.tz is not None:
        idx = idx.tz_convert("UTC").tz_localize(None)
    out.index = idx
    daily = (
        out.groupby(out.index.floor("D"))
        .agg(pdh_day=("high", "max"), pdl_day=("low", "min"))
        .sort_index()
    )
    shifted = daily.shift(1)
    day_keys = out.index.floor("D")
    out["pdh"] = day_keys.map(shifted["pdh_day"])
    out["pdl"] = day_keys.map(shifted["pdl_day"])
    return out


def rolling_median_range(df: pd.DataFrame, window: int = 50) -> pd.Series:
    rng = df["high"] - df["low"]
    return rng.rolling(window, min_periods=max(5, window // 10)).median().shift(1)


def _max_run_close_vs_level(
    d: pd.DataFrame,
    closes: np.ndarray,
    level_col: str,
    start: int,
    end: int,
    *,
    mode: str,
) -> int:
    """Longest run of closes below level (PDL) or above level (PDH). mode: 'below' | 'above'."""
    if end < start:
        return 0
    run = 0
    best = 0
    for k in range(start, end + 1):
        lv = float(d[level_col].iloc[k])
        ok = closes[k] < lv if mode == "below" else closes[k] > lv
        if ok:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best


def _find_displacement_after(
    df: pd.DataFrame,
    atr_arr: np.ndarray,
    med_range: np.ndarray,
    start_i: int,
    direction: str,
    max_scan: int = 12,
) -> Tuple[Optional[int], Optional[float], bool]:
    """
    direction LONG: bullish bar, range > rolling median range, close > open.
    Returns (bar_index, strength, micro_ok).
    """
    n = len(df)
    hi = min(n - 1, start_i + max_scan)
    for j in range(start_i, hi + 1):
        row = df.iloc[j]
        o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])
        rng = h - l
        med = float(med_range[j]) if j < len(med_range) else np.nan
        if not np.isfinite(med) or med <= 0 or not np.isfinite(rng):
            continue
        atr_j = float(atr_arr[j]) if j < len(atr_arr) else np.nan
        if not np.isfinite(atr_j) or atr_j <= 0:
            continue
        if direction == "LONG":
            if c <= o:
                continue
            if rng <= med:
                continue
            strength = rng / med
            if j > 0:
                past_hi = df["high"].iloc[max(0, j - 10) : j]
                msh = float(past_hi.max()) if len(past_hi) else None
            else:
                msh = None
            micro_ok = msh is not None and c > msh
            return j, float(strength), micro_ok
        else:
            if c >= o:
                continue
            if rng <= med:
                continue
            strength = rng / med
            if j > 0:
                past_lo = df["low"].iloc[max(0, j - 10) : j]
                msl = float(past_lo.min()) if len(past_lo) else None
            else:
                msl = None
            micro_ok = msl is not None and c < msl
            return j, float(strength), micro_ok
    return None, None, False


def htf_bias_series_m5(df: pd.DataFrame, ema_span: int = 34) -> pd.Series:
    """4H close vs EMA(ema_span) on 4H bars; bullish if close > ema else bearish; ffill to M5 index."""
    if df.empty or "close" not in df.columns:
        return pd.Series("none", index=df.index, dtype=object)
    ohlc = df[["open", "high", "low", "close"]].copy()
    h4 = ohlc.resample("4h", label="right", closed="right").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    )
    h4 = h4.dropna(subset=["close"])
    if h4.empty:
        return pd.Series("none", index=df.index, dtype=object)
    ema = h4["close"].ewm(span=int(ema_span), adjust=False).mean()
    lab = np.where(h4["close"] > ema, "bullish", "bearish")
    ser = pd.Series(lab.astype(object), index=h4.index)
    out = ser.reindex(df.index, method="ffill")
    out = out.where(out.notna(), "none")
    return out.astype(object)


@dataclass
class SweepDetectorConfig:
    min_sweep_depth_atr: float = 0.15
    max_reclaim_candles: int = 3
    median_range_window: int = 50
    atr_period: int = 14
    strategy_id: str = STRATEGY_ID_DEFAULT
    htf_bias_filter: bool = False
    htf_bias_ema_span: int = 34


def detect_sweep_events_m5(
    df_m5: pd.DataFrame,
    regime_series: Optional[pd.Series] = None,
    *,
    cfg: Optional[SweepDetectorConfig] = None,
) -> List[Dict[str, Any]]:
    """
    Scan M5 OHLCV (UTC index) for PDH/PDL sweep+reclaim sequences in London/NY windows.

    Emits at most one event per distinct excursion (first bar where depth threshold is met).
    """
    cfg = cfg or SweepDetectorConfig()
    if df_m5.empty or len(df_m5) < cfg.median_range_window + cfg.atr_period + 5:
        return []

    d = align_prev_daily_high_low(df_m5.copy())
    d = d.sort_index()
    atr_s = compute_atr(d, period=cfg.atr_period)
    d["_atr"] = atr_s
    med_range = rolling_median_range(d, window=cfg.median_range_window).values
    atr_arr = d["_atr"].values.astype(float)
    closes = d["close"].values.astype(float)
    highs = d["high"].values.astype(float)
    lows = d["low"].values.astype(float)
    n = len(d)
    idx = d.index

    bias_arr: Optional[np.ndarray] = None
    if cfg.htf_bias_filter:
        bias_ser = htf_bias_series_m5(d[["open", "high", "low", "close"]], ema_span=cfg.htf_bias_ema_span)
        bias_arr = bias_ser.astype(str).values

    reg_vals: Optional[np.ndarray] = None
    if regime_series is not None and len(regime_series) > 0:
        rs = regime_series.reindex(d.index, method="ffill")
        reg_vals = np.array([str(x) if pd.notna(x) else "none" for x in rs.values])

    events: List[Dict[str, Any]] = []

    def regime_at(i: int) -> str:
        if reg_vals is None or i >= len(reg_vals):
            return "none"
        return str(reg_vals[i])

    def jump_after_pdl_reset(sweep_i: int) -> int:
        """Next index after price trades back above session PDL (avoid chained duplicate sweeps)."""
        for t in range(sweep_i, min(sweep_i + 96, n)):
            lv = float(d["pdl"].iloc[t])
            if closes[t] > lv:
                return min(t + 1, n - 1)
        return min(sweep_i + 1, n - 1)

    def jump_after_pdh_reset(sweep_i: int) -> int:
        for t in range(sweep_i, min(sweep_i + 96, n)):
            lv = float(d["pdh"].iloc[t])
            if closes[t] < lv:
                return min(t + 1, n - 1)
        return min(sweep_i + 1, n - 1)

    i = cfg.median_range_window + 2
    while i < n:
        ts = idx[i]
        bucket = in_session_bucket_utc(ts)
        if bucket is None:
            i += 1
            continue

        pdl = d["pdl"].iloc[i]
        pdh = d["pdh"].iloc[i]
        atr_i = float(atr_arr[i])
        if not np.isfinite(pdl) or not np.isfinite(pdh) or not np.isfinite(atr_i) or atr_i <= 0:
            i += 1
            continue

        # --- PDL (bullish context): sweep down, reclaim up ---
        depth_pdl = pdl - lows[i]
        if depth_pdl >= cfg.min_sweep_depth_atr * atr_i:
            sweep_i = i
            reclaim_i: Optional[int] = None
            last_k = min(sweep_i + cfg.max_reclaim_candles, n - 1)
            for k in range(sweep_i, last_k + 1):
                if closes[k] > float(d["pdl"].iloc[k]):
                    reclaim_i = k
                    break
            wrong_run = 0
            if reclaim_i is not None:
                wrong_run = _max_run_close_vs_level(
                    d, closes, "pdl", sweep_i, reclaim_i - 1, mode="below"
                )
            acceptance_failed = reclaim_i is not None and wrong_run < 3

            disp_i, disp_strength, micro_ok = (None, None, False)
            if reclaim_i is not None:
                disp_i, disp_strength, micro_ok = _find_displacement_after(
                    d, atr_arr, med_range, reclaim_i, "LONG"
                )

            if cfg.htf_bias_filter and bias_arr is not None:
                if str(bias_arr[sweep_i]) != "bullish":
                    i = jump_after_pdl_reset(sweep_i)
                    continue

            payload = {
                "session": bucket,
                "level_type": "PDL",
                "level_price": float(pdl),
                "sweep_direction": "bearish",
                "sweep_depth_atr": float(depth_pdl / atr_i),
                "candles_to_reclaim": int(reclaim_i - sweep_i) if reclaim_i is not None else None,
                "displacement_strength": float(disp_strength) if disp_strength is not None else None,
                "micro_structure_shift": bool(micro_ok),
                "acceptance_failed": acceptance_failed,
                "news_nearby": False,
                "regime": regime_at(sweep_i),
                "atr_m5": float(atr_i),
                "reclaimed_within_window": reclaim_i is not None,
                "sweep_bar_index": int(sweep_i),
                "displacement_bar_index": int(disp_i) if disp_i is not None else None,
            }
            if cfg.htf_bias_filter and bias_arr is not None:
                payload["htf_bias"] = str(bias_arr[sweep_i])
            events.append(_wrap_event(ts, payload, cfg.strategy_id))
            i = jump_after_pdl_reset(sweep_i)
            continue

        # --- PDH (bearish context): sweep up, reclaim down ---
        depth_pdh = highs[i] - pdh
        if depth_pdh >= cfg.min_sweep_depth_atr * atr_i:
            sweep_i = i
            reclaim_i = None
            last_k = min(sweep_i + cfg.max_reclaim_candles, n - 1)
            for k in range(sweep_i, last_k + 1):
                if closes[k] < float(d["pdh"].iloc[k]):
                    reclaim_i = k
                    break
            wrong_run = 0
            if reclaim_i is not None:
                wrong_run = _max_run_close_vs_level(
                    d, closes, "pdh", sweep_i, reclaim_i - 1, mode="above"
                )
            acceptance_failed = reclaim_i is not None and wrong_run < 3

            disp_i, disp_strength, micro_ok = (None, None, False)
            if reclaim_i is not None:
                disp_i, disp_strength, micro_ok = _find_displacement_after(
                    d, atr_arr, med_range, reclaim_i, "SHORT"
                )

            if cfg.htf_bias_filter and bias_arr is not None:
                if str(bias_arr[sweep_i]) != "bearish":
                    i = jump_after_pdh_reset(sweep_i)
                    continue

            payload = {
                "session": bucket,
                "level_type": "PDH",
                "level_price": float(pdh),
                "sweep_direction": "bullish",
                "sweep_depth_atr": float(depth_pdh / atr_i),
                "candles_to_reclaim": int(reclaim_i - sweep_i) if reclaim_i is not None else None,
                "displacement_strength": float(disp_strength) if disp_strength is not None else None,
                "micro_structure_shift": bool(micro_ok),
                "acceptance_failed": acceptance_failed,
                "news_nearby": False,
                "regime": regime_at(sweep_i),
                "atr_m5": float(atr_i),
                "reclaimed_within_window": reclaim_i is not None,
                "sweep_bar_index": int(sweep_i),
                "displacement_bar_index": int(disp_i) if disp_i is not None else None,
            }
            if cfg.htf_bias_filter and bias_arr is not None:
                payload["htf_bias"] = str(bias_arr[sweep_i])
            events.append(_wrap_event(ts, payload, cfg.strategy_id))
            i = jump_after_pdh_reset(sweep_i)
            continue

        i += 1

    return events


def _wrap_event(ts: pd.Timestamp, payload: Dict[str, Any], strategy_id: str) -> Dict[str, Any]:
    tsu = pd.Timestamp(ts)
    if tsu.tzinfo is None:
        tsu = tsu.tz_localize("UTC")
    else:
        tsu = tsu.tz_convert("UTC")
    ts_iso = tsu.isoformat().replace("+00:00", "Z")
    decision = "ENTER"
    if not payload.get("reclaimed_within_window"):
        decision = "OBSERVE_NO_RECLAIM"
    elif not payload.get("acceptance_failed"):
        decision = "SKIP_ACCEPTANCE"
    elif payload.get("displacement_strength") is None:
        decision = "OBSERVE_NO_DISPLACEMENT"
    elif not payload.get("micro_structure_shift"):
        decision = "OBSERVE_NO_MICRO_SHIFT"
    payload = dict(payload)
    payload["decision"] = decision
    return {
        "event_type": "sweep_research",
        "strategy_id": strategy_id,
        "symbol": "XAUUSD",
        "timestamp_utc": ts_iso,
        "payload": payload,
    }


def events_to_jsonl_lines(events: List[Dict[str, Any]]) -> Iterator[str]:
    for e in events:
        yield json.dumps(e, separators=(",", ":"), ensure_ascii=False)


def write_jsonl(path: str, events: List[Dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for line in events_to_jsonl_lines(events):
            f.write(line + "\n")
