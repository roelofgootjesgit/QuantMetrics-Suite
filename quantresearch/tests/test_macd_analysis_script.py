"""Regression tests for EXP-MACD-MECH-001 analysis helpers."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


def _load_analysis_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "analyze_exp_macd_mech_001.py"
    spec = importlib.util.spec_from_file_location("analyze_exp_macd_mech_001", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_event(path: Path, strategy_id: str) -> None:
    path.write_text(
        json.dumps(
            {
                "event_type": "trade_closed",
                "strategy_id": strategy_id,
                "payload": {"pnl_r": 1.0},
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_find_latest_run_jsonl_ignores_newer_unrelated_experiment(tmp_path: Path) -> None:
    module = _load_analysis_module()
    runs = tmp_path / "runs"
    runs.mkdir()
    matching = runs / "macd.jsonl"
    unrelated = runs / "bb.jsonl"
    _write_event(matching, "EXP-MACD-MECH-001")
    _write_event(unrelated, "EXP-BB-MECH-001")
    os.utime(matching, (1000, 1000))
    os.utime(unrelated, (2000, 2000))

    assert module._find_latest_run_jsonl(tmp_path, "EXP-MACD-MECH-001") == matching


def test_analyze_uses_directional_permutation_for_short_signals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_analysis_module()
    dates = pd.date_range("2024-01-01", periods=20, freq="15min", tz="UTC")
    close = np.full(20, 10.0)
    close[9] = 8.0
    data = pd.DataFrame(
        {"open": close, "high": close + 0.1, "low": close - 0.1, "close": close},
        index=dates,
    )
    false = pd.Series(False, index=dates)
    macd_frame = pd.DataFrame(
        {"bullish_cross": false, "bearish_cross": false, "histogram": np.zeros(len(data))},
        index=dates,
    )
    cfg = {
        "experiment_id": "EXP-MACD-MECH-001",
        "symbol": "EURUSD",
        "data": {"base_path": "unused"},
        "backtest": {"start_date": "2024-01-01", "end_date": "2024-01-01"},
        "strategy": {},
        "risk": {"sl_atr_mult": 2.0},
    }
    monkeypatch.setattr(module, "load_config", lambda _path: cfg)
    monkeypatch.setattr(module, "quantbuild_repo_root", lambda: tmp_path)
    monkeypatch.setattr(module, "load_parquet", lambda *_args, **_kwargs: data)
    monkeypatch.setattr(module, "macd_only_strategy_cfg", lambda _cfg: cfg)
    monkeypatch.setattr(module, "compute_macd_frame", lambda _data, _macd_cfg: macd_frame)
    monkeypatch.setattr(module, "compute_atr", lambda _data, period=14: pd.Series(1.0, index=dates))
    monkeypatch.setattr(module, "detect_macd_component_observations", lambda _frame: (false, false))
    monkeypatch.setattr(
        module,
        "collect_macd_entry_signals",
        lambda *_args, **_kwargs: [
            {
                "bar_index": 1,
                "direction": "SHORT",
                "macd_cross_velocity": 0.0,
            }
        ],
    )

    summary = module.analyze(
        config_path=tmp_path / "config.yaml",
        quantlog_path=None,
        output_dir=tmp_path / "out",
    )

    assert summary["permutation_test"]["observed_hit_rate"] == 1.0
