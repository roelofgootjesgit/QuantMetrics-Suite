"""Causal HTF→LTF alignment: no intra-hour look-ahead."""
from datetime import datetime
from unittest.mock import patch

import pandas as pd

from src.quantbuild.backtest.engine import _apply_h1_gate
from src.quantbuild.data.htf_align import align_completed_htf, infer_htf_bar_duration
from src.quantbuild.strategy_modules.ict.structure_labels import (
    BULLISH_STRUCTURE,
    RANGE,
)
from src.quantbuild.strategy_modules.regime.detector import REGIME_COMPRESSION, REGIME_TREND, RegimeDetector


def test_align_completed_htf_holds_prior_hour_until_close():
    """14:00 H1 is not knowable at 14:15; 15:00 M15 may use it."""
    h1 = pd.Series(
        [False, True],
        index=pd.to_datetime(["2026-01-05 13:00", "2026-01-05 14:00"]),
    )
    m15 = pd.date_range("2026-01-05 13:00", periods=9, freq="15min")
    aligned = align_completed_htf(h1, m15)

    # 13:00 H1 completes at 14:00
    assert pd.isna(aligned.loc[pd.Timestamp("2026-01-05 13:45")])
    assert bool(aligned.loc[pd.Timestamp("2026-01-05 14:00")]) is False
    assert bool(aligned.loc[pd.Timestamp("2026-01-05 14:15")]) is False
    assert bool(aligned.loc[pd.Timestamp("2026-01-05 14:45")]) is False
    # 14:00 H1 completes at 15:00
    assert bool(aligned.loc[pd.Timestamp("2026-01-05 15:00")]) is True


def test_open_ffill_would_leak_current_hour():
    """Document the bug: naive ffill marks 14:15 with the still-open 14:00 H1."""
    h1 = pd.Series(
        [False, True],
        index=pd.to_datetime(["2026-01-05 13:00", "2026-01-05 14:00"]),
    )
    m15 = pd.date_range("2026-01-05 13:00", periods=9, freq="15min")
    leaked = h1.reindex(m15, method="ffill")
    assert bool(leaked.loc[pd.Timestamp("2026-01-05 14:15")]) is True
    causal = align_completed_htf(h1, m15)
    assert bool(causal.loc[pd.Timestamp("2026-01-05 14:15")]) is False


def test_infer_duration_uses_median_spacing():
    idx = pd.date_range("2026-01-05 00:00", periods=5, freq="1h")
    assert infer_htf_bar_duration(idx) == pd.Timedelta(hours=1)


def test_h1_gate_blocks_until_hour_closes():
    """SQE H1 gate must not admit 14:15 on a 14:00 H1 bullish flip."""
    m15 = pd.date_range("2026-01-05 13:00", periods=9, freq="15min")
    entries = pd.Series(True, index=m15)
    h1_idx = pd.date_range("2026-01-04 00:00", periods=40, freq="1h")
    h1_df = pd.DataFrame(
        {"open": 2000.0, "high": 2001.0, "low": 1999.0, "close": 2000.0},
        index=h1_idx,
    )
    flip = pd.Timestamp("2026-01-05 14:00")

    def _fake_structure(df, _cfg, inplace=False):
        out = df if inplace else df.copy()
        # Hours before 14:00 stay non-bullish; 14:00 flips (only knowable at 15:00)
        bull = out.index >= flip
        out["in_bullish_structure"] = bull
        out["in_bearish_structure"] = ~bull
        return out

    with patch("src.quantbuild.backtest.engine.load_parquet", return_value=h1_df), patch(
        "src.quantbuild.backtest.engine.add_structure_context", side_effect=_fake_structure
    ):
        filtered = _apply_h1_gate(
            entries,
            pd.DataFrame({"close": 2000.0}, index=m15),
            "LONG",
            base_path="unused",
            symbol="XAUUSD",
            start=datetime(2026, 1, 5),
            end=datetime(2026, 1, 6),
            sqe_cfg={"structure_context": {"lookback": 30, "pivot_bars": 2}},
        )

    assert bool(filtered.loc[pd.Timestamp("2026-01-05 14:15")]) is False
    assert bool(filtered.loc[pd.Timestamp("2026-01-05 15:00")]) is True


def test_regime_h1_structure_does_not_leak_into_open_hour():
    """RANGE on the 14:00 H1 must not force 14:15 M15 into compression."""
    m15 = pd.date_range("2026-01-05 13:00", periods=9, freq="15min")
    # Wide range so ATR ratio stays well above compression_threshold
    data = pd.DataFrame(
        {
            "open": 2000.0,
            "high": 2060.0,
            "low": 1940.0,
            "close": 2000.0,
        },
        index=m15,
    )
    h1_idx = pd.date_range("2026-01-04 00:00", periods=40, freq="1h")
    h1 = pd.DataFrame(
        {"open": 2000.0, "high": 2001.0, "low": 1999.0, "close": 2000.0},
        index=h1_idx,
    )
    range_from = pd.Timestamp("2026-01-05 14:00")

    def _fake_structure(df, _cfg, inplace=False):
        out = df if inplace else df.copy()
        labels = pd.Series(
            [RANGE if ts >= range_from else BULLISH_STRUCTURE for ts in out.index],
            index=out.index,
        )
        out["structure_label"] = labels
        out["in_bullish_structure"] = labels == BULLISH_STRUCTURE
        out["in_bearish_structure"] = False
        return out

    detector = RegimeDetector(
        {
            "atr_period": 2,
            "atr_sma_period": 2,
            "expansion_threshold": 99.0,
            "compression_threshold": 0.01,
            "structure_lookback": 2,
            "structure_pivot_bars": 1,
        }
    )
    with patch(
        "src.quantbuild.strategy_modules.regime.detector.add_structure_context",
        side_effect=_fake_structure,
    ):
        regimes = detector.classify(data, h1)

    assert regimes.loc[pd.Timestamp("2026-01-05 14:15")] == REGIME_TREND
    assert regimes.loc[pd.Timestamp("2026-01-05 15:00")] == REGIME_COMPRESSION
