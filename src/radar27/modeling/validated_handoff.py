from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from radar27.modeling.feature_enrichment import _resolve_feature_group
from radar27.modeling.tabular_challengers import _pipeline

MODEL_NAMES = {
    "A_persistence": "Persistencia de elección de la misma familia",
    "B_full_change": "Árbol de cambio completo sin ajuste adicional",
    "C_centered_unshrunk": "Residual centrado sin contracción",
    "E_legacy_reference": "Especificación auditada anterior",
}

PROFILE_NAMES = {
    1: "Patrón descriptivo 1: base alta y brechas por edad y sexo",
    2: "Patrón descriptivo 2: base media y brechas por edad y sexo",
    3: "Patrón descriptivo 3: base baja y mayor variabilidad histórica",
}


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def weighted_mean(values: pd.Series | np.ndarray, weights: pd.Series | np.ndarray) -> float:
    value_array = np.asarray(values, dtype=float)
    weight_array = np.asarray(weights, dtype=float)
    valid = np.isfinite(value_array) & np.isfinite(weight_array) & (weight_array > 0)
    if not valid.any():
        return float("nan")
    return float(np.average(value_array[valid], weights=weight_array[valid]))


def national_turnout_rates(totals: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        totals.groupby(["election_year", "election_family"], observed=True)[
            ["voted", "identified_records"]
        ]
        .sum()
        .reset_index()
    )
    grouped["national_turnout_ratio_of_sums"] = (
        grouped["voted"] / grouped["identified_records"]
    )
    return grouped


def available_national_component(
    rates: pd.DataFrame, target_year: int, election_family: str
) -> dict[str, Any]:
    history = rates[
        rates["election_family"].eq(election_family)
        & rates["election_year"].lt(target_year)
    ].sort_values("election_year")
    if len(history) < 2:
        return {
            "target_year": int(target_year),
            "election_family": election_family,
            "source_recent_year": pd.NA,
            "source_previous_year": pd.NA,
            "national_component": 0.0,
            "status": "zero_fallback_fewer_than_two_prior_same_family_elections",
        }
    previous, recent = history.iloc[-2], history.iloc[-1]
    return {
        "target_year": int(target_year),
        "election_family": election_family,
        "source_recent_year": int(recent["election_year"]),
        "source_previous_year": int(previous["election_year"]),
        "national_component": float(
            recent["national_turnout_ratio_of_sums"]
            - previous["national_turnout_ratio_of_sums"]
        ),
        "status": "prior_same_family_national_ratio_of_sums",
    }


def build_national_components(
    totals: pd.DataFrame, targets: list[tuple[int, str]]
) -> pd.DataFrame:
    rates = national_turnout_rates(totals)
    return pd.DataFrame(
        [available_national_component(rates, year, family) for year, family in targets]
    )


def center_with_available_weights(
    values: pd.Series | np.ndarray, weights: pd.Series | np.ndarray
) -> tuple[np.ndarray, float]:
    value_array = np.asarray(values, dtype=float)
    center = weighted_mean(value_array, weights)
    if not np.isfinite(center):
        center = 0.0
    return value_array - center, float(center)


def add_centered_residual_target(
    frame: pd.DataFrame, components: pd.Series
) -> tuple[pd.DataFrame, pd.DataFrame]:
    centered_parts = []
    diagnostics = []
    for target_year, part in frame.groupby("target_year", observed=True):
        work = part.copy()
        component = float(components.get(int(target_year), 0.0))
        work["residual_before_centering"] = (
            work["actual"] - work["participation_same_type"] - component
        )
        centered, offset = center_with_available_weights(
            work["residual_before_centering"], work["nominal_list_lag1"]
        )
        work["centered_residual_target"] = centered
        diagnostics.append(
            {
                "target_year": int(target_year),
                "national_component": component,
                "centering_offset": offset,
                "centered_target_weighted_mean": weighted_mean(
                    work["centered_residual_target"], work["nominal_list_lag1"]
                ),
                "training_units": len(work),
            }
        )
        centered_parts.append(work)
    return pd.concat(centered_parts, ignore_index=True), pd.DataFrame(diagnostics)


def _metric_row(
    frame: pd.DataFrame,
    prediction_column: str,
    model_id: str,
    model_name: str,
    total_target_sections: int,
) -> dict[str, Any]:
    valid = frame.dropna(
        subset=["actual", prediction_column, "target_identified_records"]
    ).copy()
    actual = valid["actual"].to_numpy(float)
    prediction = valid[prediction_column].to_numpy(float)
    weights = valid["target_identified_records"].to_numpy(float)
    error = prediction - actual
    return {
        "target_year": int(valid["target_year"].iloc[0]),
        "model_id": model_id,
        "model_name": model_name,
        "evaluation_units": len(valid),
        "sections_represented": int(valid["target_sections_represented"].sum()),
        "coverage_of_target_sections": float(
            valid["target_sections_represented"].sum() / total_target_sections
        ),
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error**2))),
        "bias": float(np.mean(error)),
        "weighted_mae": weighted_mean(np.abs(error), weights),
        "weighted_rmse": float(np.sqrt(weighted_mean(error**2, weights))),
        "weighted_bias": weighted_mean(error, weights),
        "actual_national": weighted_mean(actual, weights),
        "predicted_national": weighted_mean(prediction, weights),
    }


def _entity_bootstrap_delta(
    frame: pd.DataFrame,
    prediction_column: str,
    repetitions: int,
    seed: int,
) -> tuple[float, float, float]:
    rows = []
    for entity_id, part in frame.groupby("entity_id", observed=True):
        weights = part["target_identified_records"].to_numpy(float)
        actual = part["actual"].to_numpy(float)
        rows.append(
            {
                "entity_id": entity_id,
                "weight": weights.sum(),
                "candidate": np.sum(
                    weights * np.abs(part[prediction_column].to_numpy(float) - actual)
                ),
                "baseline": np.sum(
                    weights * np.abs(part["A_persistence"].to_numpy(float) - actual)
                ),
            }
        )
    entity = pd.DataFrame(rows)
    point = float(
        entity["candidate"].sum() / entity["weight"].sum()
        - entity["baseline"].sum() / entity["weight"].sum()
    )
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(entity), size=(repetitions, len(entity)))
    weight = entity["weight"].to_numpy()[indices]
    candidate = entity["candidate"].to_numpy()[indices]
    baseline = entity["baseline"].to_numpy()[indices]
    deltas = candidate.sum(axis=1) / weight.sum(axis=1) - baseline.sum(axis=1) / weight.sum(
        axis=1
    )
    low, high = np.quantile(deltas, [0.025, 0.975])
    return point, float(low), float(high)


def _fit_backtest_fold(
    mart: pd.DataFrame,
    legacy: pd.DataFrame,
    components: pd.Series,
    target_year: int,
    numeric: list[str],
    categorical: list[str],
    model_spec: dict[str, Any],
    shrinkages: list[float],
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    required = numeric + categorical
    train = mart[
        mart["target_year"].lt(target_year)
        & mart["actual"].notna()
        & mart["participation_same_type"].notna()
        & mart["nominal_list_lag1"].gt(0)
    ].copy()
    test = mart[
        mart["target_year"].eq(target_year)
        & mart["actual"].notna()
        & mart["participation_same_type"].notna()
        & mart["nominal_list_lag1"].gt(0)
    ].copy()
    legacy_year = legacy[legacy["target_year"].eq(target_year)][
        ["evaluation_unit_id", "prediction"]
    ].rename(columns={"prediction": "E_legacy_reference"})
    test = test.merge(legacy_year, on="evaluation_unit_id", how="inner", validate="one_to_one")

    full_model = _pipeline(model_spec, numeric, categorical, seed)
    full_model.fit(
        train[required],
        train["actual"] - train["participation_same_type"],
        model__sample_weight=train["target_identified_records"].astype(float),
    )
    full_change = full_model.predict(test[required])

    centered_train, diagnostics = add_centered_residual_target(train, components)
    centered_model = _pipeline(model_spec, numeric, categorical, seed)
    centered_model.fit(
        centered_train[required],
        centered_train["centered_residual_target"],
        model__sample_weight=centered_train["target_identified_records"].astype(float),
    )
    centered_prediction_raw = centered_model.predict(test[required])
    centered_prediction, prediction_center = center_with_available_weights(
        centered_prediction_raw, test["nominal_list_lag1"]
    )
    national_component = float(components.get(target_year, 0.0))

    result = test[
        [
            "target_year",
            "evaluation_unit_id",
            "entity_id",
            "geography_confidence_class",
            "target_sections_represented",
            "target_identified_records",
            "nominal_list_lag1",
            "actual",
            "participation_same_type",
        ]
    ].copy()
    result["national_component"] = national_component
    result["centered_residual_prediction"] = centered_prediction
    result["prediction_center_removed"] = prediction_center
    result["A_persistence"] = result["participation_same_type"]
    result["B_full_change"] = np.clip(
        result["participation_same_type"].to_numpy(float) + full_change, 0, 1
    )
    result["C_centered_unshrunk"] = np.clip(
        result["participation_same_type"].to_numpy(float)
        + national_component
        + centered_prediction,
        0,
        1,
    )
    for shrinkage in shrinkages:
        column = f"D_centered_shrink_{shrinkage:g}"
        result[column] = np.clip(
            result["participation_same_type"].to_numpy(float)
            + national_component
            + shrinkage * centered_prediction,
            0,
            1,
        )
    result = result.merge(
        test[["evaluation_unit_id", "E_legacy_reference"]],
        on="evaluation_unit_id",
        validate="one_to_one",
    )
    diagnostics["evaluation_target_year"] = target_year
    diagnostics["prediction_center_removed"] = prediction_center
    diagnostics["evaluation_centered_prediction_weighted_mean"] = weighted_mean(
        result["centered_residual_prediction"], result["nominal_list_lag1"]
    )
    return result, diagnostics


def run_corrected_backtests(
    project_root: Path, config: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    mart = pd.read_parquet(project_root / "artifacts/tables/feature_ablation_mart.parquet")
    legacy = pd.read_parquet(
        project_root / "artifacts/tables/entity_cycle_adaptation_predictions.parquet"
    )
    totals = pd.read_parquet(
        project_root / "artifacts/tables/provisional_section_year_totals.parquet"
    )
    targets = [
        (int(year), str(mart.loc[mart["target_year"].eq(year), "election_family"].iloc[0]))
        for year in config["evaluation_targets"]
    ]
    targets.append((int(config["forecast_target_year"]), str(config["forecast_family"])))
    component_table = build_national_components(totals, targets)
    components = component_table.set_index("target_year")["national_component"]

    feature_config = _load_yaml(project_root / str(config["feature_config"]))
    numeric, categorical = _resolve_feature_group(feature_config, config["feature_group"])
    model_config = _load_yaml(project_root / str(config["model_config"]))
    model_spec = model_config["models"][config["model_id"]]
    shrinkages = [float(value) for value in config["residual_shrinkage_candidates"]]
    seed = int(config["random_seed"])

    fold_frames = []
    diagnostic_frames = []
    metric_rows = []
    entity_rows = []
    level_rows = []
    for target_year in config["evaluation_targets"]:
        fold, diagnostics = _fit_backtest_fold(
            mart,
            legacy,
            components,
            int(target_year),
            numeric,
            categorical,
            model_spec,
            shrinkages,
            seed,
        )
        fold_frames.append(fold)
        diagnostic_frames.append(diagnostics)
        total_sections = int(
            mart.loc[mart["target_year"].eq(target_year), "target_sections_represented"].sum()
        )
        model_columns = [
            "A_persistence",
            "B_full_change",
            "C_centered_unshrunk",
            *[f"D_centered_shrink_{value:g}" for value in shrinkages],
            "E_legacy_reference",
        ]
        for column in model_columns:
            name = MODEL_NAMES.get(column, f"Residual centrado con contracción {column.rsplit('_', 1)[-1]}")
            row = _metric_row(fold, column, column, name, total_sections)
            point, low, high = _entity_bootstrap_delta(
                fold,
                column,
                int(config["bootstrap_repetitions"]),
                seed + int(target_year),
            )
            row["delta_weighted_mae_vs_persistence"] = point
            row["delta_ci_low"] = low
            row["delta_ci_high"] = high
            metric_rows.append(row)
            error_frame = fold.assign(error=fold[column] - fold["actual"])
            for entity_id, part in error_frame.groupby("entity_id", observed=True):
                entity_rows.append(
                    {
                        "target_year": int(target_year),
                        "model_id": column,
                        "entity_id": entity_id,
                        "evaluation_units": len(part),
                        "weighted_mae": weighted_mean(
                            part["error"].abs(), part["target_identified_records"]
                        ),
                        "weighted_bias": weighted_mean(
                            part["error"], part["target_identified_records"]
                        ),
                    }
                )
            bands = pd.cut(
                error_frame["participation_same_type"],
                [-np.inf, 0.4, 0.5, 0.6, np.inf],
                labels=["<40%", "40-50%", "50-60%", ">=60%"],
            )
            for band, part in error_frame.assign(prior_band=bands).groupby(
                "prior_band", observed=True
            ):
                level_rows.append(
                    {
                        "target_year": int(target_year),
                        "model_id": column,
                        "prior_turnout_band": str(band),
                        "evaluation_units": len(part),
                        "weighted_mae": weighted_mean(
                            part["error"].abs(), part["target_identified_records"]
                        ),
                        "weighted_bias": weighted_mean(
                            part["error"], part["target_identified_records"]
                        ),
                    }
                )

    predictions = pd.concat(fold_frames, ignore_index=True)
    metrics = pd.DataFrame(metric_rows)
    candidate = metrics[metrics["model_id"].str.startswith("D_centered_shrink_")].copy()
    selection_rows = []
    for model_id, part in candidate.groupby("model_id", observed=True):
        deltas = part["delta_weighted_mae_vs_persistence"]
        selection_rows.append(
            {
                "model_id": model_id,
                "shrinkage": float(model_id.rsplit("_", 1)[-1]),
                "mean_weighted_mae": float(part["weighted_mae"].mean()),
                "mean_delta_vs_persistence": float(deltas.mean()),
                "fold_wins": int(deltas.lt(0).sum()),
                "worst_fold_deterioration": float(deltas.max()),
                "eligible_for_operational_use": bool(
                    deltas.lt(0).sum()
                    >= int(config["minimum_fold_wins_for_operational_use"])
                    and deltas.max()
                    <= float(config["maximum_fold_weighted_mae_deterioration"])
                ),
            }
        )
    selection = pd.DataFrame(selection_rows).sort_values(
        ["eligible_for_operational_use", "mean_weighted_mae"],
        ascending=[False, True],
    )
    eligible = selection[selection["eligible_for_operational_use"]]
    development = (
        eligible.sort_values("mean_weighted_mae").iloc[0]
        if not eligible.empty
        else selection.sort_values("mean_weighted_mae").iloc[0]
    )
    external_required = bool(
        config.get("require_external_validation_for_advanced_operational_use", False)
    )
    if eligible.empty:
        operational_model_id = "A_persistence"
        operational_shrinkage = 0.0
        operational_reason = "no_centered_candidate_met_prespecified_robustness_gate"
    elif external_required:
        operational_model_id = "A_persistence"
        operational_shrinkage = 0.0
        operational_reason = (
            "centered_candidate_passed_development_gate_but_external_validation_is_unavailable"
        )
    else:
        chosen = eligible.sort_values("mean_weighted_mae").iloc[0]
        operational_model_id = str(chosen["model_id"])
        operational_shrinkage = float(chosen["shrinkage"])
        operational_reason = "centered_candidate_met_prespecified_robustness_gate"
    decision = {
        "operational_model_id": operational_model_id,
        "operational_shrinkage": operational_shrinkage,
        "operational_reason": operational_reason,
        "development_model_id": str(development["model_id"]),
        "development_shrinkage": float(development["shrinkage"]),
        "selection_is_external_validation": False,
        "national_component_definition": "difference_of_national_ratio_of_sums_between_two_latest_prior_same_family_elections",
        "entity_cycle_correction_used": False,
        "prediction_residual_centered_with": "pre_election_nominal_list_weights",
    }
    supporting = pd.concat(
        {
            "by_entity": pd.DataFrame(entity_rows),
            "by_prior_turnout": pd.DataFrame(level_rows),
        },
        names=["table", "row"],
    )
    diagnostics = pd.concat(diagnostic_frames, ignore_index=True)
    return predictions, metrics, selection, {
        "decision": decision,
        "components": component_table,
        "diagnostics": diagnostics,
        "supporting": supporting,
        "numeric_features": numeric,
        "categorical_features": categorical,
        "model_spec": model_spec,
    }


def _fit_2027_residual(
    project_root: Path,
    config: dict[str, Any],
    components: pd.DataFrame,
    numeric: list[str],
    categorical: list[str],
    model_spec: dict[str, Any],
) -> pd.DataFrame:
    mart = pd.read_parquet(project_root / "artifacts/tables/feature_ablation_mart.parquet")
    forecast = pd.read_parquet(project_root / "artifacts/tables/forecast_2027_model_units.parquet")
    train = mart[
        mart["actual"].notna()
        & mart["participation_same_type"].notna()
        & mart["nominal_list_lag1"].gt(0)
    ].copy()
    component_series = components.set_index("target_year")["national_component"]
    centered_train, _ = add_centered_residual_target(train, component_series)
    required = numeric + categorical
    model = _pipeline(model_spec, numeric, categorical, int(config["random_seed"]))
    model.fit(
        centered_train[required],
        centered_train["centered_residual_target"],
        model__sample_weight=centered_train["target_identified_records"].astype(float),
    )
    raw = model.predict(forecast[required])
    centered, removed = center_with_available_weights(raw, forecast["current_nominal_list"])
    return forecast[
        [
            "evaluation_unit_id",
            "entity_id",
            "geography_confidence_class",
            "current_nominal_list",
        ]
    ].assign(
        centered_residual_prediction=centered,
        prediction_center_removed=removed,
    )


def _profile_fields(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    direct = output["profile_data_source"].eq(
        "direct_age_sex_counts_aggregated_to_model_unit"
    ) & output["geography_confidence_class"].isin(["A", "B"])
    output["profile_id_validated"] = output["profile_cluster"].where(direct).map(
        lambda value: f"P{int(value)}" if pd.notna(value) else pd.NA
    )
    output["profile_name_validated"] = output["profile_cluster"].where(direct).map(
        PROFILE_NAMES
    )
    output["profile_validation_status"] = np.where(
        direct,
        "exploratory_algorithmically_stable_low_substantive_separation",
        "not_assigned_insufficient_local_profile_evidence",
    )
    output["stable_male_turnout_gap_pattern"] = (
        direct & output["archetype_male_turnout_gap_active"].fillna(False)
    )
    output["other_archetypes_status"] = np.where(
        direct,
        "descriptive_not_historically_stable",
        "not_available",
    )
    return output


def _risk_fields(frame: pd.DataFrame, quantile: float) -> tuple[pd.DataFrame, dict[str, Any]]:
    output = frame.copy()
    eligible = output["geography_confidence_class"].isin(["A", "B"]) & output[
        "risk_probability_source"
    ].eq("calibrated_ab_classifier")
    score = output["risk_probability_02pp"].where(eligible)
    threshold = float(score.dropna().quantile(quantile, interpolation="linear"))
    high = score.ge(threshold) & eligible
    output["experimental_risk_score_02pp"] = score
    output["experimental_risk_score_category"] = np.select(
        [~eligible, high],
        ["not_available_insufficient_evidence", "high_score_inclusive_p80_with_ties"],
        default="below_inclusive_p80",
    )
    output["experimental_risk_score_validation"] = np.where(
        eligible,
        "experimental_midterm_development_not_externally_validated",
        "not_available",
    )
    return output, {
        "reference_population": int(eligible.sum()),
        "threshold": threshold,
        "selected_sections": int(high.sum()),
        "selected_share": float(high.sum() / eligible.sum()),
        "ties_at_threshold": int(score.eq(threshold).sum()),
        "quantile": quantile,
    }


def _build_master(
    project_root: Path,
    config: dict[str, Any],
    unit_forecast: pd.DataFrame,
    support: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    profiles = pd.read_parquet(
        project_root / "artifacts/tables/section_risk_profiles_2027.parquet"
    )
    sections = pd.read_parquet(
        project_root / "artifacts/tables/forecast_2027_section_predictions.parquet"
    )
    totals = pd.read_parquet(
        project_root / "artifacts/tables/provisional_section_year_totals.parquet"
    )
    geo = totals[totals["election_year"].eq(2024)][
        [
            "section_key_observed",
            "entity_name",
            "municipality_name",
            "district_federal_id",
            "district_local_id",
        ]
    ].drop_duplicates("section_key_observed")
    base = profiles.merge(
        sections[
            [
                "section_key_observed",
                "evaluation_unit_id",
                "operational_baseline_prediction",
                "forecast_geography_status",
            ]
        ],
        on=["section_key_observed", "evaluation_unit_id"],
        validate="one_to_one",
        suffixes=("", "_forecast"),
    ).merge(geo, on="section_key_observed", how="left", validate="one_to_one")
    base = base.merge(
        unit_forecast[
            [
                "evaluation_unit_id",
                "centered_residual_prediction",
                "prediction_center_removed",
            ]
        ],
        on="evaluation_unit_id",
        how="left",
        validate="many_to_one",
    )
    primary = base["geography_confidence_class"].isin(["A", "B"])
    component_2027 = float(
        support["components"].set_index("target_year").loc[2027, "national_component"]
    )
    development_shrinkage = float(support["decision"]["development_shrinkage"])
    residual = base["centered_residual_prediction"].where(primary, 0.0).fillna(0.0)
    exploratory = np.clip(
        base["operational_baseline_prediction"]
        + component_2027
        + development_shrinkage * residual,
        0,
        1,
    )
    if support["decision"]["operational_model_id"] == "A_persistence":
        operational = base["operational_baseline_prediction"].clip(0, 1)
    else:
        operational_shrinkage = float(support["decision"]["operational_shrinkage"])
        operational = np.clip(
            base["operational_baseline_prediction"]
            + component_2027
            + operational_shrinkage * residual,
            0,
            1,
        )
    base["validated_operational_prediction"] = operational
    base["centered_exploratory_prediction"] = exploratory
    base["national_component_2027"] = component_2027
    base["development_residual_shrinkage"] = development_shrinkage
    base["operational_change_pp"] = 100 * (
        base["validated_operational_prediction"]
        - base["operational_baseline_prediction"]
    )
    base["exploratory_change_pp"] = 100 * (
        base["centered_exploratory_prediction"]
        - base["operational_baseline_prediction"]
    )
    base["exploratory_decline_pp"] = (-base["exploratory_change_pp"]).clip(lower=0)
    base["exploratory_additional_nonvoters"] = (
        base["nominal_list"] * base["exploratory_decline_pp"] / 100
    )
    base["positive_exploratory_decline"] = base["exploratory_decline_pp"].gt(0)
    base["prediction_uncertainty"] = np.select(
        [base["geography_confidence_class"].isin(["C", "D"]), primary],
        ["high_geographic_and_model_uncertainty", "model_uncertainty_not_quantified"],
        default="not_available",
    )
    primary_status = (
        "persistence_baseline_operational"
        if support["decision"]["operational_model_id"] == "A_persistence"
        else "centered_model_operational_after_development_gate"
    )
    base["operational_prediction_status"] = np.where(
        primary, primary_status, "hierarchical_reference_not_local_model"
    )
    base = _profile_fields(base)
    base, risk_summary = _risk_fields(base, float(config["risk_threshold_quantile"]))
    base["model_version"] = str(config["model_version"])
    base["generation_date"] = str(config["generation_date"])
    base["target_year"] = int(config["forecast_target_year"])
    base["target_election_family"] = str(config["forecast_family"])
    base["geography_version"] = "2024_snapshot_not_2027_certified"
    base["primary_source"] = "INE_CCPC_2009_2024_and_INEGI_ECEG_2020"
    base["validation_scope"] = "development_backtest_not_external_validation"
    base["material_limitations"] = np.where(
        primary,
        "future_cycle_unknown;2027_geography_not_certified;advanced_forecast_exploratory",
        "no_local_comparable_history;state_or_hierarchical_reference;2027_geography_not_certified",
    )

    selected_columns = {
        "entity_id": "clave_entidad",
        "entity_name": "nombre_entidad",
        "municipality_key_observed": "clave_municipio",
        "municipality_name": "nombre_municipio",
        "district_federal_id": "distrito_federal_2024",
        "district_local_id": "distrito_local_2024",
        "section_key_observed": "clave_seccion",
        "section_type_code": "tipo_seccion",
        "nominal_list": "lista_nominal_2024",
        "overall_turnout_2024": "participacion_observada_2024",
        "operational_baseline_prediction": "participacion_referencia_historica_2021",
        "validated_operational_prediction": "prediccion_operativa_2027",
        "centered_exploratory_prediction": "prediccion_exploratoria_centrada_2027",
        "national_component_2027": "componente_nacional_2027",
        "centered_residual_prediction": "residual_territorial_centrado",
        "development_residual_shrinkage": "contraccion_residual_desarrollo",
        "operational_change_pp": "cambio_operativo_predicho_pp",
        "exploratory_change_pp": "cambio_exploratorio_predicho_pp",
        "exploratory_decline_pp": "caida_exploratoria_predicha_pp",
        "exploratory_additional_nonvoters": "volumen_exploratorio_caida_positiva",
        "positive_exploratory_decline": "indicador_caida_exploratoria_positiva",
        "prediction_uncertainty": "incertidumbre_prediccion",
        "operational_prediction_status": "estado_prediccion_operativa",
        "profile_id_validated": "perfil_exploratorio_id",
        "profile_name_validated": "perfil_exploratorio_nombre",
        "profile_validation_status": "estado_validacion_perfil",
        "stable_male_turnout_gap_pattern": "patron_estable_brecha_desfavorable_hombres",
        "other_archetypes_status": "estado_otros_arquetipos",
        "profile_data_source": "fuente_perfil_electoral",
        "eceg_profile_source": "fuente_caracteristicas_eceg",
        "archetype_evidence_source": "fuente_evidencia_arquetipo",
        "experimental_risk_score_02pp": "score_riesgo_experimental_caida_2pp",
        "experimental_risk_score_category": "categoria_score_riesgo_experimental",
        "experimental_risk_score_validation": "estado_validacion_score_riesgo",
        "geography_confidence_class": "clase_confianza_geografica",
        "forecast_geography_status": "estado_geografia_pronostico",
        "model_version": "version_modelo",
        "generation_date": "fecha_generacion",
        "target_year": "anio_objetivo",
        "target_election_family": "tipo_eleccion_objetivo",
        "geography_version": "version_geografica",
        "primary_source": "fuente_principal",
        "validation_scope": "alcance_validacion",
        "material_limitations": "limitaciones_relevantes",
    }
    master = base[list(selected_columns)].rename(columns=selected_columns)
    return master, risk_summary


COLUMN_DICTIONARY = {
    "clave_entidad": ("Identificación", "Clave INE de entidad", "texto", "INE CCPC", "2024"),
    "nombre_entidad": ("Identificación", "Nombre de la entidad", "texto", "INE CCPC", "2024"),
    "clave_municipio": ("Identificación", "Clave territorial observada del municipio", "texto", "INE CCPC", "2024"),
    "nombre_municipio": ("Identificación", "Nombre observado del municipio", "texto", "INE CCPC", "2024"),
    "distrito_federal_2024": ("Identificación", "Distrito federal observado", "texto", "INE CCPC", "2024"),
    "distrito_local_2024": ("Identificación", "Distrito local observado", "texto", "INE CCPC", "2024"),
    "clave_seccion": ("Identificación", "Clave entidad:sección", "texto", "INE CCPC", "2024"),
    "tipo_seccion": ("Identificación", "Tipo de sección observado", "texto", "INE CCPC", "2024"),
    "lista_nominal_2024": ("Histórico", "Registros de lista nominal 2024", "personas", "INE CCPC", "2024"),
    "participacion_observada_2024": ("Histórico", "SV/(SV+NV) observado", "proporción", "INE CCPC", "2024"),
    "participacion_referencia_historica_2021": ("Predicción", "Referencia de la elección intermedia previa; local para A/B y jerárquica para C/D", "proporción", "pipeline histórico", "2021"),
    "prediccion_operativa_2027": ("Predicción", "Baseline conservador seleccionado por gate", "proporción", "pipeline corregido", "2027"),
    "prediccion_exploratoria_centrada_2027": ("Predicción", "Escenario de desarrollo con componente nacional y residual centrado", "proporción", "pipeline corregido", "2027"),
    "componente_nacional_2027": ("Predicción", "Cambio nacional 2015-2021 por razón de sumas", "proporción", "INE CCPC", "2015-2021"),
    "residual_territorial_centrado": ("Predicción", "Corrección territorial con media ponderada preelectoral cero", "proporción", "modelo corregido", "2027"),
    "contraccion_residual_desarrollo": ("Predicción", "Factor seleccionado con validación de desarrollo", "factor", "configuración", "2027"),
    "cambio_operativo_predicho_pp": ("Predicción", "Predicción operativa menos referencia", "puntos porcentuales", "derivado", "2027"),
    "cambio_exploratorio_predicho_pp": ("Predicción", "Escenario exploratorio menos referencia", "puntos porcentuales", "derivado", "2027"),
    "caida_exploratoria_predicha_pp": ("Riesgo", "Máximo entre cero y la caída del escenario exploratorio", "puntos porcentuales", "derivado", "2027"),
    "volumen_exploratorio_caida_positiva": ("Riesgo", "Lista nominal por caída exploratoria positiva", "personas estimadas", "derivado", "2027"),
    "indicador_caida_exploratoria_positiva": ("Riesgo", "Verdadero si la caída exploratoria es mayor que cero", "booleano", "derivado", "2027"),
    "incertidumbre_prediccion": ("Predicción", "Etiqueta cualitativa; no es intervalo de cobertura", "categoría", "pipeline corregido", "2027"),
    "estado_prediccion_operativa": ("Predicción", "Alcance de uso de la predicción", "categoría", "pipeline corregido", "2027"),
    "perfil_exploratorio_id": ("Perfil", "Cluster descriptivo sólo con evidencia local A/B", "categoría", "CCPC", "2024"),
    "perfil_exploratorio_nombre": ("Perfil", "Nombre neutral del patrón descriptivo", "texto", "CCPC", "2024"),
    "estado_validacion_perfil": ("Perfil", "Separación y suficiencia de evidencia", "categoría", "validación histórica", "2024"),
    "patron_estable_brecha_desfavorable_hombres": ("Perfil", "Único arquetipo con consistencia histórica suficiente", "booleano", "CCPC", "2015-2024"),
    "estado_otros_arquetipos": ("Perfil", "Estado de los restantes arquetipos", "categoría", "validación histórica", "2015-2024"),
    "fuente_perfil_electoral": ("Trazabilidad", "Procedencia de conteos por edad y sexo", "categoría", "pipeline", "2024"),
    "fuente_caracteristicas_eceg": ("Trazabilidad", "Procedencia de variables ECEG", "categoría", "INEGI ECEG", "2020"),
    "fuente_evidencia_arquetipo": ("Trazabilidad", "Procedencia efectiva para arquetipos", "categoría", "pipeline", "2024"),
    "score_riesgo_experimental_caida_2pp": ("Riesgo", "Score del clasificador; no es probabilidad externamente validada", "proporción", "modelo de riesgo", "2027"),
    "categoria_score_riesgo_experimental": ("Riesgo", "Corte p80 inclusivo sobre A/B, conserva empates", "categoría", "derivado", "2027"),
    "estado_validacion_score_riesgo": ("Riesgo", "Alcance de validación del score", "categoría", "validación histórica", "2027"),
    "clase_confianza_geografica": ("Trazabilidad", "Clase A/B/C/D de comparabilidad", "categoría", "armonización", "2024"),
    "estado_geografia_pronostico": ("Trazabilidad", "Certificación temporal de la geografía", "categoría", "pipeline", "2027"),
    "version_modelo": ("Trazabilidad", "Versión reproducible del pipeline", "texto", "configuración", "2026"),
    "fecha_generacion": ("Trazabilidad", "Fecha de generación del handoff", "fecha ISO", "configuración", "2026"),
    "anio_objetivo": ("Trazabilidad", "Año electoral objetivo", "año", "configuración", "2027"),
    "tipo_eleccion_objetivo": ("Trazabilidad", "Familia de elección objetivo", "categoría", "configuración", "2027"),
    "version_geografica": ("Trazabilidad", "Snapshot territorial utilizado", "categoría", "pipeline", "2024"),
    "fuente_principal": ("Trazabilidad", "Fuentes agregadas principales", "texto", "manifiesto", "2009-2024"),
    "alcance_validacion": ("Trazabilidad", "Indica que el backtest es de desarrollo", "categoría", "validación", "2018-2024"),
    "limitaciones_relevantes": ("Trazabilidad", "Advertencias materiales por sección", "texto", "pipeline corregido", "2027"),
}


def _build_dictionary(master: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for column in master.columns:
        category, definition, unit, source, reference = COLUMN_DICTIONARY[column]
        rows.append(
            {
                "variable": column,
                "categoria": category,
                "definicion": definition,
                "unidad": unit,
                "fuente": source,
                "periodo_referencia": reference,
                "permite_nulo": bool(master[column].isna().any()),
                "valores_no_nulos": int(master[column].notna().sum()),
            }
        )
    return pd.DataFrame(rows)


def _entity_summary(master: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (entity_id, entity_name), part in master.groupby(
        ["clave_entidad", "nombre_entidad"], observed=True, dropna=False
    ):
        weights = part["lista_nominal_2024"]
        row = {
            "clave_entidad": entity_id,
            "nombre_entidad": entity_name,
            "secciones": len(part),
            "lista_nominal_2024": float(weights.sum()),
            "participacion_observada_2024_ponderada": weighted_mean(
                part["participacion_observada_2024"], weights
            ),
            "referencia_2021_ponderada": weighted_mean(
                part["participacion_referencia_historica_2021"], weights
            ),
            "prediccion_operativa_2027_ponderada": weighted_mean(
                part["prediccion_operativa_2027"], weights
            ),
            "prediccion_exploratoria_2027_ponderada": weighted_mean(
                part["prediccion_exploratoria_centrada_2027"], weights
            ),
            "secciones_score_alto_experimental": int(
                part["categoria_score_riesgo_experimental"]
                .eq("high_score_inclusive_p80_with_ties")
                .sum()
            ),
            "secciones_caida_exploratoria_positiva": int(
                part["indicador_caida_exploratoria_positiva"].sum()
            ),
            "volumen_exploratorio_caida_positiva": float(
                part["volumen_exploratorio_caida_positiva"].sum()
            ),
        }
        for confidence in ["A", "B", "C", "D"]:
            row[f"secciones_clase_{confidence}"] = int(
                part["clase_confianza_geografica"].eq(confidence).sum()
            )
        rows.append(row)
    return pd.DataFrame(rows).sort_values("clave_entidad")


def _quality_summary(master: pd.DataFrame, risk_summary: dict[str, Any]) -> pd.DataFrame:
    rows = [
        ("universo_maestro", len(master), len(master), "una fila por sección"),
        (
            "prediccion_operativa",
            master["prediccion_operativa_2027"].notna().sum(),
            len(master),
            "baseline local A/B o referencia jerárquica C/D",
        ),
        (
            "perfil_exploratorio_con_evidencia_local",
            master["perfil_exploratorio_id"].notna().sum(),
            len(master),
            "sólo A/B con conteos locales",
        ),
        (
            "score_riesgo_experimental",
            master["score_riesgo_experimental_caida_2pp"].notna().sum(),
            len(master),
            "sólo A/B; no es probabilidad externamente validada",
        ),
        (
            "eceg_agregado_local_ab",
            master["fuente_caracteristicas_eceg"]
            .eq("aggregated_eceg_2020_to_model_unit")
            .sum(),
            len(master),
            "38 A/B usan referencia estatal",
        ),
        (
            "score_alto_experimental",
            risk_summary["selected_sections"],
            risk_summary["reference_population"],
            f"p80 inclusivo; {risk_summary['ties_at_threshold']} empates",
        ),
        (
            "caida_exploratoria_positiva",
            master["indicador_caida_exploratoria_positiva"].sum(),
            len(master),
            "magnitud puntual; no categoría probabilística",
        ),
    ]
    output = pd.DataFrame(rows, columns=["indicador", "secciones_con_dato", "universo", "nota"])
    output["cobertura"] = output["secciones_con_dato"] / output["universo"]
    return output


def _legacy_manifest(project_root: Path) -> pd.DataFrame:
    relative_paths = [
        "artifacts/tables/national_shift_estimates.csv",
        "artifacts/tables/entity_cycle_adaptation_predictions.parquet",
        "artifacts/tables/feature_ablation_mart.parquet",
        "artifacts/tables/forecast_2027_model_units.parquet",
        "artifacts/tables/forecast_2027_section_predictions.parquet",
        "artifacts/tables/section_risk_profiles_2027.parquet",
    ]
    rows = []
    for relative in relative_paths:
        path = project_root / relative
        rows.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "preservation_status": "read_only_input_not_overwritten",
            }
        )
    return pd.DataFrame(rows)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def run_validated_handoff(project_root: Path) -> None:
    config = _load_yaml(project_root / "configs/validated_handoff.yaml")
    output = project_root / str(config["output_directory"])
    output.mkdir(parents=True, exist_ok=True)

    predictions, metrics, selection, support = run_corrected_backtests(project_root, config)
    unit_forecast = _fit_2027_residual(
        project_root,
        config,
        support["components"],
        support["numeric_features"],
        support["categorical_features"],
        support["model_spec"],
    )
    master, risk_summary = _build_master(project_root, config, unit_forecast, support)
    entity_summary = _entity_summary(master)
    dictionary = _build_dictionary(master)
    quality = _quality_summary(master, risk_summary)

    master.to_csv(output / "SECCIONES_ELECTORALES_CLASIFICADAS.csv", index=False)
    entity_summary.to_csv(output / "RESUMEN_ENTIDADES.csv", index=False)
    dictionary.to_csv(output / "DICCIONARIO_VARIABLES.csv", index=False)
    quality.to_csv(output / "CALIDAD_Y_COBERTURA.csv", index=False)
    metrics.to_csv(output / "METRICAS_VALIDACION.csv", index=False)
    selection.to_csv(output / "SENSIBILIDAD_CONTRACCION.csv", index=False)
    predictions.to_parquet(output / "PREDICCIONES_BACKTEST_PAREADAS.parquet", index=False)
    support["components"].to_csv(output / "COMPONENTES_NACIONALES.csv", index=False)
    support["diagnostics"].to_csv(output / "DIAGNOSTICO_CENTRADO_RESIDUAL.csv", index=False)
    support["supporting"].xs("by_entity").to_csv(
        output / "METRICAS_POR_ENTIDAD.csv", index=False
    )
    support["supporting"].xs("by_prior_turnout").to_csv(
        output / "METRICAS_POR_NIVEL_PARTICIPACION.csv", index=False
    )
    _legacy_manifest(project_root).to_csv(output / "MANIFIESTO_RESULTADOS_ANTERIORES.csv", index=False)
    _write_json(output / "DECISION_MODELO_OPERATIVO.json", support["decision"])
    _write_json(output / "REGLA_SCORE_RIESGO.json", risk_summary)
    print(f"Validated handoff written to {output}")
