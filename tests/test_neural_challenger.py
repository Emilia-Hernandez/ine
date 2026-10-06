from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def test_dense_network_uses_same_temporal_folds_and_features() -> None:
    metrics = pd.read_csv(ROOT / "artifacts/tables/dense_neural_metrics.csv")
    registry = pd.read_csv(ROOT / "artifacts/tables/dense_neural_registry.csv")
    assert set(metrics["target_year"]) == {2018, 2021, 2024}
    assert set(metrics["feature_group"]) == {"territorial_context"}
    assert set(metrics["model_id"]) == {"dense_mlp"}
    for row in registry.itertuples(index=False):
        assert all(
            int(year) < int(row.target_year)
            for year in str(row.training_target_years).split("|")
        )


def test_dense_network_target_scaling_and_training_are_recorded() -> None:
    registry = pd.read_csv(ROOT / "artifacts/tables/dense_neural_registry.csv")
    assert registry["direct_target_scale"].gt(0).all()
    assert registry["residual_target_scale"].gt(0).all()
    assert registry["direct_iterations"].gt(0).all()
    assert registry["residual_iterations"].gt(0).all()
    assert registry["fit_seconds"].gt(0).all()
    assert registry["validation_policy"].str.contains("strictly prior").all()


def test_dense_network_is_not_promoted() -> None:
    metrics = pd.read_csv(ROOT / "artifacts/tables/dense_neural_metrics.csv").set_index(
        "target_year"
    )
    assert metrics.loc[2021, "identified_weighted_mae"] > metrics.loc[
        2021, "reference_weighted_mae"
    ]
    decision = json.loads(
        (ROOT / "artifacts/dense_neural_decision.json").read_text(encoding="utf-8")
    )
    assert decision["challenger_family"].startswith("MLPRegressor")
    assert decision["feature_group_held_constant"] == "territorial_context"
    assert decision["challenger_promoted"] is False
    assert decision["selected_model_for_next_iteration"] == "hist_gradient_boosting"
