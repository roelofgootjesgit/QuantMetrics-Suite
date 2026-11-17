from __future__ import annotations

import json

import pytest

from quantresearch.dossier import render_experiment_dossier_md, write_experiment_dossier


def test_render_dossier_contains_governance_and_compare_rows(tmp_path, monkeypatch):
    """O1: synthetic dossier with edge_verdict rows — not real EXP-2021-2025 artefacts."""
    exp_root = tmp_path / "experiments"
    monkeypatch.setattr("quantresearch.ledger.experiments_dir", lambda: exp_root)
    exp_root.mkdir()
    eid = "EXP-SYN-DOSSIER"
    suite = tmp_path / "suite"
    run_rel = "quantmetrics_os/runs/SYN-DOSSIER"
    run_dir = suite / run_rel
    baseline = run_dir / "a0_baseline" / "analytics"
    baseline.mkdir(parents=True)
    (baseline / "edge_verdict.json").write_text(
        json.dumps(
            {
                "edge_verdict": "INCONCLUSIVE",
                "confidence": "LOW",
                "main_risk": "sample_size",
            }
        ),
        encoding="utf-8",
    )
    compare = {
        "generated_at_utc": "2026-01-01T00:00:00Z",
        "baseline_variant_folder": "a0_baseline",
        "variants": [
            {
                "variant_folder": "a0_baseline",
                "promotion_decision": "VALIDATION_REQUIRED",
                "confidence": "LOW",
                "total_trades": 10,
                "expectancy_r": 0.1,
                "profit_factor": 1.2,
                "max_drawdown_r": 0.5,
            }
        ],
        "conclusions": {
            "discovery_rule_summary": {"note": "synthetic"},
            "watchlist_by_variant": {"a0_baseline": "WATCHLIST"},
        },
    }
    compare_path = run_dir / "THROUGHPUT_COMPARE.json"
    compare_path.write_text(json.dumps(compare), encoding="utf-8")

    d = exp_root / eid
    d.mkdir()
    (d / "hypothesis.md").write_text("# H\n", encoding="utf-8")
    (d / "experiment_plan.md").write_text("# P\n", encoding="utf-8")
    (d / "decision.md").write_text("# D\n\n## Final Decision\n\nX\n", encoding="utf-8")
    (d / "experiment.json").write_text(
        json.dumps(
            {
                "experiment_id": eid,
                "title": "synthetic dossier",
                "status": "completed",
                "created_at_utc": "2026-01-01T00:00:00Z",
                "completed_at_utc": "2026-01-02T00:00:00Z",
                "matrix_type": "throughput-discovery",
                "hypothesis_summary": "s",
                "primary_metric": "expectancy_R",
                "secondary_metrics": ["pf"],
                "promotion_decision": "VALIDATION_REQUIRED",
                "discovery_tier": "watchlist",
                "next_action": "none",
                "suite": {"suite_root": str(suite)},
            }
        ),
        encoding="utf-8",
    )
    (d / "links.json").write_text(
        json.dumps(
            {
                "quantos_run_dir": run_rel,
                "throughput_compare_json": f"{run_rel}/THROUGHPUT_COMPARE.json",
            }
        ),
        encoding="utf-8",
    )

    md, warns = render_experiment_dossier_md(eid)
    assert "WATCHLIST" in md
    assert "RELAX_CANDIDATE" in md
    assert "QuantOS promotion gate" in md
    assert eid in md
    assert "a0_baseline" in md
    assert "## 9. Edge verdicts" in md
    assert "edge_verdict" in md
    assert "INCONCLUSIVE" in md


def test_render_dossier_fail_closed_missing_suite_root(tmp_path, monkeypatch):
    """O1 fail-closed: missing suite_root yields warning; no invented QuantOS paths."""
    exp_root = tmp_path / "experiments"
    monkeypatch.setattr("quantresearch.ledger.experiments_dir", lambda: exp_root)
    exp_root.mkdir()
    eid = "EXP-SYN-DOSSIER-NOSUITE"
    d = exp_root / eid
    d.mkdir()
    (d / "hypothesis.md").write_text("# H\n", encoding="utf-8")
    (d / "experiment_plan.md").write_text("# P\n", encoding="utf-8")
    (d / "decision.md").write_text("# D\n", encoding="utf-8")
    (d / "experiment.json").write_text(
        json.dumps(
            {
                "experiment_id": eid,
                "title": "t",
                "status": "completed",
                "created_at_utc": "2026-01-01T00:00:00Z",
                "matrix_type": "custom",
                "hypothesis_summary": "s",
                "primary_metric": "expectancy_R",
                "secondary_metrics": [],
                "promotion_decision": "UNKNOWN",
                "discovery_tier": "none",
                "next_action": "none",
                "suite": {},
            }
        ),
        encoding="utf-8",
    )
    (d / "links.json").write_text(
        json.dumps({"quantos_run_dir": "quantmetrics_os/runs/X"}),
        encoding="utf-8",
    )
    md, warns = render_experiment_dossier_md(eid)
    assert any("suite.suite_root" in w for w in warns), warns
    assert "Missing or invalid `suite.suite_root`" in md


def test_render_dossier_fail_closed_windows_suite_root(tmp_path, monkeypatch):
    """O1 fail-closed: non-existent Windows suite_root cannot resolve QuantOS paths."""
    exp_root = tmp_path / "experiments"
    monkeypatch.setattr("quantresearch.ledger.experiments_dir", lambda: exp_root)
    exp_root.mkdir()
    eid = "EXP-SYN-DOSSIER-WIN"
    d = exp_root / eid
    d.mkdir()
    (d / "hypothesis.md").write_text("# H\n", encoding="utf-8")
    (d / "experiment_plan.md").write_text("# P\n", encoding="utf-8")
    (d / "decision.md").write_text("# D\n", encoding="utf-8")
    (d / "experiment.json").write_text(
        json.dumps(
            {
                "experiment_id": eid,
                "title": "t",
                "status": "completed",
                "created_at_utc": "2026-01-01T00:00:00Z",
                "matrix_type": "custom",
                "hypothesis_summary": "s",
                "primary_metric": "expectancy_R",
                "secondary_metrics": [],
                "promotion_decision": "UNKNOWN",
                "discovery_tier": "none",
                "next_action": "none",
                "suite": {"suite_root": "C:/Users/Gebruiker/quantmetrics-suite-missing"},
            }
        ),
        encoding="utf-8",
    )
    (d / "links.json").write_text(
        json.dumps({"quantos_run_dir": "quantmetrics_os/runs/X"}),
        encoding="utf-8",
    )
    md, warns = render_experiment_dossier_md(eid)
    assert any("suite.suite_root" in w for w in warns), warns


def test_render_dossier_warns_when_links_missing(tmp_path, monkeypatch):
    exp_root = tmp_path / "experiments"
    monkeypatch.setattr("quantresearch.ledger.experiments_dir", lambda: exp_root)
    exp_root.mkdir()
    eid = "EXP-DOSSIER-NOLINK"
    d = exp_root / eid
    d.mkdir()
    (d / "hypothesis.md").write_text("# H\n", encoding="utf-8")
    (d / "experiment_plan.md").write_text("# P\n", encoding="utf-8")
    (d / "decision.md").write_text("# D\n\n## Final Decision\n\nX\n", encoding="utf-8")
    (d / "experiment.json").write_text(
        json.dumps(
            {
                "experiment_id": eid,
                "title": "t",
                "status": "planned",
                "created_at_utc": "2026-01-01T00:00:00Z",
                "matrix_type": "custom",
                "hypothesis_summary": "s",
                "primary_metric": "expectancy_R",
                "secondary_metrics": ["pf"],
                "promotion_decision": "UNKNOWN",
                "discovery_tier": "none",
                "next_action": "none",
                "suite": {"suite_root": str(tmp_path)},
            }
        ),
        encoding="utf-8",
    )
    md, warns = render_experiment_dossier_md(eid)
    assert any("links.json" in w.lower() for w in warns)
    assert "No `links.json`" in md or "links.json" in md


def test_write_experiment_dossier_writes_file(tmp_path, monkeypatch):
    exp_root = tmp_path / "experiments"
    monkeypatch.setattr("quantresearch.ledger.experiments_dir", lambda: exp_root)
    exp_root.mkdir()
    eid = "EXP-DOSSIER-WRITE"
    d = exp_root / eid
    d.mkdir()
    (d / "hypothesis.md").write_text("# H\n", encoding="utf-8")
    (d / "experiment_plan.md").write_text("# P\n", encoding="utf-8")
    (d / "decision.md").write_text("# D\n", encoding="utf-8")
    (d / "experiment.json").write_text(
        json.dumps(
            {
                "experiment_id": eid,
                "title": "t",
                "status": "planned",
                "created_at_utc": "2026-01-01T00:00:00Z",
                "matrix_type": "custom",
                "hypothesis_summary": "s",
                "primary_metric": "expectancy_R",
                "secondary_metrics": ["pf"],
                "promotion_decision": "UNKNOWN",
                "discovery_tier": "none",
                "next_action": "none",
                "suite": {"suite_root": str(tmp_path)},
            }
        ),
        encoding="utf-8",
    )
    out = write_experiment_dossier(eid)
    assert out.name == "EXPERIMENT_DOSSIER.md"
    assert "Experiment dossier" in out.read_text(encoding="utf-8")


def test_write_dossier_idempotent_on_synthetic_experiment(tmp_path, monkeypatch):
    """Write dossier against tmp synthetic experiment (no committed EXP records)."""
    exp_root = tmp_path / "experiments"
    monkeypatch.setattr("quantresearch.ledger.experiments_dir", lambda: exp_root)
    exp_root.mkdir()
    eid = "EXP-SYN-WRITE-IDEMP"
    d = exp_root / eid
    d.mkdir()
    (d / "hypothesis.md").write_text("# H\n", encoding="utf-8")
    (d / "experiment_plan.md").write_text("# P\n", encoding="utf-8")
    (d / "decision.md").write_text("# D\n", encoding="utf-8")
    (d / "experiment.json").write_text(
        json.dumps(
            {
                "experiment_id": eid,
                "title": "t",
                "status": "planned",
                "created_at_utc": "2026-01-01T00:00:00Z",
                "matrix_type": "custom",
                "hypothesis_summary": "s",
                "primary_metric": "expectancy_R",
                "secondary_metrics": ["pf"],
                "promotion_decision": "UNKNOWN",
                "discovery_tier": "none",
                "next_action": "none",
                "suite": {"suite_root": str(tmp_path)},
            }
        ),
        encoding="utf-8",
    )
    out1 = write_experiment_dossier(eid)
    out2 = write_experiment_dossier(eid)
    assert out1 == out2
    assert out1.is_file()
    body = out1.read_text(encoding="utf-8")
    assert "Experiment dossier" in body
