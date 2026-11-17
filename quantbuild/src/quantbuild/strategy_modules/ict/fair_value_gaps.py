"""Fair Value Gaps (FVG) – confirmation on the third candle close.

M0.5 / issue #127: the event flag is written on the **third** candle of the
3-bar pattern (confirmation bar), never back-written onto the middle/origin bar.

Entry timing note (ADR-001 M3): confirmation is evaluated at the **close** of
that third candle, matching today's hub close-fill convention. If M3 later
moves the shared fill hook to **next-open**, SQE entries that consume FVG must
shift one bar forward so close-confirmation and next-open fill do not silently
mix.
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from src.quantbuild.strategy_modules.base import BaseModule


class FairValueGapModule(BaseModule):
    @property
    def name(self) -> str:
        return "Fair Value Gaps (FVG)"

    @property
    def description(self) -> str:
        return "ICT price imbalances – gaps confirmed on third candle close"

    def get_config_schema(self) -> Dict:
        return {
            "fields": [
                {"name": "min_gap_pct", "label": "Min Gap %", "type": "number", "default": 0.5, "min": 0.1, "max": 2.0},
                {"name": "validity_candles", "label": "Validity Candles", "type": "number", "default": 50, "min": 1, "max": 100},
                {
                    "name": "fvg_quality_cap_pct",
                    "label": "FVG quality cap % (gap ratio at this size → quality 1.0)",
                    "type": "number",
                    "default": 1.5,
                    "min": 0.2,
                    "max": 5.0,
                },
            ]
        }

    def calculate(self, data: pd.DataFrame, config: Dict) -> pd.DataFrame:
        df = data.copy()
        min_gap = config.get("min_gap_pct", 0.5) / 100.0
        validity = int(config.get("validity_candles", 50))
        cap_ratio = max(float(config.get("fvg_quality_cap_pct", 1.5)) / 100.0, 1e-9)

        high = df["high"].values
        low = df["low"].values
        n = len(df)

        bullish_fvg = np.zeros(n, dtype=bool)
        bearish_fvg = np.zeros(n, dtype=bool)
        bull_qual = np.zeros(n, dtype=np.float64)
        bear_qual = np.zeros(n, dtype=np.float64)

        # Confirmation bar t = third candle: gap between high[t-2] and low[t] (bullish).
        for t in range(2, n):
            prev_prev_high = high[t - 2]
            if prev_prev_high != 0 and low[t] > prev_prev_high:
                g = (low[t] - prev_prev_high) / prev_prev_high
                if g >= min_gap:
                    bullish_fvg[t] = True
                    bull_qual[t] = min(1.0, float(g / cap_ratio))

            prev_prev_low = low[t - 2]
            if prev_prev_low != 0 and high[t] < prev_prev_low:
                g = (prev_prev_low - high[t]) / prev_prev_low
                if g >= min_gap:
                    bearish_fvg[t] = True
                    bear_qual[t] = min(1.0, float(g / cap_ratio))

        df["bullish_fvg"] = bullish_fvg
        df["bearish_fvg"] = bearish_fvg
        df["in_bullish_fvg"] = (
            pd.Series(bullish_fvg, index=df.index).astype(int).rolling(window=validity, min_periods=1).max().astype(bool)
        )
        df["in_bearish_fvg"] = (
            pd.Series(bearish_fvg, index=df.index).astype(int).rolling(window=validity, min_periods=1).max().astype(bool)
        )
        df["bullish_fvg_quality"] = (
            pd.Series(bull_qual, index=df.index).rolling(window=validity, min_periods=1).max().fillna(0.0)
        )
        df["bearish_fvg_quality"] = (
            pd.Series(bear_qual, index=df.index).rolling(window=validity, min_periods=1).max().fillna(0.0)
        )
        return df

    def check_entry_condition(self, data: pd.DataFrame, index: int, config: Dict, direction: str) -> bool:
        if index >= len(data):
            return False
        row = data.iloc[index]
        if direction == "LONG":
            return bool(row.get("in_bullish_fvg", False))
        if direction == "SHORT":
            return bool(row.get("in_bearish_fvg", False))
        return False
