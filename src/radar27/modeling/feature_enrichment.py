from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from radar27.modeling.feature_models import _load_yaml, _pipeline


def add_relative_territorial_context(frame: pd.DataFrame) -> pd.DataFrame:
    """Derive entity/national context exclusively from already lagged predictors."""
    enriched = frame.copy()
    for source, prefix in [
        ("participation_same_type", "same_type"),
        ("participation_lag1", "lag1"),
    ]:
        entity_group = enriched.groupby(["target_year", "entity_id"])[source]
        enriched[f"entity_{prefix}_mean"] = entity_group.transform("mean")
        enriched[f"entity_{prefix}_std"] = entity_group.transform("std")
        enriched[f"{prefix}_minus_entity_mean"] = (
            enriched[source] - enriched[f"entity_{prefix}_mean"]
        )
        enriched[f"national_{prefix}_mean"] = enriched.groupby("target_year")[source].transform(
            "mean"
        )
        enriched[f"{prefix}_minus_national_mean"] = (
            enriched[source] - enriched[f"national_{prefix}_mean"]
        )
    return enriched


def build_enriched_feature_mart(project_root: Path) -> pd.DataFrame:
    """Add target-known territorial context without using outcomes."""
    mart = pd.read_parquet(project_root / "artifacts/tables/feature_mart_ab.parquet")
    classes = pd.read_parquet(
        project_root / "artifacts/tables/section_confidence_by_election.parquet"
    )
    stable_types = classes[classes["geography_confidence_class"].eq("A")][
        ["target_year", "section_key_observed", "section_type_code"]
    ].copy()
    stable_types["evaluation_unit_id"] = "S:" + stable_types["section_key_observed"]
    stable_types = stable_types[
        ["target_year", "evaluation_unit_id", "section_type_code"]
    ].drop_duplicates(["target_year", "evaluation_unit_id"])
    enriched = mart.merge(
        stable_types,
        on=["target_year", "evaluation_unit_id"],
        how="left",
        validate="one_to_one",
    )
    enriched["geography_unit_type"] = np.where(
        enriched["geography_confidence_class"].eq("B"),
        "official_lineage_component",
        "stable_section_type_" + enriched["section_type_code"].fillna("unknown").astype(str),
    )
    enriched = add_relative_territorial_context(enriched)
    enriched["context_source_max_year"] = enriched["max_electoral_feature_year"]
    if not (enriched["context_source_max_year"] < enriched["target_year"]).all():
        raise ValueError("El contexto territorial contiene información del target")
    enriched.to_parquet(
        project_root / "artifacts/tables/feature_ablation_mart.parquet", index=False
    )
    return enriched


def _resolve_feature_group(
    config: dict[str, Any], group_name: str, seen: set[str] | None = None
) -> tuple[list[str], list[str]]:
    seen = set() if seen is None else seen
    if group_name in seen:
        raise ValueError(f"Ciclo en feature_groups: {group_name}")
    seen.add(group_name)
    group = config["feature_groups"][group_name]
    numeric: list[str] = []
    categorical: list[str] = []
    parent = group.get("extends")
    if parent:
        parent_numeric, parent_categorical = _resolve_feature_group(config, parent, seen.copy())
        numeric.extend(parent_numeric)
        categorical.extend(parent_categorical)
    included = group.get("include_group")
    if included:
        included_numeric, included_categorical = _resolve_feature_group(
            config, included, seen.copy()
        )
        numeric.extend(included_numeric)
        categorical.extend(included_categorical)
    numeric.extend(group.get("numeric", []))
    categorical.extend(group.get("categorical", []))
    return list(dict.fromkeys(numeric)), list(dict.fromkeys(categorical))


def _predict_group(
    train: pd.DataFrame,
    test: pd.DataFrame,
    numeric: list[str],
    categorical: list[str],
    spec: dict[str, Any],
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    required = numeric + categorical
    direct = _pipeline(spec, numeric, categorical, seed)
    direct.fit(
        train[required],
        train["actual"],
        model__sample_weight=train["target_identified_records"].astype(float),
    )
    direct_prediction = direct.predict(test[required])
    residual_train = train.dropna(subset=["participation_same_type"]).copy()
    residual = _pipeline(spec, numeric, categorical, seed)
    residual.fit(
        residual_train[required],
        residual_train["actual"] - residual_train["participation_same_type"],
        model__sample_weight=residual_train["target_identified_records"].astype(float),
    )
    residual_prediction = residual.predict(test[required])
    baseline = test["participation_same_type"].to_numpy(dtype=float)
    raw = np.where(
        np.isfinite(baseline),
        baseline + float(spec["residual_shrinkage"]) * residual_prediction,
        direct_prediction,
    )
    return np.clip(raw, 0.0, 1.0), residual_prediction


def run_feature_ablation(
    project_root: Path, mart: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    config = _load_yaml(project_root / "configs/feature_ablation.yaml")
    modeling = _load_yaml(project_root / "configs/modeling.yaml")
    spec = modeling["models"][config["base_model_spec"]]
    seed = int(config["random_seed"])
    shift = pd.read_csv(project_root / "artifacts/tables/national_shift_estimates.csv").set_index(
        "target_year"
    )["national_shift_correction"]
    frozen = pd.read_csv(project_root / "artifacts/tables/backtest_metrics.csv")
    frozen = frozen[frozen["scenario"].eq("stable_plus_lineage")].set_index("target_year")
    prediction_rows = []
    metric_rows = []
    registry_rows = []
    for group_name, group_config in config["feature_groups"].items():
        numeric, categorical = _resolve_feature_group(config, group_name)
        required = numeric + categorical
        missing = set(required) - set(mart.columns)
        if missing:
            raise ValueError(f"Variables ausentes para {group_name}: {sorted(missing)}")
        is_eceg = str(group_config["availability"]).startswith("eceg_")
        targets = config["eceg_allowed_targets"] if is_eceg else config["strict_targets"]
        for target_year in targets:
            train = mart[
                mart["target_year"].lt(target_year) & mart["actual"].notna()
            ].copy()
            test = mart[mart["target_year"].eq(target_year)].copy()
            if is_eceg and target_year != 2024:
                raise ValueError("ECEG sólo puede evaluarse en el origen 2024")
            prediction, residual_prediction = _predict_group(
                train, test, numeric, categorical, spec, seed
            )
            correction = float(shift.get(target_year, 0.0))
            corrected = np.clip(prediction + correction, 0.0, 1.0)
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
            predicted["feature_group"] = group_name
            predicted["model_prediction_before_national_shift"] = prediction
            predicted["predicted_residual_unshrunk"] = residual_prediction
            predicted["national_shift_correction"] = correction
            predicted["prediction"] = corrected
            prediction_rows.append(predicted)
            valid = predicted.dropna(subset=["actual", "prediction"]).copy()
            weights = valid["target_identified_records"].astype(float)
            error = valid["prediction"] - valid["actual"]
            baseline_mae = float(frozen.loc[target_year, "identified_weighted_mae"])
            weighted_mae = float(np.average(error.abs(), weights=weights))
            metric_rows.append(
                {
                    "target_year": int(target_year),
                    "feature_group": group_name,
                    "availability": group_config["availability"],
                    "evaluation_units": len(valid),
                    "baseline_model": "lag_same_type_stable_plus_official_lineage",
                    "baseline_weighted_mae": baseline_mae,
                    "identified_weighted_mae": weighted_mae,
                    "mae_change_vs_baseline": weighted_mae - baseline_mae,
                    "weighted_bias": float(np.average(error, weights=weights)),
                    "mae": float(error.abs().mean()),
                    "share_within_5pp": float(error.abs().le(0.05).mean()),
                    "national_shift_correction": correction,
                }
            )
            registry_rows.append(
                {
                    "target_year": int(target_year),
                    "feature_group": group_name,
                    "availability": group_config["availability"],
                    "training_target_years": "|".join(
                        map(str, sorted(int(year) for year in train["target_year"].unique()))
                    ),
                    "training_units": len(train),
                    "numeric_features": "|".join(numeric),
                    "categorical_features": "|".join(categorical),
                    "numeric_feature_count": len(numeric),
                    "categorical_feature_count": len(categorical),
                    "model_family": "HistGradientBoostingRegressor residual correction",
                    "random_seed": seed,
                }
            )
    predictions = pd.concat(prediction_rows, ignore_index=True)
    metrics = pd.DataFrame(metric_rows).sort_values(["target_year", "identified_weighted_mae"])
    registry = pd.DataFrame(registry_rows)
    output = project_root / "artifacts/tables"
    predictions.to_parquet(output / "feature_ablation_predictions.parquet", index=False)
    metrics.to_csv(output / "feature_ablation_metrics.csv", index=False)
    registry.to_csv(output / "feature_ablation_registry.csv", index=False)
    return predictions, metrics, registry


def write_feature_ablation_decision(
    project_root: Path, metrics: pd.DataFrame
) -> dict[str, Any]:
    config = _load_yaml(project_root / "configs/feature_ablation.yaml")
    current_group = str(config["current_feature_group"])
    primary_year = int(config["primary_target_year"])
    strict = metrics[metrics["availability"].eq("strict_all_targets")].copy()
    primary = strict[strict["target_year"].eq(primary_year)].sort_values(
        "identified_weighted_mae"
    )
    best_strict = str(primary.iloc[0]["feature_group"])
    current_primary = primary[primary["feature_group"].eq(current_group)].iloc[0]
    best_primary = primary.iloc[0]
    max_deterioration = float(config["maximum_other_fold_weighted_mae_deterioration"])
    robustness = []
    for year in config["strict_targets"]:
        if int(year) == primary_year:
            continue
        best_row = strict[
            strict["target_year"].eq(year) & strict["feature_group"].eq(best_strict)
        ].iloc[0]
        current_row = strict[
            strict["target_year"].eq(year) & strict["feature_group"].eq(current_group)
        ].iloc[0]
        change = float(
            best_row["identified_weighted_mae"] - current_row["identified_weighted_mae"]
        )
        robustness.append(
            {
                "target_year": int(year),
                "mae_change_vs_current_features": change,
                "passes": change <= max_deterioration,
            }
        )
    strict_promoted = bool(
        float(best_primary["identified_weighted_mae"])
        < float(current_primary["identified_weighted_mae"])
        and all(row["passes"] for row in robustness)
    )
    eceg = metrics[
        metrics["target_year"].eq(2024)
        & metrics["availability"].str.startswith("eceg_")
    ].sort_values("identified_weighted_mae")
    strict_2024 = strict[
        strict["target_year"].eq(2024) & strict["feature_group"].eq(best_strict)
    ].iloc[0]
    best_eceg = eceg.iloc[0]
    eceg_improvement = float(
        strict_2024["identified_weighted_mae"] - best_eceg["identified_weighted_mae"]
    )
    eceg_promoted = eceg_improvement >= float(
        config["minimum_eceg_2024_improvement_to_promote"]
    )
    decision = {
        "baseline_model": "lag_same_type_stable_plus_official_lineage",
        "model_family_held_constant": "HistGradientBoostingRegressor residual correction",
        "current_feature_group": current_group,
        "best_strict_feature_group": best_strict,
        "current_primary_weighted_mae": float(current_primary["identified_weighted_mae"]),
        "best_primary_weighted_mae": float(best_primary["identified_weighted_mae"]),
        "strict_feature_group_promoted": strict_promoted,
        "strict_robustness": robustness,
        "best_eceg_feature_group_2024": str(best_eceg["feature_group"]),
        "best_eceg_2024_weighted_mae": float(best_eceg["identified_weighted_mae"]),
        "best_strict_2024_weighted_mae": float(strict_2024["identified_weighted_mae"]),
        "eceg_2024_improvement": eceg_improvement,
        "minimum_eceg_improvement_to_promote": float(
            config["minimum_eceg_2024_improvement_to_promote"]
        ),
        "eceg_promoted": bool(eceg_promoted),
        "selected_feature_group_for_2027": (
            str(best_eceg["feature_group"])
            if eceg_promoted
            else (best_strict if strict_promoted else current_group)
        ),
        "limitations": [
            "ECEG 2020 is only strictly available for the 2024 forecast origin and later.",
            "ECEG promotion relies on one historical target year.",
            "Territorial context uses entity and national aggregates, not polygon adjacency.",
        ],
    }
    (project_root / "artifacts/feature_ablation_decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return decision
