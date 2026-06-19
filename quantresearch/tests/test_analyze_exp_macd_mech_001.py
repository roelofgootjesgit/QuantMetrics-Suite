"""Regression tests for EXP-MACD-MECH-001 analytics helpers."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def _load_analysis_module():
    suite_root = Path(__file__).resolve().parents[2]
    for path in (
        suite_root / "quantbuild",
        suite_root / "quantbuild" / "src",
        suite_root / "quantresearch",
    ):
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
    script = suite_root / "quantresearch" / "scripts" / "analyze_exp_macd_mech_001.py"
    spec = importlib.util.spec_from_file_location("analyze_exp_macd_mech_001", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


macd_analysis = _load_analysis_module()


def test_forward_return_universe_uses_t8_horizon_and_trade_direction() -> None:
    n_bars = 18
    close = np.arange(n_bars, dtype=float)
    index = pd.date_range("2026-01-01", periods=n_bars, freq="15min")
    data = pd.DataFrame(
        {
            "close": close,
            "high": close + 0.1,
            "low": close - 0.1,
        },
        index=index,
    )
    atr = pd.Series(np.ones(n_bars), index=index)

    long_outcomes = macd_analysis._forward_return_universe(data, atr, "LONG", 8)
    short_outcomes = macd_analysis._forward_return_universe(data, atr, "SHORT", 8)

    assert long_outcomes[9] == 4.0
    assert short_outcomes[9] == -4.0
    assert np.isnan(long_outcomes[10])
    assert np.isnan(short_outcomes[10])
