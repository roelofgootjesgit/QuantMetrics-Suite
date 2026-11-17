"""Imbalance Zones – wick gaps confirmed on the third candle (no middle back-write)."""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from src.quantbuild.strategy_modules.base import BaseModule


class ImbalanceZonesModule(BaseModule):
    @property
    def name(self) -> str:
        return "Imbalance Zones"

    @property
    def description(self) -> str:
        return "ICT wick-based gaps – confirmed on third candle"

    def get_config_schema(self) -> Dict:
        return {
            "fields": [
                {"name": "min_gap_size", "label": "Min Gap Size", "type": "number", "default": 0.5, "min": 0.1, "max": 10.0},
                {"name": "validity_candles", "label": "Validity Candles", "type": "number", "default": 50, "min": 1, "max": 200},
            ]
        }

    def calculate(self, data: pd.DataFrame, config: Dict) -> pd.DataFrame:
        df = data.copy()
        min_gap = float(config.get("min_gap_size", 0.5))
        validity = int(config.get("validity_candles", 50))

        high = df["high"].values
        low = df["low"].values
        n = len(df)

        bullish_imb = np.zeros(n, dtype=bool)
        bearish_imb = np.zeros(n, dtype=bool)

        # Third candle t confirms gap vs candle t-2 (same pattern family as FVG).
        for t in range(2, n):
            if (low[t] - high[t - 2]) > min_gap:
                bullish_imb[t] = True
            if (low[t - 2] - high[t]) > min_gap:
                bearish_imb[t] = True

        df["bullish_imbalance"] = bullish_imb
        df["bearish_imbalance"] = bearish_imb
        df["in_bullish_imbalance"] = (
            pd.Series(bullish_imb, index=df.index).rolling(window=validity, min_periods=1).max().fillna(0).astype(bool)
        )
        df["in_bearish_imbalance"] = (
            pd.Series(bearish_imb, index=df.index).rolling(window=validity, min_periods=1).max().fillna(0).astype(bool)
        )
        return df

    def check_entry_condition(self, data: pd.DataFrame, index: int, config: Dict, direction: str) -> bool:
        if index >= len(data):
            return False
        row = data.iloc[index]
        if direction == "LONG":
            return bool(row.get("in_bullish_imbalance", False))
        if direction == "SHORT":
            return bool(row.get("in_bearish_imbalance", False))
        return False
