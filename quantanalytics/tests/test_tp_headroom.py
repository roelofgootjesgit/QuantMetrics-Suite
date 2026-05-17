"""Tests for TP headroom report (tp_headroom_v1)."""

from __future__ import annotations

import pytest

from quantmetrics_analytics.analysis.tp_headroom import (
    SCHEMA_VERSION,
    TP_SCENARIO_MULTIPLIERS,
    build_tp_headroom_report,
)


def _tc(run_id: str, exit_tag: str, pnl: float, mfe: float) -> dict:
    return {
        "event_type": "trade_closed",
        "run_id": run_id,
        "payload": {"exit": exit_tag, "pnl_r": pnl, "mfe_r": mfe},
    }


def test_headroom_mfe_minus_pnl():
    rid = "qb_h1"
    # TP: pnl 2, mfe 3 -> headroom 1; pnl 1, mfe 4 -> headroom 3
    events = [
        _tc(rid, "TP", 2.0, 3.0),
        _tc(rid, "TP", 1.0, 4.0),
        _tc(rid, "SL", -1.0, 0.5),
    ]
    rep = build_tp_headroom_report(events, run_id=rid, experiment_id="E")
    assert rep["schema_version"] == SCHEMA_VERSION
    assert rep["tp_trades_n"] == 2
    h = rep["headroom"]
    assert h["mean"] == pytest.approx(2.0)
    assert h["median"] == pytest.approx(2.0)
    assert h["min"] == pytest.approx(1.0)
    assert h["max"] == pytest.approx(3.0)


def test_scenario_filter_counts_and_mean_r():
    rid = "qb_h2"
    # Trade A: pnl 2, mfe 5 — x1.5 need >=3 yes; x2 need >=4 yes; x2.5 need >=5 yes; x3 need >=6 no
    # Trade B: pnl 1, mfe 1.2 — all scaled thresholds fail vs modest multipliers
    events = [
        _tc(rid, "TP", 2.0, 5.0),
        _tc(rid, "TP", 1.0, 1.2),
    ]
    rep = build_tp_headroom_report(events, run_id=rid, experiment_id="E")
    scen = {float(r["tp_multiplier"]): r for r in rep["tp_level_scenarios"]}
    assert set(scen.keys()) == set(TP_SCENARIO_MULTIPLIERS)

    assert scen[1.5]["trades_still_hit"] == 1  # only A: 5 >= 3
    assert scen[1.5]["mean_r_if_hit"] == pytest.approx(1.5 * 2.0)

    assert scen[2.0]["trades_still_hit"] == 1  # 5 >= 4
    assert scen[2.0]["mean_r_if_hit"] == pytest.approx(2.0 * 2.0)

    assert scen[2.5]["trades_still_hit"] == 1  # 5 >= 5
    assert scen[2.5]["mean_r_if_hit"] == pytest.approx(2.5 * 2.0)

    assert scen[3.0]["trades_still_hit"] == 0
    assert scen[3.0]["mean_r_if_hit"] is None


