from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def test_forecast_feature_mart_respects_information_cutoff() -> None:
    mart = pd.read_parquet(ROOT / "artifacts/tables/forecast_2027_feature_mart.parquet")
    assert len(mart) == 59_772
    assert mart["evaluation_unit_id"].is_unique
    assert mart["target_year"].eq(2027).all()
    assert mart["max_electoral_feature_year"].le(2024).all()
    assert (mart["max_electoral_feature_year"] < mart["target_year"]).all()
    assert set(mart["geography_confidence_class"]) == {"A", "B"}
    assert "actual" not in mart
    assert mart["geography_unit_type"].notna().all()
    assert mart["context_source_max_year"].lt(2027).all()
    assert {
        "entity_same_type_mean",
        "same_type_minus_entity_mean",
        "national_same_type_mean",
        "entity_same_family_change_minus_national",
    } <= set(mart)


def test_2027_model_is_the_frozen_residual_boosting_specification() -> None:
    registry = json.loads(
        (ROOT / "artifacts/forecast_2027_model_registry.json").read_text(encoding="utf-8")
    )
    assert registry["model_id"] == "hist_gradient_boosting"
    assert registry["model_family"] == "HistGradientBoostingRegressor"
    assert registry["feature_set"] == "competition_concurrency"
    assert registry["selection_source"] == "artifacts/tabular_challenger_decision.json"
    assert registry["training_target_years"] == [2015, 2018, 2021, 2024]
    assert registry["maximum_training_target_year"] == 2024
    assert registry["residual_shrinkage"] == 0.25
    assert registry["hyperparameters"]["max_iter"] == 250
    assert registry["hyperparameters"]["max_leaf_nodes"] == 15
    assert np.isclose(registry["national_shift_correction"], 0.05214965494331881)
    assert registry["entity_cycle_signal"] == "entity_same_family_change_minus_national"
    assert registry["entity_cycle_shrinkage"] == -0.5


def test_2027_intervals_are_recalibrated_for_territorial_model() -> None:
    calibration = pd.read_csv(
        ROOT / "artifacts/tables/forecast_2027_interval_calibration.csv"
    )
    assert set(calibration["geography_confidence_class"]) == {"A", "B", "C", "D"}
    ab = calibration[calibration["geography_confidence_class"].isin(["A", "B"])]
    cd = calibration[calibration["geography_confidence_class"].isin(["C", "D"])]
    assert set(ab["calibration_model"]) == {"hist_gradient_boosting"}
    assert set(ab["calibration_feature_group"]) == {"competition_concurrency"}
    assert set(cd["calibration_model"]) == {"hierarchical_fallback"}
    assert set(cd["calibration_feature_group"]) == {"not_applicable"}
    assert calibration["calibration_target_year"].eq(2021).all()
    assert calibration["interval_radius"].between(0, 1).all()


def test_section_forecast_covers_snapshot_with_explicit_fallbacks() -> None:
    forecast = pd.read_parquet(
        ROOT / "artifacts/tables/forecast_2027_section_predictions.parquet"
    )
    assert len(forecast) == 70_751
    assert forecast["section_key_observed"].is_unique
    assert set(forecast["geography_confidence_class"]) == {"A", "B", "C", "D"}
    assert forecast["model_applied"].sum() == 65_095
    assert (~forecast["model_applied"]).sum() == 5_656
    assert forecast["experimental_prediction"].between(0, 1).all()
    assert forecast["lower"].between(0, 1).all()
    assert forecast["upper"].between(0, 1).all()
    assert (forecast["lower"] <= forecast["experimental_prediction"]).all()
    assert (forecast["experimental_prediction"] <= forecast["upper"]).all()
    assert forecast["max_source_election_year"].eq(2024).all()
    assert forecast["geography_snapshot_year"].eq(2024).all()
    expected = (
        forecast["forecast_without_national_shift"]
        + forecast["national_shift_correction"]
        + forecast["entity_cycle_correction"]
    ).clip(0, 1)
    assert np.allclose(forecast["experimental_prediction"], expected)


def test_forecast_decision_names_baseline_and_does_not_claim_2027_mae() -> None:
    decision = json.loads(
        (ROOT / "artifacts/forecast_2027_decision.json").read_text(encoding="utf-8")
    )
    assert decision["status"] == "experimental_not_for_public_release"
    assert decision["baseline_model"]["id"] == "lag_same_type_stable_plus_official_lineage"
    assert decision["challenger_model"]["family"] == "HistGradientBoostingRegressor"
    assert decision["challenger_model"]["feature_group"] == "competition_concurrency"
    assert decision["challenger_model"]["entity_cycle_shrinkage"] == -0.5
    assert decision["actual_2027_available"] is False
    assert decision["mae_2027_available"] is False
    historical = {row["target_year"]: row for row in decision["historical_mae_comparison"]}
    assert set(historical) == {2018, 2021, 2024}
    assert historical[2021]["corrected_boosting_weighted_mae"] < historical[2021][
        "baseline_weighted_mae"
    ]
    assert historical[2024]["corrected_boosting_weighted_mae"] > historical[2024][
        "baseline_weighted_mae"
    ]
