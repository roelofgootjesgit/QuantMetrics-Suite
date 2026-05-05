"""HYP-002 promotion bundle manifest is valid JSON with expected keys."""

from __future__ import annotations

import json
from pathlib import Path

from quantresearch.paths import repo_root
from quantresearch.hyp002_research_pipeline import _write_exp002_experiment_ledger_folder


def test_hyp002_promotion_bundle_manifest():
    p = repo_root() / "pipelines" / "hyp002_promotion_bundle.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data.get("hypothesis_id") == "HYP-002"
    runs = data.get("runs", [])
    assert len(runs) >= 3
    ids = {r["id"] for r in runs}
    assert "v5a_expblk_5y_spread05" in ids
    assert all("config_file" in r for r in runs)


def test_hyp002_ledger_rerun_preserves_consumed_inference_verdict(tmp_path, monkeypatch):
    qr_root = tmp_path / "quantresearch"
    exp_dir = qr_root / "experiments" / "EXP-002"
    exp_dir.mkdir(parents=True)
    (qr_root / "research_logs").mkdir(parents=True)
    (exp_dir / "experiment.json").write_text(
        json.dumps(
            {
                "experiment_id": "EXP-002",
                "academic_status": "FAIL",
                "effective_status": "GOVERNANCE_ONLY",
                "inference_reason": "economic_gate=ci_95_lower(-0.018153)<minimum_effect_size_r(0.028)",
                "academic_protocol": {"inferential_statistics": "applied"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (exp_dir / "inference_report.json").write_text(
        json.dumps(
            {
                "sample": {"n": 439, "mean_r": 0.102},
                "confidence_interval": {"lower": -0.018153, "upper": 0.21},
                "verdict": {"statistical_significance": "PASS", "economic_significance": "FAIL"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    prereg = {
        "version": 1,
        "hypothesis_id": "HYP-002",
        "pre_registration_timestamp_utc": "2026-05-04T10:00:00Z",
        "pre_registration_status": "retrospective_reconstruction",
        "pre_registration_valid": False,
        "note": "retrospective fixture",
        "null_hypothesis_H0": "median R <= 0",
        "alternative_hypothesis_H1": "median R > 0",
        "alpha": 0.05,
        "minimum_n": 300,
        "minimum_effect_size_r": 0.028,
        "target_power": 0.8,
        "test_plan_summary": "test plan",
        "locked_at_utc": "2026-05-04T10:00:00Z",
    }
    monkeypatch.setenv("QUANTRESEARCH_ROOT", str(qr_root))
    monkeypatch.setattr("quantresearch.hyp002_research_pipeline._load_hyp002_preregistration_for_ledger", lambda bundle: prereg)
    monkeypatch.setattr("quantresearch.hyp002_research_pipeline.write_research_index", lambda: None)

    bundle = {
        "bundle_id": "hyp002-v5a-expansion-block-closed-2026",
        "generated_at_utc": "2026-05-05T11:01:25Z",
        "runs": [
            {
                "id": "v5a_expblk_5y_spread05",
                "label": "overall",
                "config_relative_to_quantbuild": "configs/experiments/ny_sweep_reversion/HYP-002_V5A_expansion_block_5y_spread05.yaml",
                "expectancy_r": 0.102,
                "trade_count": 439,
            },
        ],
    }

    _write_exp002_experiment_ledger_folder(
        tmp_path,
        bundle,
        "variant-rerun",
        manifest={"inference_consumer": False},
    )

    data = json.loads((exp_dir / "experiment.json").read_text(encoding="utf-8"))
    assert data["academic_status"] == "FAIL"
    assert data["effective_status"] == "GOVERNANCE_ONLY"
    assert data["inference_reason"].startswith("economic_gate=ci_95_lower")
    assert data["academic_protocol"]["inferential_statistics"] == "applied"
