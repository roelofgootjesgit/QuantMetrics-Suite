"""EXP-003 matrix: run London/NY overlap breakout backtest for all preregistered instruments."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

QUANTBUILD_ROOT = Path(__file__).resolve().parents[2] / "quantbuild"
CONFIG_BASE = QUANTBUILD_ROOT / "configs" / "experiments" / "exp003_overlap_breakout"

INSTRUMENTS = [
    {"symbol": "XAUUSD", "config": "XAUUSD.yaml"},
    {"symbol": "NAS100", "config": "NAS100.yaml"},
    {"symbol": "US30", "config": "US30.yaml"},
    {"symbol": "EURUSD", "config": "EURUSD.yaml"},
    {"symbol": "GBPUSD", "config": "GBPUSD.yaml"},
]


def main() -> int:
    results = []
    failed = False
    for inst in INSTRUMENTS:
        config_path = CONFIG_BASE / inst["config"]
        print(f"\n[EXP-003] Running {inst['symbol']}...")

        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.quantbuild.app",
                "--config",
                str(config_path),
                "backtest",
            ],
            cwd=QUANTBUILD_ROOT,
            capture_output=False,
            text=True,
        )

        results.append(
            {
                "symbol": inst["symbol"],
                "config": inst["config"],
                "exit_code": proc.returncode,
                "ran_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        )

        if proc.returncode != 0:
            failed = True
            print(f"[EXP-003] FAILED: {inst['symbol']} exit {proc.returncode}")

    summary_path = Path(__file__).resolve().parent.parent / "runs" / "EXP-003" / "matrix_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(
            {
                "experiment_id": "EXP-003",
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "runs": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\n[EXP-003] Matrix summary: {summary_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
