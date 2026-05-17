"""
Forensic alignment audit: sweep_detector year-slice indices vs full parquet simulator.

Run from quantbuild/ with PYTHONPATH=src:
  python scripts/sweep_alignment_audit.py --year 2024 --sweeps sweeps_2024.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.quantbuild.io.parquet_loader import load_parquet


def _naive_ts(ts: Any) -> pd.Timestamp:
    t = pd.Timestamp(ts)
    if t.tzinfo is not None:
        return t.tz_convert("UTC").tz_localize(None)
    return t


def load_enters(sweeps_path: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    with open(sweeps_path, encoding="utf-8") as f:
        for line in f:
            ev = json.loads(line)
            pl = ev.get("payload") or {}
            if pl.get("decision") != "ENTER":
                continue
            out.append(
                {
                    "event_ts": ev.get("timestamp_utc"),
                    "sweep_i": int(pl["sweep_bar_index"]),
                    "disp_i": int(pl["displacement_bar_index"]),
                }
            )
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Audit sweep index alignment (year slice vs full parquet)")
    p.add_argument("--year", type=int, default=2024)
    p.add_argument("--sweeps", type=Path, default=Path("sweeps_2024.jsonl"))
    p.add_argument("--parquet", type=Path, default=Path("data/market_cache/XAUUSD/5m.parquet"))
    p.add_argument("--sample", type=int, default=10)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    y = args.year
    start = datetime(y, 1, 1, tzinfo=timezone.utc)
    end = datetime(y, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

    sweep_path = args.sweeps if args.sweeps.is_absolute() else ROOT / args.sweeps
    pq_path = args.parquet if args.parquet.is_absolute() else ROOT / args.parquet
    base = pq_path.parent.parent

    enters = load_enters(sweep_path)
    if not enters:
        print("No ENTER events in", sweep_path)
        return 1

    df_full = pd.read_parquet(pq_path).sort_index()
    df_year = load_parquet(base, "XAUUSD", "5m", start=start, end=end).sort_index()

    print(f"\n=== SWEEP ALIGNMENT AUDIT (year={y}) ===\n")
    print(f"Sweeps file     : {sweep_path}")
    print(f"ENTER count     : {len(enters)}")
    print(f"Year slice bars : {len(df_year)}  [{df_year.index.min()} .. {df_year.index.max()}]")
    print(f"Full parquet    : {len(df_full)}  [{df_full.index.min()} .. {df_full.index.max()}]")

    event_vs_year_mismatch = 0
    full_vs_year_at_index = 0
    event_calendar_wrong_year = 0
    sim_uses_wrong_bar = 0  # full iloc timestamp not in calendar year

    for e in enters:
        di = e["disp_i"]
        te = _naive_ts(e["event_ts"])
        if te.year != y:
            event_calendar_wrong_year += 1

        if di < len(df_year):
            ty = pd.Timestamp(df_year.index[di])
            if abs((te - ty).total_seconds()) > 60:
                event_vs_year_mismatch += 1
        else:
            event_vs_year_mismatch += 1

        if di < len(df_full) and di < len(df_year):
            if df_full.index[di] != df_year.index[di]:
                full_vs_year_at_index += 1
        if di < len(df_year):
            ty = pd.Timestamp(df_year.index[di])
            if ty.year != y:
                sim_uses_wrong_bar += 1

    n = len(enters)
    print("\n--- Aggregate ---")
    print(f"event timestamp not in calendar {y}           : {event_calendar_wrong_year} / {n}")
    print(f"event_ts != year_df.iloc[disp_i] (±60s)      : {event_vs_year_mismatch} / {n}")
    print(f"full.iloc[i] != year.iloc[i] (same index)     : {full_vs_year_at_index} / {n}")
    print(f"sim bar (full iloc) calendar year != {y}      : {sim_uses_wrong_bar} / {n}")

    # full.iloc[i] != year.iloc[i] is EXPECTED when parquet starts before calendar year
    # (indices are relative to year slice). Valid sim must use --year on outcome_sim.
    oob_year = sum(1 for e in enters if e["disp_i"] >= len(df_year) or e["sweep_i"] >= len(df_year))
    if oob_year > 0:
        verdict = f"FAIL — {oob_year} ENTER indices out of bounds on year slice."
    elif event_calendar_wrong_year > 0:
        verdict = "FAIL — event timestamps outside calendar year."
    elif sim_uses_wrong_bar > 0:
        verdict = "FAIL — year.iloc[disp_i] outside calendar year (data gap?)."
    elif full_vs_year_at_index > 0:
        verdict = (
            "PASS (year-slice sim) — full.iloc≠year.iloc at same index is expected "
            "(indices are year-relative). Use sweep_outcome_sim.py --year."
        )
    else:
        verdict = "PASS — year-slice indices in bounds; use --year on outcome_sim."

    print(f"\nVerdict: {verdict}\n")
    if full_vs_year_at_index > 0 and oob_year == 0:
        print(
            f"Note: {full_vs_year_at_index}/{n} rows differ full vs year at same iloc — "
            f"normal when cache starts before {y}; not a failure if sim uses --year."
        )

    rng = random.Random(args.seed)
    sample = rng.sample(enters, min(args.sample, n))
    print(f"--- Sample {len(sample)} rows ---")
    print(f"{'event_ts':<22} {'year@disp':<22} {'full@disp':<22} idx_eq  y_ok")
    for e in sample:
        di = e["disp_i"]
        te = str(e["event_ts"])[:19]
        ty = str(df_year.index[di])[:19] if di < len(df_year) else "OOB"
        tf = str(df_full.index[di])[:19] if di < len(df_full) else "OOB"
        idx_eq = di < len(df_full) and di < len(df_year) and df_full.index[di] == df_year.index[di]
        y_ok = di < len(df_full) and pd.Timestamp(df_full.index[di]).year == y
        print(f"{te:<22} {ty:<22} {tf:<22} {str(idx_eq):<5} {y_ok}")

    return 0 if "PASS" in verdict else 1


if __name__ == "__main__":
    raise SystemExit(main())
