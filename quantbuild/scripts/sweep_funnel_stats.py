"""
Funnel throughput stats from sweep_research JSONL (EXP-004 herrun step 2).

Run from quantbuild/:
  python scripts/sweep_funnel_stats.py sweeps_2015.jsonl sweeps_2019.jsonl ...
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FUNNEL_ORDER = [
    "OBSERVE_NO_RECLAIM",
    "SKIP_ACCEPTANCE",
    "OBSERVE_NO_DISPLACEMENT",
    "OBSERVE_NO_MICRO_SHIFT",
    "ENTER",
]


def _year_from_path(p: Path) -> str:
    for part in p.stem.split("_"):
        if part.isdigit() and len(part) == 4:
            return part
    return p.stem


def load_events(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def funnel_counts(events: List[Dict[str, Any]]) -> Dict[str, int]:
    raw = len(events)
    c: Dict[str, int] = {d: 0 for d in FUNNEL_ORDER}
    for ev in events:
        dec = (ev.get("payload") or {}).get("decision", "UNKNOWN")
        c[dec] = c.get(dec, 0) + 1
    # survivors at each stage (cumulative through funnel)
    no_reclaim = c.get("OBSERVE_NO_RECLAIM", 0)
    after_reclaim = raw - no_reclaim
    skip_acc = c.get("SKIP_ACCEPTANCE", 0)
    after_acc = after_reclaim - skip_acc
    no_disp = c.get("OBSERVE_NO_DISPLACEMENT", 0)
    after_disp = after_acc - no_disp
    no_micro = c.get("OBSERVE_NO_MICRO_SHIFT", 0)
    enter = c.get("ENTER", 0)
    return {
        "raw_sweeps": raw,
        "after_reclaim": after_reclaim,
        "after_acceptance": after_acc,
        "after_displacement": after_disp,
        "ENTER": enter,
        "OBSERVE_NO_RECLAIM": no_reclaim,
        "SKIP_ACCEPTANCE": skip_acc,
        "OBSERVE_NO_DISPLACEMENT": no_disp,
        "OBSERVE_NO_MICRO_SHIFT": no_micro,
    }


def print_block(label: str, stats: Dict[str, int]) -> None:
    raw = stats["raw_sweeps"]
    print(f"\n=== {label} (raw={raw}) ===")
    if raw == 0:
        return
    stages = [
        ("raw sweeps", raw),
        ("after reclaim", stats["after_reclaim"]),
        ("after acceptance", stats["after_acceptance"]),
        ("after displacement", stats["after_displacement"]),
        ("ENTER", stats["ENTER"]),
    ]
    print(f"{'step':<22} {'count':>8} {'% of raw':>10}")
    for name, n in stages:
        pct = 100.0 * n / raw if raw else 0.0
        print(f"{name:<22} {n:>8} {pct:>9.1f}%")


def main() -> int:
    p = argparse.ArgumentParser(description="Funnel stats for sweep_research JSONL files")
    p.add_argument("files", nargs="+", type=Path, help="sweeps_YYYY.jsonl paths")
    args = p.parse_args()

    combined: List[Dict[str, Any]] = []
    per_year: Dict[str, List[Dict[str, Any]]] = {}

    for fp in args.files:
        path = fp if fp.is_absolute() else ROOT / fp
        evs = load_events(path)
        y = _year_from_path(path)
        per_year[y] = evs
        combined.extend(evs)

    for y in sorted(per_year.keys()):
        print_block(f"Year {y}", funnel_counts(per_year[y]))
    print_block("COMBINED", funnel_counts(combined))

    enter_total = funnel_counts(combined)["ENTER"]
    print(f"\nENTER total (combined): {enter_total}")
    if enter_total < 50:
        print("STOP: combined ENTER < 50 — throughput problem (protocol).")
        return 2
    if enter_total < 100:
        print("NOTE: combined ENTER 50–99 — LOW confidence only (protocol).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
