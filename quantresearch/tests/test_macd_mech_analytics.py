"""Regression tests for EXP-MACD-MECH-001 analytics helpers."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


def _load_macd_analysis_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "analyze_exp_macd_mech_001.py"
    spec = importlib.util.spec_from_file_location("analyze_exp_macd_mech_001", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_directional_permutation_scores_short_signals_as_shorts():
    module = _load_macd_analysis_module()
    long_returns = np.zeros(20, dtype=float)
    short_returns = np.zeros(20, dtype=float)
    long_returns[2] = 1.0
    short_returns[5] = 1.0
    long_returns[5] = -1.0
    signals = [
        {"bar_index": 2, "direction": "LONG"},
        {"bar_index": 5, "direction": "SHORT"},
    ]

    result = module._directional_permutation_test(
        long_returns,
        short_returns,
        signals,
        n_permutations=100,
        seed=7,
    )

    assert result["observed_hit_rate"] == 1.0
    assert result["n_signals"] == 2
