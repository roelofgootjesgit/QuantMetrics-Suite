"""Regression: FVG mid limit fill must beat same-bar close-outside invalidation."""
from __future__ import annotations

import pandas as pd

from src.quantbuild.strategies.ny_sweep_reversion_engine import (
    _resolve_fvg_limit_bar,
    discover_setups,
)


def test_resolve_fvg_limit_bar_fill_beats_close_outside() -> None:
    # Bar wicks through mid then closes outside the FVG → resting limit fills.
    assert (
        _resolve_fvg_limit_bar(
            low=104.0,
            high=107.0,
            close=99.0,
            mid=105.0,
            gap_lo=100.0,
            gap_hi=110.0,
        )
        == "fill"
    )


def test_resolve_fvg_limit_bar_invalidate_when_mid_not_touched() -> None:
    assert (
        _resolve_fvg_limit_bar(
            low=106.0,
            high=109.0,
            close=99.0,
            mid=105.0,
            gap_lo=100.0,
            gap_hi=110.0,
        )
        == "invalidate"
    )


def test_resolve_fvg_limit_bar_wait_when_inside_without_touch() -> None:
    assert (
        _resolve_fvg_limit_bar(
            low=106.0,
            high=109.0,
            close=108.0,
            mid=105.0,
            gap_lo=100.0,
            gap_hi=110.0,
        )
        is None
    )


def _minimal_spec() -> dict:
    return {
        "sessions": {
            "london_reference": {"start_utc": "07:00", "end_utc": "12:00"},
            "trade_allowed_window": {"start_utc": "13:00", "end_utc": "16:00"},
        },
        "setup": {
            "sweep": {"enabled": True},
            "displacement": {
                "atr_period": 3,
                # Keep the sweep bar from counting as displacement (weak body).
                "min_body_to_range_ratio": 0.5,
                "min_range_atr_multiple": 0.1,
            },
            "fair_value_gap": {
                "min_gap_points": 5.0,
                "require_after_displacement": True,
            },
        },
        "bias": {"h1_structure": {"enabled": False}},
        "entry": {"expire_if_not_filled_bars": 4},
        "stop_loss": {"buffer_points": 5.0},
        "take_profit": {"model": "fixed_r", "r_multiple": 2.0},
    }


def test_discover_setups_fills_when_wick_touches_mid_then_closes_outside() -> None:
    """End-to-end: LONG setup must fill on wick-through-mid / close-outside bar."""
    # London (07:00–12:00): high=120, low=100
    rows = [
        ("2026-01-05 07:00:00+00:00", 110.0, 115.0, 105.0, 112.0),
        ("2026-01-05 08:00:00+00:00", 110.0, 115.0, 100.0, 112.0),
        ("2026-01-05 09:00:00+00:00", 110.0, 115.0, 105.0, 112.0),
        ("2026-01-05 10:00:00+00:00", 110.0, 120.0, 105.0, 112.0),
        ("2026-01-05 11:00:00+00:00", 110.0, 115.0, 105.0, 112.0),
        ("2026-01-05 12:00:00+00:00", 112.0, 113.0, 111.0, 112.5),
        # Sweep London low: low < 100, close > 100 (body/range too weak for displacement)
        ("2026-01-05 13:00:00+00:00", 102.0, 103.0, 95.0, 101.0),
        # Displacement (strong bullish body/range) — candle j-2 of the FVG
        ("2026-01-05 13:15:00+00:00", 101.0, 112.0, 100.5, 111.5),
        # Middle candle: must NOT form an earlier bullish FVG vs sweep high
        ("2026-01-05 13:30:00+00:00", 102.0, 104.0, 101.0, 103.0),
        # Bullish FVG: low > high[j-2]=112 → gap [112, 118], mid=115
        ("2026-01-05 13:45:00+00:00", 117.0, 120.0, 118.0, 119.0),
        # Fill bar: wick through mid=115, close outside below gap_lo=112
        ("2026-01-05 14:00:00+00:00", 118.0, 119.0, 114.0, 110.0),
    ]

    idx = pd.DatetimeIndex([r[0] for r in rows], tz="UTC")
    df = pd.DataFrame(
        {
            "open": [r[1] for r in rows],
            "high": [r[2] for r in rows],
            "low": [r[3] for r in rows],
            "close": [r[4] for r in rows],
            "volume": [1] * len(rows),
        },
        index=idx,
    )

    signals = discover_setups(df, _minimal_spec(), h1_long=None, h1_short=None)
    assert len(signals) == 1
    sig = signals[0]
    assert sig["direction"] == "LONG"
    assert sig["entry_price"] == 115.0  # mid of gap [112, 118]
    assert sig["entry_idx"] == len(rows) - 1
