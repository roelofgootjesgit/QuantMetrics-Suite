"""Tests for EXP-MACD-MECH analysis wiring."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from analyze_exp_macd_mech_001 import _directional_t8_permutation_test  # noqa: E402


def _bars(n: int = 20) -> pd.DataFrame:
    close = np.arange(n, dtype=float)
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 0.1,
            "low": close - 0.1,
            "close": close,
        },
        index=pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC"),
    )


def test_directional_permutation_uses_short_sign() -> None:
    data = _bars()
    atr = pd.Series(np.ones(len(data)), index=data.index)
    signals = [{"bar_index": 0, "direction": "SHORT"}]

    result = _directional_t8_permutation_test(data, atr, signals, n_permutations=20, seed=1)

    assert result["observed_hit_rate"] == pytest.approx(-4.0)
    assert result["n_signals"] == 1


def test_directional_permutation_includes_valid_tail_t8_signal() -> None:
    data = _bars()
    atr = pd.Series(np.ones(len(data)), index=data.index)
    signals = [{"bar_index": len(data) - 9, "direction": "LONG"}]

    result = _directional_t8_permutation_test(data, atr, signals, n_permutations=20, seed=1)

    assert result["observed_hit_rate"] == pytest.approx(4.0)
    assert result["n_signals"] == 1
