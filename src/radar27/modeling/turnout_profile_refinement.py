from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from radar27.modeling.feature_enrichment import _resolve_feature_group
from radar27.modeling.feature_models import _eceg_features, _load_yaml, _target_units
from radar27.modeling.turnout_risk_profiles import (
    _classifier_pipeline,
    _weighted_mean,
)

ARCHETYPE_LABELS = {
    "low_youth_turnout": "participación juvenil baja",
    "male_turnout_gap": "brecha desfavorable a hombres",
    "female_turnout_gap": "brecha desfavorable a mujeres",
    "historical_deterioration": "deterioro histórico",
    "low_general_turnout": "participación general baja",
    "high_historical_volatility": "volatilidad histórica alta",
}


def _weighted_percentile_reference(
    reference_values: pd.Series,
    reference_weights: pd.Series,
    values: pd.Series,
) -> pd.Series:
    reference = pd.DataFrame(
        {"value": reference_values.astype(float), "weight": reference_weights.astype(float)}
    ).dropna()
    reference = reference[reference["weight"].gt(0)].sort_values("value")
    if reference.empty:
        return pd.Series(np.nan, index=values.index)
    grouped = reference.groupby("value", as_index=False, sort=True)["weight"].sum()
    midpoint = (grouped["weight"].cumsum() - 0.5 * grouped["weight"]) / grouped["weight"].sum()
    score = np.interp(
        values.astype(float),
        grouped["value"].to_numpy(dtype=float),
        midpoint.to_numpy(dtype=float),
        left=float(midpoint.iloc[0]),
        right=float(midpoint.iloc[-1]),
    )
    score[values.isna().to_numpy()] = np.nan
    return pd.Series(100.0 * score, index=values.index)


def _section_eceg_descriptors(eceg: pd.DataFrame) -> pd.DataFrame:
    result = eceg[["section_key_observed"]].copy()
    safe = lambda numerator, denominator: numerator.div(denominator.where(denominator.gt(0)))
    result["eceg_female_share"] = safe(
        eceg["eceg_population_female"], eceg["eceg_population_total"]
    )
    result["eceg_adult_share"] = safe(
        eceg["eceg_population_18_plus"], eceg["eceg_population_total"]
    )
    result["eceg_older_share"] = safe(
        eceg["eceg_population_60_plus"], eceg["eceg_population_total"]
    )
    result["eceg_illiteracy_share_15_plus"] = safe(
        eceg["eceg_population_15_plus_illiterate"], eceg["eceg_population_15_plus"]
    )
    result["eceg_economic_activity_share_12_plus"] = safe(
        eceg["eceg_economically_active_population"], eceg["eceg_population_12_plus"]
    )
    result["eceg_disability_share"] = safe(
        eceg["eceg_population_with_disability"], eceg["eceg_population_total"]
    )
    result["eceg_indigenous_language_share_3_plus"] = safe(
        eceg["eceg_population_3_plus_indigenous_language"],
        eceg["eceg_population_3_plus"],
    )
    result["eceg_internet_share_dwellings"] = safe(
        eceg["eceg_dwellings_with_internet"], eceg["eceg_inhabited_private_dwellings"]
    )
    result["eceg_average_schooling"] = eceg["eceg_average_schooling"]
    return result


def add_eceg_descriptors(
    project_root: Path, sections: pd.DataFrame, config: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    fields = list(config["eceg_descriptors"]["fields"])
    eceg = pd.read_parquet(project_root / "artifacts/tables/eceg_2020_section_features.parquet")
    classes = pd.read_parquet(
        project_root / "artifacts/tables/section_confidence_by_election.parquet"
    )
    components = pd.read_parquet(
        project_root / "artifacts/tables/lineage_components_by_election.parquet"
    )
    snapshot = classes[classes["target_year"].eq(2024)].copy()
    membership = components[components["target_year"].eq(2024)].copy()
    _, members = _target_units(snapshot, membership)
    unit_eceg = _eceg_features(members, eceg)[["evaluation_unit_id", *fields]].copy()
    unit_eceg = unit_eceg.rename(columns={field: f"{field}_unit" for field in fields})
    direct = _section_eceg_descriptors(eceg).rename(
        columns={field: f"{field}_direct" for field in fields}
    )
    result = sections.merge(unit_eceg, on="evaluation_unit_id", how="left", validate="many_to_one")
    result = result.merge(direct, on="section_key_observed", how="left", validate="one_to_one")
    primary = result["geography_confidence_class"].isin(["A", "B"])
    unit_available = result[f"{fields[0]}_unit"].notna()
    direct_available = result[f"{fields[0]}_direct"].notna()
    result["eceg_profile_source"] = np.select(
        [primary & unit_available, ~primary & direct_available],
        ["aggregated_eceg_2020_to_model_unit", "direct_2020_section_key_match"],
        default="entity_reference_fallback",
    )
    for field in fields:
        result[field] = np.where(
            primary,
            result[f"{field}_unit"],
            result[f"{field}_direct"],
        )
    entity_reference = (
        result[primary]
        .groupby("entity_id", as_index=False)
        .apply(
            lambda part: pd.Series(
                {field: _weighted_mean(part[field], part["nominal_list"]) for field in fields}
            ),
            include_groups=False,
        )
        .reset_index(drop=True)
    )
    missing_source = result["eceg_profile_source"].eq("entity_reference_fallback")
    fallback = result.loc[missing_source, ["entity_id"]].merge(
        entity_reference, on="entity_id", how="left", validate="many_to_one"
    )
    for field in fields:
        result.loc[missing_source, field] = fallback[field].to_numpy()
        result[f"{field}_percentile"] = _weighted_percentile_reference(
            result.loc[primary, field],
            result.loc[primary, "nominal_list"],
            result[field],
        )
    result = result.drop(
        columns=[
            *(f"{field}_unit" for field in fields),
            *(f"{field}_direct" for field in fields),
        ]
    )
    coverage = result.groupby(
        ["geography_confidence_class", "eceg_profile_source"], as_index=False
    ).agg(
        sections=("section_key_observed", "size"),
        nominal_list=("nominal_list", "sum"),
        complete_descriptors=(fields[0], "count"),
    )
    coverage["reference_year"] = int(config["eceg_descriptors"]["reference_year"])
    coverage.to_csv(project_root / config["outputs"]["eceg_coverage"], index=False)
    return result, coverage


def add_archetypes(
    project_root: Path, sections: pd.DataFrame, config: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    result = sections.copy()
    model_units = pd.read_parquet(
        project_root / "artifacts/tables/forecast_2027_model_units.parquet",
        columns=["evaluation_unit_id", "participation_historical_std"],
    )
    result = result.merge(model_units, on="evaluation_unit_id", how="left", validate="many_to_one")
    primary = result["geography_confidence_class"].isin(["A", "B"])
    entity_volatility = (
        result[primary]
        .groupby("entity_id", as_index=False)
        .apply(
            lambda part: pd.Series(
                {
                    "participation_historical_std": _weighted_mean(
                        part["participation_historical_std"], part["nominal_list"]
                    )
                }
            ),
            include_groups=False,
        )
        .reset_index(drop=True)
    )
    missing_volatility = result["participation_historical_std"].isna()
    fallback = result.loc[missing_volatility, ["entity_id"]].merge(
        entity_volatility, on="entity_id", how="left", validate="many_to_one"
    )
    result.loc[missing_volatility, "participation_historical_std"] = fallback[
        "participation_historical_std"
    ].to_numpy()
    change_columns = [
        "female_turnout_change_2015_2021",
        "male_turnout_change_2015_2021",
        "age_18_29_turnout_change_2015_2021",
        "age_30_44_turnout_change_2015_2021",
        "age_45_64_turnout_change_2015_2021",
        "age_65_plus_turnout_change_2015_2021",
    ]
    factors = {
        "low_youth_turnout": -result["age_18_29_minus_overall_2024"],
        "male_turnout_gap": result["female_minus_male_turnout_2024"],
        "female_turnout_gap": -result["female_minus_male_turnout_2024"],
        "historical_deterioration": -result[change_columns].mean(axis=1),
        "low_general_turnout": -result["overall_turnout_2024"],
        "high_historical_volatility": result["participation_historical_std"],
    }
    active = float(config["archetypes"]["active_percentile"])
    sensitivity = sorted(float(value) for value in config["archetypes"]["sensitivity_percentiles"])
    score_columns = []
    result["archetype_factor_fallback_count"] = 0
    for archetype, values in factors.items():
        raw_column = f"archetype_{archetype}_raw"
        score_column = f"archetype_{archetype}_score"
        result[raw_column] = values
        missing_factor = result[raw_column].isna()
        if missing_factor.any():
            reference = (
                result[primary & result[raw_column].notna()]
                .groupby("entity_id", as_index=False)
                .apply(
                    lambda part, column=raw_column: pd.Series(
                        {column: _weighted_mean(part[column], part["nominal_list"])}
                    ),
                    include_groups=False,
                )
                .reset_index(drop=True)
            )
            fallback = result.loc[missing_factor, ["entity_id"]].merge(
                reference, on="entity_id", how="left", validate="many_to_one"
            )
            result.loc[missing_factor, raw_column] = fallback[raw_column].to_numpy()
            result.loc[missing_factor, "archetype_factor_fallback_count"] += 1
        result[score_column] = _weighted_percentile_reference(
            result.loc[primary, raw_column],
            result.loc[primary, "nominal_list"],
            result[raw_column],
        )
        score_columns.append(score_column)
        for threshold in sensitivity:
            result[f"archetype_{archetype}_active_{int(threshold)}"] = result[score_column].ge(
                threshold
            )
        result[f"archetype_{archetype}_active"] = result[score_column].ge(active)
        result[f"archetype_{archetype}_threshold_stable"] = result[score_column].lt(
            sensitivity[0]
        ) | result[score_column].ge(sensitivity[-1])
    score_frame = result[score_columns].rename(
        columns={f"archetype_{name}_score": name for name in ARCHETYPE_LABELS}
    )
    result["primary_archetype"] = score_frame.idxmax(axis=1).map(ARCHETYPE_LABELS)
    result["archetype_labels"] = [
        " | ".join(
            ARCHETYPE_LABELS[name] for name in ARCHETYPE_LABELS if row[f"archetype_{name}_active"]
        )
        or "sin arquetipo sobre p80"
        for _, row in result.iterrows()
    ]
    result["robust_archetype_labels"] = [
        " | ".join(
            ARCHETYPE_LABELS[name]
            for name in ARCHETYPE_LABELS
            if row[f"archetype_{name}_active_{int(sensitivity[-1])}"]
        )
        or "sin arquetipo robusto sobre p85"
        for _, row in result.iterrows()
    ]
    result["active_archetype_count"] = result[
        [f"archetype_{name}_active" for name in ARCHETYPE_LABELS]
    ].sum(axis=1)
    result["stable_archetype_count"] = result[
        [f"archetype_{name}_threshold_stable" for name in ARCHETYPE_LABELS]
    ].sum(axis=1)
    result["archetype_assignment_stability"] = result["stable_archetype_count"].div(
        len(ARCHETYPE_LABELS)
    )
    result["archetype_evidence_source"] = np.where(
        primary & result["archetype_factor_fallback_count"].eq(0),
        "direct_ab_model_unit",
        "entity_demographic_reference",
    )

    summary_rows = []
    eceg_rows = []
    eceg_fields = list(config["eceg_descriptors"]["fields"])
    for name, label in ARCHETYPE_LABELS.items():
        selected = result[result[f"archetype_{name}_active"]]
        weights = selected["nominal_list"].astype(float)
        summary_rows.append(
            {
                "archetype": name,
                "label": label,
                "active_sections": len(selected),
                "robust_sections_p85": int(
                    result[f"archetype_{name}_active_{int(sensitivity[-1])}"].sum()
                ),
                "nominal_list": float(weights.sum()),
                "weighted_risk_probability_02pp": _weighted_mean(
                    selected["risk_probability_02pp"], weights
                ),
                "predicted_additional_nonvoters": float(
                    selected["predicted_additional_nonvoters"].sum()
                ),
                "mean_assignment_stability": _weighted_mean(
                    selected["archetype_assignment_stability"], weights
                ),
            }
        )
        row: dict[str, Any] = {
            "archetype": name,
            "label": label,
            "active_sections": len(selected),
        }
        for field in eceg_fields:
            row[field] = _weighted_mean(selected[field], weights)
        eceg_rows.append(row)
    summary = pd.DataFrame(summary_rows).sort_values(
        "predicted_additional_nonvoters", ascending=False
    )
    eceg_summary = pd.DataFrame(eceg_rows)
    summary.to_csv(project_root / config["outputs"]["archetype_summary"], index=False)
    eceg_summary.to_csv(project_root / config["outputs"]["eceg_summary"], index=False)
    return result, summary, eceg_summary


def backtest_archetypes(
    project_root: Path, config: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    mart = pd.read_parquet(project_root / "artifacts/tables/feature_ablation_mart.parquet")
    mart = mart[
        mart["target_year"].isin(config["strict_evaluation_targets"])
        & mart["actual"].notna()
        & mart["participation_same_type"].notna()
    ].copy()
    mart["decline_pp"] = mart["participation_same_type"] - mart["actual"]
    mart["risk_actual"] = mart["decline_pp"].ge(float(config["primary_decline_threshold"]))
    factor_columns = {
        "low_youth_turnout": -(mart["age_18_29_turnout_lag1"] - mart["participation_lag1"]),
        "male_turnout_gap": mart["female_minus_male_turnout_lag1"],
        "female_turnout_gap": -mart["female_minus_male_turnout_lag1"],
        "historical_deterioration": -mart["participation_change_lag1_lag2"],
        "low_general_turnout": -mart["participation_same_type"],
        "high_historical_volatility": mart["participation_historical_std"],
    }
    rows: list[dict[str, Any]] = []
    for target_year, frame in mart.groupby("target_year", observed=True):
        weights = frame["target_identified_records"].astype(float)
        actual = frame["risk_actual"].astype(int)
        for name, factor in factor_columns.items():
            values = factor.loc[frame.index]
            score = _weighted_percentile_reference(values, weights, values)
            valid = score.notna() & weights.gt(0)
            active = score.ge(float(config["archetypes"]["active_percentile"])) & valid
            inactive = ~active & valid
            positive_weight = weights * actual
            top_positive = float(positive_weight[active].sum())
            total_positive = float(positive_weight[valid].sum())
            rows.append(
                {
                    "target_year": int(target_year),
                    "archetype": name,
                    "label": ARCHETYPE_LABELS[name],
                    "evaluation_units": int(valid.sum()),
                    "active_units": int(active.sum()),
                    "weighted_observed_decline_rate_active": _weighted_mean(
                        actual[active], weights[active]
                    ),
                    "weighted_observed_decline_rate_rest": _weighted_mean(
                        actual[inactive], weights[inactive]
                    ),
                    "risk_rate_difference": _weighted_mean(actual[active], weights[active])
                    - _weighted_mean(actual[inactive], weights[inactive]),
                    "positive_volume_captured": (
                        top_positive / total_positive if total_positive else math.nan
                    ),
                    "weighted_roc_auc": float(
                        roc_auc_score(actual[valid], score[valid], sample_weight=weights[valid])
                    ),
                }
            )
    backtest = pd.DataFrame(rows)
    summary = backtest.groupby(["archetype", "label"], as_index=False).agg(
        mean_risk_rate_difference=("risk_rate_difference", "mean"),
        minimum_risk_rate_difference=("risk_rate_difference", "min"),
        mean_weighted_roc_auc=("weighted_roc_auc", "mean"),
        minimum_weighted_roc_auc=("weighted_roc_auc", "min"),
        positive_lift_folds=("risk_rate_difference", lambda values: int(values.gt(0).sum())),
    )
    summary["historically_consistent"] = summary["positive_lift_folds"].eq(
        len(config["strict_evaluation_targets"])
    ) & summary["minimum_weighted_roc_auc"].gt(0.5)
    backtest.to_csv(project_root / config["outputs"]["archetype_backtest"], index=False)
    summary.to_csv(project_root / config["outputs"]["archetype_backtest_summary"], index=False)
    return backtest, summary


def bootstrap_risk_uncertainty(
    project_root: Path,
    sections: pd.DataFrame,
    config: dict[str, Any],
    selected_group: str,
    calibrator: Any,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    training = pd.read_parquet(project_root / "artifacts/tables/feature_ablation_mart.parquet")
    training = training[
        training["target_year"].isin(config["training_target_years"])
        & training["actual"].notna()
        & training["participation_same_type"].notna()
    ].copy()
    training["decline_pp"] = training["participation_same_type"] - training["actual"]
    forecast = pd.read_parquet(project_root / "artifacts/tables/forecast_2027_model_units.parquet")
    feature_config = _load_yaml(project_root / config["feature_config"])
    numeric, categorical = _resolve_feature_group(feature_config, selected_group)
    required = numeric + categorical
    spec = config["risk_classifier"]
    seed = int(config["random_seed"])
    repetitions = int(config["bootstrap_uncertainty"]["repetitions"])
    rng = np.random.default_rng(seed + 10_000)
    entity_values = sorted(training["entity_id"].dropna().unique())
    unit_index = pd.Index(forecast["evaluation_unit_id"])
    section_positions = unit_index.get_indexer(sections["evaluation_unit_id"])
    missing_positions = section_positions < 0
    probability_draws = np.empty((repetitions, len(sections)), dtype=np.float32)
    percentile_draws = np.empty_like(probability_draws)
    volume_high = (
        sections["volume_percentile"]
        .ge(float(config["ranking"]["high_volume_quantile"]))
        .to_numpy()
    )
    tier1_draws = np.empty((repetitions, len(sections)), dtype=bool)
    top_draws = np.empty_like(tier1_draws)
    base_weights = training["target_identified_records"].astype(float)
    target = training["decline_pp"].ge(float(config["primary_decline_threshold"])).astype(int)
    for repetition in range(repetitions):
        multipliers = dict(
            zip(entity_values, rng.exponential(1.0, len(entity_values)), strict=True)
        )
        cluster_weights = training["entity_id"].map(multipliers).astype(float)
        pipeline = _classifier_pipeline(numeric, categorical, spec, seed + repetition + 1)
        pipeline.fit(
            training[required],
            target,
            model__sample_weight=base_weights * cluster_weights,
        )
        unit_raw = pipeline.predict_proba(forecast[required])[:, 1]
        section_raw = np.full(len(sections), np.nan, dtype=float)
        section_raw[~missing_positions] = unit_raw[section_positions[~missing_positions]]
        unit_probability = pd.DataFrame(
            {
                "entity_id": forecast["entity_id"],
                "weight": forecast["current_nominal_list"],
                "probability": calibrator.predict(unit_raw),
            }
        )
        entity_probability = (
            unit_probability.groupby("entity_id", as_index=True)
            .apply(
                lambda part: np.average(part["probability"], weights=part["weight"]),
                include_groups=False,
            )
            .to_dict()
        )
        calibrated = np.full(len(sections), np.nan, dtype=float)
        calibrated[~missing_positions] = calibrator.predict(section_raw[~missing_positions])
        calibrated[missing_positions] = sections.loc[missing_positions, "entity_id"].map(
            entity_probability
        )
        probability_draws[repetition] = calibrated.astype(np.float32)
        percentile = pd.Series(calibrated).rank(pct=True, method="average").to_numpy() * 100.0
        percentile_draws[repetition] = percentile.astype(np.float32)
        top = percentile >= 100.0 * float(config["ranking"]["high_risk_quantile"])
        top_draws[repetition] = top
        tier1_draws[repetition] = top & volume_high
    lower = float(config["bootstrap_uncertainty"]["lower_quantile"])
    upper = float(config["bootstrap_uncertainty"]["upper_quantile"])
    uncertainty = sections[["section_key_observed"]].copy()
    uncertainty["risk_probability_bootstrap_mean"] = probability_draws.mean(axis=0)
    uncertainty["risk_probability_bootstrap_std"] = probability_draws.std(axis=0, ddof=1)
    uncertainty["risk_probability_bootstrap_p10"] = np.quantile(probability_draws, lower, axis=0)
    uncertainty["risk_probability_bootstrap_p90"] = np.quantile(probability_draws, upper, axis=0)
    uncertainty["risk_percentile_bootstrap_p10"] = np.quantile(percentile_draws, lower, axis=0)
    uncertainty["risk_percentile_bootstrap_p90"] = np.quantile(percentile_draws, upper, axis=0)
    uncertainty["risk_top20_frequency"] = top_draws.mean(axis=0)
    uncertainty["priority_tier1_frequency"] = tier1_draws.mean(axis=0)
    uncertainty["risk_ranking_stability"] = np.select(
        [
            uncertainty["risk_top20_frequency"].ge(0.8),
            uncertainty["risk_top20_frequency"].le(0.2),
        ],
        ["robust_high_risk", "robust_not_high_risk"],
        default="ranking_sensitive",
    )
    uncertainty.to_parquet(project_root / config["outputs"]["risk_uncertainty"], index=False)
    registry = {
        "repetitions": repetitions,
        "method": config["bootstrap_uncertainty"]["method"],
        "cluster": config["bootstrap_uncertainty"]["cluster"],
        "random_seed": seed + 10_000,
        "decline_threshold": float(config["primary_decline_threshold"]),
        "feature_group": selected_group,
        "calibration_target_year": int(config["risk_classifier"]["final_calibration_target_year"]),
        "interpretation": (
            "Model and geographic-cluster stability only; it does not include uncertainty "
            "from election-cycle regime change."
        ),
    }
    (project_root / config["outputs"]["bootstrap_registry"]).write_text(
        json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return uncertainty, registry


def _update_geography_summaries(
    project_root: Path, sections: pd.DataFrame, config: dict[str, Any]
) -> None:
    for key, output_key in [
        ("municipality_key_observed", "municipality_summary"),
        ("entity_id", "entity_summary"),
    ]:
        path = project_root / config["outputs"][output_key]
        existing = pd.read_csv(path, dtype={key: "string"})
        rows = []
        for value, part in sections.groupby(key, observed=True):
            weights = part["nominal_list"].astype(float)
            rows.append(
                {
                    key: value,
                    "weighted_risk_top20_frequency": _weighted_mean(
                        part["risk_top20_frequency"], weights
                    ),
                    "weighted_tier1_frequency": _weighted_mean(
                        part["priority_tier1_frequency"], weights
                    ),
                    "robust_high_risk_sections": int(
                        part["risk_ranking_stability"].eq("robust_high_risk").sum()
                    ),
                    "dominant_primary_archetype": part.groupby("primary_archetype", observed=True)[
                        "nominal_list"
                    ]
                    .sum()
                    .idxmax(),
                }
            )
        additions = pd.DataFrame(rows)
        existing = existing.merge(additions, on=key, how="left", validate="one_to_one")
        existing.to_csv(path, index=False)


def refine_turnout_profiles(
    project_root: Path,
    config: dict[str, Any],
    sections: pd.DataFrame,
    selected_group: str,
    calibrator: Any,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    enriched, _ = add_eceg_descriptors(project_root, sections, config)
    enriched, archetype_summary, eceg_summary = add_archetypes(project_root, enriched, config)
    _, backtest_summary = backtest_archetypes(project_root, config)
    uncertainty, registry = bootstrap_risk_uncertainty(
        project_root, enriched, config, selected_group, calibrator
    )
    enriched = enriched.merge(
        uncertainty, on="section_key_observed", how="left", validate="one_to_one"
    )
    outputs = config["outputs"]
    enriched.to_parquet(project_root / outputs["section_file"], index=False)
    enriched.to_csv(project_root / outputs["section_csv"], index=False)
    _update_geography_summaries(project_root, enriched, config)
    return enriched, archetype_summary, backtest_summary, eceg_summary, registry
