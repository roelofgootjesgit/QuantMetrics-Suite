"""Locate QuantLog repository for subprocess CLI (validate-events, etc.)."""

from __future__ import annotations

import os
from pathlib import Path

from src.quantbuild.suite_layout import canonical_quantlog_repo_path


def quantbuild_project_root() -> Path:
    """Root of quantbuild (contains ``src/``, ``tests/``, ``configs/``)."""
    return Path(__file__).resolve().parents[2]


def _has_quantlog_src(repo: Path) -> bool:
    return (repo / "src" / "quantlog").is_dir()


def resolve_quantlog_repo_path() -> Path | None:
    """Path to QuantLog clone with ``src/quantlog``, or ``None`` if not found.

    Precedence (issue #119 Impl-A / O2):
    1. Explicit ``QUANTLOG_REPO_PATH`` / ``QUANTLOG_ROOT`` (env wins).
    2. ``canonical_quantlog_repo_path()`` when suite-root env is set.
    3. Monorepo sibling ``<quantbuild_root>/../quantlog`` when ``src/quantlog`` exists.
    """
    for env_key in ("QUANTLOG_REPO_PATH", "QUANTLOG_ROOT"):
        raw = os.environ.get(env_key, "").strip()
        if not raw:
            continue
        p = Path(raw)
        if _has_quantlog_src(p):
            return p.resolve()

    try:
        canonical = canonical_quantlog_repo_path()
    except Exception:
        canonical = None
    if canonical is not None and _has_quantlog_src(canonical):
        return canonical.resolve()

    sibling = quantbuild_project_root().parent / "quantlog"
    if _has_quantlog_src(sibling):
        return sibling.resolve()
    return None


def quantlog_pythonpath_prefix(repo: Path) -> str:
    return str((repo / "src").resolve())
