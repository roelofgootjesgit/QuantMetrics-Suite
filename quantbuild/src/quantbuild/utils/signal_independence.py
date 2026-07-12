"""Filter clustered signals so only spatially/temporally independent ones pass."""
from typing import Sequence

import numpy as np
import pandas as pd


def signal_independence_mask(
    signal: pd.Series,
    close: pd.Series,
    atr: pd.Series,
    min_bars_gap: int = 4,
    min_atr_distance: float = 1.5,
) -> pd.Series:
    """Return boolean mask: True where a signal bar is independent (not clustered).

    ``signal`` must be boolean (or castable). First signal in the series is always
    independent. Later signals require both:
    - at least ``min_bars_gap`` bars since the last accepted signal
    - price distance >= ``min_atr_distance`` * ATR at the signal bar
    """
    sig = signal.fillna(False).astype(bool)
    out = pd.Series(False, index=sig.index, dtype=bool)

    last_idx: int | None = None
    last_price: float | None = None

    for i in range(len(sig)):
        if not sig.iloc[i]:
            continue
        price = float(close.iloc[i])
        atr_val = float(atr.iloc[i]) if pd.notna(atr.iloc[i]) else np.nan

        if last_idx is None:
            out.iloc[i] = True
            last_idx = i
            last_price = price
            continue

        bars_gap = i - last_idx
        if bars_gap < min_bars_gap:
            continue

        if np.isnan(atr_val) or atr_val <= 0:
            dist_atr = np.inf if last_price is not None else 0.0
        else:
            dist_atr = abs(price - last_price) / atr_val

        if dist_atr >= min_atr_distance:
            out.iloc[i] = True
            last_idx = i
            last_price = price

    return out


def component_signal_independence_masks(
    signals: Sequence[pd.Series],
    close: pd.Series,
    atr: pd.Series,
    min_bars_gap: int = 4,
    min_atr_distance: float = 1.5,
) -> tuple[pd.Series, ...]:
    """Apply one independence filter across multiple component signal streams."""
    if not signals:
        return ()

    combined = pd.Series(False, index=signals[0].index, dtype=bool)
    normalized: list[pd.Series] = []
    for signal in signals:
        sig = signal.fillna(False).astype(bool)
        normalized.append(sig)
        combined = combined | sig

    global_mask = signal_independence_mask(
        combined,
        close,
        atr,
        min_bars_gap=min_bars_gap,
        min_atr_distance=min_atr_distance,
    )
    return tuple(sig & global_mask for sig in normalized)
