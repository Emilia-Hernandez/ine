from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from radar27.geography.amge import keys_for_status, lineage_components


def _ratio(voted: pd.Series, did_not_vote: pd.Series) -> pd.Series:
    denominator = voted + did_not_vote
    return voted.div(denominator.where(denominator.ne(0)))


def _aggregate(frame: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    result = (
        frame.groupby(keys, as_index=False)
        .agg(
            target_sections_represented=("section_key_observed", "nunique"),
            nominal_list=("nominal_list", "sum"),
            voted=("voted", "sum"),
            did_not_vote=("did_not_vote", "sum"),
            unspecified=("unspecified", "sum"),
        )
    )
    result["participation"] = _ratio(result["voted"], result["did_not_vote"])
    result["identified_records"] = result["voted"] + result["did_not_vote"]
    return result


def _classify_for_target(
    panel: pd.DataFrame,
    affected: pd.DataFrame,
    edges: pd.DataFrame,
    target_year: int,
    feature_year: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    history = panel[panel["election_year"].le(target_year)].copy()
    history_stats = (
        history.groupby("section_key_observed", as_index=False)
        .agg(
            elections_observed=("election_year", "nunique"),
            municipality_history_variants=("municipality_key_observed", "nunique"),
            section_type_history_variants=("section_type_code", "nunique"),
        )
    )
    target = panel[panel["election_year"].eq(target_year)].copy()
    previous_keys = set(
        panel.loc[panel["election_year"].eq(feature_year), "section_key_observed"]
    )
    target = target.merge(history_stats, on="section_key_observed", how="left", validate="one_to_one")
    components = lineage_components(edges, target_year)
    if components.empty:
        target["amge_component_id"] = pd.NA
        target["component_members"] = pd.NA
    else:
        target = target.merge(
            components[["section_key_observed", "amge_component_id", "component_members"]],
            on="section_key_observed",
            how="left",
            validate="one_to_one",
        )
    pure_keys = keys_for_status(affected, target_year, eligible=True)
    ambiguous_keys = keys_for_status(affected, target_year, eligible=False)
    ambiguous_components: set[str] = set()
    if not components.empty:
        ambiguous_components = set(
            components.loc[
                components["section_key_observed"].isin(ambiguous_keys), "amge_component_id"
            ]
        )
    target["has_previous_same_type"] = target["section_key_observed"].isin(previous_keys)
    target["prior_lineage_event"] = target["section_key_observed"].isin(pure_keys)
    target["prior_ambiguous_event"] = target["section_key_observed"].isin(ambiguous_keys)
    target["component_has_ambiguous_event"] = target["amge_component_id"].isin(
        ambiguous_components
    )
    target["metadata_stable"] = (
        target["municipality_history_variants"].eq(1)
        & target["section_type_history_variants"].eq(1)
    )
    conditions = [
        target["prior_ambiguous_event"]
        | target["component_has_ambiguous_event"]
        | ~target["metadata_stable"],
        target["prior_lineage_event"] & target["amge_component_id"].notna(),
        target["elections_observed"].lt(3) | ~target["has_previous_same_type"],
    ]
    target["geography_confidence_class"] = np.select(conditions, ["D", "B", "C"], default="A")
    target["target_year"] = target_year
    target["feature_year"] = feature_year
    target["max_geography_event_year_allowed"] = target_year - 1
    return target, components


def build_confidence_classes(
    project_root: Path, affected: pd.DataFrame, edges: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    with (project_root / "configs/evaluation.yaml").open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    panel = pd.read_parquet(project_root / "artifacts/tables/provisional_section_year_totals.parquet")
    classifications = []
    components = []
    for fold in config["folds"]:
        classified, fold_components = _classify_for_target(
            panel,
            affected,
            edges,
            int(fold["target_year"]),
            int(fold["feature_year"]),
        )
        classifications.append(classified)
        if not fold_components.empty:
            components.append(fold_components)
    classes = pd.concat(classifications, ignore_index=True)
    all_components = pd.concat(components, ignore_index=True) if components else pd.DataFrame()
    output = project_root / "artifacts/tables"
    classes.to_parquet(output / "section_confidence_by_election.parquet", index=False)
    current = classes[classes["target_year"].eq(2024)].copy()
    current[
        [
            "section_key_observed",
            "entity_id",
            "municipality_key_observed",
            "section_type_code",
            "elections_observed",
            "has_previous_same_type",
            "prior_lineage_event",
            "prior_ambiguous_event",
            "metadata_stable",
            "amge_component_id",
            "geography_confidence_class",
            "nominal_list",
        ]
    ].to_csv(output / "section_confidence_2024.csv", index=False)
    if not all_components.empty:
        all_components.to_parquet(output / "lineage_components_by_election.parquet", index=False)
    return classes, all_components


def _metrics(
    predictions: pd.DataFrame,
    scenario: str,
    target_year: int,
    all_target_sections: int,
    target_defined_sections: int,
    target_defined_nominal_list: int,
) -> dict[str, Any]:
    frame = predictions.dropna(subset=["actual", "prediction"]).copy()
    error = frame["prediction"] - frame["actual"]
    absolute = error.abs()
    identified_weight = frame["identified_records"].astype(float)
    ln_weight = frame["nominal_list"].astype(float)
    represented = int(frame["target_sections_represented"].sum())
    return {
        "target_year": target_year,
        "scenario": scenario,
        "evaluation_units": len(frame),
        "target_sections_represented": represented,
        "all_target_sections": all_target_sections,
        "target_defined_sections": target_defined_sections,
        "target_defined_share": target_defined_sections / all_target_sections,
        "section_coverage": represented / target_defined_sections,
        "nominal_list_coverage": float(ln_weight.sum() / target_defined_nominal_list),
        "mae": float(absolute.mean()),
        "rmse": float(math.sqrt((error**2).mean())),
        "bias": float(error.mean()),
        "identified_weighted_mae": float(np.average(absolute, weights=identified_weight)),
        "identified_weighted_rmse": float(
            math.sqrt(np.average(error**2, weights=identified_weight))
        ),
        "ln_weighted_mae": float(np.average(absolute, weights=ln_weight)),
        "share_within_5pp": float(absolute.le(0.05).mean()),
    }


def _stable_predictions(target: pd.DataFrame, lag: pd.DataFrame) -> pd.DataFrame:
    stable = target[target["geography_confidence_class"].eq("A")].copy()
    previous = lag[["section_key_observed", "participation"]].rename(
        columns={"participation": "prediction"}
    )
    stable = stable.merge(previous, on="section_key_observed", how="inner", validate="one_to_one")
    stable["actual"] = stable["participation"]
    stable["prediction_source"] = "same_section_previous_same_type"
    stable["evaluation_unit_id"] = stable["section_key_observed"]
    stable["target_sections_represented"] = 1
    return stable


def _lineage_predictions(
    target: pd.DataFrame,
    lag: pd.DataFrame,
    stable: pd.DataFrame,
    component_membership: pd.DataFrame,
) -> pd.DataFrame:
    lineage_target = target[
        target["geography_confidence_class"].eq("B")
        & target["amge_component_id"].notna()
    ].copy()
    if lineage_target.empty:
        return stable.copy()
    member_map = component_membership[
        ["section_key_observed", "amge_component_id"]
    ].dropna().drop_duplicates()
    target_agg = _aggregate(lineage_target, ["amge_component_id"])
    lag_members = lag.merge(member_map, on="section_key_observed", how="inner", validate="many_to_one")
    lag_agg = _aggregate(lag_members, ["amge_component_id"])[
        ["amge_component_id", "participation"]
    ].rename(columns={"participation": "prediction"})
    lineage = target_agg.merge(lag_agg, on="amge_component_id", how="inner", validate="one_to_one")
    lineage["actual"] = lineage["participation"]
    lineage["prediction_source"] = "official_lineage_component_previous_same_type"
    lineage["evaluation_unit_id"] = lineage["amge_component_id"]
    columns = sorted(set(stable.columns) & set(lineage.columns))
    required = [
        "evaluation_unit_id",
        "target_sections_represented",
        "nominal_list",
        "identified_records",
        "actual",
        "prediction",
        "prediction_source",
    ]
    columns = required + [column for column in columns if column not in required]
    return pd.concat([stable[columns], lineage[columns]], ignore_index=True)


def _fallback_predictions(
    target: pd.DataFrame, lag: pd.DataFrame, component_membership: pd.DataFrame
) -> pd.DataFrame:
    result = target.copy()
    section_lag = lag.set_index("section_key_observed")["participation"]
    result["prediction"] = result["section_key_observed"].map(section_lag)
    result["prediction_source"] = np.where(
        result["prediction"].notna(), "same_section_previous_same_type", pd.NA
    )

    component_map = component_membership[
        ["section_key_observed", "amge_component_id"]
    ].dropna().drop_duplicates()
    if not component_map.empty:
        component_lag = lag.merge(
            component_map, on="section_key_observed", how="inner", validate="many_to_one"
        )
        component_lag = _aggregate(component_lag, ["amge_component_id"]).set_index(
            "amge_component_id"
        )["participation"]
        missing = (
            result["prediction"].isna()
            & result["amge_component_id"].notna()
            & result["geography_confidence_class"].eq("B")
        )
        result.loc[missing, "prediction"] = result.loc[missing, "amge_component_id"].map(
            component_lag
        )
        filled = missing & result["prediction"].notna()
        result.loc[filled, "prediction_source"] = "official_lineage_component_previous_same_type"

    municipality_lag = _aggregate(lag, ["municipality_key_observed"]).set_index(
        "municipality_key_observed"
    )["participation"]
    missing = result["prediction"].isna()
    result.loc[missing, "prediction"] = result.loc[missing, "municipality_key_observed"].map(
        municipality_lag
    )
    filled = missing & result["prediction"].notna()
    result.loc[filled, "prediction_source"] = "target_municipality_previous_same_type"

    entity_lag = _aggregate(lag, ["entity_id"]).set_index("entity_id")["participation"]
    missing = result["prediction"].isna()
    result.loc[missing, "prediction"] = result.loc[missing, "entity_id"].map(entity_lag)
    filled = missing & result["prediction"].notna()
    result.loc[filled, "prediction_source"] = "target_entity_previous_same_type"

    national = float(lag["voted"].sum() / (lag["voted"].sum() + lag["did_not_vote"].sum()))
    missing = result["prediction"].isna()
    result.loc[missing, "prediction"] = national
    result.loc[missing, "prediction_source"] = "national_previous_same_type"
    result["actual"] = result["participation"]
    result["evaluation_unit_id"] = result["section_key_observed"]
    result["target_sections_represented"] = 1
    return result


def _variable_lineage(project_root: Path) -> pd.DataFrame:
    with (project_root / "configs/features.yaml").open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    rows = []
    for name, feature in config["features"].items():
        rows.append(
            {
                "variable": name,
                "role": feature["role"],
                "description": feature["description"],
                "source_columns": "|".join(feature["source_columns"]),
                "available_from": feature["available_from"],
                "transformation": feature["transformation"],
                "leakage_risk": feature["leakage_risk"],
                "missing_policy": feature["missing_policy"],
                "implementation": "src/radar27/modeling/lineage_evaluation.py",
            }
        )
    result = pd.DataFrame(rows)
    result.to_csv(project_root / "artifacts/tables/variable_lineage.csv", index=False)
    return result


def evaluate_scenarios(
    project_root: Path,
    classes: pd.DataFrame,
    components: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    with (project_root / "configs/evaluation.yaml").open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    panel = pd.read_parquet(project_root / "artifacts/tables/provisional_section_year_totals.parquet")
    metrics_rows: list[dict[str, Any]] = []
    predictions: list[pd.DataFrame] = []
    started = time.perf_counter()
    for fold in config["folds"]:
        target_year = int(fold["target_year"])
        feature_year = int(fold["feature_year"])
        target = classes[classes["target_year"].eq(target_year)].copy()
        lag = panel[panel["election_year"].eq(feature_year)].copy()
        component_membership = components[components["target_year"].eq(target_year)].copy()
        all_target_sections = target["section_key_observed"].nunique()
        defined_target = target[target["participation"].notna()]
        target_defined_sections = defined_target["section_key_observed"].nunique()
        target_defined_nominal = int(defined_target["nominal_list"].sum())

        stable = _stable_predictions(target, lag)
        lineage = _lineage_predictions(target, lag, stable, component_membership)
        fallback = _fallback_predictions(target, lag, component_membership)
        scenario_frames = {
            "stable_only": stable,
            "stable_plus_lineage": lineage,
            "hierarchical_fallback": fallback,
        }
        for scenario, frame in scenario_frames.items():
            frame = frame.copy()
            frame["scenario"] = scenario
            frame["target_year"] = target_year
            frame["feature_year"] = feature_year
            frame["election_family"] = fold["election_family"]
            frame["evidence_status"] = fold["evidence_status"]
            keep = [
                "scenario",
                "target_year",
                "feature_year",
                "election_family",
                "evidence_status",
                "evaluation_unit_id",
                "target_sections_represented",
                "nominal_list",
                "identified_records",
                "actual",
                "prediction",
                "prediction_source",
            ]
            if "geography_confidence_class" in frame:
                keep.append("geography_confidence_class")
            predictions.append(frame[keep])
            metrics_rows.append(
                {
                    **_metrics(
                        frame,
                        scenario,
                        target_year,
                        all_target_sections,
                        target_defined_sections,
                        target_defined_nominal,
                    ),
                    "feature_year": feature_year,
                    "election_family": fold["election_family"],
                    "evidence_status": fold["evidence_status"],
                }
            )

    prediction_frame = pd.concat(predictions, ignore_index=True)
    metrics = pd.DataFrame(metrics_rows).sort_values(["target_year", "scenario"])
    fallback = prediction_frame[
        prediction_frame["scenario"].eq("hierarchical_fallback")
        & prediction_frame["actual"].notna()
        & prediction_frame["prediction"].notna()
    ].copy()
    fallback["absolute_error"] = (fallback["prediction"] - fallback["actual"]).abs()
    error_by_class = (
        fallback.groupby(["target_year", "geography_confidence_class"], as_index=False)
        .agg(
            sections=("evaluation_unit_id", "count"),
            nominal_list=("nominal_list", "sum"),
            mae=("absolute_error", "mean"),
            median_absolute_error=("absolute_error", "median"),
        )
    )
    source_counts = (
        fallback.groupby(["target_year", "prediction_source"], as_index=False)
        .agg(sections=("evaluation_unit_id", "count"), nominal_list=("nominal_list", "sum"))
    )
    output = project_root / "artifacts/tables"
    prediction_frame.to_parquet(output / "backtest_predictions.parquet", index=False)
    metrics.to_csv(output / "backtest_metrics.csv", index=False)
    error_by_class.to_csv(output / "backtest_errors_by_class.csv", index=False)
    source_counts.to_csv(output / "fallback_source_counts.csv", index=False)
    _variable_lineage(project_root)
    metrics["elapsed_total_seconds"] = round(time.perf_counter() - started, 3)
    metrics.to_csv(output / "backtest_metrics.csv", index=False)
    return metrics, prediction_frame, error_by_class, source_counts
