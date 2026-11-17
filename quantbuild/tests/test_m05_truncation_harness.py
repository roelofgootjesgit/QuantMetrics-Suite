"""M0.5 Slice A — truncation harness, confirmation timing, fixtures (#127)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.quantbuild.indicators.swing import pivot_highs, pivot_high_prices
from src.quantbuild.strategy_modules.ict.displacement import DisplacementModule
from src.quantbuild.strategy_modules.ict.fair_value_gaps import FairValueGapModule
from src.quantbuild.strategy_modules.ict.liquidity_sweep import LiquiditySweepModule
from src.quantbuild.strategy_modules.ict.market_structure_shift import MarketStructureShiftModule
from src.quantbuild.strategy_modules.ict.order_blocks import OrderBlockModule
from src.quantbuild.testing.truncation_harness import (
    assert_registry_covers_disk,
    build_registry,
    fixture_fvg_bullish,
    fixture_ob_bullish,
    fixture_pivot_high,
    truncation_mismatches,
)


def test_registry_covers_all_strategy_modules_and_indicators():
    assert_registry_covers_disk(build_registry())


@pytest.mark.parametrize("unit", build_registry(), ids=lambda u: u.unit_id)
def test_truncation_invariance_all_output_columns(unit):
    rng = np.random.RandomState(abs(hash(unit.unit_id)) % (2**31))
    n = 80
    idx = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")
    close = 2000 + np.cumsum(rng.randn(n) * 0.8)
    data = pd.DataFrame(
        {
            "open": close + rng.randn(n) * 0.1,
            "high": close + rng.uniform(0.3, 2.0, n),
            "low": close - rng.uniform(0.3, 2.0, n),
            "close": close,
            "volume": rng.randint(1, 50, n),
        },
        index=idx,
    )
    errs = truncation_mismatches(unit, data)
    assert errs == [], errs[:20]


def test_fvg_confirms_on_third_candle_not_earlier_not_later():
    df = fixture_fvg_bullish()
    out = FairValueGapModule().calculate(df, {"min_gap_pct": 0.5, "validity_candles": 50})
    # Third candle is index 2
    assert out["bullish_fvg"].iloc[2] is True or bool(out["bullish_fvg"].iloc[2])
    assert not bool(out["bullish_fvg"].iloc[1])  # not earlier (middle)
    # Prefix ending before confirmation → no flag at end
    pref = FairValueGapModule().calculate(df.iloc[:2], {"min_gap_pct": 0.5, "validity_candles": 50})
    assert not bool(pref["bullish_fvg"].iloc[-1])
    # Including confirmation bar → flag on that bar (not later)
    pref2 = FairValueGapModule().calculate(df.iloc[:3], {"min_gap_pct": 0.5, "validity_candles": 50})
    assert bool(pref2["bullish_fvg"].iloc[2])


def test_fvg_validity_candles_one():
    df = fixture_fvg_bullish()
    out = FairValueGapModule().calculate(df, {"min_gap_pct": 0.5, "validity_candles": 1})
    assert bool(out["bullish_fvg"].iloc[2])
    assert bool(out["in_bullish_fvg"].iloc[2])
    # Next bar: event false, in_* only true if rolling still sees it — window=1 → only same bar
    assert not bool(out["in_bullish_fvg"].iloc[3]) or bool(out["bullish_fvg"].iloc[3])


def test_pivot_confirmation_not_earlier_not_later():
    df = fixture_pivot_high()
    pb = 2
    origin = 5
    conf = origin + pb
    full = pivot_highs(df, pivot_bars=pb)
    assert bool(full.iloc[conf])
    assert not bool(full.iloc[origin])  # no back-write
    # Not earlier
    pref = pivot_highs(df.iloc[:conf], pivot_bars=pb)
    assert not bool(pref.iloc[conf - 1]) if conf - 1 < len(pref) else True
    # At confirmation
    pref_c = pivot_highs(df.iloc[: conf + 1], pivot_bars=pb)
    assert bool(pref_c.iloc[conf])
    prices = pivot_high_prices(df, pivot_bars=pb)
    assert prices.iloc[conf] == pytest.approx(float(df["high"].iloc[origin]))


def test_ob_confirms_when_forward_extrema_known():
    df = fixture_ob_bullish()
    n_c = 3
    out = OrderBlockModule().calculate(df, {"min_candles": n_c, "min_move_pct": 3.0, "validity_candles": 20})
    origin = 3
    conf = origin + n_c
    assert bool(out["bullish_ob"].iloc[conf])
    assert not bool(out["bullish_ob"].iloc[origin])
    pref = OrderBlockModule().calculate(df.iloc[:conf], {"min_candles": n_c, "min_move_pct": 3.0, "validity_candles": 20})
    assert not bool(pref["bullish_ob"].iloc[-1])
    pref_c = OrderBlockModule().calculate(
        df.iloc[: conf + 1], {"min_candles": n_c, "min_move_pct": 3.0, "validity_candles": 20}
    )
    assert bool(pref_c["bullish_ob"].iloc[conf])


def test_ob_validity_candles_one():
    df = fixture_ob_bullish()
    out = OrderBlockModule().calculate(df, {"min_candles": 3, "min_move_pct": 3.0, "validity_candles": 1})
    conf = 6
    assert bool(out["bullish_ob"].iloc[conf])
    assert bool(out["in_bullish_ob"].iloc[conf])
    assert not bool(out["in_bullish_ob"].iloc[conf + 1])


def test_sweep_flags_reversal_bar_not_sweep_origin():
    # Deterministic path: lookback=5 for shorter fixture
    n = 20
    idx = pd.date_range("2024-06-01", periods=n, freq="15min", tz="UTC")
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    close = np.full(n, 100.0)
    opn = np.full(n, 100.0)
    # Establish swing low via lows at 98 before sweep
    for i in range(0, 8):
        low[i] = 98.0
        high[i] = 100.0
    # Bars 8-10 quiet
    for i in range(8, 11):
        low[i] = 99.0
        high[i] = 100.5
    sweep_i = 11
    low[sweep_i] = 97.0  # beyond threshold vs swing ~98
    high[sweep_i] = 97.8  # no reversal yet on sweep bar
    close[sweep_i] = 97.5
    rev_j = 12
    low[rev_j] = 97.5
    high[rev_j] = 100.0  # reverse above swing*(1+thresh)
    close[rev_j] = 99.5
    df = pd.DataFrame({"open": opn, "high": high, "low": low, "close": close, "volume": 1}, index=idx)
    cfg = {"lookback_candles": 5, "sweep_threshold_pct": 0.2, "reversal_candles": 3}
    out = LiquiditySweepModule().calculate(df, cfg)
    assert bool(out["bullish_sweep"].iloc[rev_j]), out["bullish_sweep"].tolist()
    assert not bool(out["bullish_sweep"].iloc[sweep_i])
    pref = LiquiditySweepModule().calculate(df.iloc[:rev_j], cfg)
    assert not bool(pref["bullish_sweep"].iloc[-1])
    pref_c = LiquiditySweepModule().calculate(df.iloc[: rev_j + 1], cfg)
    assert bool(pref_c["bullish_sweep"].iloc[rev_j])


def test_displacement_positive_event_fires():
    n = 10
    idx = pd.date_range("2024-06-01", periods=n, freq="15min", tz="UTC")
    # Three consecutive strong bullish bodies
    rows = []
    price = 100.0
    for _ in range(n):
        o = price
        c = price + 2.0
        rows.append((o, c + 0.1, o - 0.05, c))
        price = c
    df = pd.DataFrame(
        [{"open": o, "high": h, "low": l, "close": c, "volume": 1} for o, h, l, c in rows],
        index=idx,
    )
    out = DisplacementModule().calculate(df, {"min_body_pct": 70, "min_candles": 3, "min_move_pct": 1.5})
    assert bool(out["bullish_disp"].any()), "displacement never-fire is not a pass"


def test_mss_causal_can_fire_on_constructed_path():
    """Repaired MSS must be able to fire (never-fire ≠ pass) on a hand path."""
    n = 40
    idx = pd.date_range("2024-06-01", periods=n, freq="15min", tz="UTC")
    close = np.linspace(100, 110, n)
    high = close + 0.5
    low = close - 0.5
    opn = close.copy()
    # Create a clear pivot high early, then break above it later
    high[5] = 120.0
    close[5] = 119.0
    # After confirmation of that pivot, smash through
    high[-1] = 130.0
    close[-1] = 129.0
    df = pd.DataFrame({"open": opn, "high": high, "low": low, "close": close, "volume": 1}, index=idx)
    out = MarketStructureShiftModule().calculate(df, {"swing_lookback": 2, "break_threshold_pct": 0.05})
    assert bool(out["bullish_mss"].any()), "causal MSS never-fire on constructed break"


def test_short_series_no_crash():
    idx = pd.date_range("2024-01-01", periods=3, freq="15min", tz="UTC")
    df = pd.DataFrame(
        {
            "open": [1.0, 1.1, 1.2],
            "high": [1.2, 1.3, 1.4],
            "low": [0.9, 1.0, 1.1],
            "close": [1.1, 1.2, 1.25],
            "volume": [1, 1, 1],
        },
        index=idx,
    )
    for unit in build_registry():
        out = unit.runner(df)
        for col in unit.output_columns:
            assert col in out.columns


def test_ties_pivot_deterministic():
    """Equal highs in window: origin still qualifies if it equals the max (tie)."""
    n = 11
    idx = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")
    high = np.full(n, 100.0)
    high[5] = 105.0
    high[6] = 105.0  # tie with a neighbor inside right window for origin 5 when pb=2 → window includes 6
    low = np.full(n, 99.0)
    close = np.full(n, 100.0)
    df = pd.DataFrame({"open": close, "high": high, "low": low, "close": close, "volume": 1}, index=idx)
    # origin 5 with pb=2: window [3..7] max is 105; high[5]==105 → confirm at 7
    ph = pivot_highs(df, pivot_bars=2)
    assert bool(ph.iloc[7])
