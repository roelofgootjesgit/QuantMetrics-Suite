"""DATA-002 I1 — fail-closed UTC-naive index canonicalization.

Tz-aware indexes must convert via ``tz_convert("UTC").tz_localize(None)``.
Never strip a non-UTC zone with bare ``tz_localize(None)``.
Tz-naive indexes are DENY unless a verified source contract allows naive UTC.
This helper does **not** attest Dukascopy/cTrader/yfinance vendor TZ semantics.
"""
from __future__ import annotations

from typing import Optional, Union

import pandas as pd

IndexLike = Union[pd.DatetimeIndex, pd.Index, pd.Series]


class UnverifiedNaiveTimezoneError(ValueError):
    """Raised when a tz-naive index lacks a verified naive-UTC contract."""


def canonicalize_index_utc_naive(
    index: IndexLike,
    *,
    allow_naive_utc: bool = False,
    source: Optional[str] = None,
) -> pd.DatetimeIndex:
    """Return a tz-naive DatetimeIndex whose wall times are UTC instants.

    Parameters
    ----------
    index:
        Input timestamps (DatetimeIndex preferred).
    allow_naive_utc:
        When True, accept already-naive indexes as verified UTC-naive storage
        (e.g. after an attested ``to_datetime(..., utc=True)`` contract such as
        Oanda). When False (default), naive input is rejected.
    source:
        Optional label for error messages only — not vendor attestation.
    """
    if isinstance(index, pd.Series):
        index = pd.DatetimeIndex(pd.to_datetime(index, errors="raise"))
    elif not isinstance(index, pd.DatetimeIndex):
        index = pd.DatetimeIndex(pd.to_datetime(index, errors="raise"))
    else:
        # Preserve tz metadata; do not pass utc=True (would assume naive==UTC).
        index = pd.DatetimeIndex(index)

    if len(index) == 0:
        return pd.DatetimeIndex([], dtype="datetime64[ns]")

    if index.tz is not None:
        return index.tz_convert("UTC").tz_localize(None)

    if allow_naive_utc:
        return pd.DatetimeIndex(index)

    src = source if source is not None else "unknown"
    raise UnverifiedNaiveTimezoneError(
        f"tz-naive index rejected without verified timezone contract "
        f"(source={src!r}); do not assume UTC"
    )
