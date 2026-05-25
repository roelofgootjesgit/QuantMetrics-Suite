"""Tests for EXP-MACD-MECH-001 post-run analytics helpers."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "analyze_exp_macd_mech_001.py"
_SPEC = importlib.util.spec_from_file_location("analyze_exp_macd_mech_001", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
analysis = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(analysis)


def test_directional_permutation_uses_short_signal_returns() -> None:
    n = 12
    dates = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")
    close = np.linspace(100.0, 90.0, n)
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
