"""Regression tests for parquet cache refresh semantics."""
from __future__ import annotations

import pandas as pd

import src.quantbuild.io.parquet_loader as parquet_loader


def test_save_merged_parquet_preserves_history_and_updates_overlap(monkeypatch, tmp_path):
    existing = pd.DataFrame(
        {
            "open": [1.0, 2.0, 3.0],
            "high": [1.1, 2.1, 3.1],
            "low": [0.9, 1.9, 2.9],
            "close": [1.0, 2.0, 3.0],
            "volume": [10, 20, 30],
        },
        index=pd.date_range("2024-01-01", periods=3, freq="15min"),
    )
    fetched = pd.DataFrame(
        {
            "open": [30.0, 4.0],
            "high": [30.1, 4.1],
            "low": [29.9, 3.9],
            "close": [30.0, 4.0],
            "volume": [300, 40],
        },
        index=pd.date_range("2024-01-01 00:30", periods=2, freq="15min"),
    )
    saved: dict[str, pd.DataFrame] = {}

    monkeypatch.setattr(parquet_loader, "load_parquet", lambda *args, **kwargs: existing.copy())
    monkeypatch.setattr(
        parquet_loader,
        "save_parquet",
        lambda base_path, symbol, timeframe, data: saved.setdefault("data", data.copy()),
    )

    merged = parquet_loader._save_merged_parquet(tmp_path, "EURUSD", "15m", fetched)

    assert list(merged.index) == list(pd.date_range("2024-01-01", periods=4, freq="15min"))
    assert float(merged.loc[pd.Timestamp("2024-01-01 00:30"), "close"]) == 30.0
    assert float(merged.loc[pd.Timestamp("2024-01-01 00:45"), "close"]) == 4.0
    assert saved["data"].equals(merged)
