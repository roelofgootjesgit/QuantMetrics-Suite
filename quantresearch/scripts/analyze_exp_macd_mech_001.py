#!/usr/bin/env python3
"""Post-run analytics for EXP-MACD-MECH-001 (forward returns, TAE, permutation)."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_SUITE = Path(__file__).resolve().parents[2]
_QB = _SUITE / "quantbuild"
_QR = _SUITE / "quantresearch"
for p in (_QB, _QB / "src", _QR):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from src.quantbuild.config import load_config, quantbuild_repo_root
from src.quantbuild.indicators.atr import atr as compute_atr
from src.quantbuild.indicators.bollinger import bollinger_bands
from src.quantbuild.indicators.macd import macd as compute_macd
from src.quantbuild.io.parquet_loader import load_parquet
from src.quantbuild.strategies.macd_only import (
    apply_independence_to_signals,
    collect_macd_entry_signals,
    detect_macd_component_observations,
    macd_only_strategy_cfg,
    macd_cross_velocity,
    compute_macd_frame,
)


def _find_latest_run_jsonl(ql_base: Path) -> Path | None:
    runs = ql_base / "runs"
    if not runs.is_dir():
        return None
    files = sorted(runs.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _forward_return_r(
    data: pd.DataFrame,
    atr_series: pd.Series,
    bar_i: int,
    direction: str,
    horizon: int,
) -> float | None:
    j = bar_i + horizon
    if j >= len(data):
        return None
    entry = float(data["close"].iloc[bar_i])
    exit_p = float(data["close"].iloc[j])
    atr_v = float(atr_series.iloc[bar_i])
    if atr_v <= 0:
        return None
    risk = 2.0 * atr_v
    move = exit_p - entry if direction == "LONG" else entry - exit_p
    return move / risk


def _directional_return_universe(
    data: pd.DataFrame,
    atr_series: pd.Series,
    horizon: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Per-bar forward R for both possible signal directions."""
    n = len(data)
    long_returns = np.full(n, np.nan, dtype=float)
    short_returns = np.full(n, np.nan, dtype=float)
    for i in range(n):
        long_r = _forward_return_r(data, atr_series, i, "LONG", horizon)
        short_r = _forward_return_r(data, atr_series, i, "SHORT", horizon)
        if long_r is not None:
            long_returns[i] = long_r
        if short_r is not None:
            short_returns[i] = short_r
    return long_returns, short_returns


def _directional_permutation_test(
    long_outcomes: np.ndarray,
    short_outcomes: np.ndarray,
    signal_indices: np.ndarray,
    signal_directions: list[str],
    *,
    n_permutations: int = 1000,
    seed: int = 42,
) -> dict[str, float | int | bool]:
    """Permutation test that preserves LONG/SHORT labels while randomizing timestamps."""
    long_arr = np.asarray(long_outcomes, dtype=float)
    short_arr = np.asarray(short_outcomes, dtype=float)
    sig_idx = np.asarray(signal_indices, dtype=int)
    dirs = np.asarray([str(d).upper() for d in signal_directions], dtype=object)
    if long_arr.ndim != 1 or short_arr.ndim != 1 or len(long_arr) != len(short_arr):
        raise ValueError("long_outcomes and short_outcomes must be same-length 1-D arrays")
    if len(sig_idx) != len(dirs):
        raise ValueError("signal_indices and signal_directions length mismatch")
    if len(sig_idx) == 0:
        return {
            "observed_hit_rate": 0.0,
            "baseline_mean_hit_rate": 0.0,
            "p_value": 1.0,
            "significant": False,
            "n_signals": 0,
            "n_permutations": n_permutations,
            "seed": seed,
        }
    if (sig_idx < 0).any() or (sig_idx >= len(long_arr)).any():
        raise ValueError("signal_indices out of range")

    signal_values: list[float] = []
    signal_dirs: list[str] = []
    for idx, direction in zip(sig_idx, dirs):
        if direction == "LONG":
            value = long_arr[idx]
        elif direction == "SHORT":
            value = short_arr[idx]
        else:
            raise ValueError(f"invalid signal direction: {direction!r}")
        if np.isfinite(value):
            signal_values.append(float(value))
            signal_dirs.append(str(direction))

    if not signal_values:
        return {
            "observed_hit_rate": 0.0,
            "baseline_mean_hit_rate": 0.0,
            "p_value": 1.0,
            "significant": False,
            "n_signals": 0,
            "n_permutations": n_permutations,
            "seed": seed,
        }

    valid_random_indices = np.flatnonzero(np.isfinite(long_arr) & np.isfinite(short_arr))
    if len(valid_random_indices) < len(signal_values):
        raise ValueError("not enough valid outcome bars for permutation sample")

    observed = float(np.mean(signal_values))
    rng = np.random.default_rng(seed)
    dir_arr = np.asarray(signal_dirs, dtype=object)
    perm_rates = np.empty(n_permutations, dtype=float)
    for i in range(n_permutations):
        random_idx = rng.choice(valid_random_indices, size=len(signal_values), replace=False)
        sampled = np.where(dir_arr == "SHORT", short_arr[random_idx], long_arr[random_idx])
        perm_rates[i] = float(np.mean(sampled))

    baseline_mean = float(np.mean(perm_rates))
    p_value = float(np.mean(perm_rates >= observed))
    return {
        "observed_hit_rate": observed,
        "baseline_mean_hit_rate": baseline_mean,
        "p_value": p_value,
        "significant": p_value < 0.05,
        "n_signals": len(signal_values),
        "n_permutations": n_permutations,
        "seed": seed,
    }


def _time_to_adverse_excursion(
    data: pd.DataFrame,
    atr_series: pd.Series,
    bar_i: int,
    direction: str,
    sl_atr_mult: float = 2.0,
    mae_threshold_r: float = 0.5,
    max_bars: int = 16,
) -> int | None:
    entry = float(data["close"].iloc[bar_i])
    atr_v = float(atr_series.iloc[bar_i])
    if atr_v <= 0:
        return None
    risk = sl_atr_mult * atr_v
    threshold = mae_threshold_r * risk
    end = min(bar_i + max_bars, len(data) - 1)
    for j in range(bar_i + 1, end + 1):
        lo = float(data["low"].iloc[j])
        hi = float(data["high"].iloc[j])
        if direction == "LONG":
            adverse = entry - lo
        else:
            adverse = hi - entry
        if adverse >= threshold:
            return j - bar_i
    return None


def _bb_macd_correlation(data: pd.DataFrame, macd_frame: pd.DataFrame) -> dict[str, Any]:
    bands = bollinger_bands(data["close"], length=20, stddev=2.0)
    bb_any = (data["close"] < bands["lower"]) | (data["close"] > bands["upper"])
    macd_any = macd_frame["bullish_cross"] | macd_frame["bearish_cross"]
    bb_b = bb_any.fillna(False).astype(bool)
    macd_b = macd_any.fillna(False).astype(bool)
    both = int((bb_b & macd_b).sum())
    bb_only = int((bb_b & ~macd_b).sum())
    macd_only = int((~bb_b & macd_b).sum())
    neither = int((~bb_b & ~macd_b).sum())
    n = len(data)
    bb_i = bb_b.astype(int)
    macd_i = macd_b.astype(int)
    if bb_i.std() > 0 and macd_i.std() > 0:
        pearson = float(np.corrcoef(bb_i.values, macd_i.values)[0, 1])
    else:
        pearson = 0.0
    return {
        "co_occurrence_same_bar": both,
        "bb_only_bars": bb_only,
        "macd_only_bars": macd_only,
        "neither_bars": neither,
        "pearson_same_bar": pearson,
        "joint_rate": both / n if n else 0.0,
    }


def _velocity_histogram(velocities: list[float], bins: int = 10) -> dict[str, Any]:
    if not velocities:
        return {"bins": [], "counts": []}
    arr = np.array(velocities, dtype=float)
    counts, edges = np.histogram(arr, bins=bins)
    return {
        "bin_edges": [float(x) for x in edges],
        "counts": [int(c) for c in counts],
        "mean": float(arr.mean()),
        "median": float(np.median(arr)),
    }


def analyze(
    *,
    config_path: Path,
    quantlog_path: Path | None,
    output_dir: Path,
) -> dict[str, Any]:
    cfg = load_config(config_path)
    symbol = cfg.get("symbol", "EURUSD")
    base_path = quantbuild_repo_root() / Path(cfg.get("data", {}).get("base_path", "data/market_cache"))
    bt = cfg.get("backtest") or {}
    start = datetime.combine(
        datetime.fromisoformat(str(bt["start_date"])[:10]).date(),
        time.min,
        tzinfo=timezone.utc,
    )
    end = datetime.combine(
        datetime.fromisoformat(str(bt["end_date"])[:10]).date(),
        time.max,
        tzinfo=timezone.utc,
    )

    data = load_parquet(base_path, symbol, "15m", start=start, end=end)
    data = data.sort_index()
    strat_cfg = macd_only_strategy_cfg(cfg)
    macd_cfg = strat_cfg.get("macd") or {}
    macd_frame = compute_macd_frame(data, macd_cfg)
    atr_series = compute_atr(data, period=14)

    entries = collect_macd_entry_signals(data, strat_cfg, session_mode=bt.get("session_mode", "extended"))
    bull_raw, bear_raw = detect_macd_component_observations(macd_frame)
    raw_n = int(bull_raw.sum() + bear_raw.sum())
    indep_n = len(entries)
    clustering_rate = 1.0 - (indep_n / raw_n) if raw_n else 0.0

    horizons = [4, 8, 16]
    fwd: dict[str, list[float]] = {f"T+{h}": [] for h in horizons}
    tae_bars: list[int] = []
    velocities: list[float] = []
    signal_indices: list[int] = []
    signal_directions: list[str] = []
    t8_wins = 0
    t8_n = 0

    sl_mult = float((strat_cfg.get("risk") or {}).get("sl_atr_mult", 2.0))

    for sig in entries:
        i = int(sig["bar_index"])
        direction = sig["direction"]
        signal_indices.append(i)
        signal_directions.append(direction)
        velocities.append(float(sig["macd_cross_velocity"]))
        tae = _time_to_adverse_excursion(data, atr_series, i, direction, sl_atr_mult=sl_mult)
        if tae is not None:
            tae_bars.append(tae)
        for h in horizons:
            r = _forward_return_r(data, atr_series, i, direction, h)
            if r is not None:
                fwd[f"T+{h}"].append(r)
        r8 = _forward_return_r(data, atr_series, i, direction, 8)
        if r8 is not None:
            t8_n += 1
            if r8 > 0:
                t8_wins += 1

    long_universe, short_universe = _directional_return_universe(data, atr_series, horizon=8)
    perm = _directional_permutation_test(
        long_universe,
        short_universe,
        np.array(signal_indices, dtype=int),
        signal_directions,
        n_permutations=2000,
        seed=42,
    )

    # Velocity vs win at T+8
    vel_win_pairs: list[tuple[float, int]] = []
    for sig in entries:
        i = int(sig["bar_index"])
        r8 = _forward_return_r(data, atr_series, i, sig["direction"], 8)
        if r8 is not None:
            vel_win_pairs.append((float(sig["macd_cross_velocity"]), 1 if r8 > 0 else 0))
    if len(vel_win_pairs) >= 10:
        vels = np.array([p[0] for p in vel_win_pairs])
        wins = np.array([p[1] for p in vel_win_pairs])
        if vels.std() > 0:
            vel_predictive_corr = float(np.corrcoef(vels, wins)[0, 1])
        else:
            vel_predictive_corr = 0.0
    else:
        vel_predictive_corr = None

    trade_stats: dict[str, Any] = {}
    if quantlog_path and quantlog_path.is_file():
        closed = []
        for line in quantlog_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            ev = json.loads(line)
            if ev.get("event_type") == "trade_closed":
                closed.append(ev.get("payload") or {})
        if closed:
            pnl_r = [float(c.get("pnl_r", 0)) for c in closed]
            trade_stats = {
                "n_trades": len(closed),
                "expectancy_r": float(np.mean(pnl_r)),
                "win_rate_pct": 100.0 * sum(1 for r in pnl_r if r > 0) / len(pnl_r),
                "profit_factor": (
                    sum(r for r in pnl_r if r > 0) / abs(sum(r for r in pnl_r if r < 0))
                    if sum(r for r in pnl_r if r < 0) else None
                ),
            }

    summary: dict[str, Any] = {
        "experiment_id": "EXP-MACD-MECH-001",
        "data_first_bar": str(data.index.min()) if len(data) else None,
        "data_last_bar": str(data.index.max()) if len(data) else None,
        "n_bars": len(data),
        "raw_macd_crosses": raw_n,
        "independent_signals": indep_n,
        "clustering_rate": round(clustering_rate, 4),
        "forward_returns_r": {
            k: {
                "n": len(v),
                "mean": float(np.mean(v)) if v else None,
                "median": float(np.median(v)) if v else None,
                "std": float(np.std(v)) if v else None,
            }
            for k, v in fwd.items()
        },
        "win_rate_at_T8": round(100.0 * t8_wins / t8_n, 2) if t8_n else None,
        "time_to_adverse_excursion": {
            "threshold_r": 0.5,
            "n_measured": len(tae_bars),
            "mean_bars": float(np.mean(tae_bars)) if tae_bars else None,
            "median_bars": float(np.median(tae_bars)) if tae_bars else None,
            "pct_within_2_bars": (
                100.0 * sum(1 for b in tae_bars if b <= 2) / len(tae_bars) if tae_bars else None
            ),
            "pct_within_6_bars": (
                100.0 * sum(1 for b in tae_bars if b <= 6) / len(tae_bars) if tae_bars else None
            ),
        },
        "macd_cross_velocity_histogram": _velocity_histogram(velocities),
        "velocity_vs_win_t8_correlation": vel_predictive_corr,
        "bb_macd_correlation": _bb_macd_correlation(data, macd_frame),
        "permutation_test": perm,
        "backtest_trade_stats": trade_stats,
        "quantlog_path": str(quantlog_path) if quantlog_path else None,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "metrics_summary.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    perm_path = output_dir / "permutation_results.json"
    perm_path.write_text(json.dumps(perm, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze EXP-MACD-MECH-001 run")
    parser.add_argument(
        "--config",
        type=Path,
        default=_QB / "configs" / "exp_macd_mech_001.yaml",
    )
    parser.add_argument("--quantlog", type=Path, default=None, help="Path to run .jsonl")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_QR / "experiments" / "EXP-MACD-MECH-001",
    )
    args = parser.parse_args()

    ql_path = args.quantlog
    if ql_path is None:
        cfg = load_config(args.config)
        ql_cfg = cfg.get("quantlog") or {}
        ql_base = quantbuild_repo_root() / Path(ql_cfg.get("base_path", "data/quantlog_events"))
        ql_path = _find_latest_run_jsonl(ql_base)

    analyze(config_path=args.config, quantlog_path=ql_path, output_dir=args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
