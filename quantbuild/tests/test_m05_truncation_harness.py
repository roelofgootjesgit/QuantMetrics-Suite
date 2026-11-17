"""M0.5 Slice A B1 — active truncation, dual-direction timing, O1 columns (#127)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.quantbuild.indicators.swing import pivot_highs, pivot_high_prices
from src.quantbuild.strategy_modules.ict.fair_value_gaps import FairValueGapModule
from src.quantbuild.strategy_modules.ict.imbalance_zones import ImbalanceZonesModule
from src.quantbuild.strategy_modules.ict.liquidity_sweep import LiquiditySweepModule
from src.quantbuild.strategy_modules.ict.order_blocks import OrderBlockModule
from src.quantbuild.testing.truncation_harness import (
    UNIT_SEEDS,
    assert_registry_covers_disk,
    assert_registry_matches_actual_columns,
    assert_required_events_fire,
    build_registry,
    fixture_fvg_bearish,
    fixture_fvg_bullish,
    fixture_ob_bearish,
    fixture_ob_bullish,
    fixture_pivot_high,
    fixture_sweep_bearish,
    fixture_sweep_bullish,
    truncation_mismatches,
)


def test_registry_covers_all_strategy_modules_and_indicators():
    assert_registry_covers_disk(build_registry())


def test_unit_seeds_stable_no_hash():
    for unit in build_registry():
        assert unit.unit_id in UNIT_SEEDS
        assert isinstance(UNIT_SEEDS[unit.unit_id], int)


@pytest.mark.parametrize("unit", build_registry(), ids=lambda u: u.unit_id)
def test_o1_registry_columns_match_actual_output(unit):
    assert_registry_matches_actual_columns(unit)


@pytest.mark.parametrize("unit", build_registry(), ids=lambda u: u.unit_id)
def test_truncation_invariance_deterministic_data(unit):
    data = unit.truncation_data()
    assert len(data) >= 3
    errs = truncation_mismatches(unit, data)
    assert errs == [], errs[:25]


@pytest.mark.parametrize("unit", build_registry(), ids=lambda u: u.unit_id)
def test_required_boolean_events_fire_both_directions(unit):
    counts = assert_required_events_fire(unit)
    # Visible in failure messages / evidence collection
    assert isinstance(counts, dict)


def test_event_counts_report_for_evidence(capsys):
    """Print per-unit event counts for evidence pack (always runs)."""
    rows = []
    for unit in build_registry():
        if not unit.required_true_columns:
            continue
        counts = assert_required_events_fire(unit)
        rows.append((unit.unit_id, unit.config_note, counts))
    for unit_id, cfg, counts in rows:
        print(f"EVENT_COUNTS unit={unit_id} config={cfg!r} counts={counts}")
    assert rows


# --- Confirmation timing: bullish + bearish ---


def test_fvg_bullish_not_earlier_not_later():
    df = fixture_fvg_bullish()
    out = FairValueGapModule().calculate(df, {"min_gap_pct": 0.5, "validity_candles": 50})
    assert bool(out["bullish_fvg"].iloc[2])
    assert not bool(out["bullish_fvg"].iloc[1])
    pref = FairValueGapModule().calculate(df.iloc[:2], {"min_gap_pct": 0.5, "validity_candles": 50})
    assert not bool(pref["bullish_fvg"].iloc[-1])
    pref2 = FairValueGapModule().calculate(df.iloc[:3], {"min_gap_pct": 0.5, "validity_candles": 50})
    assert bool(pref2["bullish_fvg"].iloc[2])


def test_fvg_bearish_not_earlier_not_later():
    df = fixture_fvg_bearish()
    out = FairValueGapModule().calculate(df, {"min_gap_pct": 0.5, "validity_candles": 50})
    assert bool(out["bearish_fvg"].iloc[2])
    assert not bool(out["bearish_fvg"].iloc[1])
    pref = FairValueGapModule().calculate(df.iloc[:2], {"min_gap_pct": 0.5, "validity_candles": 50})
    assert not bool(pref["bearish_fvg"].iloc[-1])
    pref2 = FairValueGapModule().calculate(df.iloc[:3], {"min_gap_pct": 0.5, "validity_candles": 50})
    assert bool(pref2["bearish_fvg"].iloc[2])


def test_fvg_validity_candles_one_both_directions():
    bull = FairValueGapModule().calculate(fixture_fvg_bullish(), {"min_gap_pct": 0.5, "validity_candles": 1})
    bear = FairValueGapModule().calculate(fixture_fvg_bearish(), {"min_gap_pct": 0.5, "validity_candles": 1})
    assert bool(bull["bullish_fvg"].iloc[2]) and bool(bull["in_bullish_fvg"].iloc[2])
    assert not bool(bull["in_bullish_fvg"].iloc[3])
    assert bool(bear["bearish_fvg"].iloc[2]) and bool(bear["in_bearish_fvg"].iloc[2])
    assert not bool(bear["in_bearish_fvg"].iloc[3])


def test_ob_bullish_not_earlier_not_later():
    df = fixture_ob_bullish()
    n_c = 3
    conf = 3 + n_c
    out = OrderBlockModule().calculate(df, {"min_candles": n_c, "min_move_pct": 3.0, "validity_candles": 20})
    assert bool(out["bullish_ob"].iloc[conf])
    assert not bool(out["bullish_ob"].iloc[3])
    pref = OrderBlockModule().calculate(df.iloc[:conf], {"min_candles": n_c, "min_move_pct": 3.0, "validity_candles": 20})
    assert not bool(pref["bullish_ob"].iloc[-1])
    pref_c = OrderBlockModule().calculate(
        df.iloc[: conf + 1], {"min_candles": n_c, "min_move_pct": 3.0, "validity_candles": 20}
    )
    assert bool(pref_c["bullish_ob"].iloc[conf])


def test_ob_bearish_not_earlier_not_later():
    df = fixture_ob_bearish()
    n_c = 3
    conf = 3 + n_c
    out = OrderBlockModule().calculate(df, {"min_candles": n_c, "min_move_pct": 3.0, "validity_candles": 20})
    assert bool(out["bearish_ob"].iloc[conf]), out["bearish_ob"].tolist()
    assert not bool(out["bearish_ob"].iloc[3])
    pref = OrderBlockModule().calculate(df.iloc[:conf], {"min_candles": n_c, "min_move_pct": 3.0, "validity_candles": 20})
    assert not bool(pref["bearish_ob"].iloc[-1])
    pref_c = OrderBlockModule().calculate(
        df.iloc[: conf + 1], {"min_candles": n_c, "min_move_pct": 3.0, "validity_candles": 20}
    )
    assert bool(pref_c["bearish_ob"].iloc[conf])


def test_ob_validity_candles_one_both_directions():
    bull = OrderBlockModule().calculate(fixture_ob_bullish(), {"min_candles": 3, "min_move_pct": 3.0, "validity_candles": 1})
    bear = OrderBlockModule().calculate(fixture_ob_bearish(), {"min_candles": 3, "min_move_pct": 3.0, "validity_candles": 1})
    assert bool(bull["bullish_ob"].iloc[6]) and bool(bull["in_bullish_ob"].iloc[6])
    assert not bool(bull["in_bullish_ob"].iloc[7])
    assert bool(bear["bearish_ob"].iloc[6]) and bool(bear["in_bearish_ob"].iloc[6])
    assert not bool(bear["in_bearish_ob"].iloc[7])


def test_sweep_bullish_not_earlier_not_later():
    df = fixture_sweep_bullish()
    cfg = {"lookback_candles": 5, "sweep_threshold_pct": 0.2, "reversal_candles": 3}
    out = LiquiditySweepModule().calculate(df, cfg)
    assert bool(out["bullish_sweep"].iloc[12])
    assert not bool(out["bullish_sweep"].iloc[11])
    pref = LiquiditySweepModule().calculate(df.iloc[:12], cfg)
    assert not bool(pref["bullish_sweep"].iloc[-1])
    pref_c = LiquiditySweepModule().calculate(df.iloc[:13], cfg)
    assert bool(pref_c["bullish_sweep"].iloc[12])


def test_sweep_bearish_not_earlier_not_later():
    df = fixture_sweep_bearish()
    cfg = {"lookback_candles": 5, "sweep_threshold_pct": 0.2, "reversal_candles": 3}
    out = LiquiditySweepModule().calculate(df, cfg)
    assert bool(out["bearish_sweep"].iloc[12]), out["bearish_sweep"].tolist()
    assert not bool(out["bearish_sweep"].iloc[11])
    pref = LiquiditySweepModule().calculate(df.iloc[:12], cfg)
    assert not bool(pref["bearish_sweep"].iloc[-1])
    pref_c = LiquiditySweepModule().calculate(df.iloc[:13], cfg)
    assert bool(pref_c["bearish_sweep"].iloc[12])


def test_imbalance_bullish_not_earlier_not_later():
    df = fixture_fvg_bullish()
    out = ImbalanceZonesModule().calculate(df, {"min_gap_size": 0.5, "validity_candles": 50})
    assert bool(out["bullish_imbalance"].iloc[2])
    assert not bool(out["bullish_imbalance"].iloc[1])
    pref = ImbalanceZonesModule().calculate(df.iloc[:2], {"min_gap_size": 0.5, "validity_candles": 50})
    assert not bool(pref["bullish_imbalance"].iloc[-1])
    pref2 = ImbalanceZonesModule().calculate(df.iloc[:3], {"min_gap_size": 0.5, "validity_candles": 50})
    assert bool(pref2["bullish_imbalance"].iloc[2])


def test_imbalance_bearish_not_earlier_not_later():
    df = fixture_fvg_bearish()
    out = ImbalanceZonesModule().calculate(df, {"min_gap_size": 0.5, "validity_candles": 50})
    assert bool(out["bearish_imbalance"].iloc[2]), out["bearish_imbalance"].tolist()
    assert not bool(out["bearish_imbalance"].iloc[1])
    pref = ImbalanceZonesModule().calculate(df.iloc[:2], {"min_gap_size": 0.5, "validity_candles": 50})
    assert not bool(pref["bearish_imbalance"].iloc[-1])
    pref2 = ImbalanceZonesModule().calculate(df.iloc[:3], {"min_gap_size": 0.5, "validity_candles": 50})
    assert bool(pref2["bearish_imbalance"].iloc[2])


def test_imbalance_validity_candles_one_both_directions():
    bull = ImbalanceZonesModule().calculate(fixture_fvg_bullish(), {"min_gap_size": 0.5, "validity_candles": 1})
    bear = ImbalanceZonesModule().calculate(fixture_fvg_bearish(), {"min_gap_size": 0.5, "validity_candles": 1})
    assert bool(bull["bullish_imbalance"].iloc[2]) and bool(bull["in_bullish_imbalance"].iloc[2])
    assert not bool(bull["in_bullish_imbalance"].iloc[3])
    assert bool(bear["bearish_imbalance"].iloc[2]) and bool(bear["in_bearish_imbalance"].iloc[2])
    assert not bool(bear["in_bearish_imbalance"].iloc[3])


def test_pivot_confirmation_not_earlier_not_later():
    df = fixture_pivot_high()
    pb = 2
    origin = 5
    conf = origin + pb
    full = pivot_highs(df, pivot_bars=pb)
    assert bool(full.iloc[conf])
    assert not bool(full.iloc[origin])
    pref_c = pivot_highs(df.iloc[: conf + 1], pivot_bars=pb)
    assert bool(pref_c.iloc[conf])
    assert pivot_high_prices(df, pivot_bars=pb).iloc[conf] == pytest.approx(float(df["high"].iloc[origin]))


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
    n = 11
    idx = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")
    high = np.full(n, 100.0)
    high[5] = 105.0
    high[6] = 105.0
    low = np.full(n, 99.0)
    close = np.full(n, 100.0)
    df = pd.DataFrame({"open": close, "high": high, "low": low, "close": close, "volume": 1}, index=idx)
    assert bool(pivot_highs(df, pivot_bars=2).iloc[7])
