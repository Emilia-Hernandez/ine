from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def test_risk_backtest_is_temporal_and_preserves_cross_cycle_warning() -> None:
    predictions = pd.read_parquet(
        ROOT / "artifacts/tables/turnout_decline_risk_backtest_predictions.parquet"
    )
    assert set(predictions["target_year"]) == {2018, 2021, 2024}
    assert set(predictions["decline_threshold"]) == {0.0, 0.02, 0.05}
    assert set(predictions["feature_group"]) == {
        "competition_concurrency",
        "entity_cycle_context",
    }
    assert predictions["probability_raw"].between(0, 1).all()
    assert predictions["probability_time_calibrated"].between(0, 1).all()
    sources = predictions.groupby("target_year")["calibration_source_years"].unique()
    assert set(sources.loc[2018]) == {"none_raw_probability"}
    assert all("2021" not in source for source in sources.loc[2021])
    assert all("2024" not in source for source in sources.loc[2024])

    decision = json.loads(
        (ROOT / "artifacts/turnout_risk_profile_decision.json").read_text(encoding="utf-8")
    )
    assert decision["selected_risk_feature_group"] == "competition_concurrency"
    assert decision["final_probability_calibration_target_year"] == 2021
    assert decision["cross_cycle_transfer_warning"] is True
    assert decision["deferred_step"].startswith("policy_evaluation_after")


def test_section_profiles_cover_snapshot_and_label_lower_confidence_fallbacks() -> None:
    sections = pd.read_parquet(ROOT / "artifacts/tables/section_risk_profiles_2027.parquet")
    assert len(sections) == 70_751
    assert sections["section_key_observed"].is_unique
    assert (
        sections[
            [
                "risk_probability_00pp",
                "risk_probability_02pp",
                "risk_probability_05pp",
                "profile_name",
                "priority_tier",
            ]
        ]
        .notna()
        .all()
        .all()
    )
    assert (sections["risk_probability_00pp"] >= sections["risk_probability_02pp"]).all()
    assert (sections["risk_probability_02pp"] >= sections["risk_probability_05pp"]).all()
    lower = sections["geography_confidence_class"].isin(["C", "D"])
    assert lower.sum() == 5_656
    assert set(sections.loc[lower, "profile_data_source"]) == {"entity_ab_reference_fallback"}
    assert set(sections.loc[~lower, "profile_data_source"]) == {
        "direct_age_sex_counts_aggregated_to_model_unit"
    }
    assert sections["predicted_additional_nonvoters"].ge(0).all()


def test_subgroup_decomposition_is_exact_after_smoothing_and_has_sensitivity() -> None:
    decomposition = pd.read_parquet(
        ROOT / "artifacts/tables/historical_subgroup_decomposition.parquet"
    )
    keys = ["evaluation_unit_id", "target_year", "partition"]
    decomposition["expected_identity_term"] = (
        decomposition["target_group_share"] * decomposition["target_turnout_smoothed"]
        - decomposition["source_group_share"] * decomposition["source_turnout_smoothed"]
    )
    grouped = decomposition.groupby(keys, observed=True)
    contribution = grouped["total_contribution"].sum()
    expected = grouped["expected_identity_term"].sum()
    assert np.allclose(contribution, expected, atol=1e-12, equal_nan=True)
    assert set(decomposition["partition"]) == {"sex", "age"}
    assert decomposition["target_group_identified"].ge(0).all()

    sensitivity = pd.read_csv(
        ROOT / "artifacts/tables/historical_subgroup_decomposition_sensitivity.csv"
    )
    assert set(sensitivity["prior_strength"]) == {0.0, 50.0, 100.0, 200.0}
    assert len(sensitivity) == 96


def test_profiles_are_stable_but_explicitly_exploratory() -> None:
    validation = pd.read_csv(ROOT / "artifacts/tables/turnout_profile_validation.csv")
    selected = validation[validation["selected"]]
    assert len(selected) == 1
    assert selected.iloc[0]["clusters"] == 3
    assert selected.iloc[0]["mean_adjusted_rand"] >= 0.7
    assert selected.iloc[0]["silhouette"] < 0.2
    summary = pd.read_csv(ROOT / "artifacts/tables/turnout_profile_summary.csv")
    assert len(summary) == 3
    assert summary["profile_name"].is_unique
    assert summary["sections_represented"].sum() == 65_095
    report = (ROOT / "artifacts/reports/turnout_risk_profiles_2027.html").read_text(
        encoding="utf-8"
    )
    assert "segmentos exploratorios" in report
    assert "no deben presentarse como certezas" in report


def test_archetypes_are_continuous_overlapping_and_temporally_audited() -> None:
    sections = pd.read_parquet(ROOT / "artifacts/tables/section_risk_profiles_2027.parquet")
    archetypes = [
        "low_youth_turnout",
        "male_turnout_gap",
        "female_turnout_gap",
        "historical_deterioration",
        "low_general_turnout",
        "high_historical_volatility",
    ]
    for archetype in archetypes:
        score = f"archetype_{archetype}_score"
        assert sections[score].between(0, 100).all()
        assert sections[f"archetype_{archetype}_active"].dtype == bool
        assert sections[f"archetype_{archetype}_threshold_stable"].dtype == bool
    assert sections["active_archetype_count"].between(0, len(archetypes)).all()
    assert sections["active_archetype_count"].ge(2).any()
    assert sections["archetype_labels"].str.contains(" | ", regex=False).any()

    backtest = pd.read_csv(ROOT / "artifacts/tables/turnout_archetype_backtest.csv")
    assert set(backtest["target_year"]) == {2018, 2021, 2024}
    assert set(backtest["archetype"]) == set(archetypes)
    assert len(backtest) == 18
    summary = pd.read_csv(ROOT / "artifacts/tables/turnout_archetype_backtest_summary.csv")
    consistent = set(summary.loc[summary["historically_consistent"], "archetype"])
    assert consistent == {"male_turnout_gap"}


def test_bootstrap_uncertainty_is_complete_and_does_not_claim_cycle_uncertainty() -> None:
    sections = pd.read_parquet(ROOT / "artifacts/tables/section_risk_profiles_2027.parquet")
    columns = [
        "risk_probability_bootstrap_mean",
        "risk_probability_bootstrap_std",
        "risk_probability_bootstrap_p10",
        "risk_probability_bootstrap_p90",
        "risk_percentile_bootstrap_p10",
        "risk_percentile_bootstrap_p90",
        "risk_top20_frequency",
        "priority_tier1_frequency",
    ]
    assert sections[columns].notna().all().all()
    assert (
        sections["risk_probability_bootstrap_p10"]
        .le(sections["risk_probability_bootstrap_p90"])
        .all()
    )
    assert (
        sections["risk_percentile_bootstrap_p10"]
        .le(sections["risk_percentile_bootstrap_p90"])
        .all()
    )
    assert sections["risk_top20_frequency"].between(0, 1).all()
    assert sections["priority_tier1_frequency"].between(0, 1).all()
    assert set(sections["risk_ranking_stability"]) == {
        "robust_high_risk",
        "robust_not_high_risk",
        "ranking_sensitive",
    }
    registry = json.loads(
        (ROOT / "artifacts/turnout_risk_bootstrap_registry.json").read_text(encoding="utf-8")
    )
    assert registry["repetitions"] == 20
    assert registry["cluster"] == "entity_id"
    assert "does not include uncertainty from election-cycle" in registry["interpretation"]


def test_eceg_is_descriptive_complete_and_excluded_from_risk_model() -> None:
    sections = pd.read_parquet(ROOT / "artifacts/tables/section_risk_profiles_2027.parquet")
    fields = [
        "eceg_female_share",
        "eceg_adult_share",
        "eceg_older_share",
        "eceg_illiteracy_share_15_plus",
        "eceg_economic_activity_share_12_plus",
        "eceg_disability_share",
        "eceg_indigenous_language_share_3_plus",
        "eceg_internet_share_dwellings",
        "eceg_average_schooling",
    ]
    assert sections[fields].notna().all().all()
    assert set(sections["eceg_profile_source"]) == {
        "aggregated_eceg_2020_to_model_unit",
        "direct_2020_section_key_match",
        "entity_reference_fallback",
    }
    decision = json.loads(
        (ROOT / "artifacts/turnout_risk_profile_decision.json").read_text(encoding="utf-8")
    )
    assert decision["eceg_role"] == "descriptive_only_not_used_by_risk_classifier"
    assert decision["archetypes_primary_output"] is True
