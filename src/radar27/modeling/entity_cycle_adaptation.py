from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from radar27.modeling.feature_models import _load_yaml


def corrected_prediction(
    prediction: pd.Series | np.ndarray,
    signal: pd.Series | np.ndarray,
    shrinkage: float,
) -> np.ndarray:
    """Apply a bounded entity-level mean-reversion correction."""
    return np.clip(
        np.asarray(prediction, dtype=float)
        + float(shrinkage) * np.asarray(signal, dtype=float),
        0.0,
        1.0,
    )


def _weighted_metrics(frame: pd.DataFrame, prediction_column: str) -> dict[str, float]:
    valid = frame.dropna(
        subset=["actual", prediction_column, "target_identified_records"]
    ).copy()
    weights = valid["target_identified_records"].astype(float)
    error = valid[prediction_column] - valid["actual"]
    return {
        "evaluation_units": len(valid),
        "identified_weighted_mae": float(np.average(error.abs(), weights=weights)),
        "weighted_bias": float(np.average(error, weights=weights)),
        "mae": float(error.abs().mean()),
        "share_within_5pp": float(error.abs().le(0.05).mean()),
    }


def run_entity_cycle_adaptation(
    project_root: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Select and audit a state-cycle shrinkage using the frozen strict folds."""
    config = _load_yaml(project_root / "configs/entity_cycle_adaptation.yaml")
    feature_group = str(config["base_feature_group"])
    signal_column = str(config["signal"])
    predictions = pd.read_parquet(
        project_root / "artifacts/tables/feature_ablation_predictions.parquet"
    )
    predictions = predictions[predictions["feature_group"].eq(feature_group)].copy()
    mart = pd.read_parquet(
        project_root / "artifacts/tables/feature_ablation_mart.parquet"
    )[["target_year", "evaluation_unit_id", signal_column]]
    predictions = predictions.merge(
        mart,
        on=["target_year", "evaluation_unit_id"],
        how="left",
        validate="one_to_one",
    )
    if predictions[signal_column].isna().any():
        raise ValueError("Hay predicciones sin señal estatal de ciclo")
    target_years = {int(year) for year in config["strict_targets"]}
    if {int(year) for year in predictions["target_year"].unique()} != target_years:
        raise ValueError("Los folds de adaptación estatal no coinciden con el contrato")
    metric_rows: list[dict[str, Any]] = []
    candidate_predictions: dict[float, np.ndarray] = {}
    for shrinkage_value in config["candidate_shrinkages"]:
        shrinkage = float(shrinkage_value)
        candidate = corrected_prediction(
            predictions["prediction"], predictions[signal_column], shrinkage
        )
        candidate_predictions[shrinkage] = candidate
        scored = predictions.assign(candidate_prediction=candidate)
        for target_year, frame in scored.groupby("target_year"):
            metrics = _weighted_metrics(frame, "candidate_prediction")
            metric_rows.append(
                {
                    "target_year": int(target_year),
                    "entity_cycle_shrinkage": shrinkage,
                    "base_feature_group": feature_group,
                    "signal": signal_column,
                    **metrics,
                }
            )
    metrics = pd.DataFrame(metric_rows).sort_values(
        ["target_year", "identified_weighted_mae", "entity_cycle_shrinkage"]
    )
    primary_year = int(config["primary_target_year"])
    primary = metrics[metrics["target_year"].eq(primary_year)].copy()
    primary["absolute_shrinkage"] = primary["entity_cycle_shrinkage"].abs()
    selected = primary.sort_values(
        ["identified_weighted_mae", "absolute_shrinkage"]
    ).iloc[0]
    selected_shrinkage = float(selected["entity_cycle_shrinkage"])
    baseline = metrics[metrics["entity_cycle_shrinkage"].eq(0.0)].set_index(
        "target_year"
    )
    selected_metrics = metrics[
        metrics["entity_cycle_shrinkage"].eq(selected_shrinkage)
    ].set_index("target_year")
    minimum_improvement = float(config["minimum_primary_mae_improvement"])
    primary_improvement = float(
        baseline.loc[primary_year, "identified_weighted_mae"]
        - selected_metrics.loc[primary_year, "identified_weighted_mae"]
    )
    maximum_deterioration = float(
        config["maximum_other_fold_weighted_mae_deterioration"]
    )
    robustness = []
    for target_year in sorted(target_years - {primary_year}):
        change = float(
            selected_metrics.loc[target_year, "identified_weighted_mae"]
            - baseline.loc[target_year, "identified_weighted_mae"]
        )
        robustness.append(
            {
                "target_year": target_year,
                "mae_change_vs_uncorrected": change,
                "passes": change <= maximum_deterioration,
            }
        )
    promoted = bool(
        selected_shrinkage != 0.0
        and primary_improvement >= minimum_improvement
        and all(row["passes"] for row in robustness)
    )
    applied_shrinkage = selected_shrinkage if promoted else 0.0
    output_predictions = predictions.copy()
    output_predictions["entity_cycle_shrinkage"] = applied_shrinkage
    output_predictions["entity_cycle_correction"] = (
        applied_shrinkage * output_predictions[signal_column]
    )
    output_predictions["prediction_before_entity_cycle_correction"] = output_predictions[
        "prediction"
    ]
    output_predictions["prediction"] = candidate_predictions[applied_shrinkage]
    decision = {
        "base_feature_group": feature_group,
        "signal": signal_column,
        "interpretation": config["interpretation"],
        "selection_rule": config["selection_rule"],
        "primary_target_year": primary_year,
        "selected_shrinkage": selected_shrinkage,
        "applied_shrinkage": applied_shrinkage,
        "primary_mae_improvement": primary_improvement,
        "minimum_primary_mae_improvement": minimum_improvement,
        "maximum_other_fold_weighted_mae_deterioration": maximum_deterioration,
        "robustness": robustness,
        "promoted_for_2027": promoted,
        "fold_metrics": [
            {
                "target_year": target_year,
                "uncorrected_weighted_mae": float(
                    baseline.loc[target_year, "identified_weighted_mae"]
                ),
                "corrected_weighted_mae": float(
                    selected_metrics.loc[target_year, "identified_weighted_mae"]
                ),
            }
            for target_year in sorted(target_years)
        ],
        "limitations": [
            "The shrinkage is selected on the prespecified 2021 primary fold.",
            "Only three strict historical folds are available.",
            "A negative coefficient represents state-level mean reversion, not persistence.",
        ],
    }
    output = project_root / "artifacts"
    output_predictions.to_parquet(
        output / "tables/entity_cycle_adaptation_predictions.parquet", index=False
    )
    metrics.to_csv(output / "tables/entity_cycle_adaptation_metrics.csv", index=False)
    (output / "entity_cycle_adaptation_decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return output_predictions, metrics, decision
