"""DATA-002 I1 (#133): UTC-naive index canonicalization.

Covers America/New_York summer/winter, bare-tz_localize(None) mutant kill,
naive-without-contract DENY, multi-symbol / FX-fallback scope, and Oanda
verified utc=True contract preservation. Offline / deterministic only.
"""
from __future__ import annotations

import inspect

import pandas as pd
import pytest

from src.quantbuild.io import parquet_loader
from src.quantbuild.io.timezone_canon import (
    UnverifiedNaiveTimezoneError,
    canonicalize_index_utc_naive,
)


NY = "America/New_York"


def _ny_session_open(year: int, month: int, day: int) -> pd.Timestamp:
    """NY 09:30 wall clock as tz-aware America/New_York timestamp."""
    return pd.Timestamp(year=year, month=month, day=day, hour=9, minute=30, tz=NY)


def test_ny_summer_0930_canonicalizes_to_utc_naive_1330() -> None:
    """EDT (UTC-4): NY 09:30 → UTC-naive 13:30."""
    aware = pd.DatetimeIndex([_ny_session_open(2024, 7, 1)])
    out = canonicalize_index_utc_naive(aware, source="test")
    assert out.tz is None
    assert list(out) == [pd.Timestamp("2024-07-01 13:30:00")]


def test_ny_winter_0930_canonicalizes_to_utc_naive_1430() -> None:
    """EST (UTC-5): NY 09:30 → UTC-naive 14:30."""
    aware = pd.DatetimeIndex([_ny_session_open(2024, 12, 2)])
    out = canonicalize_index_utc_naive(aware, source="test")
    assert out.tz is None
    assert list(out) == [pd.Timestamp("2024-12-02 14:30:00")]


def test_bare_tz_localize_none_mutant_killed_for_ny_summer() -> None:
    """Regression: bare tz_localize(None) on NY summer must NOT match correct UTC.

    Mutant that strips zone without tz_convert('UTC') yields wall 09:30 naive
    instead of the required UTC-naive 13:30 — this assertion kills that mutant.
    """
    aware = pd.DatetimeIndex([_ny_session_open(2024, 7, 1)])
    correct = canonicalize_index_utc_naive(aware, source="test")
    mutant = aware.tz_localize(None)  # intentional incorrect path
    assert list(mutant) == [pd.Timestamp("2024-07-01 09:30:00")]
    assert list(correct) == [pd.Timestamp("2024-07-01 13:30:00")]
    assert list(mutant) != list(correct)


def test_naive_without_verified_contract_is_denied() -> None:
    naive = pd.DatetimeIndex(["2024-07-01 09:30:00"])
    with pytest.raises(UnverifiedNaiveTimezoneError, match="do not assume UTC"):
        canonicalize_index_utc_naive(naive, source="yfinance")


def test_naive_allowed_only_with_verified_contract_flag() -> None:
    naive = pd.DatetimeIndex(["2024-07-01 13:30:00"])
    out = canonicalize_index_utc_naive(
        naive, allow_naive_utc=True, source="oanda_verified"
    )
    assert out.tz is None
    assert list(out) == [pd.Timestamp("2024-07-01 13:30:00")]


def test_non_xauusd_fx_symbol_aware_index_canonicalizes() -> None:
    """I1 applies to all symbols incl. FX fallback paths — not XAUUSD-only."""
    aware = pd.DatetimeIndex([_ny_session_open(2024, 7, 1)])
    # Simulate EURUSD / FX path feeding the shared helper.
    out = canonicalize_index_utc_naive(aware, source="yfinance:EURUSD")
    assert list(out) == [pd.Timestamp("2024-07-01 13:30:00")]


def test_fetch_yfinance_does_not_use_bare_tz_localize_none() -> None:
    """Source-guard: _fetch_yfinance must not strip tz via bare tz_localize(None)."""
    src = inspect.getsource(parquet_loader._fetch_yfinance)
    assert "canonicalize_index_utc_naive" in src
    # Disallow the defective pattern on the index (allow comments mentioning it).
    bare = [
        line
        for line in src.splitlines()
        if "tz_localize(None)" in line and "canonicalize" not in line and not line.strip().startswith("#")
    ]
    assert bare == [], bare


def test_fetch_dukascopy_and_normalize_use_canonicalize() -> None:
    assert "canonicalize_index_utc_naive" in inspect.getsource(parquet_loader._fetch_dukascopy)
    assert "canonicalize_index_utc_naive" in inspect.getsource(parquet_loader._normalize_ohlcv_frame)


def test_normalize_ohlcv_denies_naive_ctrader_payload() -> None:
    """cTrader-like naive frame must not be silently treated as UTC."""
    frame = pd.DataFrame(
        {
            "timestamp": pd.DatetimeIndex(["2024-07-01 09:30:00"]),  # naive
            "open": [1.0],
            "high": [1.1],
            "low": [0.9],
            "close": [1.05],
            "volume": [10.0],
        }
    )
    out = parquet_loader._normalize_ohlcv_frame(frame)
    assert out.empty


def test_normalize_ohlcv_converts_aware_ny_summer() -> None:
    frame = pd.DataFrame(
        {
            "timestamp": pd.DatetimeIndex([_ny_session_open(2024, 7, 1)]),
            "open": [1.0],
            "high": [1.1],
            "low": [0.9],
            "close": [1.05],
            "volume": [10.0],
        }
    )
    out = parquet_loader._normalize_ohlcv_frame(frame)
    assert not out.empty
    assert out.index.tz is None
    assert list(out.index) == [pd.Timestamp("2024-07-01 13:30:00")]


def test_oanda_loader_preserves_verified_utc_true_then_strip() -> None:
    """Oanda known-correct contract preserved: to_datetime(..., utc=True) then strip."""
    import src.quantbuild.io.oanda_loader as oanda_loader

    src = inspect.getsource(oanda_loader.fetch_oanda_candles)
    assert "utc=True" in src
    assert "tz_localize(None)" in src
    # Must not have been "fixed" by removing the utc=True contract.
    assert "pd.to_datetime" in src
