from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import lightgbm
import numpy as np
import pandas as pd
import sklearn
import xgboost
from lightgbm import LGBMRegressor
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBRegressor

from radar27.modeling.feature_enrichment import _resolve_feature_group
from radar27.modeling.feature_models import _load_yaml


def _preprocessor(numeric: list[str], categorical: list[str]) -> ColumnTransformer:
    return ColumnTransformer(
        [
            (
                "numeric",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="median", add_indicator=True)),
                        ("scale", StandardScaler()),
                    ]
                ),
                numeric,
            ),
            (
                "categorical",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="most_frequent")),
                        (
                            "onehot",
                            OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                        ),
                    ]
                ),
                categorical,
            ),
        ],
        verbose_feature_names_out=True,
    )


def _estimator(spec: dict[str, Any], seed: int):
    family = spec["family"]
    if family == "hist_gradient_boosting":
        return HistGradientBoostingRegressor(
            learning_rate=float(spec["learning_rate"]),
            max_iter=int(spec["max_iter"]),
            max_leaf_nodes=int(spec["max_leaf_nodes"]),
            min_samples_leaf=int(spec["min_samples_leaf"]),
            l2_regularization=float(spec["l2_regularization"]),
            random_state=seed,
        )
    if family == "extra_trees":
        return ExtraTreesRegressor(
            n_estimators=int(spec["n_estimators"]),
            max_depth=int(spec["max_depth"]),
            min_samples_leaf=int(spec["min_samples_leaf"]),
            max_features=float(spec["max_features"]),
            n_jobs=int(spec["n_jobs"]),
            random_state=seed,
        )
    if family == "xgboost":
        return XGBRegressor(
            objective=spec["objective"],
            n_estimators=int(spec["n_estimators"]),
            learning_rate=float(spec["learning_rate"]),
            max_depth=int(spec["max_depth"]),
            min_child_weight=float(spec["min_child_weight"]),
            subsample=float(spec["subsample"]),
            colsample_bytree=float(spec["colsample_bytree"]),
            reg_lambda=float(spec["reg_lambda"]),
            tree_method=spec["tree_method"],
            n_jobs=int(spec["n_jobs"]),
            random_state=seed,
        )
    if family == "lightgbm":
        return LGBMRegressor(
            objective=spec["objective"],
            n_estimators=int(spec["n_estimators"]),
            learning_rate=float(spec["learning_rate"]),
            num_leaves=int(spec["num_leaves"]),
            max_depth=int(spec["max_depth"]),
            min_child_samples=int(spec["min_child_samples"]),
            subsample=float(spec["subsample"]),
            subsample_freq=int(spec["subsample_freq"]),
            colsample_bytree=float(spec["colsample_bytree"]),
            reg_lambda=float(spec["reg_lambda"]),
            n_jobs=int(spec["n_jobs"]),
            verbosity=int(spec["verbosity"]),
            random_state=seed,
        )
    raise ValueError(f"Familia tabular no soportada: {family}")


def _pipeline(
    spec: dict[str, Any], numeric: list[str], categorical: list[str], seed: int
) -> Pipeline:
    return Pipeline(
        [
            ("preprocess", _preprocessor(numeric, categorical)),
            ("model", _estimator(spec, seed)),
        ]
    )


def _predict_residual_correction(
    train: pd.DataFrame,
    test: pd.DataFrame,
    numeric: list[str],
    categorical: list[str],
    spec: dict[str, Any],
    seed: int,
    shrinkage: float,
) -> tuple[np.ndarray, np.ndarray, float]:
    required = numeric + categorical
    weights = train["target_identified_records"].astype(float)
    started = time.perf_counter()
    direct = _pipeline(spec, numeric, categorical, seed)
    direct.fit(train[required], train["actual"], model__sample_weight=weights)
    direct_prediction = direct.predict(test[required])

    residual_train = train.dropna(subset=["participation_same_type"]).copy()
    residual = _pipeline(spec, numeric, categorical, seed)
    residual.fit(
        residual_train[required],
        residual_train["actual"] - residual_train["participation_same_type"],
        model__sample_weight=residual_train["target_identified_records"].astype(float),
    )
    residual_prediction = residual.predict(test[required])
    elapsed = time.perf_counter() - started
    baseline = test["participation_same_type"].to_numpy(dtype=float)
    raw = np.where(
        np.isfinite(baseline),
        baseline + shrinkage * residual_prediction,
        direct_prediction,
    )
    return np.clip(raw, 0.0, 1.0), residual_prediction, elapsed


def run_tabular_challengers(
    project_root: Path, mart: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    config = _load_yaml(project_root / "configs/tabular_challengers.yaml")
    feature_config = _load_yaml(project_root / str(config["feature_config"]))
    numeric, categorical = _resolve_feature_group(feature_config, config["feature_group"])
    required = numeric + categorical
    missing = set(required) - set(mart.columns)
    if missing:
        raise ValueError(f"Variables ausentes para challengers: {sorted(missing)}")

    seed = int(config["random_seed"])
    shrinkage = float(config["residual_shrinkage"])
    shift = pd.read_csv(project_root / "artifacts/tables/national_shift_estimates.csv").set_index(
        "target_year"
    )["national_shift_correction"]
    baseline_metrics = pd.read_csv(project_root / "artifacts/tables/backtest_metrics.csv")
    baseline_metrics = baseline_metrics[
        baseline_metrics["scenario"].eq("stable_plus_lineage")
    ].set_index("target_year")

    prediction_rows: list[pd.DataFrame] = []
    metric_rows: list[dict[str, Any]] = []
    registry_rows: list[dict[str, Any]] = []
    for model_id, spec in config["models"].items():
        for target_year in config["evaluation_targets"]:
            train = mart[
                mart["target_year"].lt(target_year) & mart["actual"].notna()
            ].copy()
            test = mart[mart["target_year"].eq(target_year)].copy()
            before_shift, residual_prediction, elapsed = _predict_residual_correction(
                train,
                test,
                numeric,
                categorical,
                spec,
                seed,
                shrinkage,
            )
            correction = float(shift.get(target_year, 0.0))
            prediction = np.clip(before_shift + correction, 0.0, 1.0)
            predicted = test[
                [
                    "target_year",
                    "evaluation_unit_id",
                    "entity_id",
                    "geography_confidence_class",
                    "target_sections_represented",
                    "target_identified_records",
                    "actual",
                    "participation_same_type",
                ]
            ].copy()
            predicted["model_id"] = model_id
            predicted["feature_group"] = config["feature_group"]
            predicted["model_prediction_before_national_shift"] = before_shift
            predicted["predicted_residual_unshrunk"] = residual_prediction
            predicted["national_shift_correction"] = correction
            predicted["prediction"] = prediction
            prediction_rows.append(predicted)

            valid = predicted.dropna(subset=["actual", "prediction"]).copy()
            weights = valid["target_identified_records"].astype(float)
            error = valid["prediction"] - valid["actual"]
            weighted_mae = float(np.average(error.abs(), weights=weights))
            frozen_mae = float(baseline_metrics.loc[target_year, "identified_weighted_mae"])
            metric_rows.append(
                {
                    "target_year": int(target_year),
                    "model_id": model_id,
                    "model_label": spec["label"],
                    "feature_group": config["feature_group"],
                    "evaluation_units": len(valid),
                    "baseline_model": config["baseline_model"],
                    "baseline_weighted_mae": frozen_mae,
                    "identified_weighted_mae": weighted_mae,
                    "mae_change_vs_baseline": weighted_mae - frozen_mae,
                    "weighted_bias": float(np.average(error, weights=weights)),
                    "mae": float(error.abs().mean()),
                    "share_within_5pp": float(error.abs().le(0.05).mean()),
                    "national_shift_correction": correction,
                    "fit_seconds": elapsed,
                }
            )
            registry_rows.append(
                {
                    "target_year": int(target_year),
                    "model_id": model_id,
                    "model_label": spec["label"],
                    "model_family": spec["family"],
                    "training_target_years": "|".join(
                        map(str, sorted(int(year) for year in train["target_year"].unique()))
                    ),
                    "training_units": len(train),
                    "feature_group": config["feature_group"],
                    "numeric_features": "|".join(numeric),
                    "categorical_features": "|".join(categorical),
                    "residual_shrinkage": shrinkage,
                    "hyperparameters": json.dumps(spec, sort_keys=True),
                    "random_seed": seed,
                    "preprocessing": "train-only median+missing indicators+standardization; train-only categorical mode+one-hot",
                    "fit_seconds": elapsed,
                }
            )

    predictions = pd.concat(prediction_rows, ignore_index=True)
    metrics = pd.DataFrame(metric_rows).sort_values(["target_year", "identified_weighted_mae"])
    reference = metrics[metrics["model_id"].eq(config["reference_model"])][
        ["target_year", "identified_weighted_mae"]
    ].rename(columns={"identified_weighted_mae": "reference_weighted_mae"})
    metrics = metrics.merge(reference, on="target_year", validate="many_to_one")
    metrics["mae_change_vs_reference"] = (
        metrics["identified_weighted_mae"] - metrics["reference_weighted_mae"]
    )
    registry = pd.DataFrame(registry_rows)
    output = project_root / "artifacts/tables"
    predictions.to_parquet(output / "tabular_challenger_predictions.parquet", index=False)
    metrics.to_csv(output / "tabular_challenger_metrics.csv", index=False)
    registry.to_csv(output / "tabular_challenger_registry.csv", index=False)
    return predictions, metrics, registry


def write_tabular_challenger_decision(
    project_root: Path, metrics: pd.DataFrame
) -> dict[str, Any]:
    config = _load_yaml(project_root / "configs/tabular_challengers.yaml")
    primary_year = int(config["primary_target_year"])
    reference_model = str(config["reference_model"])
    primary = metrics[metrics["target_year"].eq(primary_year)].sort_values(
        "identified_weighted_mae"
    )
    best_model = str(primary.iloc[0]["model_id"])
    best_primary = float(primary.iloc[0]["identified_weighted_mae"])
    reference_primary = float(
        primary[primary["model_id"].eq(reference_model)].iloc[0]["identified_weighted_mae"]
    )
    maximum_deterioration = float(config["maximum_other_fold_weighted_mae_deterioration"])
    robustness = []
    for target_year in config["evaluation_targets"]:
        if int(target_year) == primary_year:
            continue
        row = metrics[
            metrics["target_year"].eq(target_year) & metrics["model_id"].eq(best_model)
        ].iloc[0]
        change = float(row["mae_change_vs_reference"])
        robustness.append(
            {
                "target_year": int(target_year),
                "mae_change_vs_reference": change,
                "passes": change <= maximum_deterioration,
            }
        )
    challenger_promoted = bool(
        best_model != reference_model
        and best_primary < reference_primary
        and all(item["passes"] for item in robustness)
    )
    selected_model = best_model if challenger_promoted else reference_model
    versions = {
        "scikit_learn": sklearn.__version__,
        "xgboost": xgboost.__version__,
        "lightgbm": lightgbm.__version__,
    }
    decision = {
        "objective": config["objective"],
        "baseline_model": config["baseline_model"],
        "feature_group_held_constant": config["feature_group"],
        "residual_shrinkage_held_constant": float(config["residual_shrinkage"]),
        "national_shift_correction_held_constant": True,
        "reference_model": reference_model,
        "best_primary_model": best_model,
        "primary_target_year": primary_year,
        "reference_primary_weighted_mae": reference_primary,
        "best_primary_weighted_mae": best_primary,
        "primary_improvement": reference_primary - best_primary,
        "maximum_other_fold_weighted_mae_deterioration": maximum_deterioration,
        "robustness": robustness,
        "challenger_promoted": challenger_promoted,
        "selected_model_for_next_iteration": selected_model,
        "library_versions": versions,
        "limitations": [
            "Only three strict out-of-time target elections are available.",
            "One moderate frozen specification per family was evaluated; no broad hyperparameter search was performed.",
            "Territorial context is aggregate relative context, not polygon adjacency or a spatial graph.",
        ],
    }
    (project_root / "artifacts/tabular_challenger_decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return decision
