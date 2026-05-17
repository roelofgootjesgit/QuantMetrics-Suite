#!/usr/bin/env python3
"""
Slice analysis for EXP-SLICE-BASE-2026 — no new backtest.

Reads trade_closed from existing QuantLog JSONL (BASE, V3, V4 of EXP-SQE-XAUUSD-DECON-2026):
  - BASE: WR / PF / net R by calendar year and by session (London / New York / Overlap)
  - V3:  year split (expansion-only edge stability)
  - V4:  exit tag distribution (TP / SL / TIMEOUT)

Usage (from suite root or any cwd):
  python quantresearch/scripts/slice_exp_slice_base_2026.py
  python quantresearch/scripts/slice_exp_slice_base_2026.py --suite-root C:/path/to/quantmetrics-suite
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


@dataclass
class TradeRow:
    year: int | None
    session: str | None
    regime: str
    exit_tag: str
    outcome: str
    pnl_r: float


def _parse_iso_year(ts: str) -> int | None:
    if not ts or len(ts) < 4:
        return None
    try:
        return int(ts[:4])
    except ValueError:
        return None


def load_trade_rows(jsonl: Path) -> list[TradeRow]:
    rows: list[TradeRow] = []
    if not jsonl.is_file():
        return rows
    with open(jsonl, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("event_type") != "trade_closed":
                continue
            p = ev.get("payload") or {}
            ts = ev.get("timestamp_utc") or ""
            rows.append(
                TradeRow(
                    year=_parse_iso_year(ts),
                    session=(p.get("session") or None),
                    regime=str(p.get("regime") or "").strip().lower(),
                    exit_tag=str(p.get("exit") or "unknown").upper(),
                    outcome=str(p.get("outcome") or "").upper(),
                    pnl_r=float(p.get("pnl_r") or 0.0),
                )
            )
    return rows


def _profit_factor(pnl_list: list[float]) -> float | None:
    gw = sum(x for x in pnl_list if x > 0)
    gl = sum(x for x in pnl_list if x < 0)
    if gl == 0:
        return None if gw == 0 else float("inf")
    return gw / abs(gl)


def _aggregate_year(rows: Iterable[TradeRow]) -> dict[int, dict[str, Any]]:
    by_y: dict[int, list[TradeRow]] = defaultdict(list)
    for r in rows:
        if r.year is None:
            continue
        by_y[r.year].append(r)
    out: dict[int, dict[str, Any]] = {}
    for y in sorted(by_y.keys()):
        rs = by_y[y]
        pnls = [x.pnl_r for x in rs]
        wins = sum(1 for x in rs if x.pnl_r > 0)
        n = len(rs)
        pf = _profit_factor(pnls)
        net = sum(pnls)
        out[y] = {
            "n": n,
            "net_r": round(net, 4),
            "win_rate": round(wins / n, 4) if n else 0.0,
            "profit_factor": None if pf is None else (round(pf, 4) if pf != float("inf") else "inf"),
        }
    return out


_SESSION_FOCUS = {"London", "New York", "Overlap"}


def _aggregate_session(rows: Iterable[TradeRow]) -> dict[str, dict[str, Any]]:
    by_s: dict[str, list[TradeRow]] = defaultdict(list)
    for r in rows:
        s = r.session or "unknown"
        by_s[s].append(r)
    out: dict[str, dict[str, Any]] = {}
    for s in sorted(by_s.keys()):
        rs = by_s[s]
        pnls = [x.pnl_r for x in rs]
        wins = sum(1 for x in rs if x.pnl_r > 0)
        n = len(rs)
        pf = _profit_factor(pnls)
        net = sum(pnls)
        out[s] = {
            "n": n,
            "net_r": round(net, 4),
            "win_rate": round(wins / n, 4) if n else 0.0,
            "profit_factor": None if pf is None else (round(pf, 4) if pf != float("inf") else "inf"),
        }
    return out


def _exit_breakdown(rows: Iterable[TradeRow]) -> dict[str, int]:
    c: dict[str, int] = defaultdict(int)
    for r in rows:
        c[r.exit_tag] += 1
    return dict(sorted(c.items(), key=lambda x: -x[1]))


def _md_table_years(agg: dict[int, dict[str, Any]], title: str) -> str:
    lines = [f"### {title}", "", "| Year | n | Net R | WR | PF |", "|------|---|-------|----|----|"]
    for y, d in agg.items():
        pf = d["profit_factor"]
        pf_s = "—" if pf is None else (str(pf) if pf != "inf" else "∞")
        lines.append(
            f"| {y} | {d['n']} | {d['net_r']:+.2f} | {100*d['win_rate']:.1f}% | {pf_s} |"
        )
    return "\n".join(lines) + "\n"


def _md_table_sessions(agg: dict[str, dict[str, Any]], title: str) -> str:
    lines = [f"### {title}", "", "| Session | n | Net R | WR | PF |", "|---------|---|-------|----|----|"]
    for s in ["London", "New York", "Overlap", "Asia", "unknown"]:
        if s not in agg:
            continue
        d = agg[s]
        pf = d["profit_factor"]
        pf_s = "—" if pf is None else (str(pf) if pf != "inf" else "∞")
        mark = " *" if s in _SESSION_FOCUS else ""
        lines.append(
            f"| {s}{mark} | {d['n']} | {d['net_r']:+.2f} | {100*d['win_rate']:.1f}% | {pf_s} |"
        )
    for s in sorted(agg.keys()):
        if s in ("London", "New York", "Overlap", "Asia", "unknown"):
            continue
        d = agg[s]
        pf = d["profit_factor"]
        pf_s = "—" if pf is None else (str(pf) if pf != "inf" else "∞")
        lines.append(
            f"| {s} | {d['n']} | {d['net_r']:+.2f} | {100*d['win_rate']:.1f}% | {pf_s} |"
        )
    lines.append("\n*Focus sessions for plan: London, New York, Overlap.\n")
    return "\n".join(lines)


def _md_exits(exits: dict[str, int], n_total: int) -> str:
    lines = [
        "### V4 — Exit-type distribution (trade_closed.exit)",
        "",
        "| Exit tag | Count | Share |",
        "|----------|-------|-------|",
    ]
    for tag, cnt in exits.items():
        share = f"{100*cnt/n_total:.1f}%" if n_total else "—"
        lines.append(f"| {tag} | {cnt} | {share} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="EXP-SLICE-BASE-2026 slice analysis from JSONL")
    ap.add_argument(
        "--suite-root",
        type=Path,
        default=None,
        help="QuantMetrics suite root (parent of quantmetrics_os, quantresearch).",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory (default: quantresearch/experiments/EXP-SLICE-BASE-2026)",
    )
    args = ap.parse_args()

    here = Path(__file__).resolve().parent
    quantresearch_root = here.parent
    suite_root = args.suite_root
    if suite_root is None:
        suite_root = quantresearch_root.parent
    suite_root = suite_root.resolve()

    out_dir = args.out_dir
    if out_dir is None:
        out_dir = quantresearch_root / "experiments" / "EXP-SLICE-BASE-2026"
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    runs = suite_root / "quantmetrics_os" / "runs"
    base_j = runs / "EXP-SQE-XAUUSD-DECON-2026-BASE" / "single" / "quantlog_events.jsonl"
    v3_j = runs / "EXP-SQE-XAUUSD-DECON-2026-V3" / "single" / "quantlog_events.jsonl"
    v4_j = runs / "EXP-SQE-XAUUSD-DECON-2026-V4" / "single" / "quantlog_events.jsonl"

    base_rows = load_trade_rows(base_j)
    v3_rows = load_trade_rows(v3_j)
    v4_rows = load_trade_rows(v4_j)

    metrics: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "suite_root": str(suite_root),
        "sources": {
            "BASE": str(base_j),
            "V3": str(v3_j),
            "V4": str(v4_j),
        },
        "counts": {
            "BASE_trade_closed": len(base_rows),
            "V3_trade_closed": len(v3_rows),
            "V4_trade_closed": len(v4_rows),
        },
        "BASE_by_year": _aggregate_year(base_rows),
        "BASE_by_session": _aggregate_session(base_rows),
        "V3_by_year": _aggregate_year(v3_rows),
        "V4_exit_tags": _exit_breakdown(v4_rows),
    }

    by_base_year = metrics["BASE_by_year"]
    base_years = len(by_base_year)
    base_n = sum(int(v["n"]) for v in by_base_year.values())

    interp = [
        "## Interpretation (quick)",
        "",
    ]
    if base_years <= 2 and base_n > 0:
        interp.extend(
            [
                f"- **BASE trades span only {base_years} calendar year(s)** (`n={base_n}`). ",
                "Before scaling frequency via Core(3), confirm whether this reflects **data/bar coverage** for the BASE run ",
                "(e.g. exits only through early window) vs a stable multi-year edge.",
                "",
            ]
        )
    else:
        interp.append(f"- BASE exits span **{base_years}** distinct years (`n={base_n}`).\n")

    report_lines = [
        "# EXP-SLICE-BASE-2026 — Slice report",
        "",
        "Generated from **existing** QuantLog artifacts (no new backtest).",
        "",
        f"- Generated UTC: `{metrics['generated_at_utc']}`",
        f"- Suite root: `{suite_root}`",
        "",
        "## Ordering gate",
        "",
        "This experiment **must** complete before Core(3) / portfolio frequency work: if BASE trades cluster in one or two years, downstream frequency plans rest on unstable single-instrument evidence.",
        "",
        "---",
        "",
        *interp,
        "---",
        "",
        "## BASE — By calendar year (exit `timestamp_utc`)",
        "",
        _md_table_years(metrics["BASE_by_year"], "BASE (SQE XAUUSD — EXP-SQE baseline run)"),
        "",
        "## BASE — By session (at trade exit)",
        "",
        _md_table_sessions(metrics["BASE_by_session"], "BASE"),
        "",
        "## V3 — Expansion-only — By year (critical: time stability)",
        "",
        _md_table_years(metrics["V3_by_year"], "V3 (regime_profiles.trend.skip)"),
        "",
        "## V4 — Trend-only — Exit distribution",
        "",
        _md_exits(metrics["V4_exit_tags"], len(v4_rows)),
        "",
        "---",
        "",
        "## Raw metrics JSON",
        "",
        f"See `slice_metrics.json` in this folder.",
        "",
    ]
    report_md = "\n".join(report_lines)

    (out_dir / "slice_metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (out_dir / "SLICE_REPORT.md").write_text(report_md, encoding="utf-8")

    print(f"Wrote {out_dir / 'SLICE_REPORT.md'}")
    print(f"Wrote {out_dir / 'slice_metrics.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
