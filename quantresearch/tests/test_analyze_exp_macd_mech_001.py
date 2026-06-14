from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "analyze_exp_macd_mech_001.py"
_SPEC = importlib.util.spec_from_file_location("analyze_exp_macd_mech_001", _SCRIPT_PATH)
assert _SPEC is not None
analyze_exp_macd_mech_001 = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(analyze_exp_macd_mech_001)


def _trend_frame(n: int = 12) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC")
    close = 100.0 + np.arange(n, dtype=float)
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
        },
        index=dates,
    )


def test_directional_permutation_observed_uses_short_sign() -> None:
    data = _trend_frame()
    atr = pd.Series(np.ones(len(data)), index=data.index)
    entries = [
        {"bar_index": 1, "direction": "LONG"},
        {"bar_index": 1, "direction": "SHORT"},
    ]

    perm = analyze_exp_macd_mech_001._directional_permutation_test(
        data,
        atr,
        entries,
        horizon=2,
        n_permutations=20,
        seed=7,
    )

    assert perm["n_signals"] == 2
    assert perm["observed_hit_rate"] == 0.0


def test_directional_permutation_excludes_tail_without_horizon() -> None:
    data = _trend_frame()
    atr = pd.Series(np.ones(len(data)), index=data.index)
    entries = [
        {"bar_index": 1, "direction": "LONG"},
        {"bar_index": len(data) - 1, "direction": "LONG"},
    ]

    perm = analyze_exp_macd_mech_001._directional_permutation_test(
        data,
        atr,
        entries,
        horizon=2,
        n_permutations=20,
        seed=7,
    )

    assert perm["n_signals"] == 1
    assert perm["observed_hit_rate"] == 1.0
