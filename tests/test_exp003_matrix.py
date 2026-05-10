from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


def _load_exp003_matrix_module():
    path = Path(__file__).resolve().parents[1] / "quantmetrics_os" / "scripts" / "run_exp003_matrix.py"
    spec = importlib.util.spec_from_file_location("run_exp003_matrix_for_test", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_exp003_matrix_returns_nonzero_when_any_instrument_fails(tmp_path: Path, monkeypatch) -> None:
    module = _load_exp003_matrix_module()
    module.QUANTBUILD_ROOT = tmp_path / "quantbuild"
    module.CONFIG_BASE = tmp_path / "configs"
    module.RUNS_BASE = tmp_path / "runs"
    module.INSTRUMENTS = [
        {"symbol": "XAUUSD", "config": "XAUUSD.yaml"},
        {"symbol": "NAS100", "config": "NAS100.yaml"},
    ]
    module.QUANTBUILD_ROOT.mkdir()
    module.CONFIG_BASE.mkdir()

    returncodes = iter([0, 2])

    def fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=next(returncodes))

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module.main() == 1
    assert (module.RUNS_BASE / "EXP-003" / "matrix_summary.json").is_file()
