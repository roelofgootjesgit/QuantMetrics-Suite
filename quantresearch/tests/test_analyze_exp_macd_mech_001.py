"""Tests for EXP-MACD-MECH-001 analysis helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


def _load_macd_analysis_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "analyze_exp_macd_mech_001.py"
    spec = importlib.util.spec_from_file_location("analyze_exp_macd_mech_001", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_directional_permutation_preserves_short_signal_direction() -> None:
    mod = _load_macd_analysis_module()
    long_outcomes = np.array([-1.0, -1.0, -1.0, 0.0, 0.0, 0.0])
    short_outcomes = np.array([1.0, 1.0, 1.0, 0.0, 0.0, 0.0])
    result = mod._directional_permutation_test(
        long_outcomes,
        short_outcomes,
        np.array([0, 1, 2]),
        ["SHORT", "SHORT", "SHORT"],
        n_permutations=100,
        seed=7,
    )
    assert result["observed_hit_rate"] == 1.0
    assert result["n_signals"] == 3
