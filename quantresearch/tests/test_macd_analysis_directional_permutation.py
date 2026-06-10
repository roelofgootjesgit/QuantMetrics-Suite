"""Regression tests for EXP-MACD-MECH-001 directional analytics."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "analyze_exp_macd_mech_001.py"
_SPEC = importlib.util.spec_from_file_location("analyze_exp_macd_mech_001", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)


def test_directional_permutation_observed_respects_short_direction() -> None:
    long_outcomes = np.array([0.0, 1.0, -2.0, 0.5])
    short_outcomes = -long_outcomes

    result = _MOD._directional_permutation_test(
        long_outcomes,
        short_outcomes,
        np.array([1, 2]),
        ["LONG", "SHORT"],
        n_permutations=50,
        seed=7,
    )

    assert result["observed_hit_rate"] == 1.5


def test_forward_return_universe_flips_short_returns() -> None:
    close = np.arange(10.0, 0.0, -1.0)
    data = pd.DataFrame({"close": close})
    atr = pd.Series([0.5] * len(data))

    long_returns = _MOD._forward_return_universe_r(data, atr, direction="LONG", horizon=8)
    short_returns = _MOD._forward_return_universe_r(data, atr, direction="SHORT", horizon=8)

    assert long_returns[0] == -8.0
    assert short_returns[0] == 8.0
