"""Regression: collect_run_artifact must not attach another run's inference report."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from collect_run_artifact import collect  # noqa: E402


def test_collect_keeps_matching_run_inference_not_older_sibling(tmp_path: Path) -> None:
    qb = tmp_path / "quantbuild"
    qos = tmp_path / "quantmetrics_os"
    analytics = tmp_path / "analytics_out"
    (qb / "data" / "quantlog_events" / "runs").mkdir(parents=True)
    analytics.mkdir(parents=True)
    qos.mkdir(parents=True)

    run_id = "qb_run_current"
    older_id = "qb_run_older"
    jsonl = qb / "data" / "quantlog_events" / "runs" / f"{run_id}.jsonl"
    jsonl.write_text('{"event_type":"run_started","run_id":"%s"}\n' % run_id, encoding="utf-8")

    older = analytics / f"{older_id}_inference_report.json"
    current = analytics / f"{run_id}_inference_report.json"
    older.write_text(json.dumps({"run_id": older_id, "verdict": "FAIL"}), encoding="utf-8")
    time.sleep(0.05)
    current.write_text(json.dumps({"run_id": run_id, "verdict": "PASS"}), encoding="utf-8")
    # Make older file appear newer so naive newest-first + overwrite would pick FAIL
    # if run_id filtering were absent — bump older mtime after current write.
    time.sleep(0.05)
    older.write_text(json.dumps({"run_id": older_id, "verdict": "FAIL"}), encoding="utf-8")

    dest = collect(
        experiment_id="EXP-TEST",
        role="variant",
        run_id=run_id,
        quantbuild_root=qb,
        quantmetrics_os_root=qos,
        config_yaml=None,
        resolved_config_yaml=None,
        bundle_analytics=True,
        analytics_output_dir=analytics,
        analytics_recent_seconds=900,
    )

    report = json.loads((dest / "analytics" / "inference_report.json").read_text(encoding="utf-8"))
    assert report["run_id"] == run_id
    assert report["verdict"] == "PASS"
