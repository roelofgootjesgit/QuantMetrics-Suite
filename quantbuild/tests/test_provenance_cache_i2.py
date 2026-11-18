"""DATA-002 I2 (#133): atomic parquet/sidecar protocol + fail-closed readers.

Offline / deterministic only. No network, no quarantine/move/delete on DENY.
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path

import pandas as pd
import pytest

from src.quantbuild.io import parquet_loader
from src.quantbuild.io.provenance_cache import (
    ProvenanceDenyError,
    ProvenanceIdentityError,
    inventory_snapshot,
    load_sidecar_fail_closed,
    require_owner_dta_for_htf,
    sha256_file,
    sidecar_path_for,
    validate_sidecar_against_parquet,
)
from src.quantbuild.io.timezone_canon import UnverifiedNaiveTimezoneError


def _ohlcv(n: int = 3, start: str = "2024-07-01") -> pd.DataFrame:
    idx = pd.date_range(start, periods=n, freq="h")
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


def _prov(**overrides) -> dict:
    base = {
        "symbol": "XAUUSD",
        "instrument": "spot_xauusd",
        "timeframe": "15m",
        "source": "dukascopy",
        "single_source": True,
        "offer_side": "bid",
        "timezone_storage": "unknown",
        "index_semantics": "unknown",
        "writer": "test",
        "schema_version": "data002-i2-v1",
    }
    base.update(overrides)
    return base


def test_same_source_refresh_pass(tmp_path: Path) -> None:
    base = tmp_path / "cache"
    p1 = _prov()
    parquet_loader.save_parquet(base, "XAUUSD", "15m", _ohlcv(3), provenance=p1)
    meta1 = load_sidecar_fail_closed(base, "XAUUSD", "15m")
    parquet_loader.save_parquet(base, "XAUUSD", "15m", _ohlcv(4), provenance=p1)
    meta2 = load_sidecar_fail_closed(base, "XAUUSD", "15m")
    assert meta2["source"] == "dukascopy"
    assert meta2["content_sha256"] != meta1["content_sha256"]
    df = parquet_loader.load_parquet(base, "XAUUSD", "15m")
    assert len(df) == 4


def test_cross_source_refresh_deny_originals_untouched(tmp_path: Path) -> None:
    base = tmp_path / "cache"
    p1 = _prov(source="dukascopy")
    parquet_loader.save_parquet(base, "XAUUSD", "15m", _ohlcv(3), provenance=p1)
    before = inventory_snapshot(base / "XAUUSD")
    sc_before = sidecar_path_for(base, "XAUUSD", "15m").read_text(encoding="utf-8")
    pq = parquet_loader.path_for(base, "XAUUSD", "15m")
    digest_before = sha256_file(pq)

    p2 = _prov(source="yfinance", instrument="gc_f_futures", offer_side="unknown")
    with pytest.raises(ProvenanceIdentityError, match="identity mismatch"):
        parquet_loader.save_parquet(base, "XAUUSD", "15m", _ohlcv(5), provenance=p2)

    assert inventory_snapshot(base / "XAUUSD") == before
    assert sidecar_path_for(base, "XAUUSD", "15m").read_text(encoding="utf-8") == sc_before
    assert sha256_file(pq) == digest_before


def test_crash_gap_between_replaces_deny_no_silent_recovery(tmp_path: Path) -> None:
    base = tmp_path / "cache"
    parquet_loader.save_parquet(base, "XAUUSD", "15m", _ohlcv(3), provenance=_prov())
    pq = parquet_loader.path_for(base, "XAUUSD", "15m")
    sc = sidecar_path_for(base, "XAUUSD", "15m")
    old_sc = sc.read_text(encoding="utf-8")

    # Simulate crash after parquet replace, before sidecar replace.
    _ohlcv(8).to_parquet(pq, compression="snappy")
    assert sha256_file(pq) != json.loads(old_sc)["content_sha256"]
    sc.write_text(old_sc, encoding="utf-8")  # stale sidecar

    with pytest.raises(ProvenanceDenyError, match="mismatch|content_sha256"):
        parquet_loader.load_parquet(base, "XAUUSD", "15m")

    # No silent recovery via rewrite over crash-gap.
    with pytest.raises(ProvenanceDenyError, match="invalid|crash-gap|mismatch"):
        parquet_loader.save_parquet(base, "XAUUSD", "15m", _ohlcv(2), provenance=_prov())


def test_hash_mismatch_and_missing_sidecar_deny(tmp_path: Path) -> None:
    base = tmp_path / "cache"
    parquet_loader.save_parquet(base, "XAUUSD", "15m", _ohlcv(3), provenance=_prov())
    sc = sidecar_path_for(base, "XAUUSD", "15m")
    meta = json.loads(sc.read_text(encoding="utf-8"))
    meta["content_sha256"] = "0" * 64
    sc.write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(ProvenanceDenyError, match="mismatch"):
        validate_sidecar_against_parquet(
            parquet_loader.path_for(base, "XAUUSD", "15m"), sc
        )

    sc.unlink()
    with pytest.raises(ProvenanceDenyError, match="sidecar missing"):
        parquet_loader.load_parquet(base, "XAUUSD", "15m")


def test_rejected_load_inventory_unchanged(tmp_path: Path) -> None:
    base = tmp_path / "cache"
    parquet_loader.save_parquet(base, "XAUUSD", "15m", _ohlcv(3), provenance=_prov())
    sc = sidecar_path_for(base, "XAUUSD", "15m")
    meta = json.loads(sc.read_text(encoding="utf-8"))
    meta["content_sha256"] = "deadbeef" * 8
    sc.write_text(json.dumps(meta), encoding="utf-8")

    before = inventory_snapshot(base)
    with pytest.raises(ProvenanceDenyError):
        parquet_loader.load_parquet(base, "XAUUSD", "15m")
    after = inventory_snapshot(base)
    assert after == before


def test_owner_attested_fields_not_overwritten_by_writer(tmp_path: Path) -> None:
    from src.quantbuild.io.provenance_cache import write_parquet_atomic_with_sidecar

    base = tmp_path / "cache"
    frame = _ohlcv(3)
    parquet_loader.save_parquet(base, "XAUUSD", "15m", frame, provenance=_prov())
    sc = sidecar_path_for(base, "XAUUSD", "15m")
    pq = parquet_loader.path_for(base, "XAUUSD", "15m")
    meta = json.loads(sc.read_text(encoding="utf-8"))
    meta["attested_by"] = "owner"
    meta["attested_at_utc"] = "2026-11-18T00:00:00Z"
    meta["method"] = "dta-manual"
    meta["index_semantics"] = "bar_open_utc"
    sc.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # Same parquet bytes + matching identity: writer invents attested_by — must not stick.
    raw = pq.read_bytes()
    evil_same = _prov(
        attested_by="attacker",
        index_semantics="bar_open_utc",  # must match attested identity to refresh
    )

    def _copy_same_bytes(tmp: Path) -> None:
        tmp.write_bytes(raw)

    write_parquet_atomic_with_sidecar(
        base_path=base,
        symbol="XAUUSD",
        timeframe="15m",
        frame_writer=_copy_same_bytes,
        provenance=evil_same,
    )
    after = json.loads(sc.read_text(encoding="utf-8"))
    assert after["attested_by"] == "owner"
    assert after["method"] == "dta-manual"
    assert after["index_semantics"] == "bar_open_utc"

    # Different bytes with matching writer identity: old attestation cleared; attacker stripped.
    evil_refresh = _prov(attested_by="attacker", index_semantics="bar_open_utc")
    parquet_loader.save_parquet(
        base, "XAUUSD", "15m", _ohlcv(5), provenance=evil_refresh
    )
    after2 = json.loads(sc.read_text(encoding="utf-8"))
    assert "attested_by" not in after2
    assert after2.get("attested_by") != "attacker"
    assert after2["index_semantics"] == "bar_open_utc"


def test_htf_requires_owner_dta_bound_to_content_hash(tmp_path: Path) -> None:
    base = tmp_path / "cache"
    parquet_loader.save_parquet(base, "XAUUSD", "15m", _ohlcv(3), provenance=_prov())
    meta = load_sidecar_fail_closed(base, "XAUUSD", "15m")
    with pytest.raises(ProvenanceDenyError, match="attested_by"):
        require_owner_dta_for_htf(meta, meta["content_sha256"])

    with pytest.raises(ProvenanceDenyError, match="HTF DENY"):
        parquet_loader.load_parquet(
            base, "XAUUSD", "15m", require_htf_owner_dta=True
        )

    sc = sidecar_path_for(base, "XAUUSD", "15m")
    body = json.loads(sc.read_text(encoding="utf-8"))
    body["attested_by"] = "owner"
    body["attested_at_utc"] = "2026-11-18T00:00:00Z"
    body["method"] = "dta-manual"
    sc.write_text(json.dumps(body), encoding="utf-8")
    ok = parquet_loader.load_parquet(
        base, "XAUUSD", "15m", require_htf_owner_dta=True
    )
    assert len(ok) == 3

    # Changed hash vs attestation → DENY.
    with pytest.raises(ProvenanceDenyError, match="changed|unknown|content_sha256"):
        require_owner_dta_for_htf(body, "0" * 64)


def test_dukascopy_naive_time_column_mutant_killed() -> None:
    """Non-DatetimeIndex frame with naive time column must not use utc=True."""
    frame = pd.DataFrame(
        {
            "time": ["2024-07-01 09:30:00", "2024-07-01 10:30:00"],
            "open": [1.0, 2.0],
            "high": [1.1, 2.1],
            "low": [0.9, 1.9],
            "close": [1.05, 2.05],
            "volume": [1.0, 2.0],
        }
    )
    src = inspect.getsource(parquet_loader._prepare_dukascopy_frame_index)
    assert "pd.to_datetime(out.index)" in src
    assert "pd.to_datetime(out.index, utc=True)" not in src
    assert "to_datetime(out.index, utc=" not in src

    # Forbidden mutant: utc=True would silently accept naive as UTC.
    mutant = frame.set_index("time")
    mutant_index = pd.to_datetime(mutant.index, utc=True)
    assert mutant_index.tz is not None  # mutant "succeeds"

    with pytest.raises(UnverifiedNaiveTimezoneError, match="do not assume UTC"):
        parquet_loader._prepare_dukascopy_frame_index(frame)


def test_save_parquet_requires_provenance(tmp_path: Path) -> None:
    with pytest.raises(Exception, match="provenance"):
        parquet_loader.save_parquet(tmp_path, "XAUUSD", "15m", _ohlcv(2))
