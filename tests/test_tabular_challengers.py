from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def test_all_tabular_challengers_use_same_folds_and_features() -> None:
    metrics = pd.read_csv(ROOT / "artifacts/tables/tabular_challenger_metrics.csv")
    registry = pd.read_csv(ROOT / "artifacts/tables/tabular_challenger_registry.csv")
    assert set(metrics["model_id"]) == {
        "hist_gradient_boosting",
        "extra_trees",
        "xgboost",
        "lightgbm",
    }
    assert all(set(group["target_year"]) == {2018, 2021, 2024} for _, group in metrics.groupby("model_id"))
    assert set(metrics["feature_group"]) == {"competition_concurrency"}
    assert registry.groupby("target_year")["numeric_features"].nunique().eq(1).all()
    assert registry.groupby("target_year")["categorical_features"].nunique().eq(1).all()


def test_challenger_training_is_strictly_prior() -> None:
    registry = pd.read_csv(ROOT / "artifacts/tables/tabular_challenger_registry.csv")
    for row in registry.itertuples(index=False):
        assert all(
            int(year) < int(row.target_year)
            for year in str(row.training_target_years).split("|")
        )


def test_reference_reproduces_selected_feature_ablation() -> None:
    challengers = pd.read_csv(ROOT / "artifacts/tables/tabular_challenger_metrics.csv")
    reference = challengers[challengers["model_id"].eq("hist_gradient_boosting")].set_index(
        "target_year"
    )
    ablation = pd.read_csv(ROOT / "artifacts/tables/feature_ablation_metrics.csv")
    territorial = ablation[
        ablation["feature_group"].eq("competition_concurrency")
    ].set_index("target_year")
    difference = (
        reference["identified_weighted_mae"] - territorial["identified_weighted_mae"]
    ).abs()
    assert difference.max() < 1e-10


def test_challenger_decision_is_auditable() -> None:
    decision = json.loads(
        (ROOT / "artifacts/tabular_challenger_decision.json").read_text(encoding="utf-8")
    )
    assert decision["baseline_model"] == "lag_same_type_stable_plus_official_lineage"
    assert decision["feature_group_held_constant"] == "competition_concurrency"
    assert decision["reference_model"] == "hist_gradient_boosting"
    assert decision["selected_model_for_next_iteration"] in {
        "hist_gradient_boosting",
        "extra_trees",
        "xgboost",
        "lightgbm",
    }
    assert set(decision["library_versions"]) == {"scikit_learn", "xgboost", "lightgbm"}
