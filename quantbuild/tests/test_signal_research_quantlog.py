"""QuantBuild payload builders + QuantLog validator integration for signal research."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from src.quantbuild.execution.quantlog_emitter import QuantLogEmitter
from src.quantbuild.research.signal_research_quantlog import (
    build_candidate_signal_payload,
    build_component_observed_payload,
    build_trade_closed_research_payload,
)

_QUANTLOG_SRC = Path(__file__).resolve().parents[2] / "quantlog" / "src"
if _QUANTLOG_SRC.is_dir() and str(_QUANTLOG_SRC) not in sys.path:
    sys.path.insert(0, str(_QUANTLOG_SRC))

pytest.importorskip("quantlog")

from quantlog.validate.validator import validate_path  # noqa: E402


def _emit_research_chain(tmp_path: Path) -> Path:
    out = tmp_path / "research.jsonl"
    emitter = QuantLogEmitter(
        base_path=tmp_path,
        source_component="bb_macd_research",
        environment="backtest",
        run_id="run_test",
        session_id="sess_test",
        consolidated_path=out,
    )
    ts = "2026-06-01T12:00:00Z"
    trace = "trace_test_1"
    dc = "dc_test_1"

    emitter.emit(
        event_type="component_observed",
        trace_id=trace,
        payload=build_component_observed_payload(
            component_type="MACD_BULL_CROSS",
            bar_timestamp=ts,
            session_at_signal="NEW_YORK",
            regime_at_signal="TREND",
            macd_cross_bull=True,
        ),
        timestamp_utc=ts,
    )
    emitter.emit(
        event_type="candidate_signal",
        trace_id=trace,
        payload=build_candidate_signal_payload(
            component_type="MACD_BULL_CROSS",
            bar_timestamp=ts,
            session_at_signal="NEW_YORK",
            regime_at_signal="TREND",
            direction="LONG",
            signal_is_independent=True,
            macd_cross_bull=True,
        ),
        timestamp_utc=ts,
    )
    emitter.emit(
        event_type="signal_detected",
        trace_id=trace,
        decision_cycle_id=dc,
        payload={
            "signal_id": "sig_1",
            "type": "macd_entry",
            "direction": "LONG",
            "strength": 1.0,
            "bar_timestamp": ts,
            "session": "NewYork",
            "regime": "trend",
            "component_type": "MACD_BULL_CROSS",
            "macd_cross_bull": True,
            "signal_is_independent": True,
            "regime_at_signal": "TREND",
            "session_at_signal": "NEW_YORK",
        },
        timestamp_utc=ts,
    )
    emitter.emit(
        event_type="trade_action",
        trace_id=trace,
        decision_cycle_id=dc,
        payload={
            "decision": "ENTER",
            "reason": "all_guards_passed",
            "trade_id": "BT-test-1",
        },
        timestamp_utc="2026-06-01T12:00:01Z",
    )
    emitter.emit(
        event_type="trade_closed",
        trace_id=trace,
        order_ref="BT-test-1",
        payload=build_trade_closed_research_payload(
            trade_id="BT-test-1",
            exit_price=1.1,
            pnl_r=0.25,
            exit_reason="time_exit",
            bars_held=8,
            mfe_r=0.4,
            mae_r=0.2,
        ),
        timestamp_utc="2026-06-01T14:00:00Z",
    )
    return out


def test_emitter_research_events_validate(tmp_path: Path) -> None:
    path = _emit_research_chain(tmp_path)
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 5
    component_payload = json.loads(lines[0])["payload"]
    candidate_payload = json.loads(lines[1])["payload"]
    assert component_payload["session_at_signal"] == "NEW_YORK"
    assert component_payload["regime_at_signal"] == "TREND"
    assert candidate_payload["session_at_signal"] == "NEW_YORK"
    assert candidate_payload["regime_at_signal"] == "TREND"
    report = validate_path(path)
    errors = [i for i in report.issues if i.level == "error"]
    assert errors == [], [e.message for e in errors]


def test_component_observed_payload_required_keys() -> None:
    p = build_component_observed_payload(
        component_type="BB_UPPER_BREAK",
        bar_timestamp="2026-01-01T00:00:00Z",
        session_at_signal="LONDON",
        regime_at_signal="COMPRESSION",
        bb_upper_break=True,
    )
    for key in (
        "observation_id",
        "component_type",
        "bar_timestamp",
        "session_at_signal",
        "regime_at_signal",
    ):
        assert key in p
    assert p["session_at_signal"] == "LONDON"
    assert p["regime_at_signal"] == "COMPRESSION"


def test_candidate_signal_payload_preserves_session_and_regime() -> None:
    p = build_candidate_signal_payload(
        component_type="MACD_BEAR_CROSS",
        bar_timestamp="2026-01-01T00:00:00Z",
        session_at_signal="OVERLAP",
        regime_at_signal="EXPANSION",
        direction="SHORT",
        signal_is_independent=False,
        macd_cross_bear=True,
    )

    assert p["session_at_signal"] == "OVERLAP"
    assert p["regime_at_signal"] == "EXPANSION"
    assert p["signal_is_independent"] is False
