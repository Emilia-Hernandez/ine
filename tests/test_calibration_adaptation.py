from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def test_national_shift_uses_only_prior_matching_family() -> None:
    estimates = pd.read_csv(ROOT / "artifacts/tables/national_shift_estimates.csv")
    assert (estimates["source_target_year"] < estimates["target_year"]).all()
    evaluated = estimates[estimates["target_year"].isin([2021, 2024, 2027])]
    assert evaluated["family_match"].all()
    assert evaluated.set_index("target_year").loc[2021, "source_target_year"] == 2015
    assert evaluated.set_index("target_year").loc[2024, "source_target_year"] == 2018
    assert evaluated.set_index("target_year").loc[2027, "source_target_year"] == 2021
    assert 0.05 < evaluated.set_index("target_year").loc[2027, "national_shift_correction"] < 0.053


def test_shift_correction_improves_primary_without_breaking_robustness() -> None:
    metrics = pd.read_csv(ROOT / "artifacts/tables/shift_correction_metrics.csv").set_index(
        "target_year"
    )
    assert metrics.loc[2021, "corrected_weighted_mae"] < metrics.loc[
        2021, "original_weighted_mae"
    ]
    assert abs(metrics.loc[2021, "corrected_weighted_bias"]) < abs(
        metrics.loc[2021, "original_weighted_bias"]
    )
    assert metrics.loc[2024, "weighted_mae_change"] <= 0.005
    predictions = pd.read_parquet(ROOT / "artifacts/tables/shift_corrected_predictions.parquet")
    assert predictions["prediction_shift_corrected"].dropna().between(0, 1).all()


def test_adaptive_intervals_are_prior_only_and_complete() -> None:
    intervals = pd.read_parquet(ROOT / "artifacts/tables/adaptive_interval_predictions.parquet")
    assert set(intervals["interval_method"]) == {
        "rolling_conformal_original_center",
        "rolling_conformal_shift_corrected",
        "family_analogue_shift_corrected",
    }
    assert set(intervals["target_year"]) == {2021, 2024}
    assert not intervals.duplicated(
        ["interval_method", "target_year", "evaluation_unit_id"]
    ).any()
    assert (intervals["max_calibration_target_year"] < intervals["target_year"]).all()
    assert intervals["lower"].dropna().between(0, 1).all()
    assert intervals["upper"].dropna().between(0, 1).all()
    assert (intervals["lower"] <= intervals["upper"]).all()


def test_family_analogue_recovers_coverage_floor_but_not_public_gate() -> None:
    coverage = pd.read_csv(ROOT / "artifacts/tables/adaptive_interval_coverage.csv")
    selected = coverage[
        coverage["interval_method"].eq("family_analogue_shift_corrected")
        & coverage["group_dimension"].eq("overall")
    ].set_index("target_year")
    assert selected["empirical_coverage"].ge(0.85).all()
    assert selected.loc[2021, "empirical_coverage"] >= 0.90
    assert selected.loc[2024, "empirical_coverage"] < 0.90
    decision = json.loads(
        (ROOT / "artifacts/calibration_adaptation_decision.json").read_text(encoding="utf-8")
    )
    assert decision["approved_for_experimental_2027_pipeline"] is True
    assert decision["public_interval_ready"] is False
