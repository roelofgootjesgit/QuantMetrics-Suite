"""
Post-process ENTER sweep_research events: simulate SL/TP/timeout on M5 OHLC.

Run from quantbuild/:
  $env:PYTHONPATH=".../quantbuild/src"
  python scripts/sweep_outcome_sim.py
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.quantbuild.io.parquet_loader import load_parquet


def _resolve_sweep_extreme(
    df: pd.DataFrame,
    sweep_i: int,
    disp_i: int,
    direction: str,
    payload: Dict[str, Any],
) -> Tuple[Optional[float], Optional[float]]:
    """Return (sweep_low, sweep_high) for SL; prefer payload, else bar/range fallback."""
    lo = payload.get("sweep_low")
    hi = payload.get("sweep_high")
    if lo is not None and np.isfinite(lo):
        sweep_low = float(lo)
    else:
        a = max(0, sweep_i)
        b = min(len(df) - 1, disp_i)
        if b < a:
            b = a
        sweep_low = float(df["low"].iloc[a : b + 1].min())

    if hi is not None and np.isfinite(hi):
        sweep_high = float(hi)
    else:
        a = max(0, sweep_i)
        b = min(len(df) - 1, disp_i)
        if b < a:
            b = a
        sweep_high = float(df["high"].iloc[a : b + 1].max())

    if direction == "LONG":
        return sweep_low, None
    return None, sweep_high


def _simulate_one(
    df: pd.DataFrame,
    payload: Dict[str, Any],
    tp_r: float,
    sl_buffer_atr: float,
    max_bars: int,
) -> Optional[Dict[str, Any]]:
    disp_i = payload.get("displacement_bar_index")
    sweep_i = payload.get("sweep_bar_index")
    atr_m5 = float(payload.get("atr_m5", np.nan))
    sd = str(payload.get("sweep_direction", "")).lower()

    if disp_i is None or sweep_i is None or not np.isfinite(atr_m5) or atr_m5 <= 0:
        return None
    disp_i = int(disp_i)
    sweep_i = int(sweep_i)
    if disp_i < 0 or disp_i >= len(df) or sweep_i < 0 or sweep_i >= len(df):
        return None
    if disp_i + 1 >= len(df):
        return None

    if sd == "bearish":
        direction = "LONG"
    elif sd == "bullish":
        direction = "SHORT"
    else:
        return None

    entry = float(df["close"].iloc[disp_i])
    sweep_low, sweep_high = _resolve_sweep_extreme(df, sweep_i, disp_i, direction, payload)
    buf = sl_buffer_atr * atr_m5

    if direction == "LONG":
        if sweep_low is None:
            return None
        sl_price = sweep_low - buf
        sl_distance = entry - sl_price
        if sl_distance <= 0:
            return None
        tp_price = entry + tp_r * sl_distance
    else:
        if sweep_high is None:
            return None
        sl_price = sweep_high + buf
        sl_distance = sl_price - entry
        if sl_distance <= 0:
            return None
        tp_price = entry - tp_r * sl_distance

    last_forward = disp_i + max_bars
    clipped = False
    if last_forward >= len(df):
        last_forward = len(df) - 1
        clipped = True
        warnings.warn(
            f"Clipped forward window for event at index {disp_i}: "
            f"need bars through {disp_i + max_bars}, df len {len(df)}",
            RuntimeWarning,
            stacklevel=2,
        )

    outcome = "TIMEOUT"
    pnl_r = 0.0
    exit_price = float(df["close"].iloc[last_forward])
    bars_held = last_forward - disp_i
    exit_i = last_forward

    for i in range(disp_i + 1, last_forward + 1):
        row = df.iloc[i]
        lo = float(row["low"])
        hi = float(row["high"])

        if direction == "LONG":
            if lo <= sl_price:
                outcome = "SL_HIT"
                exit_price = sl_price
                pnl_r = -1.0
                bars_held = i - disp_i
                exit_i = i
                break
            if hi >= tp_price:
                outcome = "TP_HIT"
                exit_price = tp_price
                pnl_r = tp_r
                bars_held = i - disp_i
                exit_i = i
                break
        else:
            if hi >= sl_price:
                outcome = "SL_HIT"
                exit_price = sl_price
                pnl_r = -1.0
                bars_held = i - disp_i
                exit_i = i
                break
            if lo <= tp_price:
                outcome = "TP_HIT"
                exit_price = tp_price
                pnl_r = tp_r
                bars_held = i - disp_i
                exit_i = i
                break

    if outcome == "TIMEOUT":
        c = float(df["close"].iloc[last_forward])
        exit_price = c
        exit_i = last_forward
        bars_held = last_forward - disp_i
        if direction == "LONG":
            pnl_r = (c - entry) / sl_distance
        else:
            pnl_r = (entry - c) / sl_distance

    ts_entry = df.index[disp_i]
    tsp = pd.Timestamp(ts_entry)
    if tsp.tzinfo is None:
        ts_iso = tsp.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        ts_iso = tsp.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")

    out: Dict[str, Any] = {
        "event_type": "sweep_outcome",
        "timestamp_entry": ts_iso,
        "entry_price": round(entry, 5),
        "sl_price": round(sl_price, 5),
        "tp_price": round(tp_price, 5),
        "sl_distance": round(sl_distance, 5),
        "direction": direction,
        "outcome": outcome,
        "pnl_r": round(float(pnl_r), 6),
        "bars_held": int(bars_held),
        "exit_price": round(exit_price, 5),
        "exit_bar_index": int(exit_i),
        "session": payload.get("session"),
        "level_type": payload.get("level_type"),
        "sweep_direction": payload.get("sweep_direction"),
        "sweep_depth_atr": payload.get("sweep_depth_atr"),
        "displacement_strength": payload.get("displacement_strength"),
        "regime": payload.get("regime"),
        "atr_m5": payload.get("atr_m5"),
        "sweep_bar_index": sweep_i,
        "displacement_bar_index": disp_i,
        "window_clipped": clipped,
    }
    return out


def _pct(x: float, n: int) -> str:
    if n <= 0:
        return "0.0"
    return f"{100.0 * x / n:.1f}"


def _print_summary(rows: List[Dict[str, Any]], *, label: str = "SWEEP OUTCOME SUMMARY") -> None:
    n = len(rows)
    print(f"\n=== {label} ===\n")
    if n == 0:
        print("Total ENTER events simulated : 0")
        return

    outcomes = [r["outcome"] for r in rows]
    tp = outcomes.count("TP_HIT")
    sl = outcomes.count("SL_HIT")
    to = outcomes.count("TIMEOUT")
    pnl = np.array([float(r["pnl_r"]) for r in rows], dtype=float)
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    gross_win = float(wins.sum()) if len(wins) else 0.0
    gross_loss = float(losses.sum()) if len(losses) else 0.0
    pf = np.inf if gross_loss == 0 else gross_win / abs(gross_loss)

    print(f"Total ENTER events simulated : {n}")
    print(f"TP_HIT                       : {tp}  ({_pct(tp, n)}%)")
    print(f"SL_HIT                       : {sl}  ({_pct(sl, n)}%)")
    print(f"TIMEOUT                      : {to}  ({_pct(to, n)}%)")
    print()
    print(f"Win rate (TP_HIT / total)    : {_pct(tp, n)}%")
    print(f"Expectancy (avg pnl_r)       : {float(pnl.mean()):.2f} R")
    if np.isfinite(pf) and pf != np.inf:
        print(f"Profit factor                : {pf:.2f}")
    else:
        print("Profit factor                : inf (no losing trades)")
    print(f"Total R                      : {float(pnl.sum()):.2f} R")
    bh = np.array([r["bars_held"] for r in rows], dtype=float)
    print(f"Avg bars held                : {float(bh.mean()):.1f}")

    def block(title: str, key: str) -> None:
        print(f"\n=== {title} ===")
        df = pd.DataFrame(rows)
        for name, grp in df.groupby(key):
            g = grp["pnl_r"].astype(float)
            nn = len(grp)
            wr = 100.0 * (grp["outcome"] == "TP_HIT").sum() / nn if nn else 0.0
            exp = float(g.mean())
            print(f"{str(name):12s} : n={nn}  wr={wr:.1f}%  exp={exp:.2f} R")

    block("BY SESSION", "session")
    block("BY LEVEL TYPE", "level_type")
    block("BY REGIME", "regime")

    print("\n=== BY SWEEP DEPTH (buckets) ===")
    df = pd.DataFrame(rows)
    dep = df["sweep_depth_atr"].astype(float)

    def bucket_label(x: float) -> str:
        if x < 0.30:
            return "0.15-0.30 ATR"
        if x < 0.60:
            return "0.30-0.60 ATR"
        return "0.60+ ATR"

    df["_b"] = dep.apply(bucket_label)
    for lab in ["0.15-0.30 ATR", "0.30-0.60 ATR", "0.60+ ATR"]:
        grp = df[df["_b"] == lab]
        if grp.empty:
            print(f"{lab:14s} : n=0")
            continue
        g = grp["pnl_r"].astype(float)
        nn = len(grp)
        wr = 100.0 * (grp["outcome"] == "TP_HIT").sum() / nn
        exp = float(g.mean())
        print(f"{lab:14s} : n={nn}  wr={wr:.1f}%  exp={exp:.2f} R")


def main() -> int:
    p = argparse.ArgumentParser(description="Simulate sweep ENTER outcomes on M5")
    p.add_argument("--sweeps", type=Path, default=Path("sweeps_2024.jsonl"))
    p.add_argument("--parquet", type=Path, default=Path("data/market_cache/XAUUSD/5m.parquet"))
    p.add_argument(
        "--year",
        type=int,
        default=None,
        help="Calendar year window (must match sweep_detector --year). Required for valid iloc alignment.",
    )
    p.add_argument("--symbol", default="XAUUSD")
    p.add_argument("--tp-r", type=float, default=1.5, dest="tp_r")
    p.add_argument("--sl-buffer-atr", type=float, default=0.1, dest="sl_buffer_atr")
    p.add_argument("--max-bars", type=int, default=48, dest="max_bars")
    p.add_argument("--out", type=Path, default=Path("sweep_outcomes_2024.jsonl"))
    args = p.parse_args()

    sweep_path = args.sweeps if args.sweeps.is_absolute() else ROOT / args.sweeps
    pq_path = args.parquet if args.parquet.is_absolute() else ROOT / args.parquet
    out_path = args.out if args.out.is_absolute() else ROOT / args.out

    if args.year is None:
        warnings.warn(
            "No --year set: loading full parquet. sweep_bar_index/displacement_bar_index "
            "from sweep_detector are relative to the year slice — outcomes may be invalid.",
            UserWarning,
            stacklevel=2,
        )
        df = pd.read_parquet(pq_path)
    else:
        start = datetime(int(args.year), 1, 1, tzinfo=timezone.utc)
        end = datetime(int(args.year), 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        base = pq_path.parent.parent
        df = load_parquet(base, args.symbol, "5m", start=start, end=end)

    df = df.sort_index()
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)

    rows_out: List[Dict[str, Any]] = []
    skipped = 0

    with open(sweep_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            ev = json.loads(line)
            pl = ev.get("payload") or {}
            if pl.get("decision") != "ENTER":
                continue

            ts = ev.get("timestamp_utc", "?")
            if pl.get("displacement_bar_index") is None:
                warnings.warn(f"skip ENTER missing displacement_bar_index ts={ts}", UserWarning, stacklevel=2)
                skipped += 1
                continue

            sim = _simulate_one(
                df,
                pl,
                tp_r=args.tp_r,
                sl_buffer_atr=args.sl_buffer_atr,
                max_bars=args.max_bars,
            )
            if sim is None:
                warnings.warn(f"skip ENTER invalid geometry or index ts={ts}", UserWarning, stacklevel=2)
                skipped += 1
                continue
            rows_out.append(sim)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as wf:
        for r in rows_out:
            wf.write(json.dumps(r, separators=(",", ":"), ensure_ascii=False) + "\n")

    if skipped:
        print(f"(warnings: {skipped} ENTER rows skipped, see stderr if logging enabled)\n")

    yr = f" {args.year}" if args.year else ""
    _print_summary(rows_out, label=f"SWEEP OUTCOME SUMMARY{yr}")
    print(f"\nWrote {len(rows_out)} lines -> {out_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
