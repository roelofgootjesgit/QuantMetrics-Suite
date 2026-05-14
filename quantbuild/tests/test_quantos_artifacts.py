"""QuantBuild -> QuantOS artifact collection helpers."""

from __future__ import annotations

from pathlib import Path

import yaml

from src.quantbuild.integration.quantos_artifacts import _artifact_role


def test_artifact_role_preserves_safe_matrix_names() -> None:
    assert _artifact_role("variant_xauusd") == "variant_xauusd"
    assert _artifact_role("B1 London Only") == "b1_london_only"
    assert _artifact_role("../../variant") == "variant"
    assert _artifact_role("") == "single"


def test_exp003_configs_have_distinct_artifact_roles() -> None:
    cfg_dir = Path(__file__).resolve().parents[1] / "configs" / "experiments" / "exp003_overlap_breakout"
    roles: list[str] = []
    for path in sorted(cfg_dir.glob("*.yaml")):
        cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
        roles.append(_artifact_role((cfg.get("artifacts") or {}).get("role")))

    assert len(roles) == 5
    assert len(set(roles)) == len(roles)
    assert all(role.startswith("variant_") for role in roles)
