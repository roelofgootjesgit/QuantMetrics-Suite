"""DATA-002 I0 (#133): pyarrow is a hard root-CI requirement for Parquet tests.

No pytest.importorskip / conditional skip — missing pyarrow must fail collection
or execution. Deterministic synthetic fixture only; no market-cache / network.
"""
from __future__ import annotations

from pathlib import Path

import pyarrow as pa  # noqa: F401 — hard fail if missing (no importorskip)
import pyarrow.parquet as pq


def test_pyarrow_import_is_hard_requirement() -> None:
    """I0: import pyarrow without importorskip (mirrors pytest-socket N2 pattern)."""
    assert pa.__version__  # non-empty version string


def test_pyarrow_parquet_roundtrip_deterministic(tmp_path: Path) -> None:
    """I0: root CI executes a real Parquet write/read via pyarrow (no pandas)."""
    table = pa.table(
        {
            "bar_i": pa.array([0, 1], type=pa.int64()),
            "open": pa.array([1.0, 2.0], type=pa.float64()),
            "high": pa.array([1.5, 2.5], type=pa.float64()),
            "low": pa.array([0.5, 1.5], type=pa.float64()),
            "close": pa.array([1.2, 2.2], type=pa.float64()),
        }
    )
    path = tmp_path / "i0_fixture.parquet"
    pq.write_table(table, path)

    assert path.is_file()
    assert path.stat().st_size > 0

    loaded = pq.read_table(path)
    assert loaded.num_rows == 2
    assert loaded.column_names == ["bar_i", "open", "high", "low", "close"]
    assert loaded.column("close").to_pylist() == [1.2, 2.2]
    assert loaded.equals(table)
