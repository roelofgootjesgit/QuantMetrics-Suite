#!/usr/bin/env python3
"""Post-run analytics for EXP-MACD-MECH-001 (forward returns, TAE, permutation)."""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any, Iterable

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
    simulate_macd_time_exit_trade,
)


EXPERIMENT_ID = "EXP-MACD-MECH-001"


def _strategy_ids_for_config(cfg: dict[str, Any]) -> set[str]:
    ids = {EXPERIMENT_ID, "macd_only"}
    experiment_id = cfg.get("experiment_id")
    if experiment_id:
        ids.add(str(experiment_id))
    return ids


def _event_matches_strategy(event: dict[str, Any], strategy_ids: set[str]) -> bool:
    strategy_id = event.get("strategy_id")
    return strategy_id is not None and str(strategy_id) in strategy_ids


def _jsonl_contains_strategy(path: Path, strategy_ids: set[str]) -> bool:
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if _event_matches_strategy(ev, strategy_ids):
                    return True
    except OSError:
        return False
    return False


def _find_latest_matching_run_jsonl(ql_base: Path, strategy_ids: set[str]) -> Path | None:
    runs = ql_base / "runs"
    if not runs.is_dir():
        return None
    files = sorted(runs.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in files:
        if _jsonl_contains_strategy(path, strategy_ids):
            return path
    return None


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


def _empty_summary() -> dict[str, Any]:
    neutral_perm = {
        "observed_hit_rate": 0.0,
        "baseline_mean_hit_rate": 0.0,
        "p_value": 1.0,
        "significant": False,
        "n_signals": 0,
        "n_permutations": 0,
        "seed": 42,
        "n_long_signals": 0,
        "n_short_signals": 0,
        "horizon_bars": 8,
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "data_first_bar": None,
        "data_last_bar": None,
        "n_bars": 0,
        "raw_macd_crosses": 0,
        "independent_signals": 0,
        "executable_signals": 0,
        "analysis_population": "executable_signals",
        "clustering_rate": 0.0,
        "forward_returns_r": {
            f"T+{h}": {"n": 0, "mean": None, "median": None, "std": None}
            for h in (4, 8, 16)
        },
        "win_rate_at_T8": None,
        "time_to_adverse_excursion": {
            "threshold_r": 0.5,
            "n_measured": 0,
            "mean_bars": None,
            "median_bars": None,
            "pct_within_2_bars": None,
            "pct_within_6_bars": None,
        },
        "macd_cross_velocity_histogram": _velocity_histogram([]),
        "velocity_vs_win_t8_correlation": None,
        "bb_macd_correlation": {
            "co_occurrence_same_bar": 0,
            "bb_only_bars": 0,
            "macd_only_bars": 0,
            "neither_bars": 0,
            "pearson_same_bar": 0.0,
            "joint_rate": 0.0,
        },
        "permutation_test": neutral_perm,
        "backtest_trade_stats": {},
        "quantlog_path": None,
        "status": "no_data",
    }


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


def _sample_without_replacement(
    rng: np.random.Generator,
    values: np.ndarray,
    size: int,
) -> np.ndarray:
    if size == 0:
        return np.array([], dtype=float)
    return rng.choice(values, size=size, replace=False)


def _directional_permutation_test(
    data: pd.DataFrame,
    atr_series: pd.Series,
    entries: Iterable[dict[str, Any]],
    *,
    horizon: int = 8,
    n_permutations: int = 2000,
    seed: int = 42,
) -> dict[str, float | int | bool]:
    """Compare MACD returns with random timestamps while preserving signal direction mix."""
    entries = list(entries)
    if not entries:
        return {
            "observed_hit_rate": 0.0,
            "baseline_mean_hit_rate": 0.0,
            "p_value": 1.0,
            "significant": False,
            "n_signals": 0,
            "n_permutations": n_permutations,
            "seed": seed,
            "n_long_signals": 0,
            "n_short_signals": 0,
            "horizon_bars": horizon,
        }

    close_arr = data["close"].values.astype(float)
    atr_arr = atr_series.values.astype(float)
    long_universe: list[float] = []
    short_universe: list[float] = []
    for i in range(max(0, len(close_arr) - horizon)):
        atr_v = float(atr_arr[i])
        if not math.isfinite(atr_v) or atr_v <= 0:
            continue
        entry = float(close_arr[i])
        exit_p = float(close_arr[i + horizon])
        if not math.isfinite(entry) or not math.isfinite(exit_p):
            continue
        long_r = (exit_p - entry) / (2.0 * atr_v)
        long_universe.append(long_r)
        short_universe.append(-long_r)

    observed: list[float] = []
    n_long = 0
    n_short = 0
    for sig in entries:
        direction = str(sig["direction"])
        r = _forward_return_r(data, atr_series, int(sig["bar_index"]), direction, horizon)
        if r is None:
            continue
        observed.append(float(r))
        if direction == "LONG":
            n_long += 1
        else:
            n_short += 1

    if not observed:
        return {
            "observed_hit_rate": 0.0,
            "baseline_mean_hit_rate": 0.0,
            "p_value": 1.0,
            "significant": False,
            "n_signals": 0,
            "n_permutations": n_permutations,
            "seed": seed,
            "n_long_signals": 0,
            "n_short_signals": 0,
            "horizon_bars": horizon,
        }

    long_arr = np.array(long_universe, dtype=float)
    short_arr = np.array(short_universe, dtype=float)
    if n_long > len(long_arr) or n_short > len(short_arr):
        raise ValueError("not enough universe outcomes for directional permutation")

    observed_mean = float(np.mean(observed))
    rng = np.random.default_rng(seed)
    perm_rates = np.empty(n_permutations, dtype=float)
    for i in range(n_permutations):
        samples = []
        if n_long:
            samples.append(_sample_without_replacement(rng, long_arr, n_long))
        if n_short:
            samples.append(_sample_without_replacement(rng, short_arr, n_short))
        perm_rates[i] = float(np.mean(np.concatenate(samples)))

    baseline_mean = float(np.mean(perm_rates))
    p_value = float(np.mean(perm_rates >= observed_mean))
    return {
        "observed_hit_rate": observed_mean,
        "baseline_mean_hit_rate": baseline_mean,
        "p_value": p_value,
        "significant": p_value < 0.05,
        "n_signals": len(observed),
        "n_permutations": n_permutations,
        "seed": seed,
        "n_long_signals": n_long,
        "n_short_signals": n_short,
        "horizon_bars": horizon,
    }


def _executable_macd_entries(
    data: pd.DataFrame,
    entries: Iterable[dict[str, Any]],
    strat_cfg: dict[str, Any],
    atr_series: pd.Series,
) -> list[dict[str, Any]]:
    """Mirror the backtest admission rules so analytics describe traded signals."""
    exit_cfg = strat_cfg.get("exit") or {}
    risk_cfg = strat_cfg.get("risk") or {}
    sl_atr_mult = float(risk_cfg.get("sl_atr_mult", 2.0))
    time_exit_bars = int(exit_cfg.get("time_exit_bars", 8))
    max_concurrent = int(risk_cfg.get("max_concurrent", 1))
    max_daily_loss_r = float(risk_cfg.get("max_daily_loss_r", 2.0))

    executable: list[dict[str, Any]] = []
    daily_pnl_r: dict[Any, float] = {}
    open_until_bar = -1
    atr_arr = atr_series.values.astype(float)

    for sig in entries:
        i = int(sig["bar_index"])
        if i <= open_until_bar and max_concurrent <= 1:
            continue

        entry_ts = data.index[i]
        trade_date = entry_ts.date()
        if daily_pnl_r.get(trade_date, 0.0) <= -max_daily_loss_r:
            continue

        result = simulate_macd_time_exit_trade(
            data,
            i,
            str(sig["direction"]),
            atr_arr=atr_arr,
            sl_atr_mult=sl_atr_mult,
            time_exit_bars=time_exit_bars,
        )
        open_until_bar = int(result["exit_bar_idx"])
        daily_pnl_r[trade_date] = daily_pnl_r.get(trade_date, 0.0) + float(result["profit_r"])
        executable.append(dict(sig))

    return executable


def _load_trade_stats(quantlog_path: Path, strategy_ids: set[str]) -> dict[str, Any]:
    closed = []
    with quantlog_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            ev = json.loads(line)
            if ev.get("event_type") == "trade_closed" and _event_matches_strategy(ev, strategy_ids):
                closed.append(ev.get("payload") or {})
    if not closed:
        return {}
    pnl_r = [float(c.get("pnl_r", 0)) for c in closed]
    return {
        "n_trades": len(closed),
        "expectancy_r": float(np.mean(pnl_r)),
        "win_rate_pct": 100.0 * sum(1 for r in pnl_r if r > 0) / len(pnl_r),
        "profit_factor": (
            sum(r for r in pnl_r if r > 0) / abs(sum(r for r in pnl_r if r < 0))
            if sum(r for r in pnl_r if r < 0)
            else None
        ),
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
    if data.empty:
        summary = _empty_summary()
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / "metrics_summary.json"
        out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        perm_path = output_dir / "permutation_results.json"
        perm_path.write_text(json.dumps(summary["permutation_test"], indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2))
        return summary

    strat_cfg = macd_only_strategy_cfg(cfg)
    strategy_ids = _strategy_ids_for_config(cfg)
    macd_cfg = strat_cfg.get("macd") or {}
    macd_frame = compute_macd_frame(data, macd_cfg)
    atr_series = compute_atr(data, period=14)

    entries = collect_macd_entry_signals(data, strat_cfg, session_mode=bt.get("session_mode", "extended"))
    executable_entries = _executable_macd_entries(data, entries, strat_cfg, atr_series)
    bull_raw, bear_raw = detect_macd_component_observations(macd_frame)
    raw_n = int(bull_raw.sum() + bear_raw.sum())
    indep_n = len(entries)
    clustering_rate = 1.0 - (indep_n / raw_n) if raw_n else 0.0

    horizons = [4, 8, 16]
    fwd: dict[str, list[float]] = {f"T+{h}": [] for h in horizons}
    tae_bars: list[int] = []
    velocities: list[float] = []
    t8_wins = 0
    t8_n = 0

    sl_mult = float((strat_cfg.get("risk") or {}).get("sl_atr_mult", 2.0))

    for sig in executable_entries:
        i = int(sig["bar_index"])
        direction = sig["direction"]
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

    perm = _directional_permutation_test(data, atr_series, executable_entries, n_permutations=2000, seed=42)

    # Velocity vs win at T+8
    vel_win_pairs: list[tuple[float, int]] = []
    for sig in executable_entries:
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
        trade_stats = _load_trade_stats(quantlog_path, strategy_ids)

    summary: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "data_first_bar": str(data.index.min()) if len(data) else None,
        "data_last_bar": str(data.index.max()) if len(data) else None,
        "n_bars": len(data),
        "raw_macd_crosses": raw_n,
        "independent_signals": indep_n,
        "executable_signals": len(executable_entries),
        "analysis_population": "executable_signals",
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
        ql_path = _find_latest_matching_run_jsonl(ql_base, _strategy_ids_for_config(cfg))

    analyze(config_path=args.config, quantlog_path=ql_path, output_dir=args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
