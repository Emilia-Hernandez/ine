from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from radar27.modeling.feature_enrichment import (
    _resolve_feature_group,
    add_relative_territorial_context,
)
from radar27.modeling.feature_models import (
    _aggregate_history,
    _history_features,
    _load_yaml,
    _target_units,
)
from radar27.modeling.lineage_evaluation import _fallback_predictions
from radar27.modeling.tabular_challengers import _pipeline
from radar27.modeling.uncertainty import finite_sample_conformal_quantile


def build_forecast_feature_mart(project_root: Path) -> pd.DataFrame:
    """Build 2027 predictors on the latest auditable 2024 geography snapshot."""
    config = _load_yaml(project_root / "configs/forecast_2027.yaml")
    snapshot_year = int(config["geography_snapshot_target_year"])
    target_year = int(config["target_year"])
    classes = pd.read_parquet(
        project_root / "artifacts/tables/section_confidence_by_election.parquet"
    )
    components = pd.read_parquet(
        project_root / "artifacts/tables/lineage_components_by_election.parquet"
    )
    section_year = pd.read_parquet(
        project_root / "artifacts/tables/section_year_behavioral_features.parquet"
    )
    snapshot = classes[classes["target_year"].eq(snapshot_year)].copy()
    membership = components[components["target_year"].eq(snapshot_year)].copy()
    units, members = _target_units(snapshot, membership)
    history = _aggregate_history(members, section_year, target_year)
    features = _history_features(
        history, target_year, int(config["same_family_feature_year"])
    )
    forecast = units.merge(features, on="evaluation_unit_id", how="left", validate="one_to_one")
    forecast = forecast.rename(columns={"nominal_list": "current_nominal_list"})
    forecast["target_year"] = target_year
    forecast["election_family"] = str(config["election_family"])
    forecast["lineage_class_b"] = forecast["geography_confidence_class"].eq("B").astype(int)
    stable_types = snapshot[snapshot["geography_confidence_class"].eq("A")][
        ["section_key_observed", "section_type_code"]
    ].copy()
    stable_types["evaluation_unit_id"] = "S:" + stable_types["section_key_observed"]
    forecast = forecast.merge(
        stable_types[["evaluation_unit_id", "section_type_code"]],
        on="evaluation_unit_id",
        how="left",
        validate="one_to_one",
    )
    forecast["geography_unit_type"] = np.where(
        forecast["geography_confidence_class"].eq("B"),
        "official_lineage_component",
        "stable_section_type_"
        + forecast["section_type_code"].fillna("unknown").astype(str),
    )
    forecast = add_relative_territorial_context(forecast)
    forecast["max_electoral_feature_year"] = forecast["lag1_year"]
    forecast["context_source_max_year"] = forecast["max_electoral_feature_year"]
    forecast["geography_snapshot_year"] = snapshot_year
    forecast["geography_evidence_through_year"] = int(
        config["geography_evidence_through_year"]
    )
    forecast["forecast_geography_status"] = "2024_snapshot_not_2027_certified"
    forecast = forecast.drop(columns=["actual", "voted", "did_not_vote"], errors="ignore")
    if not (forecast["max_electoral_feature_year"] < target_year).all():
        raise ValueError("El feature mart 2027 contiene información electoral del target o posterior")
    forecast.to_parquet(
        project_root / "artifacts/tables/forecast_2027_feature_mart.parquet", index=False
    )
    return forecast


def train_and_predict_2027(
    project_root: Path, forecast: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Fit the frozen residual boosting specification on all labels through 2024."""
    forecast_config = _load_yaml(project_root / "configs/forecast_2027.yaml")
    model_config = _load_yaml(project_root / str(forecast_config["model_config"]))
    feature_config = _load_yaml(project_root / str(forecast_config["feature_config"]))
    adaptation = pd.read_csv(project_root / "artifacts/tables/national_shift_estimates.csv")
    model_id = str(forecast_config["selected_model"])
    spec = model_config["models"][model_id]
    feature_group = str(forecast_config["selected_feature_group"])
    numeric, categorical = _resolve_feature_group(feature_config, feature_group)
    required = numeric + categorical
    training = pd.read_parquet(
        project_root / "artifacts/tables/feature_ablation_mart.parquet"
    )
    allowed_years = {int(year) for year in forecast_config["training"]["labeled_target_years"]}
    training = training[
        training["target_year"].isin(allowed_years) & training["actual"].notna()
    ].copy()
    if int(training["target_year"].max()) > int(forecast_config["max_source_election_year"]):
        raise ValueError("El entrenamiento excede el corte de información 2024")
    missing_training = set(required) - set(training.columns)
    missing_forecast = set(required) - set(forecast.columns)
    if missing_training or missing_forecast:
        raise ValueError(
            "Variables territoriales ausentes: "
            f"training={sorted(missing_training)}, forecast={sorted(missing_forecast)}"
        )
    seed = int(model_config["random_seed"])
    direct = _pipeline(spec, numeric, categorical, seed)
    direct.fit(
        training[required],
        training["actual"],
        model__sample_weight=training["target_identified_records"].astype(float),
    )
    direct_prediction = direct.predict(forecast[required])
    residual_training = training.dropna(subset=["participation_same_type"]).copy()
    residual = _pipeline(spec, numeric, categorical, seed)
    residual.fit(
        residual_training[required],
        residual_training["actual"] - residual_training["participation_same_type"],
        model__sample_weight=residual_training["target_identified_records"].astype(float),
    )
    residual_prediction = residual.predict(forecast[required])
    baseline = forecast["participation_same_type"].to_numpy(dtype=float)
    has_baseline = np.isfinite(baseline)
    shrinkage = float(model_config["residual_shrinkage"])
    model_raw = np.where(
        has_baseline,
        baseline + shrinkage * residual_prediction,
        direct_prediction,
    )
    model_prediction = np.clip(model_raw, 0.0, 1.0)
    shift_source = int(forecast_config["national_shift"]["source_target_year"])
    shift_row = adaptation[adaptation["target_year"].eq(int(forecast_config["target_year"]))]
    if len(shift_row) != 1 or int(shift_row.iloc[0]["source_target_year"]) != shift_source:
        raise ValueError("No existe una única corrección nacional 2027 con fuente 2021")
    national_shift = float(shift_row.iloc[0]["national_shift_correction"])
    expected = float(forecast_config["national_shift"]["expected_correction"])
    if not np.isclose(national_shift, expected, atol=1e-12):
        raise ValueError("La corrección nacional no coincide con el contrato congelado")
    result = forecast.copy()
    result["baseline_same_family_prediction"] = result["participation_same_type"]
    result["direct_model_prediction"] = np.clip(direct_prediction, 0.0, 1.0)
    result["predicted_residual_unshrunk"] = residual_prediction
    result["residual_shrinkage"] = shrinkage
    result["model_prediction_raw"] = model_raw
    result["model_prediction"] = model_prediction
    result["model_prediction_was_clipped"] = result["model_prediction"].ne(
        result["model_prediction_raw"]
    )
    result["national_shift_correction"] = national_shift
    result["national_shift_source_target_year"] = shift_source
    result["experimental_prediction_raw"] = result["model_prediction"] + national_shift
    result["experimental_prediction"] = result["experimental_prediction_raw"].clip(0.0, 1.0)
    result["experimental_prediction_was_clipped"] = result["experimental_prediction"].ne(
        result["experimental_prediction_raw"]
    )
    result["model_id"] = model_id
    result["model_family"] = "histogram_gradient_boosting_residual_correction"
    result["feature_group"] = feature_group
    result["prediction_status"] = str(forecast_config["publication_status"])
    registry = {
        "target_year": int(forecast_config["target_year"]),
        "model_id": model_id,
        "model_family": "HistGradientBoostingRegressor",
        "prediction_mode": "same-family baseline plus shrunken learned residual",
        "residual_shrinkage": shrinkage,
        "feature_set": feature_group,
        "numeric_features": numeric,
        "categorical_features": categorical,
        "training_target_years": sorted(int(year) for year in training["target_year"].unique()),
        "training_units": len(training),
        "maximum_training_target_year": int(training["target_year"].max()),
        "random_seed": seed,
        "hyperparameters": spec,
        "selection_source": "artifacts/tabular_challenger_decision.json",
        "national_shift_correction": national_shift,
        "national_shift_source_target_year": shift_source,
        "geography_snapshot_year": int(forecast_config["geography_snapshot_target_year"]),
        "publication_status": forecast_config["publication_status"],
    }
    output = project_root / "artifacts"
    result.to_parquet(output / "tables/forecast_2027_model_units.parquet", index=False)
    (output / "forecast_2027_model_registry.json").write_text(
        json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result, registry


def _calibration_radii(project_root: Path) -> pd.DataFrame:
    config = _load_yaml(project_root / "configs/forecast_2027.yaml")
    calibration_year = int(config["uncertainty"]["calibration_target_year"])
    minimum = int(config["uncertainty"]["minimum_class_calibration_units"])
    alpha = 1 - float(config["uncertainty"]["nominal_coverage"])
    selected_model = str(config["uncertainty"]["calibration_model"])
    feature_group = str(config["uncertainty"]["calibration_feature_group"])
    challenger_predictions = pd.read_parquet(
        project_root / "artifacts/tables/tabular_challenger_predictions.parquet"
    )
    ab = challenger_predictions[
        challenger_predictions["target_year"].eq(calibration_year)
        & challenger_predictions["model_id"].eq(selected_model)
        & challenger_predictions["feature_group"].eq(feature_group)
    ].copy()
    if ab.empty:
        raise ValueError("No hay predicciones fuera de tiempo para calibrar A/B 2027")
    ab["absolute_error"] = (ab["prediction"] - ab["actual"]).abs()
    hierarchy = pd.read_parquet(project_root / "artifacts/tables/backtest_predictions.parquet")
    hierarchy = hierarchy[
        hierarchy["target_year"].eq(calibration_year)
        & hierarchy["scenario"].eq("hierarchical_fallback")
    ].copy()
    shift_value = float(ab["national_shift_correction"].iloc[0])
    hierarchy["prediction_shift_corrected"] = (
        hierarchy["prediction"] + shift_value
    ).clip(0.0, 1.0)
    hierarchy["absolute_error"] = (
        hierarchy["prediction_shift_corrected"] - hierarchy["actual"]
    ).abs()
    rows = []
    for confidence_class, frame in ab.groupby("geography_confidence_class", observed=True):
        if len(frame.dropna(subset=["absolute_error"])) >= minimum:
            radius = finite_sample_conformal_quantile(frame["absolute_error"], alpha)
            rows.append(
                {
                    "geography_confidence_class": str(confidence_class),
                    "calibration_pool": f"model_class_{confidence_class}",
                    "calibration_units": int(frame["absolute_error"].notna().sum()),
                    "interval_radius": radius,
                    "calibration_model": selected_model,
                    "calibration_feature_group": feature_group,
                }
            )
    lower_pool = hierarchy[
        hierarchy["geography_confidence_class"].isin(config["uncertainty"]["lower_confidence_pool"])
    ].copy()
    pool_radius = finite_sample_conformal_quantile(lower_pool["absolute_error"], alpha)
    for confidence_class in config["uncertainty"]["lower_confidence_pool"]:
        class_frame = hierarchy[hierarchy["geography_confidence_class"].eq(confidence_class)]
        valid_count = int(class_frame["absolute_error"].notna().sum())
        if valid_count >= minimum:
            radius = finite_sample_conformal_quantile(class_frame["absolute_error"], alpha)
            pool = f"hierarchical_class_{confidence_class}"
        else:
            radius = pool_radius
            pool = "hierarchical_classes_C_D_combined"
        rows.append(
            {
                "geography_confidence_class": str(confidence_class),
                "calibration_pool": pool,
                "calibration_units": valid_count,
                "interval_radius": radius,
                "calibration_model": "hierarchical_fallback",
                "calibration_feature_group": "not_applicable",
            }
        )
    radii = pd.DataFrame(rows)
    if set(radii["geography_confidence_class"]) != {"A", "B", "C", "D"}:
        raise ValueError("No se calibraron radios para las cuatro clases territoriales")
    radii["calibration_target_year"] = calibration_year
    radii["nominal_coverage"] = float(config["uncertainty"]["nominal_coverage"])
    radii.to_csv(project_root / "artifacts/tables/forecast_2027_interval_calibration.csv", index=False)
    return radii


def expand_to_section_forecast(
    project_root: Path, model_units: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Expand A/B model units and add hierarchical C/D fallbacks on the 2024 snapshot."""
    config = _load_yaml(project_root / "configs/forecast_2027.yaml")
    snapshot_year = int(config["geography_snapshot_target_year"])
    classes = pd.read_parquet(
        project_root / "artifacts/tables/section_confidence_by_election.parquet"
    )
    components = pd.read_parquet(
        project_root / "artifacts/tables/lineage_components_by_election.parquet"
    )
    panel = pd.read_parquet(
        project_root / "artifacts/tables/provisional_section_year_totals.parquet"
    )
    snapshot = classes[classes["target_year"].eq(snapshot_year)].copy()
    membership = components[components["target_year"].eq(snapshot_year)].copy()
    lag = panel[panel["election_year"].eq(int(config["same_family_feature_year"]))].copy()
    fallback = _fallback_predictions(snapshot, lag, membership)[
        ["section_key_observed", "prediction", "prediction_source"]
    ].rename(columns={"prediction": "hierarchical_baseline_prediction"})
    sections = snapshot[
        [
            "section_key_observed",
            "entity_id",
            "municipality_key_observed",
            "section_type_code",
            "geography_confidence_class",
            "amge_component_id",
            "nominal_list",
        ]
    ].copy()
    sections["evaluation_unit_id"] = np.where(
        sections["geography_confidence_class"].eq("B")
        & sections["amge_component_id"].notna(),
        "C:" + sections["amge_component_id"].astype("string"),
        "S:" + sections["section_key_observed"],
    )
    unit_columns = [
        "evaluation_unit_id",
        "baseline_same_family_prediction",
        "predicted_residual_unshrunk",
        "residual_shrinkage",
        "model_prediction",
        "national_shift_correction",
        "experimental_prediction",
        "model_id",
    ]
    sections = sections.merge(
        model_units[unit_columns], on="evaluation_unit_id", how="left", validate="many_to_one"
    )
    sections = sections.merge(fallback, on="section_key_observed", how="left", validate="one_to_one")
    primary = sections["geography_confidence_class"].isin(["A", "B"])
    sections["operational_baseline_prediction"] = np.where(
        primary & sections["baseline_same_family_prediction"].notna(),
        sections["baseline_same_family_prediction"],
        sections["hierarchical_baseline_prediction"],
    )
    sections["forecast_without_national_shift"] = np.where(
        primary, sections["model_prediction"], sections["hierarchical_baseline_prediction"]
    )
    national_shift = float(model_units["national_shift_correction"].iloc[0])
    sections["national_shift_correction"] = national_shift
    sections["experimental_prediction"] = (
        sections["forecast_without_national_shift"] + national_shift
    ).clip(0.0, 1.0)
    sections["prediction_strategy"] = np.where(
        primary,
        "residual_boosting_plus_national_shift",
        "hierarchical_fallback_plus_national_shift",
    )
    sections["model_applied"] = primary
    radii = _calibration_radii(project_root)
    sections = sections.merge(radii, on="geography_confidence_class", how="left", validate="many_to_one")
    sections["lower"] = (sections["experimental_prediction"] - sections["interval_radius"]).clip(
        0.0, 1.0
    )
    sections["upper"] = (sections["experimental_prediction"] + sections["interval_radius"]).clip(
        0.0, 1.0
    )
    sections["target_year"] = int(config["target_year"])
    sections["max_source_election_year"] = int(config["max_source_election_year"])
    sections["geography_snapshot_year"] = snapshot_year
    sections["geography_evidence_through_year"] = int(
        config["geography_evidence_through_year"]
    )
    sections["forecast_geography_status"] = "2024_snapshot_not_2027_certified"
    sections["prediction_status"] = str(config["publication_status"])
    if sections["experimental_prediction"].isna().any():
        raise ValueError("Hay secciones del snapshot sin predicción experimental")
    if sections["section_key_observed"].duplicated().any():
        raise ValueError("La salida 2027 contiene secciones duplicadas")
    sections.to_parquet(
        project_root / "artifacts/tables/forecast_2027_section_predictions.parquet", index=False
    )
    rows = []
    for dimension, grouped in [
        ("overall", [("all", sections)]),
        ("geography_confidence_class", sections.groupby("geography_confidence_class")),
        ("entity_id", sections.groupby("entity_id")),
        ("prediction_strategy", sections.groupby("prediction_strategy")),
    ]:
        for group, frame in grouped:
            weights = frame["nominal_list"].astype(float)
            rows.append(
                {
                    "group_dimension": dimension,
                    "group_value": str(group),
                    "sections": len(frame),
                    "current_nominal_list": int(weights.sum()),
                    "weighted_operational_baseline": float(
                        np.average(frame["operational_baseline_prediction"], weights=weights)
                    ),
                    "weighted_experimental_prediction": float(
                        np.average(frame["experimental_prediction"], weights=weights)
                    ),
                    "nominal_list_weighted_mean_lower_bound": float(
                        np.average(frame["lower"], weights=weights)
                    ),
                    "nominal_list_weighted_mean_upper_bound": float(
                        np.average(frame["upper"], weights=weights)
                    ),
                    "mean_interval_width": float((frame["upper"] - frame["lower"]).mean()),
                }
            )
    summary = pd.DataFrame(rows)
    summary.to_csv(project_root / "artifacts/tables/forecast_2027_summary.csv", index=False)
    return sections, summary


def write_forecast_decision(
    project_root: Path,
    model_units: pd.DataFrame,
    sections: pd.DataFrame,
    summary: pd.DataFrame,
    registry: dict[str, Any],
) -> dict[str, Any]:
    config = _load_yaml(project_root / "configs/forecast_2027.yaml")
    frozen = pd.read_csv(project_root / "artifacts/tables/backtest_metrics.csv")
    frozen = frozen[frozen["scenario"].eq("stable_plus_lineage")].set_index("target_year")
    challenger = pd.read_csv(
        project_root / "artifacts/tables/tabular_challenger_metrics.csv"
    )
    challenger = challenger[
        challenger["model_id"].eq(config["selected_model"])
        & challenger["feature_group"].eq(config["selected_feature_group"])
    ].set_index("target_year")
    historical = []
    for year in [2018, 2021, 2024]:
        baseline_mae = float(frozen.loc[year, "identified_weighted_mae"])
        corrected_mae = float(challenger.loc[year, "identified_weighted_mae"])
        historical.append(
            {
                "target_year": year,
                "baseline_model": "lag_same_type_stable_plus_official_lineage",
                "baseline_weighted_mae": baseline_mae,
                "corrected_boosting_weighted_mae": corrected_mae,
                "mae_change_vs_baseline": corrected_mae - baseline_mae,
                "feature_group": config["selected_feature_group"],
            }
        )
    overall = summary[
        summary["group_dimension"].eq("overall") & summary["group_value"].eq("all")
    ].iloc[0]
    decision = {
        "target_year": 2027,
        "status": "experimental_not_for_public_release",
        "baseline_model": {
            "id": "lag_same_type_stable_plus_official_lineage",
            "description": (
                "Use 2021 participation for the same section or official lineage component; "
                "C/D use municipality, entity, then national fallback when needed."
            ),
        },
        "challenger_model": {
            "id": registry["model_id"],
            "family": registry["model_family"],
            "description": (
                "Histogram gradient-boosted trees predict the residual over the same-family "
                "baseline using historical and relative entity/national context; 25% of that "
                "residual is applied, followed by the separately audited national shift."
            ),
            "hyperparameters": registry["hyperparameters"],
            "feature_group": registry["feature_set"],
        },
        "historical_mae_comparison": historical,
        "forecast_units_ab": len(model_units),
        "forecast_sections_all_classes": len(sections),
        "model_applied_sections": int(sections["model_applied"].sum()),
        "hierarchical_fallback_sections": int((~sections["model_applied"]).sum()),
        "geography_snapshot_year": int(sections["geography_snapshot_year"].iloc[0]),
        "max_source_election_year": int(sections["max_source_election_year"].iloc[0]),
        "national_shift_correction": float(
            sections["national_shift_correction"].iloc[0]
        ),
        "weighted_operational_baseline": float(overall["weighted_operational_baseline"]),
        "weighted_experimental_prediction": float(overall["weighted_experimental_prediction"]),
        "nominal_list_weighted_mean_section_lower_bound": float(
            overall["nominal_list_weighted_mean_lower_bound"]
        ),
        "nominal_list_weighted_mean_section_upper_bound": float(
            overall["nominal_list_weighted_mean_upper_bound"]
        ),
        "actual_2027_available": False,
        "mae_2027_available": False,
        "limitations": [
            "The 2027 section frame is not yet available; geography is the audited 2024 snapshot.",
            "The AMGE publication used for lineage ends in 2022.",
            "The interval is recalibrated from one same-family historical target (2021).",
            "No 2027 MAE can be computed before observed 2027 participation exists.",
        ],
    }
    (project_root / "artifacts/forecast_2027_decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return decision
