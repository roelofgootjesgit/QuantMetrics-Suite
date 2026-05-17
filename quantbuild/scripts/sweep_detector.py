"""Historical M5 sweep research → JSONL (XAU/USD PDH/PDL, London/NY UTC windows).

Run from quantbuild/:

  python scripts/sweep_detector.py --year 2024 --out runs/sweeps_2024.jsonl

Requires ``data/market_cache/XAUUSD/5m.parquet`` (or use ``--base-path`` / prefetch).

Regime labels use 15m + 1h bars via ``RegimeDetector`` when those parquets exist.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from src.quantbuild.io.parquet_loader import ensure_data, load_parquet
from src.quantbuild.research.sweep_m5_xauusd import (
    SweepDetectorConfig,
    detect_sweep_events_m5,
    write_jsonl,
)
from src.quantbuild.strategy_modules.regime.detector import RegimeDetector

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _naive_utc_index(ix: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Parquet OHLC indices are naive; align tz-aware inputs to naive UTC wall time."""
    t = pd.DatetimeIndex(pd.to_datetime(ix, utc=True))
    if t.tz is not None:
        return t.tz_convert("UTC").tz_localize(None)
    return t


def _load_regime_series_m5(
    base_path: Path,
    symbol: str,
    m5_index: pd.DatetimeIndex,
) -> pd.Series | None:
    """Align 15m regime classification to M5 timestamps (ffill)."""
    h1 = load_parquet(base_path, symbol, "1h")
    m15 = load_parquet(base_path, symbol, "15m")
    if m15.empty or len(m15) < 80:
        return None
    m15 = m15.sort_index()
    m15.index = _naive_utc_index(pd.DatetimeIndex(m15.index))
    det = RegimeDetector()
    try:
        regimes = det.classify(m15, data_1h=h1 if not h1.empty and len(h1) >= 30 else None)
    except Exception as e:
        logger.warning("Regime classification skipped: %s", e)
        return None
    idx = _naive_utc_index(pd.DatetimeIndex(m5_index))
    r = regimes.reindex(m15.index, method="ffill")
    m15["_reg"] = r.values
    out = m15["_reg"].reindex(idx, method="ffill")
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="M5 XAUUSD PDH/PDL sweep research JSONL")
    p.add_argument("--symbol", default="XAUUSD")
    p.add_argument("--timeframe", default="5m", help="Parquet timeframe key (default 5m)")
    p.add_argument("--base-path", type=Path, default=None, help="market_cache root")
    p.add_argument("--year", type=int, default=2024)
    p.add_argument("--out", type=Path, required=True, help="Output .jsonl path")
    p.add_argument("--min-depth-atr", type=float, default=0.15)
    p.add_argument("--max-reclaim", type=int, default=3)
    p.add_argument("--prefetch-days", type=int, default=0, help="If set, call ensure_data for N days before load")
    p.add_argument("--no-regime", action="store_true", help="Skip 15m/1h regime alignment")
    p.add_argument(
        "--htf-bias-filter",
        action="store_true",
        help="Require 4H EMA bias: PDL longs only if bullish, PDH shorts only if bearish (from M5 resample)",
    )
    p.add_argument("--htf-bias-ema-span", type=int, default=34, help="EMA span on 4H close for bias (default 34)")
    args = p.parse_args()

    base_path = args.base_path or (ROOT / "data" / "market_cache")
    y = args.year
    start = datetime(y, 1, 1, tzinfo=timezone.utc)
    end = datetime(y, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

    if args.prefetch_days and args.prefetch_days > 0:
        ensure_data(
            symbol=args.symbol,
            timeframe=args.timeframe,
            base_path=base_path,
            period_days=max(args.prefetch_days, (end - start).days + 60),
            source="auto",
            broker=None,
        )

    data = load_parquet(base_path, args.symbol, args.timeframe, start=start, end=end)
    if data.empty or len(data) < 200:
        ensure_data(
            symbol=args.symbol,
            timeframe=args.timeframe,
            base_path=base_path,
            period_days=max(450, (end - start).days + 90),
            source="auto",
            broker=None,
        )
        data = load_parquet(base_path, args.symbol, args.timeframe, start=start, end=end)

    if data.empty or len(data) < 200:
        logger.error("Insufficient M5 data for %s %s in %s", args.symbol, args.timeframe, base_path)
        return 1

    regime = None
    if not args.no_regime:
        regime = _load_regime_series_m5(base_path, args.symbol, pd.DatetimeIndex(data.index))

    cfg = SweepDetectorConfig(
        min_sweep_depth_atr=args.min_depth_atr,
        max_reclaim_candles=args.max_reclaim,
        htf_bias_filter=args.htf_bias_filter,
        htf_bias_ema_span=args.htf_bias_ema_span,
    )
    events = detect_sweep_events_m5(data, regime_series=regime, cfg=cfg)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(str(args.out), events)
    logger.info("Wrote %d events to %s", len(events), args.out.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
