"""Regression tests for EXP-MACD-MECH-001 analytics helpers."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


def _load_analyzer_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "analyze_exp_macd_mech_001.py"
    spec = importlib.util.spec_from_file_location("analyze_exp_macd_mech_001", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_directional_permutation_scores_short_signals_as_short_returns() -> None:
    analyzer = _load_analyzer_module()
    idx = pd.date_range("2024-01-01", periods=10, freq="15min", tz="UTC")
    close = np.arange(100.0, 120.0, 2.0)
    data = pd.DataFrame({"close": close}, index=idx)
    atr = pd.Series(np.ones(len(data)), index=idx)

    result = analyzer._directional_permutation_test(
        data,
        atr,
        signal_indices=[0, 1],
        signal_directions=["SHORT", "SHORT"],
        horizon=1,
        n_permutations=25,
        seed=7,
    )

    assert result["observed_hit_rate"] == -1.0
    assert result["n_signals"] == 2


def test_directional_permutation_validates_signal_alignment() -> None:
    analyzer = _load_analyzer_module()
    idx = pd.date_range("2024-01-01", periods=3, freq="15min", tz="UTC")
    data = pd.DataFrame({"close": [1.0, 2.0, 3.0]}, index=idx)
    atr = pd.Series([1.0, 1.0, 1.0], index=idx)

    with pytest.raises(ValueError, match="same length"):
        analyzer._directional_permutation_test(data, atr, [0, 1], ["LONG"], horizon=1)
