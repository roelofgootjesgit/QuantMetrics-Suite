"""Tests for EXP-MACD-MECH-001 analytics helpers."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


def _load_analysis_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "analyze_exp_macd_mech_001.py"
    spec = importlib.util.spec_from_file_location("analyze_exp_macd_mech_001", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_directional_permutation_scores_short_signals_as_short_returns():
    module = _load_analysis_module()
    dates = pd.date_range("2024-01-01", periods=6, freq="15min", tz="UTC")
    close = np.array([100.0, 101.0, 100.0, 99.0, 98.0, 97.0])
    data = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.1,
            "low": close - 0.1,
            "close": close,
        },
        index=dates,
    )
    atr_series = pd.Series(1.0, index=dates)
    entries = [
        {"bar_index": 0, "direction": "LONG"},
        {"bar_index": 1, "direction": "SHORT"},
    ]

    result = module._directional_permutation_test(
        data,
        atr_series,
        entries,
        horizon=1,
        n_permutations=20,
        seed=1,
    )

    assert result["n_signals"] == 2
    assert result["observed_hit_rate"] == pytest.approx(0.5)
