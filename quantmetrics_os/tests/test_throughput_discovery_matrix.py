"""Tests for QuantLog consolidation in the throughput-discovery matrix."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "throughput_discovery_matrix.py"


def _load_matrix():
    spec = importlib.util.spec_from_file_location("throughput_discovery_matrix", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _event(run_id: str, seq: int) -> str:
    return json.dumps(
        {
            "event_type": "trade_closed",
            "run_id": run_id,
            "source_seq": seq,
            "payload": {"pnl_r": 1.0},
        }
    ) + "\n"


def test_consolidate_does_not_truncate_emitter_written_file(tmp_path: Path) -> None:
    """consolidated_run_file writes only runs/<id>.jsonl — opening it with 'w' was data loss."""
    mod = _load_matrix()
    run_id = "qb_run_consolidated_only"
    events_root = tmp_path / "data" / "quantlog_events"
    out = events_root / "runs" / f"{run_id}.jsonl"
    out.parent.mkdir(parents=True)
    original = _event(run_id, 1) + _event(run_id, 2)
    out.write_text(original, encoding="utf-8")

    result = mod._consolidate_run_jsonl(quantbuild_root=tmp_path, run_id=run_id)

    assert result == out
    assert out.read_text(encoding="utf-8") == original
    assert out.stat().st_size == len(original.encode("utf-8"))


def test_consolidate_rebuilds_from_day_shards_without_wiping_on_failure(tmp_path: Path) -> None:
    mod = _load_matrix()
    run_id = "qb_run_from_shards"
    events_root = tmp_path / "data" / "quantlog_events"
    day = events_root / "2026-09-14"
    day.mkdir(parents=True)
    (day / "quantbuild.jsonl").write_text(
        _event(run_id, 1) + _event("other_run", 9) + _event(run_id, 2),
        encoding="utf-8",
    )

    result = mod._consolidate_run_jsonl(quantbuild_root=tmp_path, run_id=run_id)
    lines = [json.loads(line) for line in result.read_text(encoding="utf-8").splitlines() if line]
    assert [row["source_seq"] for row in lines] == [1, 2]
    assert all(row["run_id"] == run_id for row in lines)


def test_consolidate_raises_when_no_events_without_truncating_unrelated_file(tmp_path: Path) -> None:
    mod = _load_matrix()
    events_root = tmp_path / "data" / "quantlog_events"
    other = events_root / "runs" / "someone_else.jsonl"
    other.parent.mkdir(parents=True)
    other.write_text(_event("someone_else", 1), encoding="utf-8")

    with pytest.raises(RuntimeError, match="Consolidation produced 0 events"):
        mod._consolidate_run_jsonl(quantbuild_root=tmp_path, run_id="missing_run")

    assert other.read_text(encoding="utf-8") == _event("someone_else", 1)


def test_stamp_unique_variant_run_id_overrides_shared_id() -> None:
    mod = _load_matrix()
    cfg_a = {"quantlog": {"consolidated_run_file": True, "run_id": ""}}
    cfg_b = {"quantlog": {"consolidated_run_file": True, "run_id": ""}}
    a = mod._stamp_unique_variant_run_id(cfg_a, "A0_baseline")
    b = mod._stamp_unique_variant_run_id(cfg_b, "A1_no_news")
    assert a != b
    assert cfg_a["quantlog"]["run_id"] == a
    assert cfg_b["quantlog"]["run_id"] == b
    assert a.startswith("td_A0_baseline_")
    assert cfg_a["quantlog"]["consolidated_run_file"] is True
