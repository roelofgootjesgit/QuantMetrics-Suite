"""Regression tests for the sweep outcome simulator CLI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_year_is_required_before_loading_market_data() -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "sweep_outcome_sim.py"

    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "--year" in result.stderr
    assert "required" in result.stderr
