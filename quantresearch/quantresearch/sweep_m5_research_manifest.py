"""Load EXP-004 frozen sweep-research results (XAUUSD M5 PDH/PDL pipeline)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from quantresearch.paths import repo_root

EXP004_ID = "EXP-004"
_MANIFEST = Path("experiments") / EXP004_ID / "results_manifest.json"


def results_manifest_path(root: Path | None = None) -> Path:
    return (root or repo_root()) / _MANIFEST


def load_results_manifest(root: Path | None = None) -> dict[str, Any]:
    p = results_manifest_path(root)
    if not p.is_file():
        raise FileNotFoundError(f"EXP-004 manifest missing: {p}")
    with open(p, encoding="utf-8") as f:
        return json.load(f)
