"""M0.5 truncation-invariance harness registry (#127 Slice A).

Every calculatable unit under ``strategy_modules/`` and ``indicators/`` must be
registered. Missing coverage fails discovery tests. ``news_gate`` has no frame
``calculate`` and is listed under FRAMELESS.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

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


@dataclass(frozen=True)
class FeatureUnit:
    """One harness unit that maps OHLC → named output columns."""

    unit_id: str
    source_relpath: str
    output_columns: Sequence[str]
    runner: Callable[[pd.DataFrame], pd.DataFrame]
    requires_positive_event: bool = True
    positive_fixture: Optional[Callable[[], pd.DataFrame]] = None
    config_note: str = ""


# Modules under strategy_modules/ without a frame calculate() API.
FRAMELESS_STRATEGY_MODULES: Dict[str, str] = {
    "strategy_modules/news_gate.py": "NewsGate has no DataFrame calculate(); event gate only",
    "strategy_modules/base.py": "Abstract base class",
    "strategy_modules/__init__.py": "Package init",
    "strategy_modules/ict/__init__.py": "Package init",
    "strategy_modules/ict/structure_labels.py": "Constants/helpers only",
    "strategy_modules/regime/__init__.py": "Package init",
}


def _ohlc(n: int = 120, seed: int = 0) -> pd.DataFrame:
    rng = np.random.RandomState(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")
    close = 2000 + np.cumsum(rng.randn(n) * 0.5)
    high = close + rng.uniform(0.2, 1.5, n)
    low = close - rng.uniform(0.2, 1.5, n)
    opn = close + rng.randn(n) * 0.1
    return pd.DataFrame(
        {"open": opn, "high": high, "low": low, "close": close, "volume": rng.randint(10, 100, n)},
        index=idx,
    )


def fixture_fvg_bullish() -> pd.DataFrame:
    """Hand-built bullish FVG confirming on third candle (index 2)."""
    idx = pd.date_range("2024-06-01", periods=6, freq="15min", tz="UTC")
    # t0 high=100, t1 anything, t2 low=110 → gap vs t0 high
    rows = [
        (100, 100, 99, 99.5),
        (99.5, 101, 99, 100),
        (110, 112, 110, 111),  # confirmation
        (111, 112, 110.5, 111),
        (111, 111.5, 110, 110.5),
        (110.5, 111, 110, 110.2),
    ]
    return pd.DataFrame(
        [{"open": o, "high": h, "low": l, "close": c, "volume": 1} for o, h, l, c in rows],
        index=idx,
    )


def fixture_sweep_bullish() -> pd.DataFrame:
    """Sweep below prior swing low then reverse up within window → flag on reversal bar."""
    n = 30
    idx = pd.date_range("2024-06-01", periods=n, freq="15min", tz="UTC")
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    opn = np.full(n, 100.0)
    # Build a swing low around bar 15, then sweep and reverse.
    low[10:15] = 98.0
    low[15] = 97.0  # establishes lower area
    # After lookback, create clear swing_low via prior lows then sweep
    for i in range(20, 25):
        low[i] = 98.5
        high[i] = 100.5
        close[i] = 99.5
    # Sweep bar 25
    low[25] = 97.0
    high[25] = 98.0
    close[25] = 97.5
    # Reversal bar 26
    low[26] = 97.5
    high[26] = 100.0
    close[26] = 99.5
    return pd.DataFrame(
        {"open": opn, "high": high, "low": low, "close": close, "volume": 1},
        index=idx,
    )


def fixture_ob_bullish() -> pd.DataFrame:
    """Bullish OB: strong up-candle origin then forward drop confirming at conf bar."""
    n = 12
    idx = pd.date_range("2024-06-01", periods=n, freq="15min", tz="UTC")
    opn = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    close = np.full(n, 100.0)
    # Origin i=3 bullish candle
    opn[3], close[3], high[3], low[3] = 100.0, 105.0, 106.0, 99.5
    # Forward n_c=3 bars break below origin low
    for k in range(4, 7):
        opn[k], close[k], high[k], low[k] = 104.0, 98.0, 104.5, 97.0
    return pd.DataFrame(
        {"open": opn, "high": high, "low": low, "close": close, "volume": 1},
        index=idx,
    )


def fixture_pivot_high() -> pd.DataFrame:
    """Isolated pivot high at origin; confirmation at origin+pivot_bars."""
    n = 15
    idx = pd.date_range("2024-06-01", periods=n, freq="15min", tz="UTC")
    close = np.full(n, 100.0)
    high = np.full(n, 100.5)
    low = np.full(n, 99.5)
    opn = np.full(n, 100.0)
    # origin i=5 is clear high
    high[5] = 110.0
    close[5] = 109.0
    return pd.DataFrame(
        {"open": opn, "high": high, "low": low, "close": close, "volume": 1},
        index=idx,
    )


def _run_module(mod_cls: type, config: Dict[str, Any]) -> Callable[[pd.DataFrame], pd.DataFrame]:
    def _fn(data: pd.DataFrame) -> pd.DataFrame:
        return mod_cls().calculate(data.copy(), config)

    return _fn


def _run_structure(data: pd.DataFrame) -> pd.DataFrame:
    return add_structure_context(data.copy(), {"lookback": 30, "pivot_bars": 2})


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
                {"lookback_candles": 20, "sweep_threshold_pct": 0.2, "reversal_candles": 3},
            ),
            positive_fixture=fixture_sweep_bullish,
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
            positive_fixture=fixture_fvg_bullish,
        ),
        FeatureUnit(
            "ict.order_blocks",
            "strategy_modules/ict/order_blocks.py",
            ("bullish_ob", "bearish_ob", "in_bullish_ob", "in_bearish_ob"),
            _run_module(OrderBlockModule, {"min_candles": 3, "min_move_pct": 3.0, "validity_candles": 20}),
            positive_fixture=fixture_ob_bullish,
        ),
        FeatureUnit(
            "ict.market_structure_shift",
            "strategy_modules/ict/market_structure_shift.py",
            ("swing_high", "swing_low", "bullish_mss", "bearish_mss"),
            _run_module(MarketStructureShiftModule, {"swing_lookback": 2, "break_threshold_pct": 0.05}),
            # Positive path: after causal pivots exist, a break is forced in fixture_pivot + extension
            positive_fixture=None,
            requires_positive_event=False,  # covered by dedicated MSS timing test with constructed path
        ),
        FeatureUnit(
            "ict.displacement",
            "strategy_modules/ict/displacement.py",
            ("bullish_disp", "bearish_disp"),
            _run_module(DisplacementModule, {"min_body_pct": 70, "min_candles": 3, "min_move_pct": 1.5}),
            requires_positive_event=True,
            positive_fixture=None,  # random seed path in test builds consecutive strong bodies
        ),
        FeatureUnit(
            "ict.imbalance_zones",
            "strategy_modules/ict/imbalance_zones.py",
            ("bullish_imbalance", "bearish_imbalance", "in_bullish_imbalance", "in_bearish_imbalance"),
            _run_module(ImbalanceZonesModule, {"min_gap_size": 0.5, "validity_candles": 50}),
            positive_fixture=fixture_fvg_bullish,
        ),
        FeatureUnit(
            "ict.structure_context",
            "strategy_modules/ict/structure_context.py",
            ("structure_label", "in_bullish_structure", "in_bearish_structure"),
            _run_structure,
            requires_positive_event=False,
        ),
        FeatureUnit(
            "regime.detector",
            "strategy_modules/regime/detector.py",
            ("regime",),
            _run_regime,
            requires_positive_event=False,
        ),
        FeatureUnit(
            "indicators.pivot_highs",
            "indicators/swing.py",
            ("pivot_high",),
            lambda d: _ind_frame({"pivot_high": pivot_highs(d, 2)}, d.index),
            positive_fixture=fixture_pivot_high,
        ),
        FeatureUnit(
            "indicators.pivot_lows",
            "indicators/swing.py",
            ("pivot_low",),
            lambda d: _ind_frame({"pivot_low": pivot_lows(d, 2)}, d.index),
            requires_positive_event=False,
        ),
        FeatureUnit(
            "indicators.pivot_high_prices",
            "indicators/swing.py",
            ("pivot_high_price",),
            lambda d: _ind_frame({"pivot_high_price": pivot_high_prices(d, 2)}, d.index),
            positive_fixture=fixture_pivot_high,
        ),
        FeatureUnit(
            "indicators.pivot_low_prices",
            "indicators/swing.py",
            ("pivot_low_price",),
            lambda d: _ind_frame({"pivot_low_price": pivot_low_prices(d, 2)}, d.index),
            requires_positive_event=False,
        ),
        FeatureUnit(
            "indicators.swing_highs",
            "indicators/swing.py",
            ("swing_high",),
            lambda d: _ind_frame({"swing_high": swing_highs(d, 20, True)}, d.index),
            requires_positive_event=False,
        ),
        FeatureUnit(
            "indicators.swing_lows",
            "indicators/swing.py",
            ("swing_low",),
            lambda d: _ind_frame({"swing_low": swing_lows(d, 20, True)}, d.index),
            requires_positive_event=False,
        ),
        FeatureUnit(
            "indicators.atr",
            "indicators/atr.py",
            ("atr", "true_range", "atr_ratio"),
            lambda d: _ind_frame(
                {"atr": atr(d, 14), "true_range": true_range(d), "atr_ratio": atr_ratio(d)},
                d.index,
            ),
            requires_positive_event=False,
        ),
        FeatureUnit(
            "indicators.ma",
            "indicators/ma.py",
            ("sma", "ema"),
            lambda d: _ind_frame({"sma": sma(d["close"], 10), "ema": ema(d["close"], 10)}, d.index),
            requires_positive_event=False,
        ),
        FeatureUnit(
            "indicators.bollinger",
            "indicators/bollinger.py",
            ("mid", "upper", "lower"),
            lambda d: bollinger_bands(d["close"], length=20, stddev=2.0),
            requires_positive_event=False,
        ),
        FeatureUnit(
            "indicators.macd",
            "indicators/macd.py",
            ("macd_line", "signal_line", "histogram", "bullish_cross", "bearish_cross"),
            lambda d: macd(d["close"]),
            requires_positive_event=False,
        ),
    ]


def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def discover_python_files(sub: str) -> List[Path]:
    root = package_root() / sub
    return sorted(p for p in root.rglob("*.py") if p.is_file())


def assert_registry_covers_disk(registry: Sequence[FeatureUnit]) -> None:
    """Fail if a strategy_modules/indicators .py file is neither registered nor FRAMELESS."""
    covered = {u.source_relpath.replace("\\", "/") for u in registry}
    covered |= set(FRAMELESS_STRATEGY_MODULES)
    # indicators/__init__.py is package glue
    covered.add("indicators/__init__.py")
    missing: List[str] = []
    for sub in ("strategy_modules", "indicators"):
        for path in discover_python_files(sub):
            rel = str(path.relative_to(package_root())).replace("\\", "/")
            if rel not in covered:
                missing.append(rel)
    assert not missing, f"Unregistered modules (add to harness or FRAMELESS): {missing}"


def truncation_mismatches(unit: FeatureUnit, data: pd.DataFrame) -> List[str]:
    """Return human-readable mismatch strings; empty means pass."""
    full = unit.runner(data)
    errs: List[str] = []
    n = len(data)
    # Skip warm-up edge where windows are incomplete — still require equality on all i.
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
