from __future__ import annotations

import importlib.util
import json
import os
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "quantmetrics_os" / "scripts" / "collect_run_artifact.py"


def _load_collector():
    spec = importlib.util.spec_from_file_location("collect_run_artifact", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_quantlog_run(quantbuild_root: Path, run_id: str, payload: dict[str, str] | None = None) -> None:
    runs_dir = quantbuild_root / "data" / "quantlog_events" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    event = payload or {"run_id": run_id}
    (runs_dir / f"{run_id}.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")


def test_collect_refuses_to_overwrite_different_run_without_slot(tmp_path: Path) -> None:
    collector = _load_collector()
    quantbuild_root = tmp_path / "quantbuild"
    quantmetrics_os_root = tmp_path / "quantmetrics_os"
    _write_quantlog_run(quantbuild_root, "run_a", {"run_id": "run_a"})
    _write_quantlog_run(quantbuild_root, "run_b", {"run_id": "run_b"})

    dest = collector.collect(
        experiment_id="EXP-TEST",
        role="variant",
        run_id="run_a",
        quantbuild_root=quantbuild_root,
        quantmetrics_os_root=quantmetrics_os_root,
        config_yaml=None,
        resolved_config_yaml=None,
        bundle_analytics=False,
        analytics_output_dir=None,
        analytics_recent_seconds=900,
    )

    with pytest.raises(FileExistsError):
        collector.collect(
            experiment_id="EXP-TEST",
            role="variant",
            run_id="run_b",
            quantbuild_root=quantbuild_root,
            quantmetrics_os_root=quantmetrics_os_root,
            config_yaml=None,
            resolved_config_yaml=None,
            bundle_analytics=False,
            analytics_output_dir=None,
            analytics_recent_seconds=900,
        )

    assert json.loads((dest / "quantlog_events.jsonl").read_text(encoding="utf-8"))["run_id"] == "run_a"


def test_collect_run_slot_keeps_multi_run_artifacts_separate(tmp_path: Path) -> None:
    collector = _load_collector()
    quantbuild_root = tmp_path / "quantbuild"
    quantmetrics_os_root = tmp_path / "quantmetrics_os"
    _write_quantlog_run(quantbuild_root, "run_xauusd", {"run_id": "run_xauusd"})
    _write_quantlog_run(quantbuild_root, "run_gbpusd", {"run_id": "run_gbpusd"})

    first = collector.collect(
        experiment_id="EXP-003",
        role="variant",
        run_id="run_xauusd",
        quantbuild_root=quantbuild_root,
        quantmetrics_os_root=quantmetrics_os_root,
        config_yaml=None,
        resolved_config_yaml=None,
        bundle_analytics=False,
        analytics_output_dir=None,
        analytics_recent_seconds=900,
        run_slot="XAUUSD",
    )
    second = collector.collect(
        experiment_id="EXP-003",
        role="variant",
        run_id="run_gbpusd",
        quantbuild_root=quantbuild_root,
        quantmetrics_os_root=quantmetrics_os_root,
        config_yaml=None,
        resolved_config_yaml=None,
        bundle_analytics=False,
        analytics_output_dir=None,
        analytics_recent_seconds=900,
        run_slot="GBPUSD",
    )

    assert first == quantmetrics_os_root / "runs" / "EXP-003" / "variant" / "XAUUSD"
    assert second == quantmetrics_os_root / "runs" / "EXP-003" / "variant" / "GBPUSD"
    assert json.loads((first / "run_info.json").read_text(encoding="utf-8"))["run_slot"] == "XAUUSD"
    assert json.loads((second / "run_info.json").read_text(encoding="utf-8"))["run_id"] == "run_gbpusd"


def test_collect_canonical_analytics_reports_match_current_run_id(tmp_path: Path) -> None:
    collector = _load_collector()
    quantbuild_root = tmp_path / "quantbuild"
    quantmetrics_os_root = tmp_path / "quantmetrics_os"
    analytics_dir = tmp_path / "analytics"
    analytics_dir.mkdir()
    run_id = "qb_run_current"
    other_run_id = "qb_run_other"
    _write_quantlog_run(quantbuild_root, run_id)

    now = time.time()
    files = {
        f"{other_run_id}_inference_report.json": {"run_id": other_run_id, "kind": "newer-other"},
        f"{run_id}_inference_report.json": {"run_id": run_id, "kind": "current"},
        "inference_report.json": {"run_id": "stale-canonical", "kind": "ambiguous"},
        f"{other_run_id}_mfe_timing_report.json": {"run_id": other_run_id, "kind": "newer-other"},
        f"{run_id}_mfe_timing_report.json": {"run_id": run_id, "kind": "current"},
    }
    for index, (name, payload) in enumerate(files.items()):
        path = analytics_dir / name
        path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        os.utime(path, (now - index, now - index))

    dest = collector.collect(
        experiment_id="EXP-TEST",
        role="variant",
        run_id=run_id,
        quantbuild_root=quantbuild_root,
        quantmetrics_os_root=quantmetrics_os_root,
        config_yaml=None,
        resolved_config_yaml=None,
        bundle_analytics=True,
        analytics_output_dir=analytics_dir,
        analytics_recent_seconds=900,
    )

    copied_inference = json.loads((dest / "analytics" / "inference_report.json").read_text(encoding="utf-8"))
    copied_mfe = json.loads((dest / "analytics" / "mfe_timing_report.json").read_text(encoding="utf-8"))
    assert copied_inference["run_id"] == run_id
    assert copied_mfe["run_id"] == run_id
    assert (dest / "analytics" / f"{other_run_id}_inference_report.json").is_file()
