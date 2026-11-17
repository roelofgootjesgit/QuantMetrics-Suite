"""Market Structure Shift (MSS) – confirmation-time / causal structure break.

Restored MSS is a **functionally new feature** vs the legacy centered-swing
implementation: new baselines and new experiment IDs are required (issue #127).
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from src.quantbuild.indicators.swing import pivot_high_prices, pivot_low_prices
from src.quantbuild.strategy_modules.base import BaseModule


class MarketStructureShiftModule(BaseModule):
    @property
    def name(self) -> str:
        return "Market Structure Shift (MSS)"

    @property
    def description(self) -> str:
        return "ICT trend reversals – causal confirmation-time structure breaks"

    def get_config_schema(self) -> Dict:
        return {
            "fields": [
                {"name": "swing_lookback", "label": "Swing Lookback", "type": "number", "default": 5, "min": 3, "max": 20},
                {"name": "break_threshold_pct", "label": "Break Threshold %", "type": "number", "default": 0.2, "min": 0.1, "max": 1.0},
            ]
        }

    def calculate(self, data: pd.DataFrame, config: Dict) -> pd.DataFrame:
        df = data.copy()
        lb = int(config.get("swing_lookback", 5))
        thresh = float(config.get("break_threshold_pct", 0.2)) / 100.0

        # Confirmation-time pivot prices; ffill yields last causally known swing level.
        ph = pivot_high_prices(df, pivot_bars=lb)
        pl = pivot_low_prices(df, pivot_bars=lb)
        swing_high = ph.ffill()
        swing_low = pl.ffill()
        df["swing_high"] = swing_high
        df["swing_low"] = swing_low

        # Compare against prior bar's known level (no same-bar circularity).
        prior_sh = swing_high.shift(1)
        prior_sl = swing_low.shift(1)
        df["bullish_mss"] = (df["high"] >= prior_sh * (1 + thresh)) & prior_sh.notna()
        df["bearish_mss"] = (df["low"] <= prior_sl * (1 - thresh)) & prior_sl.notna()
        return df

    def check_entry_condition(self, data: pd.DataFrame, index: int, config: Dict, direction: str) -> bool:
        if index >= len(data):
            return False
        row = data.iloc[index]
        if direction == "LONG":
            return bool(row.get("bullish_mss", False))
        if direction == "SHORT":
            return bool(row.get("bearish_mss", False))
        return False
