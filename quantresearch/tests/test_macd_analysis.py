"""Tests for EXP-MACD-MECH-001 post-run analytics helpers."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd


_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "analyze_exp_macd_mech_001.py"
_SPEC = importlib.util.spec_from_file_location("analyze_exp_macd_mech_001", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
analysis = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(analysis)


def test_directional_permutation_uses_short_signal_returns() -> None:
    dates = pd.date_range("2024-01-01", periods=12, freq="15min", tz="UTC")
    close = np.linspace(100.0, 90.0, len(dates))
    data = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.1,
            "low": close - 0.1,
            "close": close,
        },
        index=dates,
    )
    atr = pd.Series(1.0, index=dates)
    entries = [
        {"bar_index": 0, "direction": "SHORT"},
        {"bar_index": 1, "direction": "SHORT"},
    ]

    result = analysis._directional_permutation_test(
        data,
        atr,
        entries,
        horizon=2,
        n_permutations=20,
        seed=7,
    )

    expected = np.mean(
        [
            analysis._forward_return_r(data, atr, 0, "SHORT", 2),
            analysis._forward_return_r(data, atr, 1, "SHORT", 2),
        ]
    )
    assert result["observed_hit_rate"] == expected
    assert result["observed_hit_rate"] > 0


def test_main_without_quantlog_does_not_autoselect_latest_run(monkeypatch, tmp_path) -> None:
    calls = {}

    def fake_analyze(**kwargs):
        calls.update(kwargs)
        return {}

    monkeypatch.setattr(analysis, "analyze", fake_analyze)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "analyze_exp_macd_mech_001.py",
            "--config",
            str(tmp_path / "config.yaml"),
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert analysis.main() == 0
    assert calls["quantlog_path"] is None
