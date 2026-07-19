"""Unit tests for signal independence filter."""
import pandas as pd

from src.quantbuild.utils.signal_independence import (
    component_signal_independence_masks,
    signal_independence_mask,
)


def _mask(
    signals: list[bool],
    closes: list[float] | None = None,
    atrs: list[float] | None = None,
    min_bars_gap: int = 4,
    min_atr_distance: float = 1.5,
) -> pd.Series:
    n = len(signals)
    close = pd.Series(closes if closes is not None else [100.0 + i for i in range(n)], dtype=float)
    atr = pd.Series(atrs if atrs is not None else [1.0] * n, dtype=float)
    sig = pd.Series(signals, dtype=bool)
    return signal_independence_mask(
        sig, close, atr, min_bars_gap=min_bars_gap, min_atr_distance=min_atr_distance
    )


class TestSignalIndependence:
    def test_first_signal_always_true(self):
        mask = _mask([False, True, False, True], min_bars_gap=10)
        assert mask.iloc[1]
        assert not mask.iloc[3]

    def test_clustered_within_gap_only_first_true(self):
        signals = [False] * 10
        signals[2] = True
        signals[3] = True
        signals[4] = True
        mask = _mask(signals, min_bars_gap=4, min_atr_distance=0.0)
        assert mask.iloc[2]
        assert not mask.iloc[3]
        assert not mask.iloc[4]

    def test_sufficient_gap_and_distance_all_true(self):
        closes = [100.0] * 20
        closes[0] = 100.0
        closes[5] = 110.0
        closes[12] = 95.0
        signals = [False] * 20
        signals[0] = True
        signals[5] = True
        signals[12] = True
        mask = _mask(signals, closes=closes, min_bars_gap=4, min_atr_distance=1.5)
        assert mask.iloc[0]
        assert mask.iloc[5]
        assert mask.iloc[12]

    def test_atr_distance_blocks_close_prices(self):
        signals = [True, False, False, False, True]
        closes = [100.0, 100.0, 100.0, 100.0, 100.5]
        atrs = [2.0, 2.0, 2.0, 2.0, 2.0]
        mask = _mask(
            signals,
            closes=closes,
            atrs=atrs,
            min_bars_gap=4,
            min_atr_distance=1.5,
        )
        assert mask.iloc[0]
        assert not mask.iloc[4]

    def test_atr_distance_allows_far_prices(self):
        signals = [True, False, False, False, True]
        closes = [100.0, 100.0, 100.0, 100.0, 104.0]
        atrs = [2.0] * 5
        mask = _mask(
            signals,
            closes=closes,
            atrs=atrs,
            min_bars_gap=4,
            min_atr_distance=1.5,
        )
        assert mask.iloc[0]
        assert mask.iloc[4]

    def test_component_masks_filter_cross_direction_clusters(self):
        close = pd.Series([100.0, 100.0, 100.0, 110.0, 100.0], dtype=float)
        atr = pd.Series([1.0] * 5, dtype=float)
        long_raw = pd.Series([False, True, False, False, False], dtype=bool)
        short_raw = pd.Series([False, False, True, False, False], dtype=bool)

        long_ind, short_ind = component_signal_independence_masks(
            (long_raw, short_raw),
            close,
            atr,
            min_bars_gap=4,
            min_atr_distance=0.0,
        )

        assert long_ind.iloc[1]
        assert not short_ind.iloc[2]
