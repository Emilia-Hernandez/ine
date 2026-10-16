from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "audit" / "results"


def test_integrity_checks_all_pass():
    checks = pd.read_csv(RESULTS / "integrity_checks.csv")
    assert not checks.empty
    assert checks["status"].eq("PASS").all()


def test_repository_shift_is_not_national_ratio_of_sums():
    row = pd.read_csv(RESULTS / "national_shift_definition.csv").iloc[0]
    assert abs(float(row.repository_panel_weighted_shift) - 0.0521496549433188) < 1e-12
    assert abs(float(row.national_shift_ratio_of_sums) - 0.0476441578116653) < 1e-12
    assert float(row.repository_panel_weighted_shift) > float(row.national_shift_ratio_of_sums)
    assert int(row.sections_changed) == 70_655
    assert abs(float(row.forecast_difference) + 0.0045013799532573) < 1e-12


def test_final_population_and_temporal_order():
    checks = pd.read_csv(RESULTS / "integrity_checks.csv").set_index("check")
    assert int(checks.loc["final section count", "evidence"]) == 70_751
    assert int(checks.loc["feature mart key unique", "evidence"]) == 243_108
    assert int(checks.loc["feature temporal order", "evidence"]) == 0


def test_eceg_gap_is_exactly_38_unique_a_sections():
    cases = pd.read_csv(RESULTS / "eceg_38_section_reconciliation.csv")
    assert len(cases) == 38
    assert cases["section_id"].is_unique
    assert set(cases["original_classification"]) == {"A"}
    assert set(cases["effective_eceg_source"]) == {"entity_reference_fallback"}


def test_percentile_rules_reproduce_non_quintiles():
    table = pd.read_csv(RESULTS / "percentile_alternatives.csv")
    risk = table.query("indicator == 'risk' and alternative == 'A_current_rank_average_ge_80'").iloc[0]
    volume = table.query("indicator == 'volume' and alternative == 'A_current_rank_average_ge_80'").iloc[0]
    assert int(risk.selected_sections) == 15_631
    assert abs(float(risk.selected_share) - 0.2209297395) < 1e-10
    assert int(volume.selected_sections) == 9_891
    assert abs(float(volume.selected_share) - 0.1398001442) < 1e-10


def test_classifier_orientation_and_2024_failure():
    benchmarks = pd.read_csv(RESULTS / "classifier_benchmarks.csv")
    current = benchmarks.query("target_year == 2024 and model == 'current_time_calibrated'").iloc[0]
    historical = benchmarks.query("target_year == 2024 and model == 'historical_single_feature_logit'").iloc[0]
    constant = benchmarks.query("target_year == 2024 and model == 'constant_train_prevalence'").iloc[0]
    assert float(current.roc_auc_weighted) < 0.5
    assert float(current.brier_weighted) > float(constant.brier_weighted)
    assert float(historical.roc_auc_weighted) > float(current.roc_auc_weighted)
    assert float(historical.brier_weighted) < float(current.brier_weighted)


def test_current_model_only_beats_persistence_in_2021():
    metrics = pd.read_csv(RESULTS / "national_adjustment_metrics.csv")
    pivot = metrics.pivot(index="target_year", columns="model", values="weighted_mae")
    delta = pivot["C_current_repository"] - pivot["D_same_family_persistence"]
    assert delta.loc[2018] > 0
    assert delta.loc[2021] < 0
    assert delta.loc[2024] > 0


def test_paired_sample_sizes():
    metrics = pd.read_csv(RESULTS / "national_adjustment_metrics.csv")
    assert metrics.groupby("target_year")["evaluation_units"].nunique().eq(1).all()
    expected = {2018: 58_624, 2021: 58_069, 2024: 56_007}
    observed = metrics.groupby("target_year")["evaluation_units"].first().to_dict()
    assert observed == expected


def test_entity_bootstrap_supports_only_midterm_improvement():
    boot = pd.read_csv(RESULTS / "national_adjustment_bootstrap.csv")
    current = boot.query("candidate == 'model_c_repository'").set_index("target_year")
    assert current.loc[2021, "bootstrap_ci_high"] < 0
    assert current.loc[2018, "bootstrap_ci_low"] < 0 < current.loc[2018, "bootstrap_ci_high"]
    assert current.loc[2024, "bootstrap_ci_low"] < 0 < current.loc[2024, "bootstrap_ci_high"]
