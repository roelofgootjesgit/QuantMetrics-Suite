"""Contract tests for BB/MACD signal research QuantLog event types."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from quantlog.validate.validator import validate_path


class TestBBMacdSignalResearchContract(unittest.TestCase):
    def test_fixture_validates_without_errors(self) -> None:
        path = Path("tests/fixtures/contracts/bb_macd_signal_research.jsonl")
        report = validate_path(path)
        errors = [i for i in report.issues if i.level == "error"]
        self.assertEqual(errors, [], [e.message for e in errors])

    def test_invalid_component_type_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            event_file = Path(tmp) / "bad.jsonl"
            event = {
                "event_id": "00000000-0000-0000-0000-000000000201",
                "event_type": "component_observed",
                "event_version": 1,
                "timestamp_utc": "2026-06-01T12:00:00Z",
                "ingested_at_utc": "2026-06-01T12:00:01Z",
                "source_system": "quantbuild",
                "source_component": "bb_macd_research",
                "environment": "backtest",
                "run_id": "run_x",
                "session_id": "sess_x",
                "source_seq": 1,
                "trace_id": "trace_x",
                "severity": "info",
                "payload": {
                    "observation_id": "obs_x",
                    "component_type": "NOT_A_REAL_TYPE",
                    "bar_timestamp": "2026-06-01T12:00:00Z",
                    "session_at_signal": "LONDON",
                    "regime_at_signal": "TREND",
                },
            }
            event_file.write_text(json.dumps(event) + "\n", encoding="utf-8")
            report = validate_path(event_file)
            errors = [i.message for i in report.issues if i.level == "error"]
            self.assertTrue(
                any("component_observed_invalid_component_type" in m for m in errors),
                errors,
            )


if __name__ == "__main__":
    unittest.main()
