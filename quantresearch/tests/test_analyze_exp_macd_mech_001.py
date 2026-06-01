"""Tests for EXP-MACD-MECH-001 analytics helpers."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import analyze_exp_macd_mech_001 as macd_analysis  # noqa: E402


def _bars(closes: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=len(closes), freq="15min", tz="UTC")
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c + 0.1 for c in closes],
            "low": [c - 0.1 for c in closes],
            "close": closes,
        },
        index=idx,
    )


def test_directional_permutation_scores_short_signals_as_short_wins() -> None:
    data = _bars([10.0, 9.0, 8.0, 7.0, 6.0])
    atr = pd.Series([1.0] * len(data), index=data.index)
    entries = [{"bar_index": 0, "direction": "SHORT"}]

    result = macd_analysis._directional_t8_permutation_test(
        data,
        atr,
        entries,
        horizon=1,
        n_permutations=20,
        seed=7,
    )

    assert result["observed_hit_rate"] == pytest.approx(1.0)
    assert result["baseline_mean_hit_rate"] == pytest.approx(1.0)
    assert result["n_signals"] == 1


def test_directional_permutation_excludes_signals_without_horizon() -> None:
    data = _bars([10.0, 9.0, 8.0])
    atr = pd.Series([1.0] * len(data), index=data.index)
    entries = [{"bar_index": len(data) - 1, "direction": "SHORT"}]

    result = macd_analysis._directional_t8_permutation_test(
        data,
        atr,
        entries,
        horizon=1,
        n_permutations=20,
        seed=7,
    )

    assert result["observed_hit_rate"] == 0.0
    assert result["p_value"] == 1.0
    assert result["n_signals"] == 0
