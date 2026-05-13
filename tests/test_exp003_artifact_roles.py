"""Regression tests for EXP-003 matrix artifact destinations."""

from __future__ import annotations

from pathlib import Path

import yaml


def test_exp003_artifact_roles_are_unique_per_instrument() -> None:
    config_dir = (
        Path(__file__).resolve().parents[1]
        / "quantbuild"
        / "configs"
        / "experiments"
        / "exp003_overlap_breakout"
    )
    roles = {}

    for path in sorted(config_dir.glob("*.yaml")):
        cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
        symbol = str(cfg["symbol"]).lower()
        role = cfg["artifacts"]["role"]
        roles[path.name] = role
        assert role == f"variant_{symbol}"

    assert len(set(roles.values())) == len(roles)
