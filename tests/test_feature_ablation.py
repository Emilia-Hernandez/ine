from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def test_enriched_mart_context_is_prior_only() -> None:
    mart = pd.read_parquet(ROOT / "artifacts/tables/feature_ablation_mart.parquet")
    assert len(mart) == 243_108
    assert not mart.duplicated(["target_year", "evaluation_unit_id"]).any()
    assert (mart["context_source_max_year"] < mart["target_year"]).all()
    required = {
        "entity_same_type_mean",
        "same_type_minus_entity_mean",
        "national_same_type_mean",
        "entity_lag1_mean",
        "lag1_minus_entity_mean",
        "geography_unit_type",
    }
    assert required <= set(mart)
    assert mart["geography_unit_type"].notna().all()


def test_eceg_ablation_is_restricted_to_2024() -> None:
    metrics = pd.read_csv(ROOT / "artifacts/tables/feature_ablation_metrics.csv")
    eceg = metrics[metrics["availability"].str.startswith("eceg_")]
    assert set(eceg["target_year"]) == {2024}
    strict = metrics[metrics["availability"].eq("strict_all_targets")]
    assert set(strict["target_year"]) == {2018, 2021, 2024}
    assert set(strict["feature_group"]) == {
        "historical_core",
        "electoral_demographics",
        "territorial_context",
        "demographics_context",
    }


def test_territorial_context_improves_all_strict_folds() -> None:
    metrics = pd.read_csv(ROOT / "artifacts/tables/feature_ablation_metrics.csv")
    strict = metrics[metrics["availability"].eq("strict_all_targets")]
    current = strict[strict["feature_group"].eq("electoral_demographics")].set_index(
        "target_year"
    )
    territorial = strict[strict["feature_group"].eq("territorial_context")].set_index(
        "target_year"
    )
    assert (
        territorial["identified_weighted_mae"] < current["identified_weighted_mae"]
    ).all()
    assert territorial.loc[2021, "identified_weighted_mae"] < 0.081


def test_ablation_decision_does_not_overclaim_eceg() -> None:
    decision = json.loads(
        (ROOT / "artifacts/feature_ablation_decision.json").read_text(encoding="utf-8")
    )
    assert decision["baseline_model"] == "lag_same_type_stable_plus_official_lineage"
    assert decision["model_family_held_constant"].startswith("HistGradientBoostingRegressor")
    assert decision["best_strict_feature_group"] == "territorial_context"
    assert decision["strict_feature_group_promoted"] is True
    assert decision["eceg_promoted"] is False
    assert decision["selected_feature_group_for_2027"] == "territorial_context"
