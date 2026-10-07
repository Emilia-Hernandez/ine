from __future__ import annotations

import html
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import (
    adjusted_rand_score,
    average_precision_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
    silhouette_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from radar27.modeling.feature_enrichment import _resolve_feature_group
from radar27.modeling.feature_models import COUNT_COLUMNS, _load_yaml, _target_units

GROUPS = {
    "sex": ["female", "male"],
    "age": ["age_18_29", "age_30_44", "age_45_64", "age_65_plus"],
}


def _weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    valid = values.notna() & weights.notna() & weights.gt(0)
    if not valid.any():
        return math.nan
    return float(np.average(values[valid].astype(float), weights=weights[valid].astype(float)))


def _classifier_pipeline(
    numeric: list[str], categorical: list[str], spec: dict[str, Any], seed: int
) -> Pipeline:
    preprocess = ColumnTransformer(
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
    classifier = HistGradientBoostingClassifier(
        learning_rate=float(spec["learning_rate"]),
        max_iter=int(spec["max_iter"]),
        max_leaf_nodes=int(spec["max_leaf_nodes"]),
        min_samples_leaf=int(spec["min_samples_leaf"]),
        l2_regularization=float(spec["l2_regularization"]),
        random_state=seed,
    )
    return Pipeline([("preprocess", preprocess), ("model", classifier)])


def _top_share_metrics(
    actual: np.ndarray, probability: np.ndarray, weights: np.ndarray, share: float
) -> tuple[float, float]:
    order = np.argsort(-probability, kind="stable")
    ordered_weight = weights[order]
    selected = np.cumsum(ordered_weight) <= share * ordered_weight.sum()
    if not selected.any() and len(selected):
        selected[0] = True
    chosen = order[selected]
    positive_weight = weights * actual
    captured = (
        float(positive_weight[chosen].sum() / positive_weight.sum())
        if positive_weight.sum()
        else math.nan
    )
    precision = (
        float(positive_weight[chosen].sum() / weights[chosen].sum())
        if weights[chosen].sum()
        else math.nan
    )
    return precision, captured


def _risk_metric_row(
    frame: pd.DataFrame,
    feature_group: str,
    threshold: float,
    target_year: int,
    probability_column: str,
    top_share: float,
) -> dict[str, Any]:
    valid = frame.dropna(subset=["risk_actual", probability_column]).copy()
    y = valid["risk_actual"].astype(int).to_numpy()
    p = valid[probability_column].clip(1e-6, 1 - 1e-6).to_numpy(dtype=float)
    w = valid["target_identified_records"].to_numpy(dtype=float)
    precision, capture = _top_share_metrics(y, p, w, top_share)
    return {
        "feature_group": feature_group,
        "decline_threshold": threshold,
        "target_year": target_year,
        "probability_version": probability_column.removeprefix("probability_"),
        "evaluation_units": len(valid),
        "positive_rate_weighted": float(np.average(y, weights=w)),
        "weighted_brier": float(brier_score_loss(y, p, sample_weight=w)),
        "weighted_log_loss": float(log_loss(y, p, sample_weight=w, labels=[0, 1])),
        "weighted_roc_auc": float(roc_auc_score(y, p, sample_weight=w)),
        "weighted_average_precision": float(average_precision_score(y, p, sample_weight=w)),
        f"weighted_precision_top_{int(top_share * 100)}pct_electorate": precision,
        f"positive_volume_captured_top_{int(top_share * 100)}pct_electorate": capture,
    }


def _fit_isotonic(frame: pd.DataFrame) -> IsotonicRegression | None:
    required = {"risk_actual", "probability_raw", "target_identified_records"}
    if frame.empty or not required.issubset(frame.columns):
        return None
    valid = frame.dropna(subset=["risk_actual", "probability_raw", "target_identified_records"])
    if len(valid) < 100 or valid["risk_actual"].nunique() < 2:
        return None
    model = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    model.fit(
        valid["probability_raw"],
        valid["risk_actual"],
        sample_weight=valid["target_identified_records"],
    )
    return model


def evaluate_risk_models(
    project_root: Path, config: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, str, dict[float, IsotonicRegression]]:
    mart = pd.read_parquet(project_root / "artifacts/tables/feature_ablation_mart.parquet")
    mart = mart[
        mart["target_year"].isin(config["training_target_years"])
        & mart["actual"].notna()
        & mart["participation_same_type"].notna()
    ].copy()
    mart["decline_pp"] = mart["participation_same_type"] - mart["actual"]
    feature_config = _load_yaml(project_root / config["feature_config"])
    thresholds = [float(value) for value in config["decline_thresholds"]]
    targets = [int(value) for value in config["strict_evaluation_targets"]]
    seed = int(config["random_seed"])
    spec = config["risk_classifier"]
    top_share = float(config["ranking"]["top_share_for_validation"])
    all_predictions: list[pd.DataFrame] = []
    all_metrics: list[dict[str, Any]] = []

    for feature_group in config["candidate_feature_groups"]:
        numeric, categorical = _resolve_feature_group(feature_config, feature_group)
        required = numeric + categorical
        missing = set(required) - set(mart.columns)
        if missing:
            raise ValueError(f"Features ausentes para riesgo {feature_group}: {sorted(missing)}")
        for threshold in thresholds:
            earlier_oof: list[pd.DataFrame] = []
            for target_year in targets:
                train = mart[mart["target_year"].lt(target_year)].copy()
                test = mart[mart["target_year"].eq(target_year)].copy()
                y_train = train["decline_pp"].ge(threshold).astype(int)
                if y_train.nunique() < 2:
                    raise ValueError(
                        f"La clase de riesgo {threshold:.3f} no varía antes de {target_year}"
                    )
                pipeline = _classifier_pipeline(numeric, categorical, spec, seed)
                pipeline.fit(
                    train[required],
                    y_train,
                    model__sample_weight=train["target_identified_records"].astype(float),
                )
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
                        "decline_pp",
                    ]
                ].copy()
                predicted["feature_group"] = feature_group
                predicted["decline_threshold"] = threshold
                predicted["risk_actual"] = predicted["decline_pp"].ge(threshold).astype(int)
                predicted["probability_raw"] = pipeline.predict_proba(test[required])[:, 1]
                calibration_training = (
                    pd.concat(earlier_oof, ignore_index=True) if earlier_oof else pd.DataFrame()
                )
                calibrator = _fit_isotonic(calibration_training)
                if calibrator is None:
                    predicted["probability_time_calibrated"] = predicted["probability_raw"]
                    predicted["calibration_source_years"] = "none_raw_probability"
                else:
                    predicted["probability_time_calibrated"] = calibrator.predict(
                        predicted["probability_raw"]
                    )
                    years = sorted(
                        int(year) for year in calibration_training["target_year"].unique()
                    )
                    predicted["calibration_source_years"] = "|".join(map(str, years))
                earlier_oof.append(predicted)
                all_predictions.append(predicted)
                for probability_column in ["probability_raw", "probability_time_calibrated"]:
                    all_metrics.append(
                        _risk_metric_row(
                            predicted,
                            feature_group,
                            threshold,
                            target_year,
                            probability_column,
                            top_share,
                        )
                    )

    predictions = pd.concat(all_predictions, ignore_index=True)
    metrics = pd.DataFrame(all_metrics)
    primary = float(config["primary_decline_threshold"])
    selection = metrics[
        metrics["decline_threshold"].eq(primary)
        & metrics["probability_version"].eq("time_calibrated")
    ]
    comparison = (
        selection.groupby("feature_group", as_index=False)
        .agg(
            mean_weighted_brier=("weighted_brier", "mean"),
            primary_2021_weighted_brier=(
                "weighted_brier",
                lambda values: float(
                    values.loc[selection.loc[values.index, "target_year"].eq(2021)].iloc[0]
                ),
            ),
            mean_weighted_average_precision=("weighted_average_precision", "mean"),
        )
        .sort_values(
            ["primary_2021_weighted_brier", "mean_weighted_brier"],
            ascending=[True, True],
        )
    )
    selected_group = str(comparison.iloc[0]["feature_group"])
    selected_predictions = predictions[predictions["feature_group"].eq(selected_group)].copy()
    final_calibrators: dict[float, IsotonicRegression] = {}
    final_calibration_year = int(spec["final_calibration_target_year"])
    for threshold in thresholds:
        threshold_oof = selected_predictions[
            selected_predictions["decline_threshold"].eq(threshold)
            & selected_predictions["target_year"].eq(final_calibration_year)
        ]
        calibrator = _fit_isotonic(threshold_oof)
        if calibrator is None:
            raise ValueError(f"No fue posible calibrar el umbral {threshold:.3f}")
        final_calibrators[threshold] = calibrator

    outputs = config["outputs"]
    predictions.to_parquet(project_root / outputs["historical_predictions"], index=False)
    metrics.to_csv(project_root / outputs["risk_metrics"], index=False)
    comparison.to_csv(
        project_root / "artifacts/tables/turnout_decline_risk_model_selection.csv", index=False
    )
    calibration = calibration_table(selected_predictions)
    calibration.to_csv(project_root / outputs["calibration"], index=False)
    return predictions, metrics, comparison, selected_group, final_calibrators


def calibration_table(predictions: pd.DataFrame, bins: int = 10) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (threshold, year), frame in predictions.groupby(
        ["decline_threshold", "target_year"], observed=True
    ):
        ranked = frame.copy()
        ranked["calibration_bin"] = pd.qcut(
            ranked["probability_time_calibrated"].rank(method="first"),
            q=min(bins, len(ranked)),
            labels=False,
            duplicates="drop",
        )
        for bin_id, part in ranked.groupby("calibration_bin", observed=True):
            weights = part["target_identified_records"].astype(float)
            rows.append(
                {
                    "decline_threshold": float(threshold),
                    "target_year": int(year),
                    "calibration_bin": int(bin_id) + 1,
                    "evaluation_units": len(part),
                    "identified_records": float(weights.sum()),
                    "mean_probability": _weighted_mean(
                        part["probability_time_calibrated"], weights
                    ),
                    "observed_rate": _weighted_mean(part["risk_actual"], weights),
                }
            )
    return pd.DataFrame(rows)


def fit_risk_forecast(
    project_root: Path,
    config: dict[str, Any],
    selected_group: str,
    calibrators: dict[float, IsotonicRegression],
) -> pd.DataFrame:
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
    seed = int(config["random_seed"])
    spec = config["risk_classifier"]
    result = forecast[
        [
            "evaluation_unit_id",
            "entity_id",
            "geography_confidence_class",
            "target_sections_represented",
            "current_nominal_list",
            "participation_same_type",
            "experimental_prediction",
        ]
    ].copy()
    for threshold in [float(value) for value in config["decline_thresholds"]]:
        pipeline = _classifier_pipeline(numeric, categorical, spec, seed)
        pipeline.fit(
            training[required],
            training["decline_pp"].ge(threshold).astype(int),
            model__sample_weight=training["target_identified_records"].astype(float),
        )
        raw = pipeline.predict_proba(forecast[required])[:, 1]
        suffix = f"{round(threshold * 100):02d}pp"
        result[f"risk_probability_raw_{suffix}"] = raw
        result[f"risk_probability_{suffix}"] = calibrators[threshold].predict(raw)

    calibrated_columns = [
        f"risk_probability_{round(value * 100):02d}pp" for value in config["decline_thresholds"]
    ]
    calibrated = result[calibrated_columns].to_numpy(dtype=float)
    calibrated[:, 1] = np.minimum(calibrated[:, 0], calibrated[:, 1])
    calibrated[:, 2] = np.minimum(calibrated[:, 1], calibrated[:, 2])
    result[calibrated_columns] = calibrated
    result["predicted_decline_pp"] = (
        result["participation_same_type"] - result["experimental_prediction"]
    )
    result["predicted_additional_nonvoters"] = result["current_nominal_list"] * result[
        "predicted_decline_pp"
    ].clip(lower=0)
    result["risk_model_feature_group"] = selected_group
    result["risk_probability_calibration"] = "weighted_isotonic_strict_oof_midterm_2021_analogue"
    result.to_parquet(project_root / config["outputs"]["model_unit_file"], index=False)
    return result


def _aggregate_counts(
    members: pd.DataFrame, section_year: pd.DataFrame, years: list[int]
) -> pd.DataFrame:
    merged = members.merge(
        section_year[section_year["election_year"].isin(years)],
        on="section_key_observed",
        how="left",
        validate="many_to_many",
    )
    return merged.groupby(["evaluation_unit_id", "election_year"], as_index=False)[
        COUNT_COLUMNS
    ].sum(min_count=1)


def _smoothed_partition(
    counts: pd.DataFrame,
    unit_entities: pd.DataFrame,
    partition: str,
    strength: float,
) -> pd.DataFrame:
    groups = GROUPS[partition]
    long_rows: list[pd.DataFrame] = []
    base = counts.merge(unit_entities, on="evaluation_unit_id", how="left", validate="many_to_one")
    for group in groups:
        part = base[
            [
                "evaluation_unit_id",
                "entity_id",
                "election_year",
                f"{group}_nominal_list",
                f"{group}_voted",
                f"{group}_did_not_vote",
            ]
        ].rename(
            columns={
                f"{group}_nominal_list": "group_nominal_list",
                f"{group}_voted": "group_voted",
                f"{group}_did_not_vote": "group_did_not_vote",
            }
        )
        part["partition"] = partition
        part["group"] = group
        long_rows.append(part)
    long = pd.concat(long_rows, ignore_index=True)
    long["group_identified"] = long["group_voted"] + long["group_did_not_vote"]
    priors = long.groupby(["entity_id", "election_year", "partition", "group"], as_index=False).agg(
        entity_voted=("group_voted", "sum"), entity_identified=("group_identified", "sum")
    )
    priors["entity_prior_rate"] = priors["entity_voted"].div(
        priors["entity_identified"].where(priors["entity_identified"].gt(0))
    )
    long = long.merge(
        priors[["entity_id", "election_year", "partition", "group", "entity_prior_rate"]],
        on=["entity_id", "election_year", "partition", "group"],
        how="left",
        validate="many_to_one",
    )
    long["turnout_raw"] = long["group_voted"].div(
        long["group_identified"].where(long["group_identified"].gt(0))
    )
    long["turnout_smoothed"] = (long["group_voted"] + strength * long["entity_prior_rate"]).div(
        long["group_identified"] + strength
    )
    totals = (
        long.groupby(["evaluation_unit_id", "election_year", "partition"], as_index=False)[
            "group_nominal_list"
        ]
        .sum(min_count=1)
        .rename(columns={"group_nominal_list": "partition_nominal_list"})
    )
    long = long.merge(
        totals,
        on=["evaluation_unit_id", "election_year", "partition"],
        how="left",
        validate="many_to_one",
    )
    long["group_share"] = long["group_nominal_list"].div(
        long["partition_nominal_list"].where(long["partition_nominal_list"].gt(0))
    )
    long["prior_strength"] = strength
    return long


def build_historical_decomposition(
    project_root: Path, config: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    evaluation = _load_yaml(project_root / "configs/evaluation.yaml")
    section_year = pd.read_parquet(
        project_root / "artifacts/tables/section_year_behavioral_features.parquet"
    )
    classes = pd.read_parquet(
        project_root / "artifacts/tables/section_confidence_by_election.parquet"
    )
    components = pd.read_parquet(
        project_root / "artifacts/tables/lineage_components_by_election.parquet"
    )
    strength = float(config["empirical_bayes"]["prior_strength_identified_records"])
    outputs: list[pd.DataFrame] = []
    for fold in evaluation["folds"]:
        target_year = int(fold["target_year"])
        source_year = int(fold["feature_year"])
        target = classes[classes["target_year"].eq(target_year)].copy()
        membership = components[components["target_year"].eq(target_year)].copy()
        units, members = _target_units(target, membership)
        counts = _aggregate_counts(members, section_year, [source_year, target_year])
        unit_entities = units[["evaluation_unit_id", "entity_id", "geography_confidence_class"]]
        for partition in GROUPS:
            long = _smoothed_partition(counts, unit_entities, partition, strength)
            keys = ["evaluation_unit_id", "entity_id", "partition", "group"]
            source = long[long["election_year"].eq(source_year)][
                keys
                + [
                    "group_nominal_list",
                    "group_identified",
                    "group_share",
                    "turnout_raw",
                    "turnout_smoothed",
                    "entity_prior_rate",
                ]
            ].rename(
                columns={
                    "group_nominal_list": "source_group_nominal_list",
                    "group_identified": "source_group_identified",
                    "group_share": "source_group_share",
                    "turnout_raw": "source_turnout_raw",
                    "turnout_smoothed": "source_turnout_smoothed",
                    "entity_prior_rate": "source_entity_prior_rate",
                }
            )
            target_long = long[long["election_year"].eq(target_year)][
                keys
                + [
                    "group_nominal_list",
                    "group_identified",
                    "group_share",
                    "turnout_raw",
                    "turnout_smoothed",
                    "entity_prior_rate",
                ]
            ].rename(
                columns={
                    "group_nominal_list": "target_group_nominal_list",
                    "group_identified": "target_group_identified",
                    "group_share": "target_group_share",
                    "turnout_raw": "target_turnout_raw",
                    "turnout_smoothed": "target_turnout_smoothed",
                    "entity_prior_rate": "target_entity_prior_rate",
                }
            )
            change = source.merge(target_long, on=keys, how="inner", validate="one_to_one")
            change["source_year"] = source_year
            change["target_year"] = target_year
            change["geography_confidence_class"] = change["evaluation_unit_id"].map(
                unit_entities.set_index("evaluation_unit_id")["geography_confidence_class"]
            )
            change["turnout_change"] = (
                change["target_turnout_smoothed"] - change["source_turnout_smoothed"]
            )
            change["rate_effect"] = (
                0.5
                * (change["source_group_share"] + change["target_group_share"])
                * change["turnout_change"]
            )
            change["composition_effect"] = (
                0.5
                * (change["source_turnout_smoothed"] + change["target_turnout_smoothed"])
                * (change["target_group_share"] - change["source_group_share"])
            )
            change["total_contribution"] = change["rate_effect"] + change["composition_effect"]
            change["prior_strength"] = strength
            outputs.append(change)
    decomposition = pd.concat(outputs, ignore_index=True)
    summary = (
        decomposition.groupby(["source_year", "target_year", "partition", "group"], as_index=False)
        .apply(
            lambda frame: pd.Series(
                {
                    "evaluation_units": len(frame),
                    "identified_records": float(frame["target_group_identified"].sum()),
                    "mean_turnout_change": _weighted_mean(
                        frame["turnout_change"], frame["target_group_identified"]
                    ),
                    "mean_rate_effect": _weighted_mean(
                        frame["rate_effect"], frame["target_group_identified"]
                    ),
                    "mean_composition_effect": _weighted_mean(
                        frame["composition_effect"], frame["target_group_identified"]
                    ),
                }
            ),
            include_groups=False,
        )
        .reset_index(drop=True)
    )
    decomposition.to_parquet(project_root / config["outputs"]["decomposition"], index=False)
    summary.to_csv(project_root / config["outputs"]["decomposition_summary"], index=False)
    _decomposition_sensitivity(decomposition, config).to_csv(
        project_root / config["outputs"]["decomposition_sensitivity"], index=False
    )
    return decomposition, summary


def _decomposition_sensitivity(decomposition: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    strengths = [float(value) for value in config["empirical_bayes"]["sensitivity_strengths"]]
    for strength in strengths:
        frame = decomposition.copy()
        frame["source_rate_sensitivity"] = (
            frame["source_turnout_raw"] * frame["source_group_identified"]
            + strength * frame["source_entity_prior_rate"]
        ).div(frame["source_group_identified"] + strength)
        frame["target_rate_sensitivity"] = (
            frame["target_turnout_raw"] * frame["target_group_identified"]
            + strength * frame["target_entity_prior_rate"]
        ).div(frame["target_group_identified"] + strength)
        frame["rate_effect_sensitivity"] = (
            0.5
            * (frame["source_group_share"] + frame["target_group_share"])
            * (frame["target_rate_sensitivity"] - frame["source_rate_sensitivity"])
        )
        for keys, part in frame.groupby(
            ["source_year", "target_year", "partition", "group"], observed=True
        ):
            source_year, target_year, partition, group = keys
            rows.append(
                {
                    "prior_strength": strength,
                    "source_year": int(source_year),
                    "target_year": int(target_year),
                    "partition": partition,
                    "group": group,
                    "weighted_mean_rate_effect": _weighted_mean(
                        part["rate_effect_sensitivity"], part["target_group_identified"]
                    ),
                }
            )
    return pd.DataFrame(rows)


def build_current_demographic_profiles(project_root: Path, config: dict[str, Any]) -> pd.DataFrame:
    section_year = pd.read_parquet(
        project_root / "artifacts/tables/section_year_behavioral_features.parquet"
    )
    classes = pd.read_parquet(
        project_root / "artifacts/tables/section_confidence_by_election.parquet"
    )
    components = pd.read_parquet(
        project_root / "artifacts/tables/lineage_components_by_election.parquet"
    )
    target = classes[classes["target_year"].eq(2024)].copy()
    membership = components[components["target_year"].eq(2024)].copy()
    units, members = _target_units(target, membership)
    counts = _aggregate_counts(members, section_year, [2015, 2021, 2024])
    entities = units[["evaluation_unit_id", "entity_id", "geography_confidence_class"]]
    strength = float(config["empirical_bayes"]["prior_strength_identified_records"])
    result = entities.copy()
    for partition, partition_groups in GROUPS.items():
        long = _smoothed_partition(counts, entities, partition, strength)
        for group in partition_groups:
            group_data = long[long["group"].eq(group)]
            latest = group_data[group_data["election_year"].eq(2024)][
                ["evaluation_unit_id", "turnout_smoothed", "group_share", "group_identified"]
            ].rename(
                columns={
                    "turnout_smoothed": f"{group}_turnout_2024",
                    "group_share": f"{group}_share_2024",
                    "group_identified": f"{group}_identified_2024",
                }
            )
            earlier = group_data[group_data["election_year"].eq(2015)][
                ["evaluation_unit_id", "turnout_smoothed"]
            ].rename(columns={"turnout_smoothed": "turnout_2015"})
            recent = group_data[group_data["election_year"].eq(2021)][
                ["evaluation_unit_id", "turnout_smoothed"]
            ].rename(columns={"turnout_smoothed": "turnout_2021"})
            change = earlier.merge(recent, on="evaluation_unit_id", how="outer")
            change[f"{group}_turnout_change_2015_2021"] = (
                change["turnout_2021"] - change["turnout_2015"]
            )
            result = result.merge(latest, on="evaluation_unit_id", how="left")
            result = result.merge(
                change[["evaluation_unit_id", f"{group}_turnout_change_2015_2021"]],
                on="evaluation_unit_id",
                how="left",
            )
    overall = counts[counts["election_year"].eq(2024)][
        ["evaluation_unit_id", "voted", "did_not_vote"]
    ].copy()
    overall["overall_turnout_2024"] = overall["voted"].div(
        (overall["voted"] + overall["did_not_vote"]).where(
            (overall["voted"] + overall["did_not_vote"]).gt(0)
        )
    )
    result = result.merge(
        overall[["evaluation_unit_id", "overall_turnout_2024"]],
        on="evaluation_unit_id",
        how="left",
    )
    result["female_minus_male_turnout_2024"] = (
        result["female_turnout_2024"] - result["male_turnout_2024"]
    )
    for group in GROUPS["age"]:
        result[f"{group}_minus_overall_2024"] = (
            result[f"{group}_turnout_2024"] - result["overall_turnout_2024"]
        )
    result.to_parquet(
        project_root / "artifacts/tables/model_unit_demographic_profiles_2027.parquet",
        index=False,
    )
    return result


def cluster_profiles(
    demographic: pd.DataFrame,
    risk_units: pd.DataFrame,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Pipeline]:
    frame = risk_units.merge(
        demographic, on=["evaluation_unit_id", "entity_id", "geography_confidence_class"]
    )
    features = list(config["profiles"]["features"])
    risk_column = "risk_probability_02pp"
    high_share = 1.0 - float(config["profiles"]["high_risk_quantile"])
    high_count = max(1, math.ceil(high_share * len(frame)))
    high = (
        frame.sort_values(
            [risk_column, "predicted_additional_nonvoters", "evaluation_unit_id"],
            ascending=[False, False, True],
        )
        .head(high_count)
        .copy()
    )
    cutoff = float(high[risk_column].min())
    imputer = SimpleImputer(strategy="median", add_indicator=False)
    scaler = StandardScaler()
    matrix = scaler.fit_transform(imputer.fit_transform(high[features]))
    seed = int(config["random_seed"])
    sample_size = min(int(config["profiles"]["silhouette_sample_size"]), len(high))
    rng = np.random.default_rng(seed)
    sample_index = rng.choice(len(high), size=sample_size, replace=False)
    validation_rows: list[dict[str, Any]] = []
    fitted: dict[int, KMeans] = {}
    for clusters in [int(value) for value in config["profiles"]["candidate_clusters"]]:
        base = KMeans(n_clusters=clusters, n_init=20, random_state=seed)
        base_labels = base.fit_predict(matrix, sample_weight=high["current_nominal_list"])
        fitted[clusters] = base
        silhouette = float(silhouette_score(matrix[sample_index], base_labels[sample_index]))
        stabilities = []
        for repeat in range(int(config["profiles"]["stability_repeats"])):
            repeat_rng = np.random.default_rng(seed + repeat + 1)
            keep = repeat_rng.random(len(high)) < float(config["profiles"]["subsample_fraction"])
            challenger = KMeans(n_clusters=clusters, n_init=20, random_state=seed + repeat + 1)
            challenger.fit(matrix[keep], sample_weight=high.loc[keep, "current_nominal_list"])
            stabilities.append(adjusted_rand_score(base_labels, challenger.predict(matrix)))
        validation_rows.append(
            {
                "clusters": clusters,
                "high_risk_units": len(high),
                "risk_probability_cutoff": float(cutoff),
                "silhouette": silhouette,
                "mean_adjusted_rand": float(np.mean(stabilities)),
                "minimum_adjusted_rand": float(np.min(stabilities)),
            }
        )
    validation = pd.DataFrame(validation_rows)
    stable = validation[
        validation["mean_adjusted_rand"].ge(float(config["profiles"]["minimum_mean_adjusted_rand"]))
    ]
    selection_pool = stable if not stable.empty else validation
    selected_k = int(selection_pool.sort_values("silhouette", ascending=False).iloc[0]["clusters"])
    validation["selected"] = validation["clusters"].eq(selected_k)
    model = fitted[selected_k]
    all_matrix = scaler.transform(imputer.transform(frame[features]))
    frame["profile_cluster"] = model.predict(all_matrix) + 1
    centroids = pd.DataFrame(scaler.inverse_transform(model.cluster_centers_), columns=features)
    centroids["profile_cluster"] = np.arange(1, selected_k + 1)
    names = _profile_names(centroids)
    frame["profile_name"] = frame["profile_cluster"].map(names)
    summary_rows = []
    for cluster, part in frame.groupby("profile_cluster", observed=True):
        weights = part["current_nominal_list"].astype(float)
        row: dict[str, Any] = {
            "profile_cluster": int(cluster),
            "profile_name": names[int(cluster)],
            "model_units": len(part),
            "sections_represented": int(part["target_sections_represented"].sum()),
            "current_nominal_list": float(weights.sum()),
            "mean_risk_probability_02pp": _weighted_mean(part[risk_column], weights),
            "predicted_additional_nonvoters": float(part["predicted_additional_nonvoters"].sum()),
        }
        for feature in features:
            row[feature] = _weighted_mean(part[feature], weights)
        summary_rows.append(row)
    summary = pd.DataFrame(summary_rows).sort_values("profile_cluster")
    wrapper = Pipeline([("impute", imputer), ("scale", scaler), ("kmeans", model)])
    return frame, validation, summary, wrapper


def _profile_names(centroids: pd.DataFrame) -> dict[int, str]:
    names: dict[int, str] = {}
    change_columns = [
        "female_turnout_change_2015_2021",
        "male_turnout_change_2015_2021",
        "age_18_29_turnout_change_2015_2021",
        "age_30_44_turnout_change_2015_2021",
        "age_45_64_turnout_change_2015_2021",
        "age_65_plus_turnout_change_2015_2021",
    ]
    change_mean = centroids[change_columns].mean(axis=1)
    level_rank = centroids["overall_turnout_2024"].rank(method="first")
    change_rank = change_mean.rank(method="first")
    count = len(centroids)
    for _, row in centroids.iterrows():
        gaps = {
            "participación joven baja": row["age_18_29_minus_overall_2024"],
            "participación de 30–44 baja": row["age_30_44_minus_overall_2024"],
            "participación de 45–64 baja": row["age_45_64_minus_overall_2024"],
            "participación de 65+ baja": row["age_65_plus_minus_overall_2024"],
        }
        age_trait = min(gaps, key=gaps.get)
        sex_gap = float(row["female_minus_male_turnout_2024"])
        if sex_gap > 0.025:
            sex_trait = "brecha desfavorable a hombres"
        elif sex_gap < -0.025:
            sex_trait = "brecha desfavorable a mujeres"
        else:
            sex_trait = "brecha por sexo reducida"
        cluster = int(row["profile_cluster"])
        index = row.name
        level = (
            "base baja"
            if level_rank.loc[index] <= math.ceil(count / 3)
            else "base alta"
            if level_rank.loc[index] > math.ceil(2 * count / 3)
            else "base media"
        )
        change = (
            "cambio 2015–2021 débil o negativo"
            if change_rank.loc[index] <= math.ceil(count / 3)
            else "aumento 2015–2021 fuerte"
            if change_rank.loc[index] > math.ceil(2 * count / 3)
            else "aumento 2015–2021 intermedio"
        )
        names[cluster] = f"Perfil {cluster}: {level}; {change}; {age_trait}; {sex_trait}"
    return names


def expand_section_profiles(
    project_root: Path,
    config: dict[str, Any],
    clustered_units: pd.DataFrame,
    profile_pipeline: Pipeline,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    sections = pd.read_parquet(
        project_root / "artifacts/tables/forecast_2027_section_predictions.parquet"
    )
    nodes = pd.read_parquet(project_root / "artifacts/graphs/temporal/2024/nodes.parquet")
    features = list(config["profiles"]["features"])
    unit_columns = [
        "evaluation_unit_id",
        "risk_probability_00pp",
        "risk_probability_02pp",
        "risk_probability_05pp",
        "predicted_decline_pp",
        "predicted_additional_nonvoters",
        "profile_cluster",
        "profile_name",
        *features,
    ]
    result = sections.merge(
        clustered_units[unit_columns],
        on="evaluation_unit_id",
        how="left",
        validate="many_to_one",
    )
    ab = result["geography_confidence_class"].isin(["A", "B"])
    result["profile_data_source"] = np.where(
        ab, "direct_age_sex_counts_aggregated_to_model_unit", "entity_ab_reference_fallback"
    )
    result["risk_probability_source"] = np.where(
        ab, "calibrated_ab_classifier", "entity_ab_reference_fallback"
    )
    fallback_columns = [
        "risk_probability_00pp",
        "risk_probability_02pp",
        "risk_probability_05pp",
        *features,
    ]
    entity_reference = (
        result[ab]
        .groupby("entity_id", as_index=False)
        .apply(
            lambda part: pd.Series(
                {
                    column: _weighted_mean(part[column], part["nominal_list"])
                    for column in fallback_columns
                }
            ),
            include_groups=False,
        )
        .reset_index(drop=True)
    )
    missing = ~ab
    fallback = result.loc[missing, ["entity_id"]].merge(
        entity_reference, on="entity_id", how="left", validate="many_to_one"
    )
    for column in fallback_columns:
        result.loc[missing, column] = fallback[column].to_numpy()
    predicted_fallback = profile_pipeline.predict(result.loc[missing, features]) + 1
    cluster_names = clustered_units[["profile_cluster", "profile_name"]].drop_duplicates()
    name_map = cluster_names.set_index("profile_cluster")["profile_name"]
    result.loc[missing, "profile_cluster"] = predicted_fallback
    result.loc[missing, "profile_name"] = pd.Series(predicted_fallback).map(name_map).to_numpy()
    result["predicted_decline_pp"] = (
        result["operational_baseline_prediction"] - result["experimental_prediction"]
    )
    result["predicted_decline_lower_pp"] = (
        result["operational_baseline_prediction"] - result["upper"]
    )
    result["predicted_decline_upper_pp"] = (
        result["operational_baseline_prediction"] - result["lower"]
    )
    result["predicted_additional_nonvoters"] = result["nominal_list"] * result[
        "predicted_decline_pp"
    ].clip(lower=0)
    result["predicted_additional_nonvoters_upper"] = result["nominal_list"] * result[
        "predicted_decline_upper_pp"
    ].clip(lower=0)
    result["risk_percentile"] = result["risk_probability_02pp"].rank(pct=True, method="average")
    result["volume_percentile"] = result["predicted_additional_nonvoters"].rank(
        pct=True, method="average"
    )
    risk_cut = float(config["ranking"]["high_risk_quantile"])
    volume_cut = float(config["ranking"]["high_volume_quantile"])
    high_risk = result["risk_percentile"].ge(risk_cut)
    high_volume = result["volume_percentile"].ge(volume_cut)
    result["priority_tier"] = np.select(
        [high_risk & high_volume, high_volume, high_risk],
        ["1_alto_riesgo_alto_volumen", "2_alto_volumen", "3_alto_riesgo"],
        default="4_resto",
    )
    result = result.merge(
        nodes[["section_key", "centroid_lon", "centroid_lat"]].rename(
            columns={"section_key": "section_key_observed"}
        ),
        on="section_key_observed",
        how="left",
        validate="one_to_one",
    )
    keep = [
        "section_key_observed",
        "entity_id",
        "municipality_key_observed",
        "section_type_code",
        "geography_confidence_class",
        "evaluation_unit_id",
        "nominal_list",
        "operational_baseline_prediction",
        "experimental_prediction",
        "lower",
        "upper",
        "risk_probability_00pp",
        "risk_probability_02pp",
        "risk_probability_05pp",
        "predicted_decline_pp",
        "predicted_decline_lower_pp",
        "predicted_decline_upper_pp",
        "predicted_additional_nonvoters",
        "predicted_additional_nonvoters_upper",
        "risk_percentile",
        "volume_percentile",
        "priority_tier",
        "profile_cluster",
        "profile_name",
        "profile_data_source",
        "risk_probability_source",
        "centroid_lon",
        "centroid_lat",
        *features,
        "forecast_geography_status",
        "prediction_status",
    ]
    result = result[keep].sort_values(
        ["priority_tier", "predicted_additional_nonvoters"], ascending=[True, False]
    )
    municipality = _aggregate_geography(result, "municipality_key_observed")
    entity = _aggregate_geography(result, "entity_id")
    outputs = config["outputs"]
    result.to_parquet(project_root / outputs["section_file"], index=False)
    result.to_csv(project_root / outputs["section_csv"], index=False)
    municipality.to_csv(project_root / outputs["municipality_summary"], index=False)
    entity.to_csv(project_root / outputs["entity_summary"], index=False)
    return result, municipality, entity


def _aggregate_geography(frame: pd.DataFrame, key: str) -> pd.DataFrame:
    rows = []
    for value, part in frame.groupby(key, observed=True):
        weights = part["nominal_list"].astype(float)
        top_profile = part.groupby("profile_name", observed=True)["nominal_list"].sum().idxmax()
        rows.append(
            {
                key: value,
                "sections": len(part),
                "nominal_list": float(weights.sum()),
                "weighted_risk_probability_02pp": _weighted_mean(
                    part["risk_probability_02pp"], weights
                ),
                "predicted_additional_nonvoters": float(
                    part["predicted_additional_nonvoters"].sum()
                ),
                "predicted_additional_nonvoters_upper": float(
                    part["predicted_additional_nonvoters_upper"].sum()
                ),
                "tier_1_sections": int(
                    part["priority_tier"].eq("1_alto_riesgo_alto_volumen").sum()
                ),
                "dominant_profile": top_profile,
                "lower_confidence_cd_sections": int(
                    part["geography_confidence_class"].isin(["C", "D"]).sum()
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("predicted_additional_nonvoters", ascending=False)


def _write_dictionary(project_root: Path, config: dict[str, Any]) -> pd.DataFrame:
    definitions = {
        "risk_probability_02pp": "Probabilidad calibrada de que la participación baje al menos 2 puntos porcentuales frente a la elección federal de la misma familia.",
        "predicted_decline_pp": "Caída puntual prevista: participación base de misma familia menos pronóstico experimental 2027.",
        "predicted_additional_nonvoters": "Lista nominal por la caída puntual positiva prevista; volumen esperado, no conteo causal.",
        "priority_tier": "Cruce transparente de percentiles de riesgo y volumen; no prescribe intervención.",
        "profile_name": "Perfil descriptivo obtenido por clustering de brechas y cambios directos por edad/sexo.",
        "profile_data_source": "Indica conteos directos A/B o referencia estatal para C/D.",
        "geography_confidence_class": "A estable, B linaje oficial, C historia corta/nueva, D geografía ambigua.",
        "predicted_decline_lower_pp": "Extremo conservador de caída derivado del límite superior de participación.",
        "predicted_decline_upper_pp": "Extremo alto de caída derivado del límite inferior de participación.",
        "archetype_labels": "Arquetipos simultáneos con puntaje nacional ponderado por electorado igual o mayor al percentil 80.",
        "primary_archetype": "Dimensión descriptiva con el mayor puntaje continuo; no es una recomendación de intervención.",
        "archetype_assignment_stability": "Proporción de arquetipos cuya clasificación no cambia entre los cortes p75 y p85.",
        "risk_top20_frequency": "Fracción de réplicas bootstrap por entidad en que la sección queda en el 20% superior de riesgo.",
        "priority_tier1_frequency": "Fracción de réplicas bootstrap en que la sección combina alto riesgo y alto volumen.",
        "eceg_profile_source": "Procedencia de los descriptores ECEG 2020; nunca forman parte del predictor de riesgo.",
    }
    rows = []
    for output_name in ["section_file", "municipality_summary", "entity_summary", "decomposition"]:
        for column, definition in definitions.items():
            rows.append(
                {
                    "output": config["outputs"][output_name],
                    "column": column,
                    "definition": definition,
                    "causal_interpretation_allowed": False,
                }
            )
    dictionary = pd.DataFrame(rows)
    dictionary.to_csv(project_root / config["outputs"]["dictionary"], index=False)
    return dictionary


def write_report(
    project_root: Path,
    config: dict[str, Any],
    sections: pd.DataFrame,
    profiles: pd.DataFrame,
    validation: pd.DataFrame,
    entity: pd.DataFrame,
    selected_group: str,
    archetypes: pd.DataFrame,
    archetype_backtest: pd.DataFrame,
    eceg_summary: pd.DataFrame,
) -> Path:
    report_path = project_root / config["outputs"]["report"]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    points = sections[
        [
            "section_key_observed",
            "centroid_lon",
            "centroid_lat",
            "risk_probability_02pp",
            "predicted_additional_nonvoters",
            "profile_cluster",
            "priority_tier",
        ]
    ].dropna(subset=["centroid_lon", "centroid_lat"])
    points_json = json.dumps(
        [
            [
                row.section_key_observed,
                round(float(row.centroid_lon), 5),
                round(float(row.centroid_lat), 5),
                round(float(row.risk_probability_02pp), 4),
                round(float(row.predicted_additional_nonvoters), 1),
                int(row.profile_cluster),
                row.priority_tier,
            ]
            for row in points.itertuples(index=False)
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    total_volume = sections["predicted_additional_nonvoters"].sum()
    tier1 = sections["priority_tier"].eq("1_alto_riesgo_alto_volumen").sum()
    selected_validation = validation[validation["selected"]].iloc[0]
    profile_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(row.profile_name))}</td>"
        f"<td>{int(row.sections_represented):,}</td>"
        f"<td>{row.mean_risk_probability_02pp:.1%}</td>"
        f"<td>{row.predicted_additional_nonvoters:,.0f}</td>"
        "</tr>"
        for row in profiles.itertuples(index=False)
    )
    entity_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(row.entity_id))}</td>"
        f"<td>{row.weighted_risk_probability_02pp:.1%}</td>"
        f"<td>{row.predicted_additional_nonvoters:,.0f}</td>"
        f"<td>{int(row.tier_1_sections):,}</td>"
        "</tr>"
        for row in entity.head(12).itertuples(index=False)
    )
    archetype_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(row.label))}</td>"
        f"<td>{int(row.active_sections):,}</td>"
        f"<td>{int(row.robust_sections_p85):,}</td>"
        f"<td>{row.weighted_risk_probability_02pp:.1%}</td>"
        f"<td>{row.predicted_additional_nonvoters:,.0f}</td>"
        "</tr>"
        for row in archetypes.itertuples(index=False)
    )
    backtest_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(row.label))}</td>"
        f"<td>{int(row.positive_lift_folds)}/3</td>"
        f"<td>{100 * row.mean_risk_rate_difference:+.1f} pp</td>"
        f"<td>{row.mean_weighted_roc_auc:.3f}</td>"
        f"<td>{'sí' if row.historically_consistent else 'no'}</td>"
        "</tr>"
        for row in archetype_backtest.sort_values(
            "mean_risk_rate_difference", ascending=False
        ).itertuples(index=False)
    )
    eceg_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(row.label))}</td>"
        f"<td>{row.eceg_average_schooling:.1f}</td>"
        f"<td>{row.eceg_internet_share_dwellings:.1%}</td>"
        f"<td>{row.eceg_illiteracy_share_15_plus:.1%}</td>"
        f"<td>{row.eceg_indigenous_language_share_3_plus:.1%}</td>"
        "</tr>"
        for row in eceg_summary.itertuples(index=False)
    )
    robust_high = sections["risk_ranking_stability"].eq("robust_high_risk").sum()
    sensitive = sections["risk_ranking_stability"].eq("ranking_sensitive").sum()
    document = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Perfiles de riesgo de participación 2027</title>
<style>
:root{{--ink:#17212b;--muted:#62707c;--paper:#f5f1e8;--card:#fffdf8;--accent:#bf3f3f;--blue:#1d5d78}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 system-ui,sans-serif}}
main{{max-width:1180px;margin:auto;padding:32px}} h1{{font:700 42px/1.05 Georgia,serif;margin:.2em 0}} h2{{font:700 25px Georgia,serif;margin-top:1.8em}}
.lede{{max-width:850px;color:var(--muted);font-size:18px}} .grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:24px 0}}
.card{{background:var(--card);border:1px solid #ded7c9;border-radius:10px;padding:18px}} .big{{font:700 30px Georgia,serif;color:var(--accent)}}
.mapbox{{position:relative;background:#0f2532;border-radius:10px;overflow:hidden}} canvas{{width:100%;height:600px;display:block}} #tip{{position:absolute;display:none;background:#fff;padding:8px;border-radius:5px;pointer-events:none;font-size:12px}}
table{{width:100%;border-collapse:collapse;background:var(--card)}} th,td{{padding:9px;border-bottom:1px solid #ddd;text-align:right}} th:first-child,td:first-child{{text-align:left}}
.note{{color:var(--muted);font-size:13px}} .controls button{{margin:0 8px 12px 0;padding:8px 12px;border:1px solid #a9a196;background:#fff;border-radius:20px;cursor:pointer}}
@media(max-width:760px){{.grid{{grid-template-columns:1fr}} main{{padding:18px}} canvas{{height:480px}}}}
</style></head><body><main>
<p class="note">RADAR 27 · corte de información electoral 2024 · geografía provisional 2024</p>
<h1>Secciones con riesgo de caída en participación</h1>
<p class="lede">Paquete descriptivo para que especialistas en ciencia política diseñen la política pública. Separa probabilidad, magnitud y volumen; muestra brechas observadas por edad y sexo y conserva advertencias de calidad territorial. No estima efectos causales ni recomienda una intervención.</p>
<div class="grid"><div class="card"><div class="big">{len(sections):,}</div>secciones perfiladas</div><div class="card"><div class="big">{tier1:,}</div>alto riesgo y alto volumen</div><div class="card"><div class="big">{total_volume:,.0f}</div>no votantes adicionales previstos</div></div>
<h2>Mapa exploratorio por centroides oficiales</h2><div class="controls"><button onclick="mode='risk';draw()">Probabilidad ≥2 pp</button><button onclick="mode='volume';draw()">Volumen previsto</button><button onclick="mode='profile';draw()">Perfil</button></div>
<div class="mapbox"><canvas id="map"></canvas><div id="tip"></div></div><p class="note">Cada punto representa el centroide de una sección de la cartografía oficial 2024. La vista no sustituye el archivo geográfico ni implica que la sección 2027 ya esté certificada.</p>
<h2>Arquetipos superpuestos</h2><p>Una sección puede activar varias dimensiones a la vez. El corte principal es el percentil 80 ponderado por electorado; la columna robusta exige superar p85.</p>
<table><thead><tr><th>Arquetipo</th><th>Secciones activas</th><th>Robustas p85</th><th>Riesgo medio</th><th>Volumen previsto</th></tr></thead><tbody>{archetype_rows}</tbody></table>
<h2>Validación temporal de arquetipos</h2><p>El perfilamiento se reconstruye con información disponible antes de cada target. Un arquetipo descriptivo no se considera señal consistente si su lift no es positivo en los tres folds.</p>
<table><thead><tr><th>Arquetipo</th><th>Folds con lift</th><th>Lift medio</th><th>AUC media</th><th>Consistente</th></tr></thead><tbody>{backtest_rows}</tbody></table>
<h2>Estabilidad del ranking</h2><div class="grid"><div class="card"><div class="big">{robust_high:,}</div>alto riesgo robusto</div><div class="card"><div class="big">{sensitive:,}</div>sensibles al remuestreo estatal</div><div class="card"><div class="big">20</div>réplicas bootstrap</div></div><p class="note">Esta incertidumbre mide estabilidad del modelo y de la composición estatal; no incorpora cambios de régimen electoral.</p>
<h2>Contexto ECEG 2020 por arquetipo</h2><p>Descriptores para interpretación, excluidos del clasificador de riesgo.</p><table><thead><tr><th>Arquetipo</th><th>Escolaridad</th><th>Internet</th><th>Analfabetismo</th><th>Lengua indígena</th></tr></thead><tbody>{eceg_rows}</tbody></table>
<h2>Clusters exploratorios secundarios</h2><p>Se conservaron {int(selected_validation.clusters)} grupos (silhouette {selected_validation.silhouette:.3f}; estabilidad ARI media {selected_validation.mean_adjusted_rand:.3f}) sólo como segmentos exploratorios y resumen visual. La separación es débil y los arquetipos anteriores son ahora la salida principal.</p>
<table><thead><tr><th>Perfil</th><th>Secciones A/B</th><th>Riesgo medio</th><th>Volumen previsto</th></tr></thead><tbody>{profile_rows}</tbody></table>
<h2>Entidades con mayor volumen previsto</h2><table><thead><tr><th>Entidad</th><th>Riesgo ponderado</th><th>Volumen previsto</th><th>Secciones tier 1</th></tr></thead><tbody>{entity_rows}</tbody></table>
<h2>Cómo leer los archivos</h2><div class="card"><p>El clasificador usa <code>{html.escape(selected_group)}</code> y validación temporal estricta 2018/2021/2024. Como 2027 es una elección intermedia, las probabilidades finales se recalibran sólo con la predicción fuera de tiempo de 2021, el análogo directo; 2018 y 2024 se conservan como sensibilidad entre regímenes. La transferencia a 2024 fue débil, por lo que estas probabilidades no deben presentarse como certezas. La caída puntual proviene del pronóstico promovido del proyecto; el volumen multiplica esa caída positiva por la lista nominal.</p><p>Para A/B, los perfiles usan conteos directos por edad y sexo agregados a la unidad armonizada. En C/D se entrega una referencia estatal claramente marcada, nunca una medición local fingida. ECEG 2020 se usa sólo para describir contexto y nunca para producir la probabilidad.</p></div>
<script>
const pts={points_json}; let mode='risk'; const c=document.getElementById('map'),ctx=c.getContext('2d'),tip=document.getElementById('tip');
function resize(){{c.width=c.clientWidth*devicePixelRatio;c.height=c.clientHeight*devicePixelRatio;draw()}};
const palette=['#65c2a5','#fee08b','#f46d43','#7b3294','#3288bd','#d53e4f'];
function project(lon,lat){{const x=(lon+118.5)/(32.0)*c.width;const y=(33.1-lat)/(18.8)*c.height;return[x,y]}}
function draw(){{ctx.clearRect(0,0,c.width,c.height);ctx.fillStyle='#0f2532';ctx.fillRect(0,0,c.width,c.height);for(const p of pts){{let [x,y]=project(p[1],p[2]);let color;if(mode==='risk'){{let t=Math.max(0,Math.min(1,p[3]));color=`rgb(${{Math.round(70+185*t)}},${{Math.round(185-125*t)}},${{Math.round(165-105*t)}})`}}else if(mode==='volume'){{let t=Math.min(1,Math.log1p(p[4])/7);color=`rgb(${{Math.round(75+180*t)}},${{Math.round(180-120*t)}},70)`}}else color=palette[(p[5]-1)%palette.length];ctx.fillStyle=color;ctx.globalAlpha=.72;ctx.fillRect(x-1.2*devicePixelRatio,y-1.2*devicePixelRatio,2.4*devicePixelRatio,2.4*devicePixelRatio)}}ctx.globalAlpha=1}}
c.addEventListener('mousemove',e=>{{let r=c.getBoundingClientRect(),mx=(e.clientX-r.left)*devicePixelRatio,my=(e.clientY-r.top)*devicePixelRatio,b=null,bd=30*devicePixelRatio;for(const p of pts){{let [x,y]=project(p[1],p[2]),d=(x-mx)**2+(y-my)**2;if(d<bd){{bd=d;b=p}}}}if(b){{tip.style.display='block';tip.style.left=(e.clientX-r.left+12)+'px';tip.style.top=(e.clientY-r.top+12)+'px';tip.textContent=`${{b[0]}} · riesgo ${{(100*b[3]).toFixed(1)}}% · volumen ${{b[4]}}`}}else tip.style.display='none'}});window.addEventListener('resize',resize);resize();
</script></main></body></html>"""
    report_path.write_text(document, encoding="utf-8")
    return report_path


def run_turnout_risk_profiles(project_root: Path) -> dict[str, Any]:
    config = _load_yaml(project_root / "configs/turnout_risk_profiles.yaml")
    _, metrics, comparison, selected_group, calibrators = evaluate_risk_models(project_root, config)
    risk_units = fit_risk_forecast(project_root, config, selected_group, calibrators)
    decomposition, decomposition_summary = build_historical_decomposition(project_root, config)
    demographic = build_current_demographic_profiles(project_root, config)
    clustered, validation, profile_summary, profile_pipeline = cluster_profiles(
        demographic, risk_units, config
    )
    validation.to_csv(project_root / config["outputs"]["profile_validation"], index=False)
    profile_summary.to_csv(project_root / config["outputs"]["profile_summary"], index=False)
    sections, municipality, entity = expand_section_profiles(
        project_root, config, clustered, profile_pipeline
    )
    from radar27.modeling.turnout_profile_refinement import refine_turnout_profiles

    sections, archetype_summary, archetype_backtest, eceg_summary, bootstrap_registry = (
        refine_turnout_profiles(
            project_root,
            config,
            sections,
            selected_group,
            calibrators[float(config["primary_decline_threshold"])],
        )
    )
    municipality = pd.read_csv(
        project_root / config["outputs"]["municipality_summary"],
        dtype={"municipality_key_observed": "string"},
    )
    entity = pd.read_csv(
        project_root / config["outputs"]["entity_summary"], dtype={"entity_id": "string"}
    )
    _write_dictionary(project_root, config)
    report = write_report(
        project_root,
        config,
        sections,
        profile_summary,
        validation,
        entity,
        selected_group,
        archetype_summary,
        archetype_backtest,
        eceg_summary,
    )
    primary_metrics = metrics[
        metrics["feature_group"].eq(selected_group)
        & metrics["decline_threshold"].eq(float(config["primary_decline_threshold"]))
        & metrics["probability_version"].eq("time_calibrated")
    ]
    cross_cycle_warning = bool(
        primary_metrics.loc[primary_metrics["target_year"].eq(2024), "weighted_roc_auc"]
        .lt(0.5)
        .any()
    )
    decision = {
        "target_year": 2027,
        "status": "experimental_profile_handoff_not_policy_recommendation",
        "implemented_steps": [
            "historical_decline_panel_and_direct_subgroup_decomposition",
            "temporally_validated_decline_risk_classifier",
            "probability_magnitude_and_volume_ranking",
            "stable_descriptive_profiles",
            "section_municipality_entity_handoff_tables_and_map",
            "data_dictionary_and_methodological_limits",
        ],
        "deferred_step": "policy_evaluation_after_political_science_team_defines_intervention",
        "selected_risk_feature_group": selected_group,
        "model_selection": comparison.to_dict(orient="records"),
        "primary_threshold": float(config["primary_decline_threshold"]),
        "final_probability_calibration_target_year": int(
            config["risk_classifier"]["final_calibration_target_year"]
        ),
        "cross_cycle_transfer_warning": cross_cycle_warning,
        "strict_primary_metrics": primary_metrics.to_dict(orient="records"),
        "sections": len(sections),
        "municipalities": len(municipality),
        "entities": len(entity),
        "class_cd_sections_using_labeled_entity_reference": int(
            sections["geography_confidence_class"].isin(["C", "D"]).sum()
        ),
        "tier_1_sections": int(sections["priority_tier"].eq("1_alto_riesgo_alto_volumen").sum()),
        "predicted_additional_nonvoters": float(sections["predicted_additional_nonvoters"].sum()),
        "profile_clusters": int(validation.loc[validation["selected"], "clusters"].iloc[0]),
        "archetypes_primary_output": True,
        "archetype_count": len(archetype_summary),
        "historically_consistent_archetypes": archetype_backtest.loc[
            archetype_backtest["historically_consistent"], "archetype"
        ].tolist(),
        "robust_high_risk_sections": int(
            sections["risk_ranking_stability"].eq("robust_high_risk").sum()
        ),
        "ranking_sensitive_sections": int(
            sections["risk_ranking_stability"].eq("ranking_sensitive").sum()
        ),
        "bootstrap_uncertainty": bootstrap_registry,
        "eceg_role": "descriptive_only_not_used_by_risk_classifier",
        "decomposition_rows": len(decomposition),
        "decomposition_summary_rows": len(decomposition_summary),
        "report": str(report.relative_to(project_root)),
        "limitations": [
            "Risk is predictive, not causal.",
            "Age and sex profiles use direct INE counts, but associations do not identify treatment effects.",
            "A/B use harmonized section or official-lineage units; C/D use explicitly labeled entity references.",
            "The 2027 geography is not certified; the audited 2024 snapshot is used.",
            "Priority tiers are transparent quantile summaries, not policy prescriptions.",
            "The 2024 presidential sensitivity fold did not transfer well; 2027 probabilities are calibrated to the strict 2021 midterm analogue.",
        ],
    }
    decision_path = project_root / config["outputs"]["decision"]
    decision_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    return decision
