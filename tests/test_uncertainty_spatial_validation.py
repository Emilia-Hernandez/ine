from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from radar27.modeling.uncertainty import finite_sample_conformal_quantile

ROOT = Path(__file__).resolve().parents[1]


def test_finite_sample_conformal_quantile_is_conservative() -> None:
    assert finite_sample_conformal_quantile([1.0, 2.0, 3.0, 4.0], alpha=0.25) == 4.0


def test_conformal_intervals_are_out_of_time_and_bounded() -> None:
    intervals = pd.read_parquet(ROOT / "artifacts/tables/conformal_backtest_intervals.parquet")
    assert set(intervals["target_year"]) == {2021, 2024}
    assert not intervals.duplicated(["target_year", "evaluation_unit_id"]).any()
    assert (intervals["max_calibration_target_year"] < intervals["target_year"]).all()
    assert intervals["lower"].dropna().between(0, 1).all()
    assert intervals["upper"].dropna().between(0, 1).all()
    assert (intervals["lower"] <= intervals["upper"]).all()
    assert intervals.loc[
        intervals["target_year"].eq(2021), "calibration_target_years"
    ].eq("2018").all()
    assert intervals.loc[
        intervals["target_year"].eq(2024), "calibration_target_years"
    ].eq("2018|2021").all()


def test_coverage_is_reported_globally_and_by_required_subgroups() -> None:
    coverage = pd.read_csv(ROOT / "artifacts/tables/conformal_coverage_metrics.csv")
    required_dimensions = {
        "overall",
        "entity_id",
        "geography_confidence_class",
        "section_size_band",
        "predicted_risk_decile",
    }
    assert required_dimensions <= set(coverage["group_dimension"])
    overall = coverage[coverage["group_dimension"].eq("overall")]
    assert set(overall["target_year"]) == {2021, 2024}
    assert overall["empirical_coverage"].between(0, 1).all()
    assert overall["identified_weighted_coverage"].between(0, 1).all()
    assert overall["mean_interval_width"].gt(0).all()


def test_spatial_holdout_excludes_complete_entities_and_future_years() -> None:
    predictions = pd.read_parquet(ROOT / "artifacts/tables/spatial_holdout_predictions.parquet")
    assert set(predictions["target_year"]) == {2018, 2021, 2024}
    assert not predictions.duplicated(["target_year", "evaluation_unit_id"]).any()
    assert (predictions["max_training_target_year"] < predictions["target_year"]).all()
    assert predictions["spatial_holdout_prediction"].between(0, 1).all()
    held_out_matches = predictions.apply(
        lambda row: str(row["entity_id"]) in str(row["held_out_entities"]).split("|"), axis=1
    )
    assert held_out_matches.all()
    metrics = pd.read_csv(ROOT / "artifacts/tables/spatial_robustness_metrics.csv")
    overall = metrics[metrics["scope"].eq("overall")]
    assert set(overall["target_year"]) == {2018, 2021, 2024}
    assert overall["entities"].eq(32).all()


def test_uncertainty_decision_preserves_failed_calibration_diagnostic() -> None:
    decision = json.loads(
        (ROOT / "artifacts/uncertainty_decision.json").read_text(encoding="utf-8")
    )
    assert decision["selected_model"] == "hist_gradient_boosting_electoral"
    assert decision["nominal_coverage"] == 0.9
    assert decision["spatial_deterioration_diagnostic_passes"] is True
    assert decision["global_coverage_diagnostic_passes"] is False
    assert decision["ready_for_first_2027_projection"] is False
