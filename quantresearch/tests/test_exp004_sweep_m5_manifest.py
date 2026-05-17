"""Regression tests for EXP-004 frozen sweep-research manifest (XAUUSD M5 PDH/PDL)."""

from __future__ import annotations

import pytest

from quantresearch.sweep_m5_research_manifest import EXP004_ID, load_results_manifest, results_manifest_path


def test_manifest_file_exists():
    p = results_manifest_path()
    assert p.is_file(), f"expected {p}"


def test_manifest_ids_and_verdict():
    m = load_results_manifest()
    assert m.get("experiment_id") == EXP004_ID
    assert m.get("verdict") == "VALIDATION_REQUIRED"


def test_pre_herrun_invalid_aggregate():
    m = load_results_manifest()
    inv = m["pre_herrun_invalid"]["outcomes_baseline_aggregate"]
    assert inv["n"] == 98
    assert inv["total_r"] == pytest.approx(-10.83, rel=0, abs=0.01)


def test_herrun_enter_and_h1():
    m = load_results_manifest()
    h = m["herrun_aligned"]
    assert h["funnel_combined"]["ENTER"] == 148
    assert h["enter_by_year"]["2024"] == 37
    agg = h["h1_outcomes_aligned"]
    assert agg["n"] == 148
    assert agg["expectancy_r"] == pytest.approx(0.03, abs=0.02)
    assert agg["profit_factor"] == pytest.approx(1.06, abs=0.02)
    assert h["h2"]["decision"] == "PASS"
