from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "analyze_exp_macd_mech_001.py"
_SPEC = importlib.util.spec_from_file_location("analyze_exp_macd_mech_001", _SCRIPT_PATH)
assert _SPEC is not None
macd_analysis = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(macd_analysis)


def test_directional_permutation_observed_return_uses_signal_direction():
    dates = pd.date_range("2024-01-01", periods=8, freq="15min", tz="UTC")
    close = np.arange(10.0, 18.0)
    data = pd.DataFrame(
        {
            "open": close,
            "high": close,
            "low": close,
            "close": close,
        },
        index=dates,
    )
    atr = pd.Series(1.0, index=dates)

    result = macd_analysis._directional_permutation_test(
        data,
        atr,
        [{"bar_index": 0, "direction": "SHORT"}],
        horizon=1,
        n_permutations=10,
        seed=1,
    )

    assert result["observed_hit_rate"] == -0.5
