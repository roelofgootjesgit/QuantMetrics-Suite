"""#124 E1/C1 — read-only observation of committed EXP-2021-2025 ledger validation.

validatie van de echte experimentrecords: NOT RUN in CI (artefacten niet in repo)

CI (typically POSIX) exercises the unavailable ``suite_root`` branch of C1.
Full QuantOS artefact validation for these EXP ids is only asserted when the
configured ``suite_root`` actually exists as a directory on the running machine
(developer Windows checkout with artefacts present). Do not invent artefacts.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quantresearch.ledger import load_experiment, load_links, validate_experiment

COMMITTED_EXP_IDS = (
    "EXP-2021-2025-throughput-discovery-v1",
    "EXP-2021-2025-session-relax-watchlist-v1",
)

SUITE_ROOT_ERR = "suite.suite_root missing or invalid — cannot verify QuantOS artifacts"


def _configured_suite_root(eid: str) -> Path:
    exp = load_experiment(eid)
    raw = str((exp.get("suite") or {}).get("suite_root") or "").strip()
    assert raw, f"{eid}: committed experiment.json must declare suite.suite_root"
    return Path(raw)


@pytest.mark.parametrize("eid", COMMITTED_EXP_IDS)
def test_committed_exp_validate_c1_suite_root_branch(eid: str):
    """C1 machine-dependent exact asserts — no skip/xfail/soft membership checks.

    - configured suite_root not a directory → errs == [SUITE_ROOT_ERR] exactly
    - configured suite_root is a directory → errs == [] (full artefact validation)

    CI documents/uses the unavailable-root branch (Windows ``C:/...`` is not a
    local directory on POSIX). Do not assume ``C:/...`` is valid on Linux.
    """
    root = _configured_suite_root(eid)
    errs = validate_experiment(eid)
    if root.is_dir():
        assert errs == [], errs
    else:
        assert errs == [SUITE_ROOT_ERR], errs


def test_committed_exp_existing_suite_root_missing_runs_not_auto_green(monkeypatch):
    """C1 existing-root branch via path-scoped Path.is_dir monkeypatch.

    Making only the configured suite_root appear to exist must **not** yield
    ``errs == []`` when QuantOS run trees are absent — expect exact run/artefact
    validation errors (not the suite_root-missing message).
    """
    eid = "EXP-2021-2025-throughput-discovery-v1"
    exp = load_experiment(eid)
    links = load_links(eid) or {}
    suite_root = _configured_suite_root(eid)
    suite_key = suite_root.resolve()
    qrd = str(links.get("quantos_run_dir") or "").strip()
    assert qrd, "committed links.json must declare quantos_run_dir"
    cap = str(exp.get("canonical_artifact_path") or "").strip()
    assert cap, "committed experiment.json must declare canonical_artifact_path"

    expected_run = (suite_key / qrd).resolve()
    expected_cap = (suite_key / cap).resolve()
    expected_errs = [
        f"QuantOS run dir does not exist: {expected_run}",
        f"canonical_artifact_path is not a directory: {expected_cap}",
    ]

    real_is_dir = Path.is_dir

    def scoped_is_dir(self: Path) -> bool:  # noqa: N802 — matches Path.is_dir
        try:
            resolved = self.resolve()
        except OSError:
            resolved = self
        if resolved == suite_key or str(self) == str(suite_root):
            return True
        return real_is_dir(self)

    monkeypatch.setattr(Path, "is_dir", scoped_is_dir)

    assert suite_root.is_dir()
    assert not expected_run.is_dir()

    errs = validate_experiment(eid)
    assert errs == expected_errs, errs
