"""
Rolling Year-Slice Runner
-------------------------
Runs calendar-year backtests for a YAML config, aggregates medians, writes JSON.

Usage (from quantbuild/):
    python scripts/rolling_year_runner.py --config configs/strict_prod_v2.yaml --years 2022 2023 2024 2025
    python scripts/rolling_year_runner.py --config configs/strict_prod_v2.yaml --compare configs/strict_prod_v2.yaml
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.quantbuild.backtest.engine import run_backtest
from src.quantbuild.config import load_config
from src.quantbuild.models.trade import TradeResult

logging.disable(logging.WARNING)

DEFAULT_YEARS = list(range(2022, 2026))


def _profit_factor(pnls: list[float]) -> float:
    """Gross profit / gross loss from signed R multiples (includes TIMEOUT outcomes)."""
    gw = sum(p for p in pnls if p > 0)
    gl = abs(sum(p for p in pnls if p < 0))
    if gl <= 0:
        return float("inf") if gw > 0 else 0.0
    return gw / gl


def run_year(config_path: str, year: int) -> dict:
    cfg = load_config(config_path)

    cfg.setdefault("backtest", {})
    cfg["backtest"]["start_date"] = f"{year}-01-01"
    cfg["backtest"]["end_date"] = f"{year}-12-31"

    cfg.setdefault("quantlog", {})
    cfg["quantlog"]["enabled"] = True
    cfg["quantlog"]["run_id"] = f"rolling_{Path(config_path).stem}_{year}"

    trades = run_backtest(cfg)

    if not trades:
        return {
            "year": year,
            "trades": 0,
            "mean_r": None,
            "win_rate": None,
            "profit_factor": None,
            "max_dd_r": None,
            "total_r": None,
            "verdict": "NO_TRADES",
        }

    wins = [t for t in trades if t.result == TradeResult.WIN]
    pnls = [t.profit_r for t in trades]

    pf = _profit_factor(pnls)

    equity = peak = 0.0
    max_dd = 0.0
    for p in pnls:
        equity += p
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)

    mean_r = sum(pnls) / len(pnls)
    win_rate = len(wins) / len(trades)

    return {
        "year": year,
        "trades": len(trades),
        "mean_r": round(mean_r, 3),
        "win_rate": round(win_rate, 3),
        "profit_factor": round(pf, 2) if pf != float("inf") else None,
        "max_dd_r": round(max_dd, 2),
        "total_r": round(sum(pnls), 2),
        "verdict": "OK",
    }


def aggregate(results: list) -> dict:
    valid = [r for r in results if r["verdict"] == "OK"]
    if not valid:
        return {}
    n = len(valid)
    positive_years = sum(1 for r in valid if r["mean_r"] and r["mean_r"] > 0)
    pf_vals = [r["profit_factor"] for r in valid if r["profit_factor"] is not None]
    median_pf = round(statistics.median(pf_vals), 2) if pf_vals else None

    return {
        "years_tested": len(results),
        "years_with_data": n,
        "years_positive": positive_years,
        "median_trades": statistics.median(r["trades"] for r in valid),
        "median_mean_r": round(statistics.median(r["mean_r"] for r in valid), 3),
        "median_wr": round(statistics.median(r["win_rate"] for r in valid), 3),
        "median_pf": median_pf,
        "median_max_dd": round(statistics.median(r["max_dd_r"] for r in valid), 2),
        "total_r_all": round(sum(r["total_r"] for r in valid), 2),
        "consistency": f"{positive_years}/{n} jaren positief",
    }


def print_table(label: str, results: list, agg: dict) -> None:
    print(f"\n{'='*72}")
    print(f"  {label}")
    print(f"{'='*72}")
    print(
        f"  {'Jaar':<6} {'Trades':>6} {'Mean R':>8} {'WR':>6} "
        f"{'PF':>6} {'Max DD':>8} {'Total R':>8}  Status"
    )
    print(f"  {'-'*68}")
    for r in results:
        if r["verdict"] == "NO_TRADES":
            print(
                f"  {r['year']:<6} {'—':>6} {'—':>8} {'—':>6} "
                f"{'—':>6} {'—':>8} {'—':>8}  NO_TRADES"
            )
        else:
            mark = "+" if r["mean_r"] and r["mean_r"] > 0 else "-"
            pfs = f"{r['profit_factor']:>6.2f}" if r["profit_factor"] is not None else "   inf"
            print(
                f"  {r['year']:<6} {r['trades']:>6} {r['mean_r']:>+8.3f} "
                f"{r['win_rate']:>5.1%} {pfs} "
                f"{r['max_dd_r']:>+8.2f} {r['total_r']:>+8.2f}  {mark}"
            )
    print(f"  {'-'*68}")
    if agg:
        mpf = agg.get("median_pf")
        mpfs = f"{mpf:6.2f}" if mpf is not None else "   inf"
        print(
            f"  {'MEDIAAN':<6} {agg['median_trades']:>6.0f} "
            f"{agg['median_mean_r']:>+8.3f} {agg['median_wr']:>5.1%} "
            f"{mpfs} {agg['median_max_dd']:>+8.2f} "
            f"{agg['total_r_all']:>+8.2f}"
        )
        print(f"\n  Consistentie: {agg['consistency']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Rolling calendar-year backtests")
    parser.add_argument("--config", required=True)
    parser.add_argument("--compare", default=None)
    parser.add_argument("--years", nargs="+", type=int, default=DEFAULT_YEARS)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    qb_root = Path(__file__).resolve().parents[1]
    print(f"\n[rolling_year_runner] cwd should be quantbuild root; qb_root={qb_root}")
    print(f"[rolling_year_runner] config={args.config}  jaren={args.years}")

    exp_results: list = []
    for year in args.years:
        print(f"  {year}...", end=" ", flush=True)
        r = run_year(args.config, year)
        exp_results.append(r)
        if r["verdict"] == "OK":
            print(f"{r['trades']} trades  mean_r={r['mean_r']}")
        else:
            print("NO_TRADES")

    exp_agg = aggregate(exp_results)
    print_table(Path(args.config).stem, exp_results, exp_agg)

    base_results = None
    base_agg = None
    if args.compare:
        print(f"\n[rolling_year_runner] baseline={args.compare}")
        base_results = []
        for year in args.years:
            print(f"  baseline {year}...", end=" ", flush=True)
            r = run_year(args.compare, year)
            base_results.append(r)
            if r["verdict"] == "OK":
                print(f"{r['trades']} trades  mean_r={r['mean_r']}")
            else:
                print("NO_TRADES")
        base_agg = aggregate(base_results)
        print_table(f"BASELINE: {Path(args.compare).stem}", base_results, base_agg)

        print("\n  DELTA (experiment - baseline)")
        print(f"  {'Jaar':<6} {'dTrades':>8} {'dMean R':>9} {'dPF':>7} {'dTot R':>9}")
        print(f"  {'-'*44}")
        for e, b in zip(exp_results, base_results):
            if e["verdict"] == "OK" and b["verdict"] == "OK":
                dpf = (e["profit_factor"] or 0) - (b["profit_factor"] or 0)
                if e["profit_factor"] is None or b["profit_factor"] is None:
                    dpf_str = "    nan"
                else:
                    dpf_str = f"{dpf:+7.2f}"
                print(
                    f"  {e['year']:<6} {e['trades'] - b['trades']:>+8} "
                    f"{e['mean_r'] - b['mean_r']:>+9.3f} "
                    f"{dpf_str} "
                    f"{e['total_r'] - b['total_r']:>+9.2f}"
                )

    output: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": args.config,
        "years": args.years,
        "results": exp_results,
        "aggregate": exp_agg,
    }
    if base_results is not None:
        output["baseline_config"] = args.compare
        output["baseline_results"] = base_results
        output["baseline_aggregate"] = base_agg

    out_path = args.out or f"reports/rolling/{Path(args.config).stem}_rolling.json"
    outp = Path(out_path)
    if not outp.is_absolute():
        outp = qb_root / outp
    outp.parent.mkdir(parents=True, exist_ok=True)
    with open(outp, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n  Output: {outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
