from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd
import yaml
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

COUNT_COLUMNS = [
    "nominal_list",
    "voted",
    "did_not_vote",
    "unspecified",
    "female_nominal_list",
    "female_voted",
    "female_did_not_vote",
    "male_nominal_list",
    "male_voted",
    "male_did_not_vote",
    "age_18_29_nominal_list",
    "age_18_29_voted",
    "age_18_29_did_not_vote",
    "age_30_44_nominal_list",
    "age_30_44_voted",
    "age_30_44_did_not_vote",
    "age_45_64_nominal_list",
    "age_45_64_voted",
    "age_45_64_did_not_vote",
    "age_65_plus_nominal_list",
    "age_65_plus_voted",
    "age_65_plus_did_not_vote",
]

ECEG_COUNT_COLUMNS = [
    "eceg_population_total",
    "eceg_population_female",
    "eceg_population_18_plus",
    "eceg_population_60_plus",
    "eceg_population_15_plus",
    "eceg_population_12_plus",
    "eceg_population_3_plus",
    "eceg_population_15_plus_illiterate",
    "eceg_economically_active_population",
    "eceg_population_with_disability",
    "eceg_population_3_plus_indigenous_language",
    "eceg_inhabited_private_dwellings",
    "eceg_dwellings_with_internet",
]


def _sql_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator.astype(float).div(denominator.astype(float).where(denominator.ne(0)))


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def build_section_year_behavioral_features(project_root: Path) -> pd.DataFrame:
    """Aggregate the age/sex CCPC rows without averaging published rates."""
    source_glob = project_root / "data/interim/harmonized_demographic/*/ccpc_*_harmonized.parquet"
    destination = project_root / "artifacts/tables/section_year_behavioral_features.parquet"
    query = f"""
    SELECT
      election_year,
      any_value(election_family) AS election_family,
      entity_id,
      any_value(municipality_key_observed) AS municipality_key_observed,
      section_key_observed,
      any_value(section_type_code) AS section_type_code,
      sum(nominal_list)::BIGINT AS nominal_list,
      sum(voted)::BIGINT AS voted,
      sum(did_not_vote)::BIGINT AS did_not_vote,
      sum(unspecified)::BIGINT AS unspecified,
      sum(nominal_list) FILTER (WHERE sex_code = 1)::BIGINT AS female_nominal_list,
      sum(voted) FILTER (WHERE sex_code = 1)::BIGINT AS female_voted,
      sum(did_not_vote) FILTER (WHERE sex_code = 1)::BIGINT AS female_did_not_vote,
      sum(nominal_list) FILTER (WHERE sex_code = 0)::BIGINT AS male_nominal_list,
      sum(voted) FILTER (WHERE sex_code = 0)::BIGINT AS male_voted,
      sum(did_not_vote) FILTER (WHERE sex_code = 0)::BIGINT AS male_did_not_vote,
      sum(nominal_list) FILTER (WHERE age BETWEEN 18 AND 29)::BIGINT AS age_18_29_nominal_list,
      sum(voted) FILTER (WHERE age BETWEEN 18 AND 29)::BIGINT AS age_18_29_voted,
      sum(did_not_vote) FILTER (WHERE age BETWEEN 18 AND 29)::BIGINT AS age_18_29_did_not_vote,
      sum(nominal_list) FILTER (WHERE age BETWEEN 30 AND 44)::BIGINT AS age_30_44_nominal_list,
      sum(voted) FILTER (WHERE age BETWEEN 30 AND 44)::BIGINT AS age_30_44_voted,
      sum(did_not_vote) FILTER (WHERE age BETWEEN 30 AND 44)::BIGINT AS age_30_44_did_not_vote,
      sum(nominal_list) FILTER (WHERE age BETWEEN 45 AND 64)::BIGINT AS age_45_64_nominal_list,
      sum(voted) FILTER (WHERE age BETWEEN 45 AND 64)::BIGINT AS age_45_64_voted,
      sum(did_not_vote) FILTER (WHERE age BETWEEN 45 AND 64)::BIGINT AS age_45_64_did_not_vote,
      sum(nominal_list) FILTER (WHERE age >= 65)::BIGINT AS age_65_plus_nominal_list,
      sum(voted) FILTER (WHERE age >= 65)::BIGINT AS age_65_plus_voted,
      sum(did_not_vote) FILTER (WHERE age >= 65)::BIGINT AS age_65_plus_did_not_vote
    FROM read_parquet('{_sql_path(source_glob)}')
    GROUP BY election_year, entity_id, section_key_observed
    ORDER BY election_year, entity_id, section_key_observed
    """
    connection = duckdb.connect(database=":memory:")
    connection.execute("SET threads TO 4")
    connection.execute("SET memory_limit='2GB'")
    try:
        frame = connection.execute(query).df()
    finally:
        connection.close()
    if frame.duplicated(["election_year", "section_key_observed"]).any():
        raise ValueError("El agregado conductual contiene claves sección-año duplicadas")
    frame["identified_records"] = frame["voted"] + frame["did_not_vote"]
    frame["participation"] = _safe_ratio(frame["voted"], frame["identified_records"])
    frame.to_parquet(destination, index=False)
    return frame


def _derive_lag_rates(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["participation"] = _safe_ratio(result["voted"], result["voted"] + result["did_not_vote"])
    result["identified_coverage"] = _safe_ratio(
        result["voted"] + result["did_not_vote"], result["nominal_list"]
    )
    result["female_nominal_share"] = _safe_ratio(
        result["female_nominal_list"], result["nominal_list"]
    )
    for label in ["female", "male", "age_18_29", "age_30_44", "age_45_64", "age_65_plus"]:
        result[f"{label}_turnout"] = _safe_ratio(
            result[f"{label}_voted"],
            result[f"{label}_voted"] + result[f"{label}_did_not_vote"],
        )
    for label in ["age_18_29", "age_30_44", "age_45_64", "age_65_plus"]:
        result[f"{label}_nominal_share"] = _safe_ratio(
            result[f"{label}_nominal_list"], result["nominal_list"]
        )
    result["female_minus_male_turnout"] = result["female_turnout"] - result["male_turnout"]
    result["log_nominal_list"] = np.log1p(result["nominal_list"].astype(float))
    return result


def _target_units(
    target: pd.DataFrame, component_membership: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    stable = target[target["geography_confidence_class"].eq("A")].copy()
    stable["evaluation_unit_id"] = "S:" + stable["section_key_observed"]
    stable["target_sections_represented"] = 1
    stable["actual"] = stable["participation"]
    stable_units = stable[
        [
            "evaluation_unit_id",
            "entity_id",
            "geography_confidence_class",
            "target_sections_represented",
            "nominal_list",
            "voted",
            "did_not_vote",
            "actual",
        ]
    ]
    stable_members = stable[["evaluation_unit_id", "section_key_observed"]]

    lineage = target[
        target["geography_confidence_class"].eq("B") & target["amge_component_id"].notna()
    ].copy()
    lineage_units = (
        lineage.groupby("amge_component_id", as_index=False)
        .agg(
            entity_count=("entity_id", "nunique"),
            entity_id=("entity_id", "first"),
            target_sections_represented=("section_key_observed", "nunique"),
            nominal_list=("nominal_list", "sum"),
            voted=("voted", "sum"),
            did_not_vote=("did_not_vote", "sum"),
        )
    )
    if not lineage_units.empty and lineage_units["entity_count"].ne(1).any():
        raise ValueError("Un componente AMGE cruza entidades federativas")
    lineage_units["evaluation_unit_id"] = "C:" + lineage_units["amge_component_id"]
    lineage_units["geography_confidence_class"] = "B"
    lineage_units["actual"] = _safe_ratio(
        lineage_units["voted"], lineage_units["voted"] + lineage_units["did_not_vote"]
    )
    lineage_units = lineage_units[
        [
            "evaluation_unit_id",
            "entity_id",
            "geography_confidence_class",
            "target_sections_represented",
            "nominal_list",
            "voted",
            "did_not_vote",
            "actual",
        ]
    ]
    component_ids = set(lineage["amge_component_id"].dropna())
    lineage_members = component_membership[
        component_membership["amge_component_id"].isin(component_ids)
    ][["amge_component_id", "section_key_observed"]].drop_duplicates()
    lineage_members["evaluation_unit_id"] = "C:" + lineage_members["amge_component_id"]
    lineage_members = lineage_members[["evaluation_unit_id", "section_key_observed"]]

    units = pd.concat([stable_units, lineage_units], ignore_index=True)
    members = pd.concat([stable_members, lineage_members], ignore_index=True).drop_duplicates()
    if units["evaluation_unit_id"].duplicated().any():
        raise ValueError("IDs de unidad de evaluación duplicados")
    return units, members


def _aggregate_history(
    members: pd.DataFrame, section_year: pd.DataFrame, target_year: int
) -> pd.DataFrame:
    history = members.merge(section_year, on="section_key_observed", how="left", validate="many_to_many")
    history = history[history["election_year"].lt(target_year)].copy()
    return history.groupby(["evaluation_unit_id", "election_year"], as_index=False)[
        COUNT_COLUMNS
    ].sum(min_count=1)


def _history_features(
    history: pd.DataFrame, target_year: int, same_type_year: int
) -> pd.DataFrame:
    history = _derive_lag_rates(history)
    prior_years = sorted(int(year) for year in history["election_year"].dropna().unique())
    if len(prior_years) < 2:
        raise ValueError(f"Historia insuficiente para construir features de {target_year}")
    lag1_year, lag2_year = prior_years[-1], prior_years[-2]
    lag1_columns = {
        "participation": "participation_lag1",
        "log_nominal_list": "log_nominal_list_lag1",
        "identified_coverage": "identified_coverage_lag1",
        "female_nominal_share": "female_nominal_share_lag1",
        "age_18_29_nominal_share": "age_18_29_nominal_share_lag1",
        "age_30_44_nominal_share": "age_30_44_nominal_share_lag1",
        "age_45_64_nominal_share": "age_45_64_nominal_share_lag1",
        "age_65_plus_nominal_share": "age_65_plus_nominal_share_lag1",
        "female_turnout": "female_turnout_lag1",
        "male_turnout": "male_turnout_lag1",
        "female_minus_male_turnout": "female_minus_male_turnout_lag1",
        "age_18_29_turnout": "age_18_29_turnout_lag1",
        "age_30_44_turnout": "age_30_44_turnout_lag1",
        "age_45_64_turnout": "age_45_64_turnout_lag1",
        "age_65_plus_turnout": "age_65_plus_turnout_lag1",
    }
    lag1 = history[history["election_year"].eq(lag1_year)][
        ["evaluation_unit_id", "nominal_list", *lag1_columns]
    ].rename(columns={**lag1_columns, "nominal_list": "nominal_list_lag1"})
    lag2 = history[history["election_year"].eq(lag2_year)][
        ["evaluation_unit_id", "participation", "nominal_list"]
    ].rename(
        columns={"participation": "participation_lag2", "nominal_list": "nominal_list_lag2"}
    )
    same_type = history[history["election_year"].eq(same_type_year)][
        ["evaluation_unit_id", "participation"]
    ].rename(columns={"participation": "participation_same_type"})

    valid = history.dropna(subset=["participation"]).copy()
    valid["year_sum"] = valid["election_year"].astype(float)
    valid["year_sq"] = valid["year_sum"] ** 2
    valid["year_participation"] = valid["year_sum"] * valid["participation"]
    stats = (
        valid.groupby("evaluation_unit_id", as_index=False)
        .agg(
            historical_observations=("participation", "count"),
            participation_historical_mean=("participation", "mean"),
            participation_historical_std=("participation", "std"),
            sum_year=("year_sum", "sum"),
            sum_year_sq=("year_sq", "sum"),
            sum_participation=("participation", "sum"),
            sum_year_participation=("year_participation", "sum"),
        )
    )
    denominator = (
        stats["historical_observations"] * stats["sum_year_sq"] - stats["sum_year"] ** 2
    )
    stats["participation_trend_per_year"] = (
        stats["historical_observations"] * stats["sum_year_participation"]
        - stats["sum_year"] * stats["sum_participation"]
    ).div(denominator.where(denominator.ne(0)))
    stats = stats.drop(
        columns=["sum_year", "sum_year_sq", "sum_participation", "sum_year_participation"]
    )

    result = stats.merge(lag1, on="evaluation_unit_id", how="outer", validate="one_to_one")
    result = result.merge(lag2, on="evaluation_unit_id", how="outer", validate="one_to_one")
    result = result.merge(same_type, on="evaluation_unit_id", how="outer", validate="one_to_one")
    result["participation_change_lag1_lag2"] = (
        result["participation_lag1"] - result["participation_lag2"]
    )
    result["participation_same_type_minus_lag1"] = (
        result["participation_same_type"] - result["participation_lag1"]
    )
    result["nominal_list_growth_lag1_lag2"] = _safe_ratio(
        result["nominal_list_lag1"] - result["nominal_list_lag2"],
        result["nominal_list_lag2"],
    )
    result["lag1_year"] = lag1_year
    result["lag2_year"] = lag2_year
    result["same_type_year"] = same_type_year
    return result


def _eceg_features(members: pd.DataFrame, eceg: pd.DataFrame) -> pd.DataFrame:
    merged = members.merge(eceg, on="section_key_observed", how="left", validate="many_to_one")
    merged["schooling_weighted"] = (
        merged["eceg_average_schooling"] * merged["eceg_population_15_plus"]
    )
    result = merged.groupby("evaluation_unit_id", as_index=False).agg(
        **{column: (column, "sum") for column in ECEG_COUNT_COLUMNS},
        schooling_weighted=("schooling_weighted", "sum"),
        eceg_sections_matched=("eceg_population_total", "count"),
        member_sections=("section_key_observed", "nunique"),
    )
    result["eceg_female_share"] = _safe_ratio(
        result["eceg_population_female"], result["eceg_population_total"]
    )
    result["eceg_adult_share"] = _safe_ratio(
        result["eceg_population_18_plus"], result["eceg_population_total"]
    )
    result["eceg_older_share"] = _safe_ratio(
        result["eceg_population_60_plus"], result["eceg_population_total"]
    )
    result["eceg_illiteracy_share_15_plus"] = _safe_ratio(
        result["eceg_population_15_plus_illiterate"], result["eceg_population_15_plus"]
    )
    result["eceg_economic_activity_share_12_plus"] = _safe_ratio(
        result["eceg_economically_active_population"], result["eceg_population_12_plus"]
    )
    result["eceg_disability_share"] = _safe_ratio(
        result["eceg_population_with_disability"], result["eceg_population_total"]
    )
    result["eceg_indigenous_language_share_3_plus"] = _safe_ratio(
        result["eceg_population_3_plus_indigenous_language"], result["eceg_population_3_plus"]
    )
    result["eceg_internet_share_dwellings"] = _safe_ratio(
        result["eceg_dwellings_with_internet"], result["eceg_inhabited_private_dwellings"]
    )
    result["eceg_average_schooling"] = _safe_ratio(
        result["schooling_weighted"], result["eceg_population_15_plus"]
    )
    result["eceg_member_match_share"] = _safe_ratio(
        result["eceg_sections_matched"], result["member_sections"]
    )
    return result


def _write_feature_lineage(project_root: Path, modeling: dict[str, Any]) -> pd.DataFrame:
    electoral = modeling["feature_sets"]["electoral"]
    eceg = modeling["feature_sets"]["electoral_eceg"]["numeric"]
    rows = []
    for name in electoral["numeric"]:
        availability = "strictly_before_target_election"
        source = "CCPC INE age-sex counts; ratio of sums"
        rows.append(
            {
                "feature": name,
                "feature_set": "electoral",
                "source": source,
                "availability_rule": availability,
                "transformation": "see src/radar27/modeling/feature_models.py",
                "missing_policy": "median imputation fitted on earlier target years only",
                "leakage_control": "all contributing election_year values are < target_year",
            }
        )
    for name in electoral["categorical"]:
        rows.append(
            {
                "feature": name,
                "feature_set": "electoral",
                "source": "target geography/election schedule known before voting",
                "availability_rule": "known_before_target_election",
                "transformation": "one-hot; unknown categories ignored",
                "missing_policy": "most-frequent imputation fitted on training years",
                "leakage_control": "contains no target outcome",
            }
        )
    for name in eceg:
        rows.append(
            {
                "feature": name,
                "feature_set": "eceg_2020",
                "source": "INEGI ECEG 2020 section CSV",
                "availability_rule": "available from 2021-08-18; evaluated only for target 2024",
                "transformation": "ratio of published count sums; schooling is population-weighted",
                "missing_policy": "median imputation fitted on training rows at 2024 forecast origin",
                "leakage_control": "prohibited in strict 2015/2018/2021 backtests",
            }
        )
    lineage = pd.DataFrame(rows).drop_duplicates(["feature", "feature_set"])
    lineage.to_csv(project_root / "artifacts/tables/model_feature_lineage.csv", index=False)
    return lineage


def build_feature_mart(project_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    evaluation = _load_yaml(project_root / "configs/evaluation.yaml")
    modeling = _load_yaml(project_root / "configs/modeling.yaml")
    section_year = pd.read_parquet(
        project_root / "artifacts/tables/section_year_behavioral_features.parquet"
    )
    classes = pd.read_parquet(
        project_root / "artifacts/tables/section_confidence_by_election.parquet"
    )
    components = pd.read_parquet(
        project_root / "artifacts/tables/lineage_components_by_election.parquet"
    )
    eceg = pd.read_parquet(project_root / "artifacts/tables/eceg_2020_section_features.parquet")
    rows = []
    coverage_rows = []
    for fold in evaluation["folds"]:
        target_year = int(fold["target_year"])
        same_type_year = int(fold["feature_year"])
        target = classes[classes["target_year"].eq(target_year)].copy()
        memberships = components[components["target_year"].eq(target_year)].copy()
        units, members = _target_units(target, memberships)
        history = _aggregate_history(members, section_year, target_year)
        features = _history_features(history, target_year, same_type_year)
        census = _eceg_features(members, eceg)
        mart = units.merge(features, on="evaluation_unit_id", how="left", validate="one_to_one")
        mart = mart.merge(census, on="evaluation_unit_id", how="left", validate="one_to_one")
        mart["target_year"] = target_year
        mart["election_family"] = fold["election_family"]
        mart["evidence_status"] = fold["evidence_status"]
        mart["lineage_class_b"] = mart["geography_confidence_class"].eq("B").astype(int)
        mart["target_identified_records"] = mart["voted"] + mart["did_not_vote"]
        mart["max_electoral_feature_year"] = mart["lag1_year"]
        mart["eceg_reference_year"] = 2020
        mart["eceg_available_from"] = "2021-08-18"
        mart["eceg_strict_backtest_allowed"] = target_year in set(
            modeling["training_policy"]["eceg_strict_backtest_targets"]
        )
        total_defined = int(target["participation"].notna().sum())
        represented_defined = int(
            mart.loc[mart["actual"].notna(), "target_sections_represented"].sum()
        )
        coverage_rows.append(
            {
                "target_year": target_year,
                "feature_units": len(mart),
                "target_defined_sections": total_defined,
                "ab_defined_sections_represented": represented_defined,
                "ab_section_coverage": represented_defined / total_defined,
                "max_electoral_feature_year": int(mart["max_electoral_feature_year"].max()),
                "eceg_strict_backtest_allowed": bool(mart["eceg_strict_backtest_allowed"].all()),
                "eceg_full_member_match_units": int(mart["eceg_member_match_share"].eq(1).sum()),
            }
        )
        rows.append(mart)
    feature_mart = pd.concat(rows, ignore_index=True).sort_values(
        ["target_year", "evaluation_unit_id"]
    )
    if not (feature_mart["max_electoral_feature_year"] < feature_mart["target_year"]).all():
        raise ValueError("Se detectó fuga temporal en las variables electorales")
    feature_mart.to_parquet(project_root / "artifacts/tables/feature_mart_ab.parquet", index=False)
    coverage = pd.DataFrame(coverage_rows)
    coverage.to_csv(project_root / "artifacts/tables/feature_mart_coverage.csv", index=False)
    _write_feature_lineage(project_root, modeling)
    return feature_mart, coverage


def _feature_spec(modeling: dict[str, Any], feature_set: str) -> tuple[list[str], list[str]]:
    electoral = modeling["feature_sets"]["electoral"]
    numeric = list(electoral["numeric"])
    categorical = list(electoral["categorical"])
    if feature_set == "electoral_eceg":
        numeric.extend(modeling["feature_sets"]["electoral_eceg"]["numeric"])
    return numeric, categorical


def _pipeline(spec: dict[str, Any], numeric: list[str], categorical: list[str], seed: int) -> Pipeline:
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
    if spec["family"] == "ridge":
        estimator = Ridge(alpha=float(spec["alpha"]))
    else:
        estimator = HistGradientBoostingRegressor(
            learning_rate=float(spec["learning_rate"]),
            max_iter=int(spec["max_iter"]),
            max_leaf_nodes=int(spec["max_leaf_nodes"]),
            min_samples_leaf=int(spec["min_samples_leaf"]),
            l2_regularization=float(spec["l2_regularization"]),
            random_state=seed,
        )
    return Pipeline([("preprocess", preprocess), ("model", estimator)])


def _metric_row(
    frame: pd.DataFrame,
    model_id: str,
    target_year: int,
    training_years: list[int],
    all_target_defined_sections: int,
) -> dict[str, Any]:
    valid = frame.dropna(subset=["actual", "prediction"]).copy()
    error = valid["prediction"] - valid["actual"]
    absolute = error.abs()
    weights = valid["target_identified_records"].astype(float)
    represented = int(valid["target_sections_represented"].sum())
    return {
        "target_year": target_year,
        "model_id": model_id,
        "training_target_years": "|".join(map(str, training_years)),
        "evaluation_units": len(valid),
        "target_sections_represented": represented,
        "all_target_defined_sections": all_target_defined_sections,
        "section_coverage": represented / all_target_defined_sections,
        "mae": float(absolute.mean()),
        "rmse": float(math.sqrt((error**2).mean())),
        "bias": float(error.mean()),
        "identified_weighted_mae": float(np.average(absolute, weights=weights)),
        "share_within_5pp": float(absolute.le(0.05).mean()),
        "clipped_predictions": int(valid["prediction_was_clipped"].sum()),
    }


def evaluate_models(
    project_root: Path, feature_mart: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    modeling = _load_yaml(project_root / "configs/modeling.yaml")
    baseline_metrics = pd.read_csv(project_root / "artifacts/tables/backtest_metrics.csv")
    classes = pd.read_parquet(
        project_root / "artifacts/tables/section_confidence_by_election.parquet"
    )
    seed = int(modeling["random_seed"])
    predictions = []
    metric_rows = []
    importance_rows = []
    model_run_rows = []
    started = time.perf_counter()
    for target_year in modeling["training_policy"]["evaluation_targets"]:
        train = feature_mart[
            feature_mart["target_year"].lt(target_year) & feature_mart["actual"].notna()
        ].copy()
        test = feature_mart[feature_mart["target_year"].eq(target_year)].copy()
        training_years = sorted(int(year) for year in train["target_year"].unique())
        all_target_defined = int(
            classes.loc[
                classes["target_year"].eq(target_year), "participation"
            ].notna().sum()
        )

        baseline = test.copy()
        baseline["prediction_raw"] = baseline["participation_same_type"]
        baseline["prediction"] = baseline["prediction_raw"]
        baseline["prediction_was_clipped"] = False
        baseline["model_id"] = "lag_same_type_baseline"
        predictions.append(baseline)
        metric_rows.append(
            _metric_row(
                baseline,
                "lag_same_type_baseline",
                target_year,
                training_years,
                all_target_defined,
            )
        )

        for model_id, spec in modeling["models"].items():
            allowed = spec.get("allowed_target_years")
            if allowed and target_year not in allowed:
                continue
            numeric, categorical = _feature_spec(modeling, spec["feature_set"])
            required = numeric + categorical
            missing_columns = set(required) - set(feature_mart.columns)
            if missing_columns:
                raise ValueError(f"Features ausentes para {model_id}: {sorted(missing_columns)}")
            direct_pipeline = _pipeline(spec, numeric, categorical, seed)
            direct_pipeline.fit(
                train[required],
                train["actual"],
                model__sample_weight=train["target_identified_records"].astype(float),
            )
            raw = direct_pipeline.predict(test[required])
            interpretation_pipeline = direct_pipeline
            prediction_mode = spec.get("prediction_mode", "direct")
            if prediction_mode == "residual_correction":
                residual_train = train.dropna(subset=["participation_same_type"]).copy()
                residual_target = (
                    residual_train["actual"] - residual_train["participation_same_type"]
                )
                residual_pipeline = _pipeline(spec, numeric, categorical, seed)
                residual_pipeline.fit(
                    residual_train[required],
                    residual_target,
                    model__sample_weight=residual_train["target_identified_records"].astype(float),
                )
                correction = residual_pipeline.predict(test[required])
                has_baseline = test["participation_same_type"].notna().to_numpy()
                shrinkage = float(spec["residual_shrinkage"])
                corrected = test["participation_same_type"].to_numpy() + shrinkage * correction
                raw = np.where(has_baseline, corrected, raw)
                interpretation_pipeline = residual_pipeline
            predicted = test.copy()
            predicted["prediction_raw"] = raw
            predicted["prediction"] = np.clip(raw, 0.0, 1.0)
            predicted["prediction_was_clipped"] = predicted["prediction"].ne(
                predicted["prediction_raw"]
            )
            predicted["model_id"] = model_id
            predictions.append(predicted)
            metric_rows.append(
                _metric_row(
                    predicted, model_id, target_year, training_years, all_target_defined
                )
            )
            model_run_rows.append(
                {
                    "target_year": target_year,
                    "model_id": model_id,
                    "feature_set": spec["feature_set"],
                    "training_target_years": "|".join(map(str, training_years)),
                    "training_units": len(train),
                    "numeric_features": "|".join(numeric),
                    "categorical_features": "|".join(categorical),
                    "hyperparameters": json.dumps(spec, sort_keys=True),
                    "random_seed": seed,
                    "prediction_mode": prediction_mode,
                    "residual_shrinkage": spec.get("residual_shrinkage"),
                    "missing_baseline_policy": (
                        "direct prediction from the same model family"
                        if prediction_mode == "residual_correction"
                        else "not applicable"
                    ),
                    "preprocessing": "train-only median+missing indicators+standardization; train-only categorical mode+one-hot",
                }
            )
            if spec["family"] == "ridge":
                names = interpretation_pipeline.named_steps["preprocess"].get_feature_names_out()
                coefficients = interpretation_pipeline.named_steps["model"].coef_
                importance_rows.extend(
                    {
                        "target_year": target_year,
                        "model_id": model_id,
                        "feature": name,
                        "importance_method": "standardized_ridge_coefficient",
                        "importance": float(value),
                    }
                    for name, value in zip(names, coefficients, strict=True)
                )
            else:
                sample_required = ["actual"]
                if prediction_mode == "residual_correction":
                    sample_required.append("participation_same_type")
                sample_pool = test.dropna(subset=sample_required)
                sample = sample_pool.sample(n=min(5000, len(sample_pool)), random_state=seed)
                importance_target = sample["actual"]
                if prediction_mode == "residual_correction":
                    importance_target = importance_target - sample["participation_same_type"]
                permutation = permutation_importance(
                    interpretation_pipeline,
                    sample[required],
                    importance_target,
                    scoring="neg_mean_absolute_error",
                    n_repeats=3,
                    random_state=seed,
                    n_jobs=1,
                )
                importance_rows.extend(
                    {
                        "target_year": target_year,
                        "model_id": model_id,
                        "feature": name,
                        "importance_method": "unweighted_permutation_mae_sample_max_5000",
                        "importance": float(value),
                    }
                    for name, value in zip(required, permutation.importances_mean, strict=True)
                )

    prediction_frame = pd.concat(predictions, ignore_index=True)
    metrics = pd.DataFrame(metric_rows).sort_values(["target_year", "model_id"])
    metrics["elapsed_total_seconds"] = round(time.perf_counter() - started, 3)
    importances = pd.DataFrame(importance_rows).sort_values(
        ["target_year", "model_id", "importance"], ascending=[True, True, False]
    )
    model_runs = pd.DataFrame(model_run_rows)

    primary_year = int(modeling["primary_gate_target_year"])
    frozen = baseline_metrics[
        baseline_metrics["target_year"].eq(primary_year)
        & baseline_metrics["scenario"].eq(modeling["primary_baseline_scenario"])
    ].iloc[0]
    required_coverage = max(
        float(modeling["minimum_primary_section_coverage"]), float(frozen["section_coverage"])
    )
    candidates = metrics[
        metrics["target_year"].eq(primary_year)
        & metrics["model_id"].str.endswith("_electoral")
        & metrics["section_coverage"].ge(required_coverage)
    ].sort_values("identified_weighted_mae")
    best = candidates.iloc[0] if not candidates.empty else None
    maximum_deterioration = float(
        modeling["maximum_absolute_weighted_mae_deterioration_other_folds"]
    )
    robustness_rows = []
    if best is not None:
        candidate_id = str(best["model_id"])
        for year in modeling["training_policy"]["evaluation_targets"]:
            if year == primary_year:
                continue
            candidate_row = metrics[
                metrics["target_year"].eq(year) & metrics["model_id"].eq(candidate_id)
            ]
            baseline_row = metrics[
                metrics["target_year"].eq(year)
                & metrics["model_id"].eq("lag_same_type_baseline")
            ]
            if candidate_row.empty or baseline_row.empty:
                continue
            deterioration = float(
                candidate_row.iloc[0]["identified_weighted_mae"]
                - baseline_row.iloc[0]["identified_weighted_mae"]
            )
            robustness_rows.append(
                {
                    "target_year": int(year),
                    "role": (
                        "shrinkage_calibration_fold"
                        if int(year) == 2018
                        else "robustness_fold_partial_geography"
                    ),
                    "absolute_weighted_mae_deterioration": deterioration,
                    "passes": deterioration <= maximum_deterioration,
                }
            )
    robustness_passes = bool(robustness_rows) and all(row["passes"] for row in robustness_rows)
    approved = bool(
        best is not None
        and best["identified_weighted_mae"] < frozen["identified_weighted_mae"]
        and robustness_passes
    )
    decision = {
        "primary_target_year": primary_year,
        "metric": modeling["primary_metric"],
        "frozen_baseline_model": modeling["primary_baseline_scenario"],
        "frozen_baseline_identified_weighted_mae": float(frozen["identified_weighted_mae"]),
        "frozen_baseline_section_coverage": float(frozen["section_coverage"]),
        "minimum_section_coverage": required_coverage,
        "maximum_absolute_weighted_mae_deterioration_other_folds": maximum_deterioration,
        "best_eligible_candidate": None if best is None else str(best["model_id"]),
        "best_candidate_identified_weighted_mae": (
            None if best is None else float(best["identified_weighted_mae"])
        ),
        "best_candidate_section_coverage": (
            None if best is None else float(best["section_coverage"])
        ),
        "candidate_approved": approved,
        "robustness_checks": robustness_rows,
        "selected_for_next_phase": (
            str(best["model_id"]) if approved else "stable_plus_lineage_baseline"
        ),
        "decision_rule": "approve only if 2021 weighted MAE improves, coverage matches the frozen A+B baseline, and no other fold worsens by more than 0.005 absolute MAE",
        "eceg_status": "secondary_2024_only; prohibited from primary 2021 gate",
    }
    output = project_root / "artifacts/tables"
    keep = [
        "target_year",
        "model_id",
        "evaluation_unit_id",
        "entity_id",
        "geography_confidence_class",
        "target_sections_represented",
        "nominal_list",
        "target_identified_records",
        "actual",
        "prediction_raw",
        "prediction",
        "prediction_was_clipped",
        "participation_same_type",
        "max_electoral_feature_year",
        "eceg_strict_backtest_allowed",
        "eceg_member_match_share",
    ]
    prediction_frame[keep].to_parquet(output / "model_backtest_predictions.parquet", index=False)
    metrics.to_csv(output / "model_backtest_metrics.csv", index=False)
    importances.to_csv(output / "model_feature_importance.csv", index=False)
    model_runs.to_csv(output / "model_run_registry.csv", index=False)
    error_frame = prediction_frame.dropna(subset=["actual", "prediction"]).copy()
    error_frame["error"] = error_frame["prediction"] - error_frame["actual"]
    error_frame["absolute_error"] = error_frame["error"].abs()
    error_frame["weighted_absolute_error"] = (
        error_frame["absolute_error"] * error_frame["target_identified_records"]
    )
    error_frame["weighted_error"] = (
        error_frame["error"] * error_frame["target_identified_records"]
    )
    errors = (
        error_frame.groupby(
            ["target_year", "model_id", "entity_id", "geography_confidence_class"],
            as_index=False,
        )
        .agg(
            evaluation_units=("evaluation_unit_id", "count"),
            sections=("target_sections_represented", "sum"),
            mae=("absolute_error", "mean"),
            bias=("error", "mean"),
            identified_records=("target_identified_records", "sum"),
            weighted_absolute_error_sum=("weighted_absolute_error", "sum"),
            weighted_error_sum=("weighted_error", "sum"),
        )
    )
    errors["identified_weighted_mae"] = _safe_ratio(
        errors["weighted_absolute_error_sum"], errors["identified_records"]
    )
    errors["identified_weighted_bias"] = _safe_ratio(
        errors["weighted_error_sum"], errors["identified_records"]
    )
    errors.to_csv(output / "model_errors_by_entity_class.csv", index=False)
    (project_root / "artifacts/model_decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return metrics, prediction_frame, importances, decision
