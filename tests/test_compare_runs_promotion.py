"""Regression: compare_runs must not PROMOTE without absolute positive expectancy."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


def _load_compare_runs():
    path = Path(__file__).resolve().parents[1] / "quantmetrics_os" / "scripts" / "compare_runs.py"
    spec = importlib.util.spec_from_file_location("compare_runs", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_events(
    pnl_r: float,
    *,
    n: int = 120,
    months: tuple[str, ...] = ("2024-01", "2024-02", "2024-03"),
    with_ts: bool = True,
    action_rate_den: int = 200,
    enters: int = 20,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for _ in range(action_rate_den):
        events.append(
            {
                "event_type": "signal_evaluated",
                "timestamp_utc": "2024-01-01T00:00:00Z",
                "payload": {},
            }
        )
    for _ in range(enters):
        events.append(
            {
                "event_type": "trade_action",
                "timestamp_utc": "2024-01-01T00:00:00Z",
                "payload": {"decision": "ENTER"},
            }
        )
    per = n // len(months)
    for month in months:
        for _ in range(per):
            ev: dict[str, Any] = {"event_type": "trade_closed", "payload": {"pnl_r": pnl_r}}
            if with_ts:
                ev["timestamp_utc"] = f"{month}-15T12:00:00Z"
            events.append(ev)
    for _ in range(n - per * len(months)):
        events.append(
            {
                "event_type": "trade_closed",
                "timestamp_utc": f"{months[-1]}-20T12:00:00Z",
                "payload": {"pnl_r": pnl_r},
            }
        )
    for guard_name, count in (("spread_guard", 10), ("news_guard", 8), ("cooldown_guard", 7)):
        for _ in range(count):
            events.append(
                {
                    "event_type": "risk_guard_decision",
                    "payload": {"decision": "BLOCK", "guard_name": guard_name},
                }
            )
    return events


def test_rejects_negative_expectancy_even_if_improved() -> None:
    mod = _load_compare_runs()
    result = mod.build_comparison(
        baseline_events=_make_events(-0.50),
        candidate_events=_make_events(-0.40),
        min_trades=100,
        max_guard_dominance=0.60,
    )
    assert result["verdict"] == "REJECT"
    assert any("not strictly positive" in r for r in result["reasons"])


def test_rejects_equal_negative_expectancy() -> None:
    mod = _load_compare_runs()
    result = mod.build_comparison(
        baseline_events=_make_events(-0.30),
        candidate_events=_make_events(-0.30),
        min_trades=100,
        max_guard_dominance=0.60,
    )
    assert result["verdict"] == "REJECT"
    assert any("not strictly positive" in r for r in result["reasons"])


def test_rejects_worse_candidate_when_month_consistency_unavailable() -> None:
    mod = _load_compare_runs()
    result = mod.build_comparison(
        baseline_events=_make_events(-0.10, with_ts=False),
        candidate_events=_make_events(-0.80, with_ts=False),
        min_trades=100,
        max_guard_dominance=0.60,
    )
    assert result["verdict"] == "REJECT"
    joined = " ".join(result["reasons"])
    assert "not strictly positive" in joined
    assert "does not improve on baseline" in joined


def test_promotes_positive_improved_candidate() -> None:
    mod = _load_compare_runs()
    result = mod.build_comparison(
        baseline_events=_make_events(0.10),
        candidate_events=_make_events(0.25),
        min_trades=100,
        max_guard_dominance=0.60,
    )
    assert result["verdict"] == "PROMOTE"
    assert result["candidate"]["performance"]["expectancy_r"] == 0.25
    assert result["gates"]["require_positive_candidate_expectancy"] is True
    assert result["gates"]["require_expectancy_improvement"] is True
