"""Exploratory TP headroom: ``mfe_r - pnl_r`` on TP exits (schema ``tp_headroom_v1``)."""

from __future__ import annotations

import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quantmetrics_analytics.analysis.r_series_input import resolve_inference_run_id

SCHEMA_VERSION = "tp_headroom_v1"

TP_SCENARIO_MULTIPLIERS: tuple[float, ...] = (1.5, 2.0, 2.5, 3.0)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _extract_tp_trades(events: list[dict[str, Any]], run_id: str) -> list[dict[str, float]]:
    """TP-only trades with numeric ``pnl_r`` and ``mfe_r``."""
    rid = str(run_id).strip()
    rows: list[dict[str, float]] = []
    for ev in events:
        if ev.get("event_type") != "trade_closed":
            continue
        if str(ev.get("run_id", "")).strip() != rid:
            continue
        pl = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
        exit_tag = pl.get("exit") or pl.get("exit_tag")
        if str(exit_tag or "").strip().upper() != "TP":
            continue
        pr = pl.get("pnl_r")
        mr = pl.get("mfe_r")
        if pr is None or mr is None:
            continue
        try:
            pnl_r = float(pr)
            mfe_r = float(mr)
        except (TypeError, ValueError):
            continue
        rows.append({"pnl_r": pnl_r, "mfe_r": mfe_r})
    return rows


def _percentile(values: list[float], p: float) -> float | None:
    """Linear interpolation percentile ``p`` in [0, 100]."""
    if not values:
        return None
    xs = sorted(values)
    n = len(xs)
    if n == 1:
        return float(xs[0])
    if p <= 0:
        return float(xs[0])
    if p >= 100:
        return float(xs[-1])
    k = (n - 1) * (p / 100.0)
    f = int(math.floor(k))
    c = int(math.ceil(k))
    if f == c:
        return float(xs[f])
    return float(xs[f] + (k - f) * (xs[c] - xs[f]))


def _headroom_distribution(headrooms: list[float]) -> dict[str, float | None]:
    if not headrooms:
        return {
            "mean": None,
            "median": None,
            "p25": None,
            "p75": None,
            "min": None,
            "max": None,
        }
    return {
        "mean": float(statistics.mean(headrooms)),
        "median": float(statistics.median(headrooms)),
        "p25": _percentile(headrooms, 25.0),
        "p75": _percentile(headrooms, 75.0),
        "min": float(min(headrooms)),
        "max": float(max(headrooms)),
    }


def _scenario_row(
    trades: list[dict[str, float]],
    tp_multiplier: float,
) -> dict[str, Any]:
    """Trades that would still hit TP at ``tp_multiplier * pnl_r`` (need ``mfe_r >=`` that)."""
    hit: list[dict[str, float]] = []
    for t in trades:
        pnl = float(t["pnl_r"])
        mfe = float(t["mfe_r"])
        threshold = tp_multiplier * pnl
        if mfe >= threshold:
            hit.append(t)
    n_hit = len(hit)
    if n_hit == 0:
        return {
            "tp_multiplier": float(tp_multiplier),
            "trades_still_hit": 0,
            "mean_r_if_hit": None,
        }
    hypothetical_r = [tp_multiplier * float(t["pnl_r"]) for t in hit]
    return {
        "tp_multiplier": float(tp_multiplier),
        "trades_still_hit": int(n_hit),
        "mean_r_if_hit": float(statistics.mean(hypothetical_r)),
    }


def build_tp_headroom_report(
    events: list[dict[str, Any]],
    *,
    run_id: str,
    experiment_id: str,
) -> dict[str, Any]:
    trades = _extract_tp_trades(events, run_id)
    headrooms = [float(t["mfe_r"]) - float(t["pnl_r"]) for t in trades]

    scenarios = [_scenario_row(trades, m) for m in TP_SCENARIO_MULTIPLIERS]

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utcnow_iso(),
        "run_id": str(run_id),
        "experiment_id": str(experiment_id or "").strip() or "unknown",
        "tp_trades_n": len(trades),
        "headroom": _headroom_distribution(headrooms),
        "tp_level_scenarios": scenarios,
    }


def write_tp_headroom_report(report: dict[str, Any], *, output_dir: Path, run_id: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{run_id}_tp_headroom_report.json"
    path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return path


def run_tp_headroom_for_events(
    events: list[dict[str, Any]],
    jsonl_paths: list[Path],
    *,
    run_id_explicit: str | None,
    experiment_id: str,
    output_dir: Path,
) -> tuple[Path, dict[str, Any]]:
    run_id = resolve_inference_run_id(events, run_id_explicit)
    report = build_tp_headroom_report(
        events,
        run_id=run_id,
        experiment_id=experiment_id,
    )
    path = write_tp_headroom_report(report, output_dir=output_dir, run_id=run_id)
    return path, report


def format_tp_headroom_text_summary(report: dict[str, Any]) -> str:
    h = report.get("headroom") or {}
    lines = [
        "TP headroom (exploratory, tp_headroom_v1)",
        f"- TP trades with mfe_r+pnl_r: {report.get('tp_trades_n')}",
        f"- headroom mean={h.get('mean')} median={h.get('median')} "
        f"p25={h.get('p25')} p75={h.get('p75')}",
    ]
    for row in report.get("tp_level_scenarios") or []:
        lines.append(
            f"  - x{row.get('tp_multiplier')}: still_hit={row.get('trades_still_hit')} "
            f"mean_r_if_hit={row.get('mean_r_if_hit')}"
        )
    return "\n".join(lines) + "\n"
