from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_eceg_public_source_is_frozen_and_unique() -> None:
    config = yaml.safe_load((ROOT / "configs/inegi_eceg.yaml").read_text(encoding="utf-8"))
    source = config["source"]
    archive = ROOT / source["local_zip"]
    assert archive.stat().st_size == source["bytes"]
    assert _sha256(archive) == source["sha256"]
    assert str(source["available_for_predictions_from"]) == "2021-08-18"
    manifest = pd.read_csv(ROOT / "data/manifests/eceg_source_manifest.csv")
    assert manifest.iloc[0]["validation_status"] == "zip_signature_crc_paths_hash_verified"
    eceg = pd.read_parquet(ROOT / "artifacts/tables/eceg_2020_section_features.parquet")
    assert len(eceg) == 68_806
    assert eceg["section_key_observed"].is_unique


def test_behavioral_features_reconcile_to_clean_section_years() -> None:
    behavior = pd.read_parquet(
        ROOT / "artifacts/tables/section_year_behavioral_features.parquet"
    )
    provisional = pd.read_parquet(
        ROOT / "artifacts/tables/provisional_section_year_totals.parquet"
    )
    assert len(behavior) == 406_866
    assert not behavior.duplicated(["election_year", "section_key_observed"]).any()
    left = behavior.groupby("election_year")[["nominal_list", "voted", "did_not_vote"]].sum()
    right = provisional.groupby("election_year")[["nominal_list", "voted", "did_not_vote"]].sum()
    pd.testing.assert_frame_equal(left, right, check_dtype=False)


def test_feature_mart_has_temporal_and_geographic_contracts() -> None:
    mart = pd.read_parquet(ROOT / "artifacts/tables/feature_mart_ab.parquet")
    coverage = pd.read_csv(ROOT / "artifacts/tables/feature_mart_coverage.csv")
    assert len(mart) == 243_108
    assert not mart.duplicated(["target_year", "evaluation_unit_id"]).any()
    assert set(mart["geography_confidence_class"]) == {"A", "B"}
    assert (mart["max_electoral_feature_year"] < mart["target_year"]).all()
    assert not mart.loc[mart["target_year"].lt(2024), "eceg_strict_backtest_allowed"].any()
    assert mart.loc[mart["target_year"].eq(2024), "eceg_strict_backtest_allowed"].all()
    assert coverage.set_index("target_year").loc[2021, "ab_section_coverage"] > 0.96


def test_model_backtests_are_out_of_time_and_reproduce_baseline() -> None:
    metrics = pd.read_csv(ROOT / "artifacts/tables/model_backtest_metrics.csv")
    predictions = pd.read_parquet(ROOT / "artifacts/tables/model_backtest_predictions.parquet")
    assert predictions["prediction"].dropna().between(0, 1).all()
    assert set(metrics.loc[metrics["model_id"].str.endswith("_eceg"), "target_year"]) == {2024}
    for row in metrics.itertuples(index=False):
        years = [int(year) for year in str(row.training_target_years).split("|")]
        assert max(years) < row.target_year
    frozen = pd.read_csv(ROOT / "artifacts/tables/backtest_metrics.csv")
    frozen = frozen[frozen["scenario"].eq("stable_plus_lineage")].set_index("target_year")
    baseline = metrics[metrics["model_id"].eq("lag_same_type_baseline")].set_index(
        "target_year"
    )
    for year in [2018, 2021, 2024]:
        assert abs(
            baseline.loc[year, "identified_weighted_mae"]
            - frozen.loc[year, "identified_weighted_mae"]
        ) < 1e-12


def test_primary_model_gate_and_traceability() -> None:
    decision = json.loads((ROOT / "artifacts/model_decision.json").read_text(encoding="utf-8"))
    assert decision["candidate_approved"] is True
    assert decision["selected_for_next_phase"] == "hist_gradient_boosting_electoral"
    assert decision["best_candidate_identified_weighted_mae"] < 0.09
    assert all(item["passes"] for item in decision["robustness_checks"])
    lineage = pd.read_csv(ROOT / "artifacts/tables/model_feature_lineage.csv")
    required = {
        "feature",
        "feature_set",
        "source",
        "availability_rule",
        "transformation",
        "missing_policy",
        "leakage_control",
    }
    assert required <= set(lineage)
    assert not lineage[list(required)].isna().any().any()
    registry = pd.read_csv(ROOT / "artifacts/tables/model_run_registry.csv")
    assert registry["random_seed"].eq(27).all()
    assert registry["training_target_years"].notna().all()
