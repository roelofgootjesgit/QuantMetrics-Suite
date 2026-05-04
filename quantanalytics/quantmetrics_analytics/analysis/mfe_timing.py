"""TP-trade MFE timing slice: ``bars_to_mfe`` vs ``pnl_r`` (schema ``mfe_timing_v1``)."""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quantmetrics_analytics.analysis.r_series_input import resolve_inference_run_id

SCHEMA_VERSION = "mfe_timing_v1"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _extract_tp_rows(events: list[dict[str, Any]], run_id: str) -> list[dict[str, Any]]:
    """Rows from ``trade_closed`` with TP exit only."""
    rid = str(run_id).strip()
    rows: list[dict[str, Any]] = []
    for ev in events:
        if ev.get("event_type") != "trade_closed":
            continue
        if str(ev.get("run_id", "")).strip() != rid:
            continue
        pl = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
        exit_tag = pl.get("exit") or pl.get("exit_tag")
        if str(exit_tag or "").strip().upper() != "TP":
            continue
        rows.append(
            {
                "pnl_r": pl.get("pnl_r"),
                "bars_to_mfe": pl.get("bars_to_mfe"),
                "mfe_r": pl.get("mfe_r"),
            }
        )
    return rows


def _bucket_key(bars_to_mfe: Any) -> str:
    if bars_to_mfe is None:
        return "null"
    try:
        b = int(bars_to_mfe)
    except (TypeError, ValueError):
        return "null"
    if b <= 2:
        return "early_1_2"
    if b <= 6:
        return "mid_3_6"
    return "late_7_plus"


def _stats(vals: list[float]) -> dict[str, Any]:
    if not vals:
        return {"n": 0, "mean_r": None, "median_r": None}
    return {
        "n": len(vals),
        "mean_r": float(statistics.mean(vals)),
        "median_r": float(statistics.median(vals)),
    }


def build_mfe_timing_report(
    events: list[dict[str, Any]],
    *,
    run_id: str,
    experiment_id: str,
    jsonl_paths: list[Path],
) -> dict[str, Any]:
    """Build the canonical ``mfe_timing_v1`` dict (no file I/O)."""
    tp = _extract_tp_rows(events, run_id)

    pnl_list: list[float] = []
    for t in tp:
        v = t.get("pnl_r")
        if v is None:
            continue
        try:
            pnl_list.append(float(v))
        except (TypeError, ValueError):
            continue

    buckets: dict[str, list[float]] = defaultdict(list)
    for t in tp:
        v = t.get("pnl_r")
        if v is None:
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        buckets[_bucket_key(t.get("bars_to_mfe"))].append(fv)

    order = ("early_1_2", "mid_3_6", "late_7_plus", "null")
    buckets_out: dict[str, Any] = {}
    for key in order:
        buckets_out[key] = _stats(buckets.get(key, []))

    bars_numeric: list[int] = []
    for t in tp:
        b = t.get("bars_to_mfe")
        if b is None:
            continue
        try:
            bars_numeric.append(int(b))
        except (TypeError, ValueError):
            continue

    dist: dict[str, Any] | None
    if bars_numeric:
        dist = {
            "min": int(min(bars_numeric)),
            "median": float(statistics.median(bars_numeric)),
            "max": int(max(bars_numeric)),
        }
    else:
        dist = None

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utcnow_iso(),
        "run_id": str(run_id),
        "experiment_id": str(experiment_id or "").strip() or "unknown",
        "input": {
            "jsonl_paths": [str(p.resolve()) for p in jsonl_paths],
            "trade_closed_events_seen": sum(
                1
                for e in events
                if e.get("event_type") == "trade_closed"
                and str(e.get("run_id", "")).strip() == str(run_id).strip()
            ),
        },
        "filter": {
            "exit_payload_keys": ["exit", "exit_tag"],
            "tp_token": "TP",
        },
        "tp_trades": {
            "n": len(tp),
            "pnl_r_available": len(pnl_list),
            "bars_to_mfe_distribution_tp_only": dist,
        },
        "buckets": buckets_out,
        "bucket_definitions": {
            "early_1_2": "bars_to_mfe <= 2 (non-null)",
            "mid_3_6": "3 <= bars_to_mfe <= 6",
            "late_7_plus": "bars_to_mfe >= 7",
            "null": "bars_to_mfe missing or non-integer",
        },
    }


def write_mfe_timing_report(report: dict[str, Any], *, output_dir: Path, run_id: str) -> Path:
    """Write ``{run_id}_mfe_timing_report.json`` under ``output_dir``."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{run_id}_mfe_timing_report.json"
    path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return path


def run_mfe_timing_for_events(
    events: list[dict[str, Any]],
    jsonl_paths: list[Path],
    *,
    run_id_explicit: str | None,
    experiment_id: str,
    output_dir: Path,
) -> tuple[Path, dict[str, Any]]:
    run_id = resolve_inference_run_id(events, run_id_explicit)
    report = build_mfe_timing_report(
        events,
        run_id=run_id,
        experiment_id=experiment_id,
        jsonl_paths=jsonl_paths,
    )
    path = write_mfe_timing_report(report, output_dir=output_dir, run_id=run_id)
    return path, report


def format_mfe_timing_text_summary(report: dict[str, Any]) -> str:
    """Short Markdown-friendly block for inclusion in combined text reports."""
    tp_n = int((report.get("tp_trades") or {}).get("n") or 0)
    dist = (report.get("tp_trades") or {}).get("bars_to_mfe_distribution_tp_only")
    lines = [
        "MFE timing (TP trades, bars_to_mfe vs pnl_r)",
        f"- schema: {report.get('schema_version')}",
        f"- TP trades: {tp_n}",
    ]
    if isinstance(dist, dict):
        lines.append(
            f"- bars_to_mfe (TP only): min={dist.get('min')} median={dist.get('median')} max={dist.get('max')}"
        )
    buckets = report.get("buckets") or {}
    lines.append("- buckets (mean_r | median_r | n):")
    for key in ("early_1_2", "mid_3_6", "late_7_plus", "null"):
        b = buckets.get(key) or {}
        n = b.get("n", 0)
        mr = b.get("mean_r")
        med = b.get("median_r")
        lines.append(f"  - {key}: mean_r={mr} median_r={med} n={n}")
    return "\n".join(lines) + "\n"
