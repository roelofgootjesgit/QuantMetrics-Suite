"""
EXP-004 — year diagnostic (ENTER bars): displacement, sweep depth, regime, ATR context.

Run from quantbuild/:
  python scripts/sweep_year_diagnostic.py --years 2015 2019 2022 2024
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.quantbuild.indicators.atr import atr as compute_atr
from src.quantbuild.io.parquet_loader import load_parquet


def _load_enters(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            ev = json.loads(line)
            pl = ev.get("payload") or {}
            if pl.get("decision") != "ENTER":
                continue
            rows.append(pl)
    return rows


def _year_m5(year: int, base: Path) -> pd.DataFrame:
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    end = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    return load_parquet(base, "XAUUSD", "5m", start=start, end=end).sort_index()


def _dist_stats(name: str, arr: np.ndarray) -> str:
    if len(arr) == 0:
        return f"{name}: n=0"
    a = arr[np.isfinite(arr)]
    if len(a) == 0:
        return f"{name}: n=0 (non-finite)"
    return (
        f"{name}: n={len(a)}  mean={a.mean():.3f}  median={np.median(a):.3f}  "
        f"std={a.std():.3f}  p25={np.percentile(a,25):.3f}  p75={np.percentile(a,75):.3f}"
    )


def _regime_table(enters: List[Dict[str, Any]]) -> pd.Series:
    regs = [str(e.get("regime", "none")) for e in enters]
    return pd.Series(regs).value_counts()


def _m5_year_context(df: pd.DataFrame) -> Dict[str, float]:
    if df.empty:
        return {}
    atr_s = compute_atr(df, period=14)
    ret = df["close"].pct_change()
  # trend persistence: fraction of bars where 20-bar return same sign as 60-bar return
    r20 = df["close"].diff(20)
    r60 = df["close"].diff(60)
    align = ((r20 > 0) & (r60 > 0)) | ((r20 < 0) & (r60 < 0))
    valid = r20.notna() & r60.notna()
    persist = float(align[valid].mean()) if valid.any() else float("nan")
    return {
        "bars": len(df),
        "atr_mean": float(atr_s.mean()),
        "atr_median": float(atr_s.median()),
        "daily_range_mean": float((df["high"] - df["low"]).mean()),
        "abs_ret_mean_bps": float(ret.abs().mean() * 10000) if ret.notna().any() else float("nan"),
        "trend_persist_20v60": persist,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="EXP-004 per-year ENTER diagnostic")
    p.add_argument("--years", nargs="+", type=int, default=[2015, 2019, 2022, 2024])
    p.add_argument("--sweeps-template", default="sweeps_{year}.jsonl")
    p.add_argument("--outcomes-template", default="sweep_outcomes_{year}_aligned.jsonl")
    p.add_argument("--base-path", type=Path, default=Path("data/market_cache"))
    args = p.parse_args()

    print("\n=== EXP-004 YEAR DIAGNOSTIC (ENTER bars only) ===\n")

    by_year: Dict[int, List[Dict[str, Any]]] = {}
    outcomes: Dict[int, List[Dict[str, Any]]] = {}

    for year in args.years:
        sp = ROOT / args.sweeps_template.format(year=year)
        by_year[year] = _load_enters(sp)
        op = ROOT / args.outcomes_template.format(year=year)
        if op.is_file():
            outcomes[year] = [json.loads(l) for l in open(op, encoding="utf-8") if l.strip()]

    # --- A: M5 year context (full calendar year, not just ENTER) ---
    print("--- A: M5 year context (all session bars in calendar year) ---\n")
    ctx_rows = []
    for year in args.years:
        df = _year_m5(year, args.base_path)
        c = _m5_year_context(df)
        c["year"] = year
        ctx_rows.append(c)
        print(f"Year {year}: bars={c['bars']}  ATR_mean={c['atr_mean']:.3f}  "
              f"daily_range_mean={c['daily_range_mean']:.3f}  "
              f"trend_persist_20v60={c['trend_persist_20v60']:.3f}")
    print()

    # --- B: ENTER feature distributions ---
    print("--- B: ENTER feature distributions ---\n")
    for year in args.years:
        ent = by_year[year]
        print(f"### Year {year} (ENTER n={len(ent)}) ###")
        depth = np.array([float(e["sweep_depth_atr"]) for e in ent if e.get("sweep_depth_atr") is not None])
        disp = np.array(
            [float(e["displacement_strength"]) for e in ent if e.get("displacement_strength") is not None]
        )
        reclaim = np.array(
            [float(e["candles_to_reclaim"]) for e in ent if e.get("candles_to_reclaim") is not None]
        )
        atr_e = np.array([float(e["atr_m5"]) for e in ent if e.get("atr_m5") is not None])
        print(_dist_stats("sweep_depth_atr", depth))
        print(_dist_stats("displacement_strength", disp))
        print(_dist_stats("candles_to_reclaim", reclaim))
        print(_dist_stats("atr_m5_at_sweep", atr_e))
        print("regime on ENTER:")
        for k, v in _regime_table(ent).items():
            print(f"  {k}: {v} ({100*v/len(ent):.1f}%)")
        if year in outcomes and outcomes[year]:
            pnl = np.array([float(r["pnl_r"]) for r in outcomes[year]])
            print(_dist_stats("pnl_r (aligned sim)", pnl))
        print()

    # --- C: 2019 vs pool of other years ---
    if 2019 in by_year:
        other = [e for y in args.years if y != 2019 for e in by_year[y]]
        y19 = by_year[2019]
        print("--- C: 2019 vs other years (ENTER) ---\n")

        def col(rows, key):
            return np.array([float(r[key]) for r in rows if r.get(key) is not None])

        for key in ("sweep_depth_atr", "displacement_strength", "candles_to_reclaim"):
            a, b = col(y19, key), col(other, key)
            if len(a) and len(b):
                print(f"{key}: 2019 mean={a.mean():.3f}  others mean={b.mean():.3f}  "
                      f"diff={a.mean()-b.mean():+.3f}")

        r19 = _regime_table(y19)
        ro = _regime_table(other)
        print("\nregime % on ENTER:")
        all_regs = sorted(set(r19.index) | set(ro.index))
        for reg in all_regs:
            p19 = 100 * r19.get(reg, 0) / len(y19) if len(y19) else 0
            po = 100 * ro.get(reg, 0) / len(other) if len(other) else 0
            print(f"  {reg}: 2019={p19:.1f}%  others={po:.1f}%")

        c19 = next((c for c in ctx_rows if c["year"] == 2019), None)
        if c19:
            coth = [c for c in ctx_rows if c["year"] != 2019]
            atr_o = np.mean([c["atr_mean"] for c in coth])
            print(f"\nM5 ATR_mean: 2019={c19['atr_mean']:.3f}  others_avg={atr_o:.3f}")
            tp_o = np.mean([c["trend_persist_20v60"] for c in coth])
            print(f"trend_persist_20v60: 2019={c19['trend_persist_20v60']:.3f}  others_avg={tp_o:.3f}")

    # SE reminder for 2019
    if 2019 in outcomes and outcomes[2019]:
        pnl19 = np.array([float(r["pnl_r"]) for r in outcomes[2019]])
        se = pnl19.std(ddof=1) / np.sqrt(len(pnl19)) if len(pnl19) > 1 else float("nan")
        print(f"\n2019 pnl_r: mean={pnl19.mean():.3f}  SE~{se:.3f}  "
              f"95% CI approx [{pnl19.mean()-1.96*se:.2f}, {pnl19.mean()+1.96*se:.2f}]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
