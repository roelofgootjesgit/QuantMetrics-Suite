"""
Aggregate sweep_outcome JSONL rows excluding 0.30 <= sweep_depth_atr < 0.60 bucket.

Run from quantbuild/:
  python scripts/sweep_outcome_subset_stats.py
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd


def _file_year(path: Path) -> Optional[int]:
    m = re.search(r"(20\d{2})", path.name)
    return int(m.group(1)) if m else None


def _load_rows(paths: List[Path]) -> pd.DataFrame:
    rows = []
    for p in paths:
        fy = _file_year(p)
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                r["_file_year"] = fy
                rows.append(r)
    return pd.DataFrame(rows)


def _summarize(df: pd.DataFrame, title: str) -> None:
    n = len(df)
    print(f"\n=== {title} (n={n}) ===")
    if n == 0:
        return
    tp = (df["outcome"] == "TP_HIT").sum()
    pnl = df["pnl_r"].astype(float)
    wins = pnl[pnl > 0].sum()
    losses = pnl[pnl < 0].sum()
    pf = np.inf if losses == 0 else wins / abs(losses)
    print(f"TP_HIT    : {int(tp)}  ({100*tp/n:.1f}%)")
    print(f"SL_HIT    : {int((df['outcome']=='SL_HIT').sum())}")
    print(f"TIMEOUT   : {int((df['outcome']=='TIMEOUT').sum())}")
    print(f"Win rate  : {100*tp/n:.1f}%")
    print(f"Expectancy: {float(pnl.mean()):.2f} R")
    if np.isfinite(pf) and pf != np.inf:
        print(f"PF        : {pf:.2f}")
    else:
        print("PF        : inf")
    print(f"Total R   : {float(pnl.sum()):.2f} R")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser(description="Outcome stats excluding mid sweep-depth bucket")
    p.add_argument(
        "files",
        nargs="*",
        default=[
            "sweep_outcomes_2023.jsonl",
            "sweep_outcomes_2024.jsonl",
            "sweep_outcomes_2025.jsonl",
        ],
        help="Paths to sweep_outcome JSONL (relative to quantbuild/)",
    )
    args = p.parse_args()
    paths = [root / x if not Path(x).is_absolute() else Path(x) for x in args.files]

    df = _load_rows(paths)
    ycol = "_file_year"
    if ycol not in df.columns or df[ycol].isna().all():
        df["year"] = pd.to_datetime(df["timestamp_entry"], utc=True).dt.year
        ycol = "year"

    _summarize(df, "ALL rows (all files)")

    dep = df["sweep_depth_atr"].astype(float)
    mask = (dep < 0.30) | (dep >= 0.60)
    sub = df.loc[mask].copy()
    _summarize(sub, "SUBSET: depth < 0.30 OR depth >= 0.60 (excl. [0.30, 0.60))")

    if ycol in sub.columns and sub[ycol].notna().any():
        for y in sorted(int(x) for x in sub[ycol].dropna().unique()):
            _summarize(sub[sub[ycol] == y], f"SUBSET file-year {y}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
