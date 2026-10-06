from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from radar27.modeling.feature_models import _load_yaml
from radar27.modeling.uncertainty import (
    _coverage_metrics,
    _risk_decile,
    _size_band,
    finite_sample_conformal_quantile,
)


def _weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    valid = values.notna() & weights.notna() & weights.gt(0)
    if not valid.any():
        raise ValueError("No hay valores con peso positivo para estimar el cambio nacional")
    return float(np.average(values.loc[valid].astype(float), weights=weights.loc[valid]))


def estimate_national_shift(project_root: Path) -> pd.DataFrame:
    """Estimate each target's national correction from the prior same-family cycle only."""
    config = _load_yaml(project_root / "configs/calibration_adaptation.yaml")
    shift = config["national_shift"]
    cycle_years = int(shift["cycle_years"])
    mart = pd.read_parquet(project_root / "artifacts/tables/feature_mart_ab.parquet")
    eligible = mart.dropna(
        subset=["actual", "participation_same_type", "target_identified_records"]
    ).copy()
    eligible["observed_same_family_change"] = (
        eligible["actual"] - eligible["participation_same_type"]
    )
    observed_rows = []
    for source_year, frame in eligible.groupby("target_year", sort=True):
        observed_rows.append(
            {
                "source_target_year": int(source_year),
                "source_election_family": str(frame["election_family"].iloc[0]),
                "source_units": len(frame),
                "source_identified_records": int(frame["target_identified_records"].sum()),
                "weighted_national_same_family_change": _weighted_mean(
                    frame["observed_same_family_change"], frame["target_identified_records"]
                ),
                "unweighted_national_same_family_change": float(
                    frame["observed_same_family_change"].mean()
                ),
            }
        )
    observed = pd.DataFrame(observed_rows)
    family_by_year = (
        mart[["target_year", "election_family"]]
        .drop_duplicates("target_year")
        .set_index("target_year")["election_family"]
        .to_dict()
    )
    targets = sorted(
        {int(year) for year in shift["evaluation_targets"]}
        | {int(year) for year in shift["operational_targets"]}
        | {int(year) for year in mart["target_year"].unique()}
    )
    rows = []
    for target_year in targets:
        source_year = target_year - cycle_years
        source = observed[observed["source_target_year"].eq(source_year)]
        target_family = shift["operational_targets"].get(
            target_year, shift["operational_targets"].get(str(target_year), family_by_year.get(target_year))
        )
        if source.empty:
            rows.append(
                {
                    "target_year": target_year,
                    "target_election_family": target_family,
                    "source_target_year": source_year,
                    "source_election_family": pd.NA,
                    "source_units": 0,
                    "source_identified_records": 0,
                    "national_shift_correction": 0.0,
                    "source_strictly_prior": True,
                    "family_match": pd.NA,
                    "status": "zero_fallback_no_prior_same_family_target",
                }
            )
            continue
        source_row = source.iloc[0]
        source_family = str(source_row["source_election_family"])
        family_match = target_family == source_family
        if not family_match:
            raise ValueError(
                f"La fuente {source_year} ({source_family}) no coincide con {target_year} ({target_family})"
            )
        rows.append(
            {
                "target_year": target_year,
                "target_election_family": target_family,
                "source_target_year": source_year,
                "source_election_family": source_family,
                "source_units": int(source_row["source_units"]),
                "source_identified_records": int(source_row["source_identified_records"]),
                "national_shift_correction": float(
                    source_row["weighted_national_same_family_change"]
                ),
                "source_strictly_prior": source_year < target_year,
                "family_match": family_match,
                "status": (
                    "operational_parameter_only"
                    if target_year in {int(year) for year in shift["operational_targets"]}
                    else "out_of_time_evaluation_parameter"
                ),
            }
        )
    estimates = pd.DataFrame(rows).sort_values("target_year")
    if not estimates["source_strictly_prior"].all():
        raise ValueError("Una corrección nacional usa un target no anterior")
    estimates.to_csv(
        project_root / "artifacts/tables/national_shift_estimates.csv", index=False
    )
    return estimates


def build_shift_corrected_predictions(
    project_root: Path, estimates: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    config = _load_yaml(project_root / "configs/calibration_adaptation.yaml")
    model_id = str(config["selected_model"])
    predictions = pd.read_parquet(
        project_root / "artifacts/tables/model_backtest_predictions.parquet"
    )
    selected = predictions[predictions["model_id"].eq(model_id)].copy()
    correction = estimates.set_index("target_year")["national_shift_correction"]
    source_year = estimates.set_index("target_year")["source_target_year"]
    selected["national_shift_correction"] = selected["target_year"].map(correction).fillna(0.0)
    selected["shift_source_target_year"] = selected["target_year"].map(source_year)
    selected["prediction_original"] = selected["prediction"]
    selected["prediction_shift_corrected_raw"] = (
        selected["prediction_original"] + selected["national_shift_correction"]
    )
    selected["prediction_shift_corrected"] = selected[
        "prediction_shift_corrected_raw"
    ].clip(0.0, 1.0)
    selected["shift_corrected_was_clipped"] = selected["prediction_shift_corrected"].ne(
        selected["prediction_shift_corrected_raw"]
    )
    metric_rows = []
    for target_year, frame in selected.groupby("target_year", sort=True):
        valid = frame.dropna(
            subset=["actual", "prediction_original", "prediction_shift_corrected"]
        ).copy()
        weights = valid["target_identified_records"].astype(float)
        original_error = valid["prediction_original"] - valid["actual"]
        corrected_error = valid["prediction_shift_corrected"] - valid["actual"]
        metric_rows.append(
            {
                "target_year": int(target_year),
                "national_shift_correction": float(valid["national_shift_correction"].iloc[0]),
                "shift_source_target_year": int(valid["shift_source_target_year"].iloc[0]),
                "evaluation_units": len(valid),
                "original_weighted_mae": float(np.average(original_error.abs(), weights=weights)),
                "corrected_weighted_mae": float(np.average(corrected_error.abs(), weights=weights)),
                "weighted_mae_change": float(
                    np.average(corrected_error.abs(), weights=weights)
                    - np.average(original_error.abs(), weights=weights)
                ),
                "original_weighted_bias": float(np.average(original_error, weights=weights)),
                "corrected_weighted_bias": float(np.average(corrected_error, weights=weights)),
                "original_mae": float(original_error.abs().mean()),
                "corrected_mae": float(corrected_error.abs().mean()),
            }
        )
    metrics = pd.DataFrame(metric_rows)
    keep = [
        "target_year",
        "evaluation_unit_id",
        "entity_id",
        "geography_confidence_class",
        "target_sections_represented",
        "nominal_list",
        "target_identified_records",
        "actual",
        "prediction_original",
        "prediction_shift_corrected_raw",
        "prediction_shift_corrected",
        "national_shift_correction",
        "shift_source_target_year",
        "shift_corrected_was_clipped",
    ]
    output = project_root / "artifacts/tables"
    selected[keep].to_parquet(output / "shift_corrected_predictions.parquet", index=False)
    metrics.to_csv(output / "shift_correction_metrics.csv", index=False)
    return selected[keep], metrics


def _add_interval(
    test: pd.DataFrame,
    calibration: pd.DataFrame,
    method: str,
    center_column: str,
    calibration_prediction_column: str,
    config: dict[str, Any],
    calibration_predictor: str,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    alpha = float(config["alpha"])
    minimum = int(config["minimum_class_calibration_units"])
    calibration = calibration.dropna(
        subset=["actual", calibration_prediction_column]
    ).copy()
    calibration["calibration_absolute_error"] = (
        calibration["actual"] - calibration[calibration_prediction_column]
    ).abs()
    global_radius = finite_sample_conformal_quantile(
        calibration["calibration_absolute_error"], alpha
    )
    class_radii: dict[str, float] = {}
    for confidence_class, frame in calibration.groupby(
        "geography_confidence_class", observed=True
    ):
        if len(frame) >= minimum:
            class_radii[str(confidence_class)] = finite_sample_conformal_quantile(
                frame["calibration_absolute_error"], alpha
            )
    result = test.copy()
    result["prediction"] = result[center_column]
    result["conformal_radius"] = result["geography_confidence_class"].map(class_radii)
    result["used_global_fallback"] = result["conformal_radius"].isna()
    result["conformal_radius"] = result["conformal_radius"].fillna(global_radius)
    result["lower"] = (result["prediction"] - result["conformal_radius"]).clip(0.0, 1.0)
    result["upper"] = (result["prediction"] + result["conformal_radius"]).clip(0.0, 1.0)
    result["interval_method"] = method
    result["calibration_predictor"] = calibration_predictor
    result["calibration_target_years"] = "|".join(
        map(str, sorted(int(year) for year in calibration["target_year"].unique()))
    )
    result["max_calibration_target_year"] = int(calibration["target_year"].max())
    result["nominal_coverage"] = float(config["nominal_coverage"])
    summary = [
        {
            "target_year": int(result["target_year"].iloc[0]),
            "interval_method": method,
            "calibration_predictor": calibration_predictor,
            "calibration_target_years": result["calibration_target_years"].iloc[0],
            "stratum": "global",
            "calibration_units": len(calibration),
            "radius": global_radius,
            "used_global_fallback": False,
        }
    ]
    for confidence_class, frame in calibration.groupby(
        "geography_confidence_class", observed=True
    ):
        summary.append(
            {
                "target_year": int(result["target_year"].iloc[0]),
                "interval_method": method,
                "calibration_predictor": calibration_predictor,
                "calibration_target_years": result["calibration_target_years"].iloc[0],
                "stratum": f"geography_confidence_class={confidence_class}",
                "calibration_units": len(frame),
                "radius": class_radii.get(str(confidence_class), global_radius),
                "used_global_fallback": str(confidence_class) not in class_radii,
            }
        )
    return result, summary


def build_adaptive_interval_comparison(
    project_root: Path,
    corrected_predictions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    config = _load_yaml(project_root / "configs/calibration_adaptation.yaml")
    interval_config = config["adaptive_intervals"]
    mart = pd.read_parquet(project_root / "artifacts/tables/feature_mart_ab.parquet")
    original_intervals = pd.read_parquet(
        project_root / "artifacts/tables/conformal_backtest_intervals.parquet"
    )
    interval_frames = []
    calibration_rows: list[dict[str, Any]] = []
    for target_year in interval_config["evaluation_targets"]:
        target = corrected_predictions[corrected_predictions["target_year"].eq(target_year)].copy()
        original = original_intervals[original_intervals["target_year"].eq(target_year)].copy()
        original["interval_method"] = "rolling_conformal_original_center"
        original["calibration_predictor"] = "approved_candidate_original_center"
        interval_frames.append(original)

        rolling_calibration = corrected_predictions[
            corrected_predictions["target_year"].lt(target_year)
        ].copy()
        rolling, summary = _add_interval(
            target,
            rolling_calibration,
            "rolling_conformal_shift_corrected",
            "prediction_shift_corrected",
            "prediction_shift_corrected",
            interval_config,
            "shift_corrected_candidate",
        )
        interval_frames.append(rolling)
        calibration_rows.extend(summary)

        analogue_year = int(target_year) - int(config["national_shift"]["cycle_years"])
        model_analogue = corrected_predictions[
            corrected_predictions["target_year"].eq(analogue_year)
        ].copy()
        if model_analogue.empty:
            family_calibration = mart[mart["target_year"].eq(analogue_year)].copy()
            calibration_column = "participation_same_type"
            calibration_predictor = "same_type_baseline_cold_start"
        else:
            family_calibration = model_analogue
            calibration_column = "prediction_shift_corrected"
            calibration_predictor = "shift_corrected_candidate"
        family, summary = _add_interval(
            target,
            family_calibration,
            "family_analogue_shift_corrected",
            "prediction_shift_corrected",
            calibration_column,
            interval_config,
            calibration_predictor,
        )
        interval_frames.append(family)
        calibration_rows.extend(summary)

    intervals = pd.concat(interval_frames, ignore_index=True, sort=False)
    intervals["section_size_band"] = _size_band(intervals["nominal_list"], interval_config).astype(
        "string"
    )
    intervals["predicted_risk_decile"] = intervals.groupby(
        ["target_year", "interval_method"], group_keys=False
    )["prediction"].transform(lambda values: _risk_decile(1 - values))
    if not (intervals["max_calibration_target_year"] < intervals["target_year"]).all():
        raise ValueError("Un intervalo adaptativo usa calibración del target o posterior")
    coverage_frames = []
    for method, frame in intervals.groupby("interval_method", sort=True):
        metrics = _coverage_metrics(frame)
        metrics.insert(0, "interval_method", method)
        coverage_frames.append(metrics)
    coverage = pd.concat(coverage_frames, ignore_index=True)
    calibration = pd.DataFrame(calibration_rows)
    output = project_root / "artifacts/tables"
    intervals.to_parquet(output / "adaptive_interval_predictions.parquet", index=False)
    coverage.to_csv(output / "adaptive_interval_coverage.csv", index=False)
    calibration.to_csv(output / "adaptive_interval_calibration.csv", index=False)
    return intervals, coverage, calibration


def write_adaptation_decision(
    project_root: Path,
    shift_metrics: pd.DataFrame,
    coverage: pd.DataFrame,
) -> dict[str, Any]:
    config = _load_yaml(project_root / "configs/calibration_adaptation.yaml")
    selected_method = str(config["promotion"]["selected_interval_candidate"])
    floor = float(config["adaptive_intervals"]["minimum_acceptable_global_coverage"])
    nominal = float(config["adaptive_intervals"]["nominal_coverage"])
    max_deterioration = float(
        config["national_shift"]["maximum_other_fold_weighted_mae_deterioration"]
    )
    overall = coverage[
        coverage["group_dimension"].eq("overall")
        & coverage["interval_method"].eq(selected_method)
    ].sort_values("target_year")
    original = coverage[
        coverage["group_dimension"].eq("overall")
        & coverage["interval_method"].eq("rolling_conformal_original_center")
    ].sort_values("target_year")
    primary = shift_metrics[shift_metrics["target_year"].eq(2021)].iloc[0]
    robustness = shift_metrics[shift_metrics["target_year"].eq(2024)].iloc[0]
    primary_improves = float(primary["weighted_mae_change"]) < 0
    robustness_passes = float(robustness["weighted_mae_change"]) <= max_deterioration
    coverage_passes = bool(overall["empirical_coverage"].ge(floor).all())
    nominal_passes = bool(overall["empirical_coverage"].ge(nominal).all())
    comparisons = []
    for row in overall.itertuples(index=False):
        baseline = original[original["target_year"].eq(row.target_year)].iloc[0]
        comparisons.append(
            {
                "target_year": int(row.target_year),
                "selected_empirical_coverage": float(row.empirical_coverage),
                "original_empirical_coverage": float(baseline["empirical_coverage"]),
                "coverage_change": float(
                    row.empirical_coverage - baseline["empirical_coverage"]
                ),
                "selected_mean_interval_width": float(row.mean_interval_width),
                "original_mean_interval_width": float(baseline["mean_interval_width"]),
                "width_change": float(
                    row.mean_interval_width - baseline["mean_interval_width"]
                ),
            }
        )
    experimental_approved = bool(primary_improves and robustness_passes and coverage_passes)
    decision = {
        "point_prediction_method": "approved_candidate_plus_previous_same_family_national_change",
        "selected_interval_method": selected_method,
        "primary_2021_weighted_mae_improves": bool(primary_improves),
        "primary_2021_original_weighted_mae": float(primary["original_weighted_mae"]),
        "primary_2021_corrected_weighted_mae": float(primary["corrected_weighted_mae"]),
        "primary_2021_original_weighted_bias": float(primary["original_weighted_bias"]),
        "primary_2021_corrected_weighted_bias": float(primary["corrected_weighted_bias"]),
        "other_fold_2024_weighted_mae_deterioration": float(
            robustness["weighted_mae_change"]
        ),
        "other_fold_deterioration_passes": bool(robustness_passes),
        "minimum_acceptable_global_coverage": floor,
        "coverage_floor_passes_all_targets": coverage_passes,
        "nominal_coverage_passes_all_targets": nominal_passes,
        "interval_comparisons": comparisons,
        "approved_for_experimental_2027_pipeline": experimental_approved,
        "public_interval_ready": bool(experimental_approved and nominal_passes),
        "interpretation": (
            "The adaptive family analogue passes the diagnostic floor and may support an internal "
            "2027 experiment, but it is not a public coverage guarantee unless every target reaches "
            "nominal coverage."
        ),
    }
    (project_root / "artifacts/calibration_adaptation_decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return decision
