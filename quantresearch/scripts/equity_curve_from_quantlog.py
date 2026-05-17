#!/usr/bin/env python3
"""Reconstruct cumulative R equity curve from trade_closed in a QuantLog JSONL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Cumulative pnl_r curve from trade_closed events")
    ap.add_argument("jsonl", type=Path, help="Path to quantlog_events.jsonl")
    ap.add_argument("--kill-threshold", type=float, default=10.0, help="R drawdown from peak (engine default)")
    args = ap.parse_args()

    trades: list[tuple[str, float]] = []
    for line in args.jsonl.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        if e.get("event_type") != "trade_closed":
            continue
        p = e.get("payload") or {}
        trades.append((e["timestamp_utc"], float(p.get("pnl_r") or 0.0)))
    trades.sort(key=lambda x: x[0])

    cum = 0.0
    peak = 0.0
    max_dd = 0.0
    print(f"{'idx':>4} | {'timestamp':<24} | {'pnl_r':>7} | {'cum_R':>8} | {'peak':>7} | {'dd_from_peak':>12}")
    for i, (ts, r) in enumerate(trades, 1):
        cum += r
        if cum > peak:
            peak = cum
        dd = peak - cum
        if dd > max_dd:
            max_dd = dd
        flag = ""
        if dd >= args.kill_threshold:
            flag = " <- >= kill DD from peak"
        print(f"{i:4} | {ts[:24]:<24} | {r:+7.2f} | {cum:+8.2f} | {peak:+7.2f} | {dd:12.2f}{flag}")

    print()
    print(f"n={len(trades)} final_cum_R={cum:.4f} peak_R={peak:.4f} max_dd_from_peak_R={max_dd:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
