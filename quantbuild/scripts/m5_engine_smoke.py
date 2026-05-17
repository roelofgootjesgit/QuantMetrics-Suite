"""M5 signal-engine diagnostic — data OK vs SQE/regime/H1 path.

Run from quantbuild/:
  python scripts/m5_engine_smoke.py
  python scripts/m5_engine_smoke.py --config configs/experiments/freq_exp/exp_a2_m5_baseline.yaml --year 2024

Does NOT judge edge; measures where signals disappear (ICT vs H1 vs regime labels).
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, time, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from src.quantbuild.backtest.engine import _apply_h1_gate
from src.quantbuild.config import load_config
from src.quantbuild.data.sessions import session_from_timestamp
from src.quantbuild.io.parquet_loader import ensure_data, load_parquet
from src.quantbuild.policy.system_mode import resolve_effective_filters
from src.quantbuild.strategy_modules.regime.detector import REGIME_EXPANSION, RegimeDetector
from src.quantbuild.strategies.sqe_xauusd import (
    _compute_modules_once,
    get_sqe_default_config,
    run_sqe_conditions,
)

logging.disable(logging.WARNING)


def _deep_merge(base: dict, override: dict) -> None:
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


def main() -> int:
    p = argparse.ArgumentParser(description="M5 engine path diagnostic")
    p.add_argument(
        "--config",
        default="configs/experiments/freq_exp/exp_a2_m5_baseline.yaml",
        help="YAML (defaults to EXP-A2 M5 baseline)",
    )
    p.add_argument("--year", type=int, default=2024, help="Single calendar year slice (UTC)")
    args = p.parse_args()

    cfg = load_config(args.config)
    symbol = cfg.get("symbol", "XAUUSD")
    timeframes = cfg.get("timeframes", ["5m", "1h"])
    tf = timeframes[0]
    base_path = Path(cfg.get("data", {}).get("base_path", "data/market_cache"))
    strategy_cfg = cfg.get("strategy", {}) or {}

    y = args.year
    start = datetime(y, 1, 1, tzinfo=timezone.utc)
    end = datetime(y, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

    print(f"\n{'='*60}")
    print("  M5 ENGINE SMOKE (diagnostic)")
    print(f"  config={args.config}")
    print(f"  symbol={symbol}  primary_tf={tf}  window={y}-01-01 .. {y}-12-31 UTC")
    print(f"{'='*60}\n")

    data = load_parquet(base_path, symbol, tf, start=start, end=end)
    if data.empty or len(data) < 50:
        print(f"    prefetch {tf} (need history for window)...")
        ensure_data(symbol=symbol, timeframe=tf, base_path=base_path, period_days=max(450, (end - start).days + 120))
        data = load_parquet(base_path, symbol, tf, start=start, end=end)
    if data.empty or len(data) < 50:
        print(f"FAIL: no or too few {tf} bars ({len(data)}). Run fetch/smoke first.")
        return 1

    data = data.sort_index()
    n = len(data)
    print(f"[1] Bars loaded: {n} ({tf})")

    data_1h = load_parquet(base_path, symbol, "1h", start=start, end=end)
    if data_1h.empty or len(data_1h) < 30:
        ensure_data(symbol=symbol, timeframe="1h", base_path=base_path, period_days=max(450, (end - start).days + 120))
        data_1h = load_parquet(base_path, symbol, "1h", start=start, end=end)
    if not data_1h.empty:
        data_1h = data_1h.sort_index()
    print(f"    1h bars (regime structure): {len(data_1h)}")

    regime_cfg = cfg.get("regime", {}) or {}
    print(
        f"    regime cfg: atr_period={regime_cfg.get('atr_period')} "
        f"atr_sma_period={regime_cfg.get('atr_sma_period')} "
        f"expansion_th={regime_cfg.get('expansion_threshold')} "
        f"compression_th={regime_cfg.get('compression_threshold')}"
    )

    detector = RegimeDetector(config=regime_cfg)
    regime_series = detector.classify(data, data_1h if len(data_1h) >= 30 else None)
    rc = regime_series.value_counts(normalize=True).sort_index() * 100
    print("[2] Regime distribution (% of M5 bars):")
    for lab, pct in rc.items():
        print(f"    {lab}: {pct:.2f}%")

    sqe_cfg = get_sqe_default_config()
    if strategy_cfg:
        _deep_merge(sqe_cfg, strategy_cfg)

    pre = _compute_modules_once(data, sqe_cfg)
    long_raw = run_sqe_conditions(data, "LONG", sqe_cfg, _precomputed_df=pre)
    short_raw = run_sqe_conditions(data, "SHORT", sqe_cfg, _precomputed_df=pre)
    nl = int(long_raw.sum())
    ns = int(short_raw.sum())
    both = long_raw & short_raw
    either = long_raw | short_raw
    print("[3] Raw SQE (pre H1 gate, pre regime/session loop):")
    print(f"    LONG bars:  {nl}")
    print(f"    SHORT bars: {ns}")
    print(f"    LONG+SHORT same bar: {int(both.sum())}")
    print(f"    any signal bar:      {int(either.sum())}")
    print(f"    signal rate / bar:   {either.mean():.6f}")

    # Raw signals broken down by regime (explains expansion-only configs)
    reg_long = regime_series[long_raw].value_counts()
    reg_short = regime_series[short_raw].value_counts()
    print("    raw LONG by regime:")
    for lab, c in reg_long.items():
        print(f"      {lab}: {int(c)}")
    print("    raw SHORT by regime:")
    for lab, c in reg_short.items():
        print(f"      {lab}: {int(c)}")

    _, eff_f = resolve_effective_filters(cfg)
    wants_h1 = (
        strategy_cfg.get("structure_use_h1_gate", False)
        and "1h" in timeframes
        and tf != "1h"
    )
    print(f"\n[4] Effective filters (subset): structure_h1_gate={eff_f.get('structure_h1_gate')} "
          f"wants_h1_engine_path={wants_h1}")

    long_h1 = long_raw
    short_h1 = short_raw
    if wants_h1 and eff_f.get("structure_h1_gate", True):
        long_h1 = _apply_h1_gate(long_raw, data, "LONG", base_path, symbol, start, end, sqe_cfg)
        short_h1 = _apply_h1_gate(short_raw, data, "SHORT", base_path, symbol, start, end, sqe_cfg)
    elif wants_h1:
        print("    (H1 gate skipped: effective structure_h1_gate=false)")
    either_h1 = long_h1 | short_h1
    print(f"    After H1 gate - LONG: {int(long_h1.sum())}  SHORT: {int(short_h1.sum())}  any bar: {int(either_h1.sum())}")

    exp_mask = regime_series.eq(REGIME_EXPANSION)
    raw_exp_bars = either & exp_mask
    h1_exp_bars = either_h1 & exp_mask
    print("\n    expansion regime bars (share of window): "
          f"{100.0 * float(exp_mask.mean()):.2f}%")
    print(f"    raw SQE ANY signal AND regime==expansion: {int(raw_exp_bars.sum())} bars")
    post_h1_exp = int(h1_exp_bars.sum())
    print(f"    post-H1 ANY signal AND regime==expansion: {post_h1_exp} bars")

    regime_profiles = cfg.get("regime_profiles") or {}
    trend_skip = bool((regime_profiles.get("trend") or {}).get("skip"))
    comp_skip = bool((regime_profiles.get("compression") or {}).get("skip"))
    print(f"\n    regime_profiles: trend.skip={trend_skip} compression.skip={comp_skip}")

    # Session / hour gate (mirrors engine expansion profile, not full news/cooldown)
    exp_prof = regime_profiles.get("expansion") or {}
    allowed = exp_prof.get("allowed_sessions")
    min_h = exp_prof.get("min_hour_utc")
    mode = str((cfg.get("backtest") or {}).get("session_mode") or "extended")
    sess_hits: dict[str, int] = {}
    pass_sess = 0
    for i in range(len(data)):
        if not h1_exp_bars.iloc[i]:
            continue
        ts = data.index[i]
        sess = session_from_timestamp(ts, mode=mode)
        sess_hits[sess] = sess_hits.get(sess, 0) + 1
        ok = True
        if allowed and sess not in allowed:
            ok = False
        if min_h is not None and ts.hour < int(min_h):
            ok = False
        if ok:
            pass_sess += 1
    print(f"    post-H1 + expansion + session/hour (expansion profile): {pass_sess} bars")
    print(f"    (session_mode={mode!r} for labelling; expansion allows {allowed}, min_hour_utc={min_h})")
    if post_h1_exp > 0 and sess_hits:
        print("    post-H1+expansion bars by session label:")
        for s, c in sorted(sess_hits.items(), key=lambda x: -x[1]):
            print(f"      {s}: {c}")

    print("\n[5] Interpretation hints:")
    if nl == 0 and ns == 0:
        print("    - Raw SQE is zero: ICT params / module pipeline likely too strict for this bar size,")
        print("      or loader/tf mismatch — NOT proven 'no market edge'.")
    elif int(either_h1.sum()) == 0:
        print("    - Raw > 0 but H1 gate removes all: structure alignment issue on this tf combo.")
    elif int(h1_exp_bars.sum()) == 0 and int(either_h1.sum()) > 0:
        print("    - Post-H1 signals exist but NONE on expansion regime bars: expansion-only configs")
        print("      will produce NO_TRADES even though SQE fires (signals cluster on trend/compression).")
    elif int(raw_exp_bars.sum()) == 0 and int(either.sum()) > 0:
        print("    - Raw SQE fires but never on expansion bars: ATR/threshold mix labels almost no bars")
        print("      as expansion on this timeframe — consider regime calibration for M5 research.")
    else:
        print(
            f"    - Post-H1 + expansion bars: {post_h1_exp}; "
            f"after expansion session/hour rules: {pass_sess}. If trades still 0, check news/cooldown/sim."
        )

    print(f"\n{'='*60}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
