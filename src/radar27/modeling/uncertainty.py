from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from radar27.modeling.feature_models import _feature_spec, _load_yaml, _pipeline


def finite_sample_conformal_quantile(scores: pd.Series | np.ndarray, alpha: float) -> float:
    """Return the conservative split-conformal quantile using the finite-sample rank."""
    values = np.asarray(scores, dtype=float)
    values = values[np.isfinite(values)]
    if not 0 < alpha < 1:
        raise ValueError("alpha debe estar estrictamente entre 0 y 1")
    if not len(values):
        raise ValueError("No hay residuos válidos para calibrar el intervalo")
    rank = min(math.ceil((len(values) + 1) * (1 - alpha)), len(values))
    return float(np.partition(values, rank - 1)[rank - 1])


def _size_band(values: pd.Series, config: dict[str, Any]) -> pd.Series:
    edges = [float(value) for value in config["section_size_edges"]]
    labels = list(config["section_size_labels"])
    if len(edges) != len(labels) + 1:
        raise ValueError("section_size_edges debe tener exactamente una entrada más que labels")
    return pd.cut(values.astype(float), bins=edges, labels=labels, include_lowest=True, right=False)


def _risk_decile(values: pd.Series) -> pd.Series:
    valid = values.notna()
    result = pd.Series(pd.NA, index=values.index, dtype="Int64")
    if valid.any():
        ranked = values.loc[valid].rank(method="first")
        result.loc[valid] = pd.qcut(ranked, q=10, labels=False, duplicates="drop") + 1
    return result


def _coverage_row(frame: pd.DataFrame, target_year: int, dimension: str, group: str) -> dict[str, Any]:
    valid = frame.dropna(subset=["actual", "lower", "upper"]).copy()
    covered = valid["actual"].between(valid["lower"], valid["upper"], inclusive="both")
    weights = valid["target_identified_records"].astype(float)
    width = valid["upper"] - valid["lower"]
    weight_sum = float(weights.sum())
    return {
        "target_year": int(target_year),
        "group_dimension": dimension,
        "group_value": str(group),
        "evaluation_units": len(valid),
        "target_sections_represented": int(valid["target_sections_represented"].sum()),
        "identified_records": int(weight_sum),
        "empirical_coverage": float(covered.mean()) if len(valid) else np.nan,
        "identified_weighted_coverage": (
            float(np.average(covered.astype(float), weights=weights)) if weight_sum else np.nan
        ),
        "mean_interval_width": float(width.mean()) if len(valid) else np.nan,
        "identified_weighted_interval_width": (
            float(np.average(width, weights=weights)) if weight_sum else np.nan
        ),
        "lower_miss_share": float(valid["actual"].lt(valid["lower"]).mean()) if len(valid) else np.nan,
        "upper_miss_share": float(valid["actual"].gt(valid["upper"]).mean()) if len(valid) else np.nan,
    }


def _coverage_metrics(intervals: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    dimensions = [
        "entity_id",
        "geography_confidence_class",
        "section_size_band",
        "predicted_risk_decile",
    ]
    for target_year, year_frame in intervals.groupby("target_year", sort=True):
        rows.append(_coverage_row(year_frame, int(target_year), "overall", "all"))
        for dimension in dimensions:
            for group, frame in year_frame.groupby(dimension, observed=True, dropna=False):
                rows.append(_coverage_row(frame, int(target_year), dimension, str(group)))
    return pd.DataFrame(rows)


def build_conformal_intervals(
    project_root: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Calibrate rolling, out-of-time conformal intervals for the approved model."""
    config = _load_yaml(project_root / "configs/uncertainty.yaml")
    conformal = config["conformal"]
    model_id = str(config["selected_model"])
    alpha = float(conformal["alpha"])
    minimum = int(conformal["minimum_stratum_units"])
    predictions = pd.read_parquet(
        project_root / "artifacts/tables/model_backtest_predictions.parquet"
    )
    selected = predictions[predictions["model_id"].eq(model_id)].copy()
    selected["absolute_error"] = (selected["prediction"] - selected["actual"]).abs()
    interval_rows = []
    calibration_rows = []
    for target_year in conformal["evaluation_target_years"]:
        calibration = selected[
            selected["target_year"].lt(target_year)
            & selected["absolute_error"].notna()
            & selected["prediction"].notna()
        ].copy()
        test = selected[selected["target_year"].eq(target_year)].copy()
        if calibration.empty or test.empty:
            raise ValueError(f"No hay calibración o evaluación disponible para {target_year}")
        if int(calibration["target_year"].max()) >= int(target_year):
            raise ValueError("La calibración conformal contiene el año objetivo o uno posterior")
        global_quantile = finite_sample_conformal_quantile(calibration["absolute_error"], alpha)
        quantiles: dict[str, float] = {}
        for confidence_class, class_frame in calibration.groupby(
            "geography_confidence_class", observed=True
        ):
            if len(class_frame) >= minimum:
                quantiles[str(confidence_class)] = finite_sample_conformal_quantile(
                    class_frame["absolute_error"], alpha
                )
        test["conformal_radius"] = test["geography_confidence_class"].map(quantiles)
        test["used_global_fallback"] = test["conformal_radius"].isna()
        test["conformal_radius"] = test["conformal_radius"].fillna(global_quantile)
        test["lower_unclipped"] = test["prediction"] - test["conformal_radius"]
        test["upper_unclipped"] = test["prediction"] + test["conformal_radius"]
        test["lower"] = test["lower_unclipped"].clip(0.0, 1.0)
        test["upper"] = test["upper_unclipped"].clip(0.0, 1.0)
        test["interval_was_clipped"] = test["lower"].ne(test["lower_unclipped"]) | test[
            "upper"
        ].ne(test["upper_unclipped"])
        test["calibration_target_years"] = "|".join(
            map(str, sorted(int(year) for year in calibration["target_year"].unique()))
        )
        test["max_calibration_target_year"] = int(calibration["target_year"].max())
        test["interval_method"] = str(conformal["method"])
        test["nominal_coverage"] = float(conformal["nominal_coverage"])
        test["section_size_band"] = _size_band(test["nominal_list"], conformal).astype("string")
        test["predicted_risk_decile"] = _risk_decile(1 - test["prediction"])
        interval_rows.append(test)
        calibration_rows.append(
            {
                "target_year": int(target_year),
                "calibration_target_years": test["calibration_target_years"].iloc[0],
                "max_calibration_target_year": int(calibration["target_year"].max()),
                "stratum": "global",
                "calibration_units": len(calibration),
                "conformal_radius": global_quantile,
                "used_global_fallback": False,
                "alpha": alpha,
            }
        )
        for confidence_class, class_frame in calibration.groupby(
            "geography_confidence_class", observed=True
        ):
            calibration_rows.append(
                {
                    "target_year": int(target_year),
                    "calibration_target_years": test["calibration_target_years"].iloc[0],
                    "max_calibration_target_year": int(calibration["target_year"].max()),
                    "stratum": f"geography_confidence_class={confidence_class}",
                    "calibration_units": len(class_frame),
                    "conformal_radius": quantiles.get(str(confidence_class), global_quantile),
                    "used_global_fallback": str(confidence_class) not in quantiles,
                    "alpha": alpha,
                }
            )
    intervals = pd.concat(interval_rows, ignore_index=True)
    if not (intervals["max_calibration_target_year"] < intervals["target_year"]).all():
        raise ValueError("Se detectó fuga temporal en la calibración conformal")
    coverage = _coverage_metrics(intervals)
    calibration_summary = pd.DataFrame(calibration_rows)
    output = project_root / "artifacts/tables"
    intervals.to_parquet(output / "conformal_backtest_intervals.parquet", index=False)
    coverage.to_csv(output / "conformal_coverage_metrics.csv", index=False)
    calibration_summary.to_csv(output / "conformal_calibration_summary.csv", index=False)
    return intervals, coverage, calibration_summary


def _predict_model(
    train: pd.DataFrame,
    test: pd.DataFrame,
    modeling: dict[str, Any],
    model_id: str,
) -> np.ndarray:
    spec = modeling["models"][model_id]
    numeric, categorical = _feature_spec(modeling, spec["feature_set"])
    required = numeric + categorical
    seed = int(modeling["random_seed"])
    direct = _pipeline(spec, numeric, categorical, seed)
    direct.fit(
        train[required],
        train["actual"],
        model__sample_weight=train["target_identified_records"].astype(float),
    )
    raw = direct.predict(test[required])
    if spec.get("prediction_mode") == "residual_correction":
        residual_train = train.dropna(subset=["participation_same_type"]).copy()
        residual = _pipeline(spec, numeric, categorical, seed)
        residual.fit(
            residual_train[required],
            residual_train["actual"] - residual_train["participation_same_type"],
            model__sample_weight=residual_train["target_identified_records"].astype(float),
        )
        correction = residual.predict(test[required])
        has_baseline = test["participation_same_type"].notna().to_numpy()
        corrected = test["participation_same_type"].to_numpy() + float(
            spec["residual_shrinkage"]
        ) * correction
        raw = np.where(has_baseline, corrected, raw)
    return np.clip(raw, 0.0, 1.0)


def _spatial_metric_row(
    frame: pd.DataFrame, target_year: int, scope: str, value: str
) -> dict[str, Any]:
    valid = frame.dropna(subset=["actual", "spatial_holdout_prediction"]).copy()
    weights = valid["target_identified_records"].astype(float)
    spatial_error = (valid["spatial_holdout_prediction"] - valid["actual"]).abs()
    standard_error = (valid["standard_temporal_prediction"] - valid["actual"]).abs()
    return {
        "target_year": int(target_year),
        "scope": scope,
        "scope_value": str(value),
        "evaluation_units": len(valid),
        "entities": int(valid["entity_id"].nunique()),
        "target_sections_represented": int(valid["target_sections_represented"].sum()),
        "spatial_holdout_weighted_mae": float(np.average(spatial_error, weights=weights)),
        "standard_temporal_weighted_mae": float(np.average(standard_error, weights=weights)),
        "weighted_mae_deterioration": float(
            np.average(spatial_error, weights=weights) - np.average(standard_error, weights=weights)
        ),
        "spatial_holdout_mae": float(spatial_error.mean()),
        "standard_temporal_mae": float(standard_error.mean()),
    }


def run_spatial_entity_holdout(
    project_root: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Evaluate temporal transfer while holding complete entity groups out of training."""
    config = _load_yaml(project_root / "configs/uncertainty.yaml")
    modeling = _load_yaml(project_root / "configs/modeling.yaml")
    spatial = config["spatial_validation"]
    model_id = str(config["selected_model"])
    feature_mart = pd.read_parquet(project_root / "artifacts/tables/feature_mart_ab.parquet")
    standard = pd.read_parquet(
        project_root / "artifacts/tables/model_backtest_predictions.parquet"
    )
    standard = standard[standard["model_id"].eq(model_id)][
        ["target_year", "evaluation_unit_id", "prediction"]
    ].rename(columns={"prediction": "standard_temporal_prediction"})
    entities = sorted(str(value) for value in feature_mart["entity_id"].dropna().unique())
    group_count = int(spatial["entity_groups"])
    entity_group = {entity: index % group_count for index, entity in enumerate(entities)}
    predictions = []
    for target_year in spatial["target_years"]:
        prior = feature_mart[
            feature_mart["target_year"].lt(target_year) & feature_mart["actual"].notna()
        ].copy()
        target = feature_mart[feature_mart["target_year"].eq(target_year)].copy()
        for group_id in range(group_count):
            held_out = sorted(entity for entity, group in entity_group.items() if group == group_id)
            train = prior[~prior["entity_id"].isin(held_out)].copy()
            test = target[target["entity_id"].isin(held_out)].copy()
            if train.empty or test.empty:
                raise ValueError(f"Grupo espacial vacío para {target_year}, grupo {group_id}")
            if set(train["entity_id"]) & set(held_out):
                raise ValueError("Una entidad retenida apareció en el entrenamiento espacial")
            test["spatial_holdout_prediction"] = _predict_model(train, test, modeling, model_id)
            test["spatial_group"] = group_id
            test["held_out_entities"] = "|".join(held_out)
            test["training_target_years"] = "|".join(
                map(str, sorted(int(year) for year in train["target_year"].unique()))
            )
            test["max_training_target_year"] = int(train["target_year"].max())
            predictions.append(test)
    result = pd.concat(predictions, ignore_index=True)
    if not (result["max_training_target_year"] < result["target_year"]).all():
        raise ValueError("Se detectó fuga temporal en la validación espacial")
    result = result.merge(
        standard, on=["target_year", "evaluation_unit_id"], how="left", validate="one_to_one"
    )
    metric_rows: list[dict[str, Any]] = []
    for target_year, frame in result.groupby("target_year", sort=True):
        metric_rows.append(_spatial_metric_row(frame, int(target_year), "overall", "all"))
        for group_id, group_frame in frame.groupby("spatial_group", sort=True):
            metric_rows.append(
                _spatial_metric_row(group_frame, int(target_year), "spatial_group", str(group_id))
            )
        for entity_id, entity_frame in frame.groupby("entity_id", sort=True):
            metric_rows.append(
                _spatial_metric_row(entity_frame, int(target_year), "entity_id", str(entity_id))
            )
    metrics = pd.DataFrame(metric_rows)
    keep = [
        "target_year",
        "evaluation_unit_id",
        "entity_id",
        "geography_confidence_class",
        "target_sections_represented",
        "target_identified_records",
        "actual",
        "standard_temporal_prediction",
        "spatial_holdout_prediction",
        "spatial_group",
        "held_out_entities",
        "training_target_years",
        "max_training_target_year",
    ]
    output = project_root / "artifacts/tables"
    result[keep].to_parquet(output / "spatial_holdout_predictions.parquet", index=False)
    metrics.to_csv(output / "spatial_robustness_metrics.csv", index=False)
    return result[keep], metrics


def write_uncertainty_decision(
    project_root: Path,
    coverage: pd.DataFrame,
    spatial_metrics: pd.DataFrame,
) -> dict[str, Any]:
    config = _load_yaml(project_root / "configs/uncertainty.yaml")
    conformal = config["conformal"]
    diagnostics = config["readiness_diagnostics"]
    overall_coverage = coverage[coverage["group_dimension"].eq("overall")].copy()
    overall_spatial = spatial_metrics[spatial_metrics["scope"].eq("overall")].copy()
    coverage_floor = float(diagnostics["minimum_acceptable_global_coverage"])
    spatial_ceiling = float(
        diagnostics["maximum_overall_spatial_weighted_mae_deterioration"]
    )
    decision = {
        "selected_model": config["selected_model"],
        "nominal_coverage": float(conformal["nominal_coverage"]),
        "calibration_policy": conformal["calibration_policy"],
        "interval_method": conformal["method"],
        "coverage_diagnostic_floor": coverage_floor,
        "global_coverage_by_target": [
            {
                "target_year": int(row.target_year),
                "empirical_coverage": float(row.empirical_coverage),
                "identified_weighted_coverage": float(row.identified_weighted_coverage),
                "mean_interval_width": float(row.mean_interval_width),
            }
            for row in overall_coverage.itertuples(index=False)
        ],
        "spatial_weighted_mae_by_target": [
            {
                "target_year": int(row.target_year),
                "spatial_holdout_weighted_mae": float(row.spatial_holdout_weighted_mae),
                "standard_temporal_weighted_mae": float(row.standard_temporal_weighted_mae),
                "weighted_mae_deterioration": float(row.weighted_mae_deterioration),
            }
            for row in overall_spatial.itertuples(index=False)
        ],
        "global_coverage_diagnostic_passes": bool(
            overall_coverage["empirical_coverage"].ge(coverage_floor).all()
        ),
        "spatial_deterioration_diagnostic_passes": bool(
            overall_spatial["weighted_mae_deterioration"].le(spatial_ceiling).all()
        ),
        "limitations": [
            "Only two target years have strictly prior out-of-time residuals for interval evaluation.",
            "Entity holdout is a transfer stress test; production training may use prior data from every entity.",
            "AMGE evidence for the 2024 fold remains partial after 2022.",
        ],
    }
    decision["ready_for_first_2027_projection"] = bool(
        decision["global_coverage_diagnostic_passes"]
        and decision["spatial_deterioration_diagnostic_passes"]
    )
    (project_root / "artifacts/uncertainty_decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return decision
