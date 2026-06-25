from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "analyze_exp_macd_mech_001.py"
_SPEC = importlib.util.spec_from_file_location("analyze_exp_macd_mech_001", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)


def _ohlc_from_close(close: np.ndarray) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=len(close), freq="15min", tz="UTC")
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 0.1,
            "low": close - 0.1,
            "close": close,
        },
        index=dates,
    )


def test_directional_permutation_scores_short_signals_as_shorts() -> None:
    close = np.linspace(100.0, 80.5, 40)
    data = _ohlc_from_close(close)
    atr = pd.Series(np.ones(len(data)), index=data.index)
    signals = [{"bar_index": i, "direction": "SHORT"} for i in (2, 6, 10, 14, 18)]

    result = _MOD._directional_permutation_test(
        data,
        atr,
        signals,
        horizon=8,
        n_permutations=100,
        seed=7,
    )

    assert result["n_signals"] == len(signals)
    assert result["observed_hit_rate"] == pytest.approx(2.0)


def test_directional_permutation_preserves_mixed_signal_directions() -> None:
    close = np.array(
        [
            100.0,
            100.0,
            101.0,
            101.0,
            102.0,
            102.0,
            101.0,
            101.0,
            100.0,
            100.0,
        ],
        dtype=float,
    )
    data = _ohlc_from_close(close)
    atr = pd.Series(np.ones(len(data)), index=data.index)
    signals = [
        {"bar_index": 0, "direction": "LONG"},
        {"bar_index": 4, "direction": "SHORT"},
    ]

    result = _MOD._directional_permutation_test(
        data,
        atr,
        signals,
        horizon=4,
        n_permutations=50,
        seed=3,
    )

    assert result["n_signals"] == 2
    assert result["observed_hit_rate"] == pytest.approx(1.0)
