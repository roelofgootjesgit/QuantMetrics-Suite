#!/usr/bin/env python3
"""MAE/MFE summary by regime from trade_closed in QuantLog JSONL (no new backtest)."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any


def _pct(xs: list[float], p: float) -> float:
    if not xs:
        return float("nan")
    s = sorted(xs)
    k = (len(s) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (k - f) * (s[c] - s[f]) if f != c else float(s[f])


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        if e.get("event_type") != "trade_closed":
            continue
        p = e.get("payload") or {}
        rows.append(
            {
                "regime": str(p.get("regime") or "").strip().lower() or "unknown",
                "pnl_r": float(p.get("pnl_r") or 0),
                "mae_r": float(p.get("mae_r") or 0),
                "mfe_r": float(p.get("mfe_r") or 0),
                "outcome": str(p.get("outcome") or ""),
            }
        )
    return rows


def summarize(name: str, xs: list[float]) -> str:
    if not xs:
        return f"{name}: (empty)"
    return (
        f"{name}: n={len(xs)}  mean={statistics.mean(xs):.3f}  "
        f"p50={_pct(xs, 50):.3f}  p90={_pct(xs, 90):.3f}"
    )


def block_for_subset(label: str, rows: list[dict[str, Any]]) -> None:
    print(f"\n### {label} (n={len(rows)})")
    if not rows:
        return
    mae = [r["mae_r"] for r in rows]
    mfe = [r["mfe_r"] for r in rows]
    ratio = [r["mfe_r"] / r["mae_r"] if r["mae_r"] > 1e-9 else float("inf") for r in rows]
    ratio_f = [x for x in ratio if x != float("inf")]
    ge1 = sum(1 for r in rows if r["mfe_r"] >= 1.0)
    wins = [r for r in rows if str(r["outcome"]).upper() == "WIN"]
    losses = [r for r in rows if str(r["outcome"]).upper() == "LOSS"]
    print(f"  {summarize('MAE_R', mae)}")
    print(f"  {summarize('MFE_R', mfe)}")
    if ratio_f:
        print(f"  {summarize('MFE/MAE (finite)', ratio_f)}")
    print(f"  share with MFE_R >= 1: {100.0 * ge1 / len(rows):.1f}%")
    if wins:
        wmfe = [r["mfe_r"] for r in wins]
        print(f"  winners MFE_R mean: {statistics.mean(wmfe):.3f}")
    if losses:
        lmfe = [r["mfe_r"] for r in losses]
        lmae = [r["mae_r"] for r in losses]
        print(f"  losers  MFE_R mean: {statistics.mean(lmfe):.3f}  MAE_R mean: {statistics.mean(lmae):.3f}")


def main() -> int:
    ap = argparse.ArgumentParser(description="MAE/MFE by regime from quantlog JSONL")
    ap.add_argument("jsonl", type=Path)
    ap.add_argument("--label", default="", help="Short label for header")
    args = ap.parse_args()
    rows = load_rows(args.jsonl)
    tag = args.label or str(args.jsonl)
    print(f"# {tag}")
    print(f"trade_closed events: {len(rows)}")
    regimes: dict[str, list] = {}
    for r in rows:
        regimes.setdefault(r["regime"], []).append(r)
    for rg in sorted(regimes.keys()):
        block_for_subset(rg, regimes[rg])
    all_mae = [r["mae_r"] for r in rows]
    all_mfe = [r["mfe_r"] for r in rows]
    print("\n### ALL regimes combined")
    print(f"  {summarize('MAE_R', all_mae)}")
    print(f"  {summarize('MFE_R', all_mfe)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
