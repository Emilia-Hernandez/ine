from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline

from radar27.modeling.feature_enrichment import _resolve_feature_group
from radar27.modeling.feature_models import _load_yaml
from radar27.modeling.tabular_challengers import _preprocessor


def _dense_pipeline(
    network: dict[str, Any], numeric: list[str], categorical: list[str], seed: int
) -> Pipeline:
    estimator = MLPRegressor(
        hidden_layer_sizes=tuple(int(value) for value in network["hidden_layer_sizes"]),
        activation=str(network["activation"]),
        solver=str(network["solver"]),
        loss=str(network["loss"]),
        alpha=float(network["alpha"]),
        batch_size=int(network["batch_size"]),
        learning_rate_init=float(network["learning_rate_init"]),
        max_iter=int(network["max_iter"]),
        early_stopping=bool(network["early_stopping"]),
        validation_fraction=float(network["validation_fraction"]),
        n_iter_no_change=int(network["n_iter_no_change"]),
        tol=float(network["tol"]),
        random_state=seed,
    )
    return Pipeline(
        [("preprocess", _preprocessor(numeric, categorical)), ("model", estimator)]
    )


def _fit_dense_pair(
    train: pd.DataFrame,
    test: pd.DataFrame,
    numeric: list[str],
    categorical: list[str],
    network: dict[str, Any],
    seed: int,
    shrinkage: float,
) -> tuple[np.ndarray, np.ndarray, dict[str, float | int]]:
    required = numeric + categorical
    started = time.perf_counter()
    direct_weights = train["target_identified_records"].astype(float)
    direct_target = train["actual"].astype(float)
    direct_center = float(np.average(direct_target, weights=direct_weights))
    direct_scale = float(
        np.sqrt(np.average((direct_target - direct_center) ** 2, weights=direct_weights))
    )
    direct = _dense_pipeline(network, numeric, categorical, seed)
    direct.fit(
        train[required],
        (direct_target - direct_center) / direct_scale,
        model__sample_weight=direct_weights,
    )
    direct_prediction = direct.predict(test[required]) * direct_scale + direct_center

    residual_train = train.dropna(subset=["participation_same_type"]).copy()
    residual_weights = residual_train["target_identified_records"].astype(float)
    residual_target = (
        residual_train["actual"] - residual_train["participation_same_type"]
    ).astype(float)
    residual_center = float(np.average(residual_target, weights=residual_weights))
    residual_scale = float(
        np.sqrt(
            np.average((residual_target - residual_center) ** 2, weights=residual_weights)
        )
    )
    residual = _dense_pipeline(network, numeric, categorical, seed)
    residual.fit(
        residual_train[required],
        (residual_target - residual_center) / residual_scale,
        model__sample_weight=residual_weights,
    )
    residual_prediction = residual.predict(test[required]) * residual_scale + residual_center
    baseline = test["participation_same_type"].to_numpy(dtype=float)
    raw = np.where(
        np.isfinite(baseline),
        baseline + shrinkage * residual_prediction,
        direct_prediction,
    )
    diagnostics: dict[str, float | int] = {
        "fit_seconds": time.perf_counter() - started,
        "direct_iterations": int(direct.named_steps["model"].n_iter_),
        "residual_iterations": int(residual.named_steps["model"].n_iter_),
        "direct_final_loss": float(direct.named_steps["model"].loss_),
        "residual_final_loss": float(residual.named_steps["model"].loss_),
        "direct_target_center": direct_center,
        "direct_target_scale": direct_scale,
        "residual_target_center": residual_center,
        "residual_target_scale": residual_scale,
    }
    return np.clip(raw, 0.0, 1.0), residual_prediction, diagnostics


def run_dense_neural_challenger(
    project_root: Path, mart: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    config = _load_yaml(project_root / "configs/dense_neural_challenger.yaml")
    feature_config = _load_yaml(project_root / str(config["feature_config"]))
    numeric, categorical = _resolve_feature_group(feature_config, config["feature_group"])
    required = numeric + categorical
    missing = set(required) - set(mart.columns)
    if missing:
        raise ValueError(f"Variables ausentes para la red densa: {sorted(missing)}")

    reference = pd.read_csv(project_root / "artifacts/tables/tabular_challenger_metrics.csv")
    reference = reference[reference["model_id"].eq(config["reference_model"])][
        ["target_year", "identified_weighted_mae"]
    ].rename(columns={"identified_weighted_mae": "reference_weighted_mae"})
    baseline_metrics = pd.read_csv(project_root / "artifacts/tables/backtest_metrics.csv")
    baseline_metrics = baseline_metrics[
        baseline_metrics["scenario"].eq("stable_plus_lineage")
    ].set_index("target_year")
    shift = pd.read_csv(project_root / "artifacts/tables/national_shift_estimates.csv").set_index(
        "target_year"
    )["national_shift_correction"]
    seed = int(config["random_seed"])
    shrinkage = float(config["residual_shrinkage"])
    network = config["network"]
    prediction_rows: list[pd.DataFrame] = []
    metric_rows: list[dict[str, Any]] = []
    registry_rows: list[dict[str, Any]] = []

    for target_year in config["evaluation_targets"]:
        train = mart[
            mart["target_year"].lt(target_year) & mart["actual"].notna()
        ].copy()
        test = mart[mart["target_year"].eq(target_year)].copy()
        before_shift, residual_prediction, diagnostics = _fit_dense_pair(
            train,
            test,
            numeric,
            categorical,
            network,
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
        predicted["model_id"] = config["model_id"]
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
                "model_id": config["model_id"],
                "model_label": config["model_label"],
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
                **diagnostics,
            }
        )
        registry_rows.append(
            {
                "target_year": int(target_year),
                "model_id": config["model_id"],
                "model_family": "MLPRegressor",
                "training_target_years": "|".join(
                    map(str, sorted(int(year) for year in train["target_year"].unique()))
                ),
                "training_units": len(train),
                "feature_group": config["feature_group"],
                "numeric_features": "|".join(numeric),
                "categorical_features": "|".join(categorical),
                "residual_shrinkage": shrinkage,
                "network": json.dumps(network, sort_keys=True),
                "random_seed": seed,
                "preprocessing": "train-only median+missing indicators+standardization; train-only categorical mode+one-hot",
                "validation_policy": "random internal holdout drawn only from strictly prior training elections",
                **diagnostics,
            }
        )

    predictions = pd.concat(prediction_rows, ignore_index=True)
    metrics = pd.DataFrame(metric_rows).merge(reference, on="target_year", validate="one_to_one")
    metrics["mae_change_vs_reference"] = (
        metrics["identified_weighted_mae"] - metrics["reference_weighted_mae"]
    )
    registry = pd.DataFrame(registry_rows)
    output = project_root / "artifacts/tables"
    predictions.to_parquet(output / "dense_neural_predictions.parquet", index=False)
    metrics.to_csv(output / "dense_neural_metrics.csv", index=False)
    registry.to_csv(output / "dense_neural_registry.csv", index=False)
    return predictions, metrics, registry


def write_dense_neural_decision(project_root: Path, metrics: pd.DataFrame) -> dict[str, Any]:
    config = _load_yaml(project_root / "configs/dense_neural_challenger.yaml")
    primary_year = int(config["primary_target_year"])
    primary = metrics[metrics["target_year"].eq(primary_year)].iloc[0]
    improvement = float(primary["reference_weighted_mae"] - primary["identified_weighted_mae"])
    maximum_deterioration = float(config["maximum_other_fold_weighted_mae_deterioration"])
    robustness = []
    for row in metrics.itertuples(index=False):
        if int(row.target_year) == primary_year:
            continue
        change = float(row.mae_change_vs_reference)
        robustness.append(
            {
                "target_year": int(row.target_year),
                "mae_change_vs_reference": change,
                "passes": change <= maximum_deterioration,
            }
        )
    promoted = bool(improvement > 0 and all(item["passes"] for item in robustness))
    decision = {
        "objective": config["objective"],
        "baseline_model": config["baseline_model"],
        "feature_group_held_constant": config["feature_group"],
        "reference_model": config["reference_model"],
        "challenger_model": config["model_id"],
        "challenger_family": "MLPRegressor dense feed-forward neural network",
        "primary_target_year": primary_year,
        "reference_primary_weighted_mae": float(primary["reference_weighted_mae"]),
        "challenger_primary_weighted_mae": float(primary["identified_weighted_mae"]),
        "primary_improvement": improvement,
        "robustness": robustness,
        "challenger_promoted": promoted,
        "selected_model_for_next_iteration": (
            config["model_id"] if promoted else config["reference_model"]
        ),
        "network": config["network"],
        "scikit_learn_version": sklearn.__version__,
        "limitations": [
            "Only three strict out-of-time target elections are available.",
            "The internal early-stopping split is random but contains only elections prior to the evaluated target.",
            "One small frozen architecture was tested; a broad architecture search would overfit model selection.",
        ],
    }
    (project_root / "artifacts/dense_neural_decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return decision
