"""
H2 — forward return after ENTER vs session baseline (no exit), EXP-004 herrun step 3.

Run from quantbuild/:
  python scripts/sweep_forward_return_h2.py --year 2024 --sweeps sweeps_2024.jsonl
  python scripts/sweep_forward_return_h2.py --years 2015 2019 2022 2024 --sweeps-glob "sweeps_{year}.jsonl"
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.quantbuild.io.parquet_loader import load_parquet
from src.quantbuild.research.sweep_m5_xauusd import in_session_bucket_utc


def _load_year_df(year: int, base: Path, symbol: str) -> pd.DataFrame:
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    end = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    df = load_parquet(base, symbol, "5m", start=start, end=end).sort_index()
    return df


def _forward_r_signed(
    df: pd.DataFrame,
    i: int,
    horizon: int,
    direction: str,
) -> Optional[float]:
    """Close-to-close return over `horizon` bars, signed for trade direction (in price units)."""
    j = i + horizon
    if i < 0 or j >= len(df):
        return None
    entry = float(df["close"].iloc[i])
    exit_c = float(df["close"].iloc[j])
    if direction == "LONG":
        return exit_c - entry
    return entry - exit_c


def _direction_from_payload(pl: Dict[str, Any]) -> Optional[str]:
    sd = str(pl.get("sweep_direction", "")).lower()
    if sd == "bearish":
        return "LONG"
    if sd == "bullish":
        return "SHORT"
    return None


def _enter_bars_from_sweeps(path: Path) -> List[Tuple[int, str, int]]:
    """(displacement_bar_index, direction, year) — year parsed from filename."""
    y = 0
    for part in path.stem.split("_"):
        if part.isdigit() and len(part) == 4:
            y = int(part)
            break
    out: List[Tuple[int, str, int]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            ev = json.loads(line)
            pl = ev.get("payload") or {}
            if pl.get("decision") != "ENTER":
                continue
            di = pl.get("displacement_bar_index")
            d = _direction_from_payload(pl)
            if di is None or d is None:
                continue
            out.append((int(di), d, y))
    return out


def _baseline_sample(
    df: pd.DataFrame,
    exclude: set[int],
    n_target: int,
    horizon: int,
    rng: random.Random,
) -> List[float]:
    """Random session bars not in exclude, with valid forward window."""
    candidates: List[int] = []
    for i in range(len(df) - horizon):
        if i in exclude:
            continue
        if in_session_bucket_utc(df.index[i]) is None:
            continue
        candidates.append(i)
    if not candidates:
        return []
    rng.shuffle(candidates)
    rets: List[float] = []
    for i in candidates:
        # baseline direction-agnostic: use absolute move / ATR proxy = raw signed long
        r = _forward_r_signed(df, i, horizon, "LONG")
        if r is not None and np.isfinite(r):
            rets.append(float(r))
        if len(rets) >= n_target:
            break
    return rets


def _summarize(name: str, vals: List[float]) -> None:
    if not vals:
        print(f"{name}: n=0")
        return
    a = np.array(vals, dtype=float)
    print(
        f"{name}: n={len(a)}  mean={a.mean():.4f}  median={np.median(a):.4f}  "
        f"%pos={100*np.mean(a>0):.1f}%"
    )


def main() -> int:
    p = argparse.ArgumentParser(description="H2 forward return ENTER vs baseline")
    p.add_argument("--years", nargs="+", type=int, default=[2024])
    p.add_argument(
        "--sweeps-template",
        default="sweeps_{year}.jsonl",
        help="Path template with {year}",
    )
    p.add_argument("--horizon", type=int, default=10)
    p.add_argument("--baseline-mult", type=float, default=10.0, help="baseline n = mult * ENTER n")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--symbol", default="XAUUSD")
    p.add_argument("--base-path", type=Path, default=Path("data/market_cache"))
    args = p.parse_args()

    rng = random.Random(args.seed)
    enter_rets: List[float] = []
    enter_by_year: Dict[int, List[float]] = {}

    for year in args.years:
        sweep_path = ROOT / args.sweeps_template.format(year=year)
        if not sweep_path.is_file():
            print(f"SKIP {year}: missing {sweep_path}")
            continue
        df = _load_year_df(year, args.base_path, args.symbol)
        if df.empty:
            print(f"SKIP {year}: no M5 data")
            continue
        bars = _enter_bars_from_sweeps(sweep_path)
        exclude = {b[0] for b in bars}
        yr_rets: List[float] = []
        for di, direction, _ in bars:
            r = _forward_r_signed(df, di, args.horizon, direction)
            if r is not None and np.isfinite(r):
                yr_rets.append(r)
                enter_rets.append(r)
        enter_by_year[year] = yr_rets
        n_base = max(1, int(len(yr_rets) * args.baseline_mult))
        base_rets = _baseline_sample(df, exclude, n_base, args.horizon, rng)
        print(f"\n--- Year {year} (horizon={args.horizon} bars, price delta) ---")
        _summarize("ENTER", yr_rets)
        _summarize("baseline", base_rets)

    print(f"\n=== H2 COMBINED (years={args.years}) ===")
    _summarize("ENTER", enter_rets)
    if not enter_rets:
        print("H2: no ENTER bars — cannot decide")
        return 1

    # pooled baseline: concatenate per-year baselines would need second pass — quick pooled sample from last year only is wrong; re-sample per year and pool
    all_base: List[float] = []
    for year in args.years:
        sweep_path = ROOT / args.sweeps_template.format(year=year)
        if not sweep_path.is_file():
            continue
        df = _load_year_df(year, args.base_path, args.symbol)
        bars = _enter_bars_from_sweeps(sweep_path)
        exclude = {b[0] for b in bars}
        n_base = max(len(bars) * int(args.baseline_mult), 100)
        all_base.extend(_baseline_sample(df, exclude, n_base, args.horizon, rng))

    _summarize("baseline (pooled)", all_base)

    em = float(np.mean(enter_rets))
    bm = float(np.mean(all_base)) if all_base else 0.0
    print(f"\nENTER mean - baseline mean = {em - bm:.4f} (price units, {args.horizon} bars)")

    if em > 0 and em > bm + 1e-6:
        print("H2 DECISION: PASS - ENTER forward mean > 0 and above baseline - proceed to H1 sim")
        return 0
    print("H2 DECISION: FAIL - detectie geen bruikbare forward edge vs baseline - stop (no H1)")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
