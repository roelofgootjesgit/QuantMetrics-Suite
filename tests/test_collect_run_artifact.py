from __future__ import annotations

import json
import os
import time
from pathlib import Path

from quantmetrics_os.scripts.collect_run_artifact import collect


def test_collect_keeps_non_current_run_mfe_reports(tmp_path: Path) -> None:
    qb_root = tmp_path / "quantbuild"
    qmos_root = tmp_path / "quantmetrics_os"
    runs_dir = qb_root / "data" / "quantlog_events" / "runs"
    runs_dir.mkdir(parents=True)
    (runs_dir / "run_b.jsonl").write_text('{"event_type":"trade_closed"}\n', encoding="utf-8")

    analytics_out = tmp_path / "output_rapport"
    analytics_out.mkdir()
    old_report = analytics_out / "run_a_mfe_timing_report.json"
    current_report = analytics_out / "run_b_mfe_timing_report.json"
    old_report.write_text(json.dumps({"run_id": "run_a"}), encoding="utf-8")
    current_report.write_text(json.dumps({"run_id": "run_b"}), encoding="utf-8")
    now = time.time()
    old_time = now - 10
    old_report.touch()
    current_report.touch()
    os.utime(old_report, (old_time, old_time))

    dest = collect(
        experiment_id="EXP",
        role="variant",
        run_id="run_b",
        quantbuild_root=qb_root,
        quantmetrics_os_root=qmos_root,
        config_yaml=None,
        resolved_config_yaml=None,
        bundle_analytics=True,
        analytics_output_dir=analytics_out,
        analytics_recent_seconds=900,
    )

    analytics_dest = dest / "analytics"
    assert json.loads((analytics_dest / "mfe_timing_report.json").read_text(encoding="utf-8"))["run_id"] == "run_b"
    assert json.loads((analytics_dest / "run_a_mfe_timing_report.json").read_text(encoding="utf-8"))["run_id"] == "run_a"
