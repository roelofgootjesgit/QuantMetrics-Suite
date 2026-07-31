"""Causal regressions for HYP-002 failure-window / reclaim entry timing."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from src.quantbuild.strategies.ny_sweep_failure_reclaim_engine import (
    discover_failure_reclaim_signals,
)


def _v5a_spec() -> dict:
    return {
        "parameters": {
            "c_max_continuation_points": 2.0,
            "n_failure_window_bars": 3,
            "m_reclaim_window_bars": 6,
        },
        "sessions": {
            "london_reference": {"start_utc": "07:00", "end_utc": "12:00"},
            "trade_allowed_window": {"start_utc": "13:30", "end_utc": "16:00"},
        },
        "stop_loss": {"buffer_points": 0.5},
        "take_profit": {"rr": 2.0},
    }


def _synthetic_day(*, deep_continuation_on_rel_bar: int | None = None) -> pd.DataFrame:
    """
    London high/low = 2010/2000. Sweep at 13:30 (long). Reclaim close at 13:45.

    If deep_continuation_on_rel_bar == 2, bar i+2 prints continuation > C=2;
    otherwise failure-window bars stay mild so the sweep classifies as failure.
    """
    start = datetime(2024, 3, 5, 6, 0, tzinfo=timezone.utc)
    rows = []
    for b in range(50):
        ts = start + timedelta(minutes=15 * b)
        o = c = 2005.0
        h, l = 2006.0, 2004.0
        hhmm = ts.hour * 100 + ts.minute
        if 700 <= hhmm < 1200:
            if hhmm == 800:
                h, l, c = 2010.0, 2005.0, 2008.0
            elif hhmm == 1000:
                h, l, c = 2005.0, 2000.0, 2002.0
            else:
                h, l, c = 2007.0, 2003.0, 2005.0
        if hhmm == 1330:
            h, l, c = 1999.0, 1998.0, 1998.5
        elif hhmm == 1345:
            h, l, c = 2001.0, 1999.5, 2000.5
        elif hhmm == 1400:
            if deep_continuation_on_rel_bar == 2:
                h, l, c = 1999.0, 1996.0, 1997.0
            else:
                h, l, c = 2001.0, 1999.2, 2000.2
        elif hhmm == 1415:
            h, l, c = 2001.5, 1999.5, 2000.8
        elif hhmm == 1430:
            h, l, c = 2002.0, 2000.0, 2001.0
        elif hhmm > 1330:
            # Avoid extra long sweeps after the setup bar under test.
            h, l, c = 2005.0, 2001.0, 2003.0
        rows.append(
            {
                "timestamp": ts,
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": 1,
            }
        )
    return pd.DataFrame(rows).set_index("timestamp")


def test_failure_entry_not_before_classification_bar():
    df = _synthetic_day()
    sweep_i = df.index.get_loc(datetime(2024, 3, 5, 13, 30, tzinfo=timezone.utc))
    class_idx = sweep_i + 3
    signals = discover_failure_reclaim_signals(
        df,
        _v5a_spec(),
        ql_emitter=None,
        session_mode="extended",
        regime_series=None,
        account_id="test",
        symbol="XAUUSD",
    )
    from_setup = [s for s in signals if s["setup_bar"] == sweep_i]
    assert len(from_setup) == 1
    assert from_setup[0]["entry_idx"] >= class_idx
    assert from_setup[0]["entry_idx"] == class_idx
    assert from_setup[0]["entry_price"] == float(df["close"].iloc[class_idx])


def test_future_failure_window_mutation_flips_entry_only_after_reclaim_prefix():
    """
    Identical OHLC through the early reclaim bar: deep continuation later in the
    failure window must not be compatible with an entry stamped at that reclaim.
    """
    df_fail = _synthetic_day()
    df_cont = _synthetic_day(deep_continuation_on_rel_bar=2)
    reclaim_ts = datetime(2024, 3, 5, 13, 45, tzinfo=timezone.utc)
    prefix = df_fail.index <= reclaim_ts
    assert (
        df_fail.loc[prefix, ["open", "high", "low", "close"]].equals(
            df_cont.loc[prefix, ["open", "high", "low", "close"]]
        )
    )

    sweep_i = df_fail.index.get_loc(datetime(2024, 3, 5, 13, 30, tzinfo=timezone.utc))
    class_idx = sweep_i + 3
    reclaim_i = sweep_i + 1

    sig_fail = [
        s
        for s in discover_failure_reclaim_signals(
            df_fail,
            _v5a_spec(),
            ql_emitter=None,
            session_mode="extended",
            regime_series=None,
            account_id="test",
            symbol="XAUUSD",
        )
        if s["setup_bar"] == sweep_i
    ]
    sig_cont = [
        s
        for s in discover_failure_reclaim_signals(
            df_cont,
            _v5a_spec(),
            ql_emitter=None,
            session_mode="extended",
            regime_series=None,
            account_id="test",
            symbol="XAUUSD",
        )
        if s["setup_bar"] == sweep_i
    ]

    assert len(sig_fail) == 1
    assert sig_fail[0]["entry_idx"] >= class_idx
    assert sig_fail[0]["entry_idx"] != reclaim_i
    assert sig_cont == []
