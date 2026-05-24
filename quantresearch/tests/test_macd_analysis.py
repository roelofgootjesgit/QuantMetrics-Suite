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


def test_directional_permutation_inputs_flip_short_returns() -> None:
    dates = pd.date_range("2024-01-01", periods=6, freq="15min", tz="UTC")
    close = np.array([10.0, 9.0, 8.0, 7.0, 6.0, 5.0])
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

    outcomes, signal_indices = analysis._directional_permutation_inputs(
        data,
        atr_series,
        [
            {"bar_index": 0, "direction": "SHORT"},
            {"bar_index": 1, "direction": "LONG"},
        ],
        horizon=2,
    )

    assert signal_indices.tolist() == [len(data), 1]
    assert outcomes[signal_indices].tolist() == [1.0, -1.0]
