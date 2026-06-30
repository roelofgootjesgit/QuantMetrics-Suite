"""Regression tests for EXP-MACD-MECH-001 analytics helpers."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.analyze_exp_macd_mech_001 import _direction_aware_permutation_test


def _frame_with_close(close: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=len(close), freq="15min", tz="UTC")
    return pd.DataFrame(
        {
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": [1] * len(close),
        },
        index=idx,
    )


def test_direction_aware_permutation_scores_short_favorable_moves() -> None:
    close = [100.0] * 24
    close[10] = 100.0
    close[18] = 96.0
    data = _frame_with_close(close)
    atr = pd.Series(np.ones(len(data)), index=data.index)

    result = _direction_aware_permutation_test(
        data,
        atr,
        signal_indices=[10],
        signal_directions=["SHORT"],
        horizon=8,
        n_permutations=100,
        seed=7,
    )

    assert result["n_signals"] == 1
    assert result["observed_hit_rate"] == pytest.approx(2.0)


def test_direction_aware_permutation_preserves_mixed_signal_directions() -> None:
    close = [100.0] * 32
    close[4] = 100.0
    close[12] = 104.0
    close[16] = 100.0
    close[24] = 96.0
    data = _frame_with_close(close)
    atr = pd.Series(np.ones(len(data)), index=data.index)

    result = _direction_aware_permutation_test(
        data,
        atr,
        signal_indices=[4, 16],
        signal_directions=["LONG", "SHORT"],
        horizon=8,
        n_permutations=100,
        seed=11,
    )

    assert result["n_signals"] == 2
    assert result["observed_hit_rate"] == pytest.approx(2.0)


def test_direction_aware_permutation_rejects_mismatched_signal_metadata() -> None:
    data = _frame_with_close([100.0] * 16)
    atr = pd.Series(np.ones(len(data)), index=data.index)

    with pytest.raises(ValueError, match="length mismatch"):
        _direction_aware_permutation_test(
            data,
            atr,
            signal_indices=[1],
            signal_directions=[],
        )
