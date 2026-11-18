"""DATA-002 I4 (#133): owner quarantine CLI — COPY default, --move, never delete.

Offline only. Does not touch real owner cache. Does not import unmerged I2.
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path

import pandas as pd
import pytest

from src.quantbuild.io import parquet_loader
from src.quantbuild.io.legacy_cache_quarantine import (
    QUARANTINE_DIRNAME,
    QuarantineError,
    inventory_snapshot,
    run_quarantine,
    scan_legacy_cache,
    sidecar_path_for_parquet,
)
from src.quantbuild.io.research_source_policy import ResearchSourcePolicyError


def _ohlcv(n: int = 3) -> pd.DataFrame:
    from datetime import datetime, timedelta, timezone

    last = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    idx = pd.date_range(last - timedelta(hours=n - 1), periods=n, freq="h")
    return pd.DataFrame(
        {
            "open": [1.0 + i for i in range(n)],
            "high": [1.5 + i for i in range(n)],
            "low": [0.5 + i for i in range(n)],
            "close": [1.2 + i for i in range(n)],
            "volume": [10.0 + i for i in range(n)],
        },
        index=idx,
    )


def _seed_legacy_parquet(base: Path, symbol: str = "XAUUSD", tf: str = "15m") -> Path:
    d = base / symbol
    d.mkdir(parents=True, exist_ok=True)
    pq = d / f"{tf}.parquet"
    _ohlcv(5).to_parquet(pq, compression="snappy")
    return pq


def test_i4_does_not_import_unmerged_i2_provenance_cache() -> None:
    import src.quantbuild.io.legacy_cache_quarantine as qc

    # Docstring may mention provenance_cache; executable imports must not.
    import_lines = [
        ln for ln in inspect.getsource(qc).splitlines()
        if ln.lstrip().startswith(("import ", "from "))
    ]
    assert not any("provenance_cache" in ln for ln in import_lines)
    # Stable I2 naming without import.
    pq = Path("XAUUSD/15m.parquet")
    assert sidecar_path_for_parquet(pq).name == "15m.provenance.json"


def test_load_ensure_never_call_quarantine_source_guard() -> None:
    src = inspect.getsource(parquet_loader)
    assert "legacy_cache_quarantine" not in src
    assert "quarantine_legacy_cache" not in src
    assert QUARANTINE_DIRNAME not in src


def test_no_delete_api_mutant_guard() -> None:
    import src.quantbuild.io.legacy_cache_quarantine as qc

    src = inspect.getsource(qc)
    assert "unlink(" not in src
    assert "os.remove" not in src
    assert "rmtree" not in src
    assert "never delete" in src.lower() or "Never delete" in src

    # CLI must not expose --delete.
    from pathlib import Path as P
    import importlib.util

    script = P(__file__).resolve().parents[1] / "scripts" / "quarantine_legacy_cache.py"
    spec = importlib.util.spec_from_file_location("quarantine_legacy_cache_i4", script)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    help_txt = mod.build_parser().format_help()
    assert "--delete" not in help_txt
    assert "--move" in help_txt


def test_rejected_ensure_deny_inventory_unchanged(tmp_path: Path) -> None:
    """Rejected load/ensure DENY must not mutate inventory (path/size/mtime)."""
    base = tmp_path / "cache"
    _seed_legacy_parquet(base)
    before = inventory_snapshot(base)
    with pytest.raises(ResearchSourcePolicyError):
        parquet_loader.ensure_data(
            symbol="XAUUSD",
            timeframe="15m",
            base_path=base,
            period_days=60,
            source="yfinance",
        )
    assert inventory_snapshot(base) == before
    # load of sparse legacy file also must not create quarantine artifacts.
    before2 = inventory_snapshot(base)
    _ = parquet_loader.load_parquet(base, "XAUUSD", "15m")
    assert inventory_snapshot(base) == before2
    assert not (base / QUARANTINE_DIRNAME).exists()


def test_dry_run_inventory_unchanged(tmp_path: Path) -> None:
    base = tmp_path / "cache"
    _seed_legacy_parquet(base)
    orphan = base / "XAUUSD" / ".15m.parquet.tmp.999"
    orphan.write_bytes(b"orphan-bytes")
    before = inventory_snapshot(base)
    report = run_quarantine(base, dry_run=True, move=False)
    assert inventory_snapshot(base) == before
    assert report.dry_run is True
    assert report.mode == "copy"
    kinds = {f.kind for f in report.findings}
    assert "legacy_parquet_no_sidecar" in kinds
    assert "orphan_temp" in kinds
    assert all(not a.performed for a in report.actions)


def test_default_copy_preserves_original(tmp_path: Path) -> None:
    base = tmp_path / "cache"
    pq = _seed_legacy_parquet(base)
    before_live = inventory_snapshot(base / "XAUUSD")
    raw = pq.read_bytes()
    report = run_quarantine(base, dry_run=False, move=False)
    assert report.mode == "copy"
    assert pq.is_file()
    assert pq.read_bytes() == raw
    # Live symbol tree inventory unchanged (quarantine is sibling under base).
    assert inventory_snapshot(base / "XAUUSD") == before_live
    q_files = list((base / QUARANTINE_DIRNAME).rglob("*"))
    assert any(p.is_file() and p.name.endswith(".quarantined") for p in q_files)
    assert any(p.name.endswith(".note.json") for p in q_files)
    note = next(p for p in q_files if p.name.endswith(".note.json"))
    body = json.loads(note.read_text(encoding="utf-8"))
    assert body["action"] == "copy"
    assert body["content_sha256"]


def test_move_requires_opt_in_and_preserves_bytes(tmp_path: Path) -> None:
    base = tmp_path / "cache"
    pq = _seed_legacy_parquet(base)
    raw = pq.read_bytes()
    # Default path is copy, not move.
    report_copy = run_quarantine(base, dry_run=True, move=False)
    assert report_copy.mode == "copy"

    report = run_quarantine(base, dry_run=False, move=True)
    assert report.mode == "move"
    assert not pq.exists()  # moved out of live path
    dest = Path(report.actions[0].dest_path)
    assert dest.is_file()
    assert dest.read_bytes() == raw  # never deleted — retained in quarantine
    note = json.loads(Path(report.actions[0].note_path).read_text(encoding="utf-8"))
    assert note["action"] == "move"


def test_orphan_temp_quarantine_copy_and_move(tmp_path: Path) -> None:
    base = tmp_path / "cache"
    sym = base / "XAUUSD"
    sym.mkdir(parents=True)
    orphan = sym / ".15m.parquet.tmp.42"
    orphan.write_bytes(b"crash-gap-temp")
    before = inventory_snapshot(sym)

    dry = run_quarantine(base, dry_run=True)
    assert inventory_snapshot(sym) == before
    assert any(f.kind == "orphan_temp" for f in dry.findings)

    run_quarantine(base, dry_run=False, move=False)
    assert orphan.is_file()  # COPY preserves orphan in place
    assert orphan.read_bytes() == b"crash-gap-temp"
    assert list((base / QUARANTINE_DIRNAME / "_orphans").rglob("*.quarantined"))

    # MOVE orphan out of live tree into quarantine (still not deleted).
    run_quarantine(base, dry_run=False, move=True)
    assert not orphan.exists()
    moved = list((base / QUARANTINE_DIRNAME / "_orphans").rglob("*.quarantined"))
    assert moved
    assert any(p.read_bytes() == b"crash-gap-temp" for p in moved)


def test_scan_skips_quarantine_tree_and_pairs_with_sidecar(tmp_path: Path) -> None:
    base = tmp_path / "cache"
    pq = _seed_legacy_parquet(base)
    # Simulated I2 pair: sidecar present → not a legacy finding.
    sidecar_path_for_parquet(pq).write_text("{}", encoding="utf-8")
    # Already-quarantined noise must be ignored.
    q = base / QUARANTINE_DIRNAME / "XAUUSD"
    q.mkdir(parents=True)
    (q / "noise.parquet.abc.quarantined").write_bytes(b"x")

    findings = scan_legacy_cache(base)
    assert findings == []


def test_cli_dry_run_and_execute_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib.util

    script = Path(__file__).resolve().parents[1] / "scripts" / "quarantine_legacy_cache.py"
    spec = importlib.util.spec_from_file_location("qleg_i4_cli", script)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    base = tmp_path / "cache"
    _seed_legacy_parquet(base)
    before = inventory_snapshot(base)
    rc = mod.main(["--base-path", str(base), "--dry-run"])
    assert rc == 0
    assert inventory_snapshot(base) == before

    rc2 = mod.main(["--base-path", str(base), "--execute"])
    assert rc2 == 0
    assert (base / "XAUUSD" / "15m.parquet").is_file()
    assert list((base / QUARANTINE_DIRNAME).rglob("*.quarantined"))


def test_quarantine_error_rejects_unknown_mode(tmp_path: Path) -> None:
    from src.quantbuild.io.legacy_cache_quarantine import quarantine_finding, CacheFinding

    f = CacheFinding(
        kind="legacy_parquet_no_sidecar",
        symbol="XAUUSD",
        relative_path="XAUUSD/15m.parquet",
        absolute_path=str(tmp_path / "missing.parquet"),
        size=0,
        mtime_ns=0,
    )
    with pytest.raises(QuarantineError, match="never delete|unsupported mode"):
        quarantine_finding(tmp_path, f, mode="delete")  # type: ignore[arg-type]
