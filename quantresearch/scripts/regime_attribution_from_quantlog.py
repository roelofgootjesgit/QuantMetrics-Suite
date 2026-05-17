#!/usr/bin/env python3
"""Regime attribution from trade_closed in QuantLog JSONL (no new backtest)."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def load_trade_closed(path: Path) -> list[dict[str, Any]]:
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
                "ts": e.get("timestamp_utc") or "",
                "regime": str(p.get("regime") or "").strip().lower(),
                "pnl_r": float(p.get("pnl_r") or 0),
                "outcome": str(p.get("outcome") or ""),
            }
        )
    rows.sort(key=lambda x: x["ts"])
    return rows


def aggregate_by_regime(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_reg: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"n": 0, "wins": 0, "losses": 0, "timeouts": 0, "sum_r": 0.0, "pnls": []}
    )
    for r in rows:
        rg = r["regime"] or "unknown"
        d = by_reg[rg]
        d["n"] += 1
        d["sum_r"] += r["pnl_r"]
        d["pnls"].append(r["pnl_r"])
        o = r["outcome"].upper()
        if o == "WIN":
            d["wins"] += 1
        elif o == "LOSS":
            d["losses"] += 1
        elif "TIME" in o:
            d["timeouts"] += 1
    return dict(by_reg)


def pf_from_pnls(pnls: list[float]) -> float | None:
    gp = sum(x for x in pnls if x > 0)
    gl = abs(sum(x for x in pnls if x < 0))
    if gl == 0:
        return None if gp == 0 else float("inf")
    return gp / gl


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl", type=Path, help="quantlog_events.jsonl")
    ap.add_argument("--by-year", action="store_true", help="Also print calendar year breakdown")
    args = ap.parse_args()

    rows = load_trade_closed(args.jsonl)
    total_r = sum(r["pnl_r"] for r in rows)
    print(f"file: {args.jsonl}")
    print(f"trade_closed count: {len(rows)}  total net R (sum pnl_r): {total_r:+.4f}\n")

    by_reg = aggregate_by_regime(rows)
    for rg in sorted(by_reg.keys()):
        d = by_reg[rg]
        n = d["n"]
        wr = d["wins"] / n if n else 0.0
        pf = pf_from_pnls(d["pnls"])
        pfs = "inf" if pf == float("inf") else (f"{pf:.2f}" if pf is not None else "—")
        print(
            f"  {rg:12}  n={n:3}  net_R={d['sum_r']:+7.2f}  W/L={d['wins']}/{d['losses']}"
            f"  WR={100*wr:5.1f}%  PF={pfs}"
        )

    if args.by_year:
        print("\n--- by calendar year (exit ts) ---")
        by_y: dict[str, list[float]] = defaultdict(list)
        for r in rows:
            y = r["ts"][:4] if len(r["ts"]) >= 4 else "?"
            by_y[y].append(r["pnl_r"])
        for y in sorted(by_y.keys()):
            pnls = by_y[y]
            s = sum(pnls)
            print(f"  {y}: n={len(pnls):3}  net_R={s:+7.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
