"""Tests for QuantLog repository path resolution (#119 N1 / O2)."""

from pathlib import Path

from src.quantbuild.quantlog_repo import quantbuild_project_root, resolve_quantlog_repo_path


def _fake_repo(root: Path) -> Path:
    (root / "src" / "quantlog").mkdir(parents=True)
    return root


def _clear_quantlog_and_suite_env(monkeypatch) -> None:
    for key in (
        "QUANTLOG_REPO_PATH",
        "QUANTLOG_ROOT",
        "QUANTMETRICS_SUITE_ROOT",
        "QUANTMETRICS_OS_ROOT",
    ):
        monkeypatch.delenv(key, raising=False)


def test_resolve_accepts_quantlog_root(tmp_path, monkeypatch):
    good = _fake_repo(tmp_path / "ql")
    monkeypatch.delenv("QUANTLOG_REPO_PATH", raising=False)
    monkeypatch.setenv("QUANTLOG_ROOT", str(good))
    assert resolve_quantlog_repo_path() == good.resolve()


def test_resolve_prefers_repo_path_over_root(tmp_path, monkeypatch):
    preferred = _fake_repo(tmp_path / "a")
    other = _fake_repo(tmp_path / "b")
    monkeypatch.setenv("QUANTLOG_REPO_PATH", str(preferred))
    monkeypatch.setenv("QUANTLOG_ROOT", str(other))
    assert resolve_quantlog_repo_path() == preferred.resolve()


def test_resolve_falls_back_to_root_when_repo_path_invalid(tmp_path, monkeypatch):
    fallback = _fake_repo(tmp_path / "ok")
    monkeypatch.setenv("QUANTLOG_REPO_PATH", str(tmp_path / "missing"))
    monkeypatch.setenv("QUANTLOG_ROOT", str(fallback))
    assert resolve_quantlog_repo_path() == fallback.resolve()


def test_resolve_sibling_when_no_env(monkeypatch):
    """Monorepo: sibling quantlog resolves without QUANTLOG_* or suite-root env."""
    _clear_quantlog_and_suite_env(monkeypatch)
    sibling = quantbuild_project_root().parent / "quantlog"
    assert (sibling / "src" / "quantlog").is_dir(), "expected monorepo quantlog sibling"
    resolved = resolve_quantlog_repo_path()
    assert resolved == sibling.resolve()


def test_resolve_env_wins_over_sibling(tmp_path, monkeypatch):
    """Explicit QUANTLOG_REPO_PATH wins even when monorepo sibling exists."""
    fake = _fake_repo(tmp_path / "override-ql")
    monkeypatch.setenv("QUANTLOG_REPO_PATH", str(fake))
    monkeypatch.delenv("QUANTLOG_ROOT", raising=False)
    monkeypatch.delenv("QUANTMETRICS_SUITE_ROOT", raising=False)
    monkeypatch.delenv("QUANTMETRICS_OS_ROOT", raising=False)
    sibling = quantbuild_project_root().parent / "quantlog"
    assert (sibling / "src" / "quantlog").is_dir()
    assert resolve_quantlog_repo_path() == fake.resolve()
    assert resolve_quantlog_repo_path() != sibling.resolve()
