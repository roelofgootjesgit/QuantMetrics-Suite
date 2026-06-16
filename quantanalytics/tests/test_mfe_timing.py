"""Tests for MFE timing report (mfe_timing_v1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quantmetrics_analytics.analysis.mfe_timing import (
    SCHEMA_VERSION,
    build_mfe_timing_report,
    run_mfe_timing_for_events,
    write_mfe_timing_report,
)


def _ev(run_id: str, exit_tag: str, pnl: float, bars: int | None) -> dict:
    return {
        "event_type": "trade_closed",
        "run_id": run_id,
        "payload": {
            "exit": exit_tag,
            "pnl_r": pnl,
            "bars_to_mfe": bars,
            "mfe_r": 1.0,
        },
    }


def test_build_report_buckets_and_schema():
    rid = "qb_run_test"
    events = [
        _ev(rid, "TP", 1.5, 1),
        _ev(rid, "TP", 2.0, 2),
        _ev(rid, "TP", 1.9, 4),
        _ev(rid, "TP", 1.8, 10),
        _ev(rid, "SL", -1.0, 3),
    ]
    rep = build_mfe_timing_report(
        events,
        run_id=rid,
        experiment_id="EXP-TEST",
        jsonl_paths=[Path("dummy.jsonl")],
    )
    assert rep["schema_version"] == SCHEMA_VERSION
    assert rep["run_id"] == rid
    assert rep["experiment_id"] == "EXP-TEST"
    assert rep["tp_trades"]["n"] == 4
    b = rep["buckets"]
    assert b["early_1_2"]["n"] == 2
    assert b["mid_3_6"]["n"] == 1
    assert b["late_7_plus"]["n"] == 1
    assert b["early_1_2"]["mean_r"] == pytest.approx(1.75)
    dist = rep["tp_trades"]["bars_to_mfe_distribution_tp_only"]
    assert dist is not None
    assert dist["min"] == 1
    assert dist["max"] == 10


def test_write_and_roundtrip_no_nan(tmp_path: Path):
    events = [_ev("r1", "TP", 1.0, 5)]
    rep = build_mfe_timing_report(events, run_id="r1", experiment_id="e", jsonl_paths=[])
    p = write_mfe_timing_report(rep, output_dir=tmp_path, run_id="r1")
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["schema_version"] == SCHEMA_VERSION
    json.dumps(data, allow_nan=False)  # must not raise


def test_write_report_sanitizes_run_id_filename(tmp_path: Path):
    rep = build_mfe_timing_report([], run_id="../evil", experiment_id="e", jsonl_paths=[])
    p = write_mfe_timing_report(rep, output_dir=tmp_path, run_id="../evil")

    assert p.parent == tmp_path
    assert p.name == "evil_mfe_timing_report.json"
    assert not (tmp_path.parent / "evil_mfe_timing_report.json").exists()


def test_run_mfe_timing_for_events_resolves_run_id(tmp_path: Path):
    events = [_ev("qb_x", "TP", 1.1, 2), _ev("qb_x", "TP", 1.2, 8)]
    path, rep = run_mfe_timing_for_events(
        events,
        [tmp_path / "f.jsonl"],
        run_id_explicit="qb_x",
        experiment_id="EXP",
        output_dir=tmp_path,
    )
    assert path.name == "qb_x_mfe_timing_report.json"
    assert rep["buckets"]["early_1_2"]["n"] == 1
    assert path.is_file()
