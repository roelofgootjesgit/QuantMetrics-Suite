"""M0.5 truncation-invariance harness registry (#127 Slice A / B1 repair).

Every calculatable unit under ``strategy_modules/`` and ``indicators/`` must be
registered. Missing coverage fails discovery tests. ``news_gate`` has no frame
``calculate`` and is listed under FRAMELESS.

Truncation datasets are **deterministic per unit_id** (stable integer seeds —
never ``hash(unit_id)``). Boolean event columns (``bullish_*``, ``bearish_*``,
``in_*``, and bool ``*_mss`` / ``*_disp`` / ``*_cross`` / ``pivot_*``) must fire
at least once on the unit's truncation frame or the activation test fails.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from src.quantbuild.indicators.atr import atr, atr_ratio, true_range
from src.quantbuild.indicators.bollinger import bollinger_bands
from src.quantbuild.indicators.ma import ema, sma
from src.quantbuild.indicators.macd import macd
from src.quantbuild.indicators.swing import (
    pivot_high_prices,
    pivot_highs,
    pivot_low_prices,
    pivot_lows,
    swing_highs,
    swing_lows,
)
from src.quantbuild.strategy_modules.ict.displacement import DisplacementModule
from src.quantbuild.strategy_modules.ict.fair_value_gaps import FairValueGapModule
from src.quantbuild.strategy_modules.ict.imbalance_zones import ImbalanceZonesModule
from src.quantbuild.strategy_modules.ict.liquidity_sweep import LiquiditySweepModule
from src.quantbuild.strategy_modules.ict.market_structure_shift import MarketStructureShiftModule
from src.quantbuild.strategy_modules.ict.order_blocks import OrderBlockModule
from src.quantbuild.strategy_modules.ict.structure_context import add_structure_context
from src.quantbuild.strategy_modules.regime.detector import RegimeDetector

# Stable seeds per unit — do not use hash().
UNIT_SEEDS: Dict[str, int] = {
    "ict.liquidity_sweep": 101,
    "ict.fair_value_gaps": 102,
    "ict.order_blocks": 103,
    "ict.market_structure_shift": 104,
    "ict.displacement": 105,
    "ict.imbalance_zones": 106,
    "ict.structure_context": 107,
    "regime.detector": 108,
    "indicators.pivot_highs": 109,
    "indicators.pivot_lows": 110,
    "indicators.pivot_high_prices": 111,
    "indicators.pivot_low_prices": 112,
    "indicators.swing_highs": 113,
    "indicators.swing_lows": 114,
    "indicators.atr": 115,
    "indicators.ma": 116,
    "indicators.bollinger": 117,
    "indicators.macd": 118,
}


@dataclass(frozen=True)
class FeatureUnit:
    """One harness unit that maps OHLC → named output columns."""

    unit_id: str
    source_relpath: str
    output_columns: Sequence[str]
    runner: Callable[[pd.DataFrame], pd.DataFrame]
    truncation_data: Callable[[], pd.DataFrame]
    config_note: str = ""
    # Columns that must be True at least once on truncation_data (bool events).
    required_true_columns: Sequence[str] = ()


FRAMELESS_STRATEGY_MODULES: Dict[str, str] = {
    "strategy_modules/news_gate.py": "NewsGate has no DataFrame calculate(); event gate only",
    "strategy_modules/base.py": "Abstract base class",
    "strategy_modules/__init__.py": "Package init",
    "strategy_modules/ict/__init__.py": "Package init",
    "strategy_modules/ict/structure_labels.py": "Constants/helpers only",
    "strategy_modules/regime/__init__.py": "Package init",
    "testing/__init__.py": "Test helpers package",
    "testing/truncation_harness.py": "Harness itself",
}


def _base_frame(n: int, seed: int) -> pd.DataFrame:
    rng = np.random.RandomState(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")
    close = 2000 + np.cumsum(rng.randn(n) * 0.15)
    high = close + 0.4
    low = close - 0.4
    opn = close.copy()
    return pd.DataFrame(
        {"open": opn, "high": high, "low": low, "close": close, "volume": np.ones(n, dtype=int)},
        index=idx,
    )


def fixture_fvg_bullish() -> pd.DataFrame:
    """Single bullish FVG confirm at index 2; later bars do not re-gap."""
    idx = pd.date_range("2024-06-01", periods=6, freq="15min", tz="UTC")
    # (open, high, low, close)
    rows = [
        (100, 100, 99, 99.5),       # t0 high=100
        (99.5, 100.2, 99.0, 99.8),  # t1
        (110, 112, 110, 111),       # t2 confirm: low 110 > high t0
        (110.5, 111, 109.5, 110),   # no new gap vs t1 high 100.2 with low 109.5? 109.5>100.2 still gaps!
        (110.2, 110.5, 109.8, 110),
        (110.1, 110.3, 109.9, 110),
    ]
    # Ensure post-confirm bars do not satisfy low[t] > high[t-2] by enough %:
    # t3: vs t1 high 100.2 — still large. Raise t1 high and keep post lows near range.
    rows = [
        (100, 100, 99, 99.5),
        (99.5, 109.0, 99.0, 108.0),  # t1 high high enough that t3+ won't gap vs t1
        (110, 112, 110, 111),          # t2: low 110 > t0 high 100
        (111, 111.5, 109.5, 110.5),    # t3: low 109.5 vs t1 high 109 → no gap
        (110.5, 111, 109.8, 110.2),
        (110.2, 110.5, 109.9, 110.1),
    ]
    return pd.DataFrame(
        [{"open": o, "high": h, "low": l, "close": c, "volume": 1} for o, h, l, c in rows],
        index=idx,
    )


def fixture_fvg_bearish() -> pd.DataFrame:
    """Single bearish FVG confirm at index 2."""
    idx = pd.date_range("2024-06-02", periods=6, freq="15min", tz="UTC")
    rows = [
        (110, 111, 110, 110.5),        # t0 low=110
        (110.5, 111, 101.0, 102.0),    # t1 low low enough that later bars won't re-gap
        (100, 100, 98, 99),            # t2 high 100 < t0 low 110
        (99.5, 101.5, 99.0, 100.5),    # t3 high 101.5 vs t1 low 101 → no bearish gap
        (100, 100.5, 99.5, 100),
        (100, 100.2, 99.8, 100),
    ]
    return pd.DataFrame(
        [{"open": o, "high": h, "low": l, "close": c, "volume": 1} for o, h, l, c in rows],
        index=idx,
    )


def fixture_fvg_both() -> pd.DataFrame:
    """Concat bullish then bearish FVG patterns for dual-direction activation."""
    a = fixture_fvg_bullish()
    b = fixture_fvg_bearish()
    b.index = pd.date_range(a.index[-1] + pd.Timedelta(minutes=15), periods=len(b), freq="15min", tz="UTC")
    return pd.concat([a, b])


def fixture_sweep_bullish() -> pd.DataFrame:
    n = 20
    idx = pd.date_range("2024-06-01", periods=n, freq="15min", tz="UTC")
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    close = np.full(n, 100.0)
    opn = np.full(n, 100.0)
    for i in range(0, 8):
        low[i], high[i] = 98.0, 100.0
    for i in range(8, 11):
        low[i], high[i] = 99.0, 100.5
    low[11], high[11], close[11] = 97.0, 97.8, 97.5
    low[12], high[12], close[12] = 97.5, 100.0, 99.5
    return pd.DataFrame({"open": opn, "high": high, "low": low, "close": close, "volume": 1}, index=idx)


def fixture_sweep_bearish() -> pd.DataFrame:
    n = 20
    idx = pd.date_range("2024-07-01", periods=n, freq="15min", tz="UTC")
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    close = np.full(n, 100.0)
    opn = np.full(n, 100.0)
    for i in range(0, 8):
        low[i], high[i] = 100.0, 102.0  # swing high ~102
    for i in range(8, 11):
        low[i], high[i] = 99.5, 101.0
    # Sweep above swing high; keep low elevated so reversal is NOT same-bar
    low[11], high[11], close[11] = 102.2, 103.0, 102.5
    # Reversal down on next bar
    low[12], high[12], close[12] = 99.0, 102.0, 99.5
    return pd.DataFrame({"open": opn, "high": high, "low": low, "close": close, "volume": 1}, index=idx)


def fixture_sweep_both() -> pd.DataFrame:
    a = fixture_sweep_bullish()
    b = fixture_sweep_bearish()
    b.index = pd.date_range(a.index[-1] + pd.Timedelta(minutes=15), periods=len(b), freq="15min", tz="UTC")
    return pd.concat([a, b])


def fixture_ob_bullish() -> pd.DataFrame:
    n = 12
    idx = pd.date_range("2024-06-01", periods=n, freq="15min", tz="UTC")
    opn = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    close = np.full(n, 100.0)
    opn[3], close[3], high[3], low[3] = 100.0, 105.0, 106.0, 99.5
    for k in range(4, 7):
        opn[k], close[k], high[k], low[k] = 104.0, 98.0, 104.5, 97.0
    return pd.DataFrame({"open": opn, "high": high, "low": low, "close": close, "volume": 1}, index=idx)


def fixture_ob_bearish() -> pd.DataFrame:
    """Bearish OB: down-candle origin then forward rally confirming at conf."""
    n = 12
    idx = pd.date_range("2024-08-01", periods=n, freq="15min", tz="UTC")
    opn = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    close = np.full(n, 100.0)
    # Origin bearish candle
    opn[3], close[3], high[3], low[3] = 105.0, 100.0, 105.5, 99.5
    for k in range(4, 7):
        opn[k], close[k], high[k], low[k] = 101.0, 108.0, 109.0, 100.5
    return pd.DataFrame({"open": opn, "high": high, "low": low, "close": close, "volume": 1}, index=idx)


def fixture_ob_both() -> pd.DataFrame:
    a = fixture_ob_bullish()
    b = fixture_ob_bearish()
    b.index = pd.date_range(a.index[-1] + pd.Timedelta(minutes=15), periods=len(b), freq="15min", tz="UTC")
    return pd.concat([a, b])


def fixture_imbalance_both() -> pd.DataFrame:
    """Both bullish and bearish wick imbalances (third-candle confirm)."""
    return fixture_fvg_both()


def fixture_pivot_high() -> pd.DataFrame:
    n = 15
    idx = pd.date_range("2024-06-01", periods=n, freq="15min", tz="UTC")
    close = np.full(n, 100.0)
    high = np.full(n, 100.5)
    low = np.full(n, 99.5)
    high[5] = 110.0
    close[5] = 109.0
    return pd.DataFrame({"open": close, "high": high, "low": low, "close": close, "volume": 1}, index=idx)


def fixture_pivot_low() -> pd.DataFrame:
    n = 15
    idx = pd.date_range("2024-06-01", periods=n, freq="15min", tz="UTC")
    close = np.full(n, 100.0)
    high = np.full(n, 100.5)
    low = np.full(n, 99.5)
    low[5] = 90.0
    close[5] = 91.0
    return pd.DataFrame({"open": close, "high": high, "low": low, "close": close, "volume": 1}, index=idx)


def fixture_displacement_both() -> pd.DataFrame:
    n = 20
    idx = pd.date_range("2024-06-01", periods=n, freq="15min", tz="UTC")
    rows = []
    price = 100.0
    # bullish streak
    for _ in range(8):
        o, c = price, price + 2.0
        rows.append((o, c + 0.1, o - 0.05, c))
        price = c
    # bearish streak
    for _ in range(8):
        o, c = price, price - 2.0
        rows.append((o, o + 0.05, c - 0.1, c))
        price = c
    while len(rows) < n:
        rows.append((price, price + 0.2, price - 0.2, price))
    return pd.DataFrame(
        [{"open": o, "high": h, "low": l, "close": c, "volume": 1} for o, h, l, c in rows[:n]],
        index=idx,
    )


def fixture_mss_both() -> pd.DataFrame:
    n = 50
    idx = pd.date_range("2024-06-01", periods=n, freq="15min", tz="UTC")
    close = np.linspace(100, 105, n)
    high = close + 0.5
    low = close - 0.5
    # Pivot high then break up (bullish mss), pivot low then break down (bearish mss)
    high[5] = 120.0
    close[5] = 119.0
    high[30] = 130.0
    close[30] = 129.0
    low[15] = 80.0
    close[15] = 81.0
    low[40] = 70.0
    close[40] = 71.0
    return pd.DataFrame({"open": close, "high": high, "low": low, "close": close, "volume": 1}, index=idx)


def fixture_structure_trend() -> pd.DataFrame:
    """HH/HL then LH/LL so both bullish and bearish structure labels appear.

    Base path is strictly sloping so only planted spikes become pivots.
    """
    n = 90
    idx = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")
    # Gentle up-slope: no local pivots on base path for pivot_bars=2
    close = 100.0 + np.arange(n) * 0.01
    high = close + 0.2
    low = close - 0.2
    # Rising swings (bullish): HH + HL
    for i, h in ((8, 105.0), (18, 110.0), (28, 115.0)):
        high[i] = h
        close[i] = h - 0.3
        low[i] = h - 1.0
    for i, l in ((13, 97.0), (23, 99.0), (33, 101.0)):
        low[i] = l
        close[i] = l + 0.3
        high[i] = l + 1.0
    # Falling swings (bearish): LH + LL (after a flat bridge)
    for i, h in ((48, 114.0), (58, 109.0), (68, 104.0)):
        high[i] = h
        close[i] = h - 0.3
        low[i] = h - 1.0
    for i, l in ((53, 100.0), (63, 95.0), (73, 90.0)):
        low[i] = l
        close[i] = l + 0.3
        high[i] = l + 1.0
    return pd.DataFrame({"open": close, "high": high, "low": low, "close": close, "volume": 1}, index=idx)


def fixture_macd_crosses() -> pd.DataFrame:
    n = 120
    seed = UNIT_SEEDS["indicators.macd"]
    rng = np.random.RandomState(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")
    # Trending up then down to force crosses
    close = np.concatenate([np.linspace(100, 130, 60), np.linspace(130, 90, 60)])
    close = close + rng.randn(n) * 0.05
    return pd.DataFrame(
        {"open": close, "high": close + 0.2, "low": close - 0.2, "close": close, "volume": 1},
        index=idx,
    )


def _run_module(mod_cls: type, config: Dict[str, Any]) -> Callable[[pd.DataFrame], pd.DataFrame]:
    def _fn(data: pd.DataFrame) -> pd.DataFrame:
        return mod_cls().calculate(data.copy(), config)

    return _fn


def _run_structure(data: pd.DataFrame) -> pd.DataFrame:
    return add_structure_context(data.copy(), {"lookback": 50, "pivot_bars": 2})


def _run_regime(data: pd.DataFrame) -> pd.DataFrame:
    out = data.copy()
    out["regime"] = RegimeDetector().classify(out, data_1h=None)
    return out


def _ind_frame(series_map: Dict[str, pd.Series], index: pd.Index) -> pd.DataFrame:
    return pd.DataFrame(series_map, index=index)


def build_registry() -> List[FeatureUnit]:
    return [
        FeatureUnit(
            "ict.liquidity_sweep",
            "strategy_modules/ict/liquidity_sweep.py",
            ("bullish_sweep", "bearish_sweep", "swept_low", "swept_high", "swing_high", "swing_low"),
            _run_module(
                LiquiditySweepModule,
                {"lookback_candles": 5, "sweep_threshold_pct": 0.2, "reversal_candles": 3},
            ),
            truncation_data=fixture_sweep_both,
            config_note="lookback_candles=5",
            required_true_columns=("bullish_sweep", "bearish_sweep"),
        ),
        FeatureUnit(
            "ict.fair_value_gaps",
            "strategy_modules/ict/fair_value_gaps.py",
            (
                "bullish_fvg",
                "bearish_fvg",
                "in_bullish_fvg",
                "in_bearish_fvg",
                "bullish_fvg_quality",
                "bearish_fvg_quality",
            ),
            _run_module(FairValueGapModule, {"min_gap_pct": 0.5, "validity_candles": 50}),
            truncation_data=fixture_fvg_both,
            required_true_columns=("bullish_fvg", "bearish_fvg", "in_bullish_fvg", "in_bearish_fvg"),
        ),
        FeatureUnit(
            "ict.order_blocks",
            "strategy_modules/ict/order_blocks.py",
            ("bullish_ob", "bearish_ob", "in_bullish_ob", "in_bearish_ob"),
            _run_module(OrderBlockModule, {"min_candles": 3, "min_move_pct": 3.0, "validity_candles": 20}),
            truncation_data=fixture_ob_both,
            required_true_columns=("bullish_ob", "bearish_ob", "in_bullish_ob", "in_bearish_ob"),
        ),
        FeatureUnit(
            "ict.market_structure_shift",
            "strategy_modules/ict/market_structure_shift.py",
            ("swing_high", "swing_low", "bullish_mss", "bearish_mss"),
            _run_module(MarketStructureShiftModule, {"swing_lookback": 2, "break_threshold_pct": 0.05}),
            truncation_data=fixture_mss_both,
            required_true_columns=("bullish_mss", "bearish_mss"),
        ),
        FeatureUnit(
            "ict.displacement",
            "strategy_modules/ict/displacement.py",
            ("bullish_disp", "bearish_disp"),
            _run_module(DisplacementModule, {"min_body_pct": 70, "min_candles": 3, "min_move_pct": 1.5}),
            truncation_data=fixture_displacement_both,
            required_true_columns=("bullish_disp", "bearish_disp"),
        ),
        FeatureUnit(
            "ict.imbalance_zones",
            "strategy_modules/ict/imbalance_zones.py",
            ("bullish_imbalance", "bearish_imbalance", "in_bullish_imbalance", "in_bearish_imbalance"),
            _run_module(ImbalanceZonesModule, {"min_gap_size": 0.5, "validity_candles": 50}),
            truncation_data=fixture_imbalance_both,
            required_true_columns=(
                "bullish_imbalance",
                "bearish_imbalance",
                "in_bullish_imbalance",
                "in_bearish_imbalance",
            ),
        ),
        FeatureUnit(
            "ict.structure_context",
            "strategy_modules/ict/structure_context.py",
            ("structure_label", "in_bullish_structure", "in_bearish_structure"),
            _run_structure,
            truncation_data=fixture_structure_trend,
            required_true_columns=("in_bullish_structure", "in_bearish_structure"),
        ),
        FeatureUnit(
            "regime.detector",
            "strategy_modules/regime/detector.py",
            ("regime",),
            _run_regime,
            truncation_data=lambda: _base_frame(100, UNIT_SEEDS["regime.detector"]),
            required_true_columns=(),
        ),
        FeatureUnit(
            "indicators.pivot_highs",
            "indicators/swing.py",
            ("pivot_high",),
            lambda d: _ind_frame({"pivot_high": pivot_highs(d, 2)}, d.index),
            truncation_data=fixture_pivot_high,
            required_true_columns=("pivot_high",),
        ),
        FeatureUnit(
            "indicators.pivot_lows",
            "indicators/swing.py",
            ("pivot_low",),
            lambda d: _ind_frame({"pivot_low": pivot_lows(d, 2)}, d.index),
            truncation_data=fixture_pivot_low,
            required_true_columns=("pivot_low",),
        ),
        FeatureUnit(
            "indicators.pivot_high_prices",
            "indicators/swing.py",
            ("pivot_high_price",),
            lambda d: _ind_frame({"pivot_high_price": pivot_high_prices(d, 2)}, d.index),
            truncation_data=fixture_pivot_high,
            required_true_columns=(),
        ),
        FeatureUnit(
            "indicators.pivot_low_prices",
            "indicators/swing.py",
            ("pivot_low_price",),
            lambda d: _ind_frame({"pivot_low_price": pivot_low_prices(d, 2)}, d.index),
            truncation_data=fixture_pivot_low,
            required_true_columns=(),
        ),
        FeatureUnit(
            "indicators.swing_highs",
            "indicators/swing.py",
            ("swing_high",),
            lambda d: _ind_frame({"swing_high": swing_highs(d, 20, True)}, d.index),
            truncation_data=lambda: _base_frame(60, UNIT_SEEDS["indicators.swing_highs"]),
            required_true_columns=(),
        ),
        FeatureUnit(
            "indicators.swing_lows",
            "indicators/swing.py",
            ("swing_low",),
            lambda d: _ind_frame({"swing_low": swing_lows(d, 20, True)}, d.index),
            truncation_data=lambda: _base_frame(60, UNIT_SEEDS["indicators.swing_lows"]),
            required_true_columns=(),
        ),
        FeatureUnit(
            "indicators.atr",
            "indicators/atr.py",
            ("atr", "true_range", "atr_ratio"),
            lambda d: _ind_frame(
                {"atr": atr(d, 14), "true_range": true_range(d), "atr_ratio": atr_ratio(d)},
                d.index,
            ),
            truncation_data=lambda: _base_frame(60, UNIT_SEEDS["indicators.atr"]),
            required_true_columns=(),
        ),
        FeatureUnit(
            "indicators.ma",
            "indicators/ma.py",
            ("sma", "ema"),
            lambda d: _ind_frame({"sma": sma(d["close"], 10), "ema": ema(d["close"], 10)}, d.index),
            truncation_data=lambda: _base_frame(60, UNIT_SEEDS["indicators.ma"]),
            required_true_columns=(),
        ),
        FeatureUnit(
            "indicators.bollinger",
            "indicators/bollinger.py",
            ("mid", "upper", "lower"),
            lambda d: bollinger_bands(d["close"], length=20, stddev=2.0),
            truncation_data=lambda: _base_frame(60, UNIT_SEEDS["indicators.bollinger"]),
            required_true_columns=(),
        ),
        FeatureUnit(
            "indicators.macd",
            "indicators/macd.py",
            ("macd_line", "signal_line", "histogram", "bullish_cross", "bearish_cross"),
            lambda d: macd(d["close"]),
            truncation_data=fixture_macd_crosses,
            required_true_columns=("bullish_cross", "bearish_cross"),
        ),
    ]


def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def discover_python_files(sub: str) -> List[Path]:
    root = package_root() / sub
    return sorted(p for p in root.rglob("*.py") if p.is_file())


def assert_registry_covers_disk(registry: Sequence[FeatureUnit]) -> None:
    covered = {u.source_relpath.replace("\\", "/") for u in registry}
    covered |= set(FRAMELESS_STRATEGY_MODULES)
    covered.add("indicators/__init__.py")
    missing: List[str] = []
    for sub in ("strategy_modules", "indicators"):
        for path in discover_python_files(sub):
            rel = str(path.relative_to(package_root())).replace("\\", "/")
            if rel not in covered:
                missing.append(rel)
    assert not missing, f"Unregistered modules (add to harness or FRAMELESS): {missing}"


def actual_output_columns(unit: FeatureUnit, data: Optional[pd.DataFrame] = None) -> List[str]:
    """Columns present after runner minus original OHLC inputs."""
    frame = data if data is not None else unit.truncation_data()
    base_cols = set(frame.columns)
    out = unit.runner(frame)
    return sorted(c for c in out.columns if c not in base_cols)


def assert_registry_matches_actual_columns(unit: FeatureUnit) -> None:
    """O1: registry output_columns must equal produced non-input columns."""
    actual = set(actual_output_columns(unit))
    expected = set(unit.output_columns)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    assert not missing and not extra, (
        f"{unit.unit_id}: column mismatch missing={missing} extra={extra} "
        f"expected={sorted(expected)} actual={sorted(actual)}"
    )


def boolean_event_columns(unit: FeatureUnit) -> List[str]:
    """Registry bool-like event columns that must activate when listed in required_true_columns."""
    return list(unit.required_true_columns)


def event_true_counts(unit: FeatureUnit, data: Optional[pd.DataFrame] = None) -> Dict[str, int]:
    frame = data if data is not None else unit.truncation_data()
    out = unit.runner(frame)
    counts: Dict[str, int] = {}
    for col in unit.required_true_columns:
        s = out[col]
        if s.dtype == object:
            counts[col] = int((s == True).sum())  # noqa: E712
        else:
            counts[col] = int(s.fillna(False).astype(bool).sum())
    return counts


def assert_required_events_fire(unit: FeatureUnit) -> Dict[str, int]:
    counts = event_true_counts(unit)
    dead = [c for c, n in counts.items() if n < 1]
    assert not dead, (
        f"{unit.unit_id}: required event columns never True: {dead} "
        f"(counts={counts}, config={unit.config_note!r})"
    )
    return counts


def truncation_mismatches(unit: FeatureUnit, data: pd.DataFrame) -> List[str]:
    full = unit.runner(data)
    errs: List[str] = []
    n = len(data)
    for i in range(n):
        prefix = data.iloc[: i + 1]
        pref = unit.runner(prefix)
        for col in unit.output_columns:
            if col not in full.columns or col not in pref.columns:
                errs.append(f"{unit.unit_id}:{col}: missing column")
                continue
            a = pref[col].iloc[i]
            b = full[col].iloc[i]
            if pd.isna(a) and pd.isna(b):
                continue
            if isinstance(a, (float, np.floating)) or isinstance(b, (float, np.floating)):
                if not (np.isfinite(a) and np.isfinite(b) and abs(float(a) - float(b)) <= 1e-12):
                    if not (pd.isna(a) and pd.isna(b)):
                        errs.append(f"{unit.unit_id}:{col}:i={i}: {a!r} != {b!r}")
            else:
                if a != b:
                    errs.append(f"{unit.unit_id}:{col}:i={i}: {a!r} != {b!r}")
    return errs
