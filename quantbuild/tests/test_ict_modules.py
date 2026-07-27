"""Unit tests for ICT strategy modules."""
import numpy as np
import pandas as pd
import pytest

from src.quantbuild.strategy_modules.ict.liquidity_sweep import LiquiditySweepModule
from src.quantbuild.strategy_modules.ict.displacement import DisplacementModule
from src.quantbuild.strategy_modules.ict.fair_value_gaps import FairValueGapModule
from src.quantbuild.strategy_modules.ict.market_structure_shift import MarketStructureShiftModule
from src.quantbuild.strategy_modules.ict.order_blocks import OrderBlockModule
from src.quantbuild.strategy_modules.ict.imbalance_zones import ImbalanceZonesModule
from src.quantbuild.strategy_modules.ict.structure_context import compute_structure_labels, add_structure_context


def _make_ohlcv(n: int = 100, base: float = 2000.0, seed: int = 42) -> pd.DataFrame:
    rng = np.random.RandomState(seed)
    dates = pd.date_range("2025-01-01", periods=n, freq="15min", tz="UTC")
    close = base + np.cumsum(rng.randn(n) * 2)
    high = close + rng.uniform(0.5, 3.0, n)
    low = close - rng.uniform(0.5, 3.0, n)
    opn = close + rng.randn(n) * 0.5
    return pd.DataFrame({"open": opn, "high": high, "low": low, "close": close, "volume": rng.randint(100, 1000, n)}, index=dates)


def _make_bullish_sweep_reclaim_frame() -> pd.DataFrame:
    """Flat range, swing low, sweep below, then reclaim a few bars later."""
    n = 40
    idx = pd.date_range("2025-01-01", periods=n, freq="15min", tz="UTC")
    close = np.full(n, 2000.0)
    high = np.full(n, 2002.0)
    low = np.full(n, 1998.0)
    opn = np.full(n, 2000.0)
    low[10] = 1995.0
    close[10] = 1997.0
    high[10] = 1998.0
    # Sweep bar
    low[25] = 1990.0
    high[25] = 1996.0
    close[25] = 1992.0
    opn[25] = 1995.0
    for i in (26, 27):
        low[i] = 1991.0
        high[i] = 1997.0
        close[i] = 1993.0
        opn[i] = 1992.0
    # Reclaim bar
    low[28] = 1994.0
    high[28] = 2001.0
    close[28] = 2000.0
    opn[28] = 1995.0
    return pd.DataFrame(
        {"open": opn, "high": high, "low": low, "close": close, "volume": np.full(n, 100)},
        index=idx,
    )


def _make_bullish_fvg_frame() -> pd.DataFrame:
    """3-candle bullish FVG completing on bar 5 (gap vs bar 3 high)."""
    n = 10
    idx = pd.date_range("2025-01-01", periods=n, freq="15min", tz="UTC")
    o = np.full(n, 100.0)
    h = np.full(n, 101.0)
    l = np.full(n, 99.0)
    c = np.full(n, 100.0)
    h[3], l[3], c[3] = 100.0, 98.0, 99.0
    h[4], l[4], c[4] = 103.0, 101.0, 102.0
    h[5], l[5], c[5] = 105.0, 102.5, 104.0
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "volume": np.ones(n)}, index=idx)


class TestLiquiditySweep:
    def test_output_columns(self):
        result = LiquiditySweepModule().calculate(_make_ohlcv(), {"lookback_candles": 20, "sweep_threshold_pct": 0.2, "reversal_candles": 3})
        for col in ["bullish_sweep", "bearish_sweep", "swept_low", "swept_high"]:
            assert col in result.columns

    def test_boolean_types(self):
        result = LiquiditySweepModule().calculate(_make_ohlcv(), {"lookback_candles": 20, "sweep_threshold_pct": 0.2, "reversal_candles": 3})
        assert result["bullish_sweep"].dtype == bool

    def test_check_entry(self):
        cfg = {"lookback_candles": 20, "sweep_threshold_pct": 0.2, "reversal_candles": 3}
        result = LiquiditySweepModule().calculate(_make_ohlcv(), cfg)
        assert isinstance(LiquiditySweepModule().check_entry_condition(result, 50, cfg, "LONG"), bool)

    def test_bullish_sweep_stamps_on_reclaim_not_sweep_bar(self):
        """Reclaim confirmation must not mark the earlier sweep bar (look-ahead)."""
        cfg = {"lookback_candles": 10, "sweep_threshold_pct": 0.05, "reversal_candles": 3}
        df = _make_bullish_sweep_reclaim_frame()
        full = LiquiditySweepModule().calculate(df, cfg)
        assert bool(full["bullish_sweep"].iloc[25]) is False
        assert bool(full["bullish_sweep"].iloc[28]) is True

        asof_sweep = LiquiditySweepModule().calculate(df.iloc[:26], cfg)
        assert bool(asof_sweep["bullish_sweep"].iloc[25]) is False
        asof_reclaim = LiquiditySweepModule().calculate(df.iloc[:29], cfg)
        assert bool(asof_reclaim["bullish_sweep"].iloc[28]) is True
        assert bool(asof_reclaim["bullish_sweep"].iloc[25]) is False


class TestDisplacement:
    def test_output_columns(self):
        result = DisplacementModule().calculate(_make_ohlcv(), {"min_body_pct": 70, "min_candles": 3, "min_move_pct": 1.5})
        assert "bullish_disp" in result.columns and "bearish_disp" in result.columns


class TestFairValueGaps:
    def test_output_columns(self):
        result = FairValueGapModule().calculate(_make_ohlcv(), {"min_gap_pct": 0.5, "validity_candles": 50})
        for col in [
            "bullish_fvg",
            "bearish_fvg",
            "in_bullish_fvg",
            "in_bearish_fvg",
            "bullish_fvg_quality",
            "bearish_fvg_quality",
        ]:
            assert col in result.columns

    def test_bullish_fvg_tags_completing_candle_not_middle(self):
        """FVG must appear on the completing candle, not one bar early."""
        cfg = {"min_gap_pct": 0.1, "validity_candles": 5}
        df = _make_bullish_fvg_frame()
        full = FairValueGapModule().calculate(df, cfg)
        assert bool(full["bullish_fvg"].iloc[4]) is False
        assert bool(full["bullish_fvg"].iloc[5]) is True

        asof_mid = FairValueGapModule().calculate(df.iloc[:5], cfg)
        assert bool(asof_mid["bullish_fvg"].iloc[4]) is False
        asof_complete = FairValueGapModule().calculate(df.iloc[:6], cfg)
        assert bool(asof_complete["bullish_fvg"].iloc[5]) is True


class TestMarketStructureShift:
    def test_output_columns(self):
        result = MarketStructureShiftModule().calculate(_make_ohlcv(), {"swing_lookback": 5, "break_threshold_pct": 0.2})
        assert "bullish_mss" in result.columns and "bearish_mss" in result.columns


class TestOrderBlocks:
    def test_output_columns(self):
        result = OrderBlockModule().calculate(_make_ohlcv(200), {"min_candles": 3, "min_move_pct": 3.0, "validity_candles": 20})
        for col in ["bullish_ob", "bearish_ob", "in_bullish_ob", "in_bearish_ob"]:
            assert col in result.columns

    def test_order_block_stamps_on_confirmation_bar(self):
        """OB detection using a forward window must not flag the candidate bar early."""
        n = 30
        idx = pd.date_range("2025-01-01", periods=n, freq="15min", tz="UTC")
        o = np.full(n, 100.0)
        h = np.full(n, 101.0)
        l = np.full(n, 99.0)
        c = np.full(n, 100.0)
        # Candidate bullish OB candle at 10 (close > open), then sharp sell in next 3 bars
        o[10], c[10], h[10], l[10] = 100.0, 102.0, 103.0, 99.5
        for i, px in enumerate((98.0, 95.0, 90.0), start=11):
            o[i] = px + 1.0
            c[i] = px
            h[i] = px + 1.5
            l[i] = px - 0.5
        df = pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "volume": np.ones(n)}, index=idx)
        cfg = {"min_candles": 3, "min_move_pct": 3.0, "validity_candles": 20}
        full = OrderBlockModule().calculate(df, cfg)
        confirm = 10 + 3
        assert bool(full["bullish_ob"].iloc[10]) is False
        assert bool(full["bullish_ob"].iloc[confirm]) is True

        asof_candidate = OrderBlockModule().calculate(df.iloc[:11], cfg)
        assert asof_candidate["bullish_ob"].any() == False
        asof_confirm = OrderBlockModule().calculate(df.iloc[: confirm + 1], cfg)
        assert bool(asof_confirm["bullish_ob"].iloc[confirm]) is True


class TestImbalanceZones:
    def test_output_columns(self):
        result = ImbalanceZonesModule().calculate(_make_ohlcv(), {"min_gap_size": 0.5, "validity_candles": 50})
        for col in ["bullish_imbalance", "bearish_imbalance"]:
            assert col in result.columns


class TestStructureContext:
    def test_labels_values(self):
        labels = compute_structure_labels(_make_ohlcv(200), lookback=30, pivot_bars=2)
        assert set(labels.unique()).issubset({"BULLISH_STRUCTURE", "BEARISH_STRUCTURE", "RANGE"})

    def test_add_structure_context(self):
        result = add_structure_context(_make_ohlcv(200), {"lookback": 30, "pivot_bars": 2})
        assert "structure_label" in result.columns
        assert "in_bullish_structure" in result.columns
