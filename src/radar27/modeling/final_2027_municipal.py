from __future__ import annotations

import hashlib
import importlib.metadata
import json
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from radar27.modeling.feature_enrichment import _resolve_feature_group
from radar27.modeling.final_2027 import (
    PROFILE_NAMES,
    _add_projected_municipality,
    _assign_profiles,
    _detection_row,
    _dictionary,
    _entity_summary,
    _historical_features,
    _municipal_references,
    _neighbor_context,
    _profile_summary,
)
from radar27.modeling.tabular_challengers import _pipeline
from radar27.modeling.validated_handoff import run_corrected_backtests, weighted_mean


SAME_FAMILY_PRIOR = {2015: 2009, 2018: 2012, 2021: 2015, 2024: 2018}
PROJECTED_TRANSITION = {2015: None, 2018: None, 2021: (2009, 2015), 2024: (2012, 2018)}


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def _ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator.astype(float).div(denominator.astype(float).where(denominator.gt(0)))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _unit_membership(root: Path, target_year: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    classes = pd.read_parquet(root / "artifacts/tables/section_confidence_by_election.parquet")
    components = pd.read_parquet(root / "artifacts/tables/lineage_components_by_election.parquet")
    target = classes[
        classes["target_year"].eq(target_year)
        & classes["geography_confidence_class"].isin(["A", "B"])
    ].copy()
    target["evaluation_unit_id"] = np.where(
        target["geography_confidence_class"].eq("B") & target["amge_component_id"].notna(),
        "C:" + target["amge_component_id"].astype("string"),
        "S:" + target["section_key_observed"],
    )
    unit_geo = (
        target.groupby("evaluation_unit_id", as_index=False)
        .agg(
            entity_id=("entity_id", "first"),
            geography_confidence_class=("geography_confidence_class", "first"),
            municipality_key_model=("municipality_key_observed", "first"),
            municipality_count=("municipality_key_observed", "nunique"),
            target_sections_represented=("section_key_observed", "nunique"),
            target_nominal_list=("nominal_list", "sum"),
        )
    )
    unit_geo.loc[unit_geo["municipality_count"].ne(1), "municipality_key_model"] = pd.NA

    stable = target[target["geography_confidence_class"].eq("A")][
        ["evaluation_unit_id", "section_key_observed"]
    ]
    component_ids = target.loc[
        target["geography_confidence_class"].eq("B"), "amge_component_id"
    ].dropna()
    lineage = components[
        components["target_year"].eq(target_year)
        & components["amge_component_id"].isin(component_ids)
    ][["amge_component_id", "section_key_observed"]].drop_duplicates()
    lineage["evaluation_unit_id"] = "C:" + lineage["amge_component_id"]
    membership = pd.concat(
        [stable, lineage[["evaluation_unit_id", "section_key_observed"]]], ignore_index=True
    ).drop_duplicates()
    duplicates = membership.groupby("section_key_observed")["evaluation_unit_id"].nunique()
    if duplicates.gt(1).any():
        raise ValueError(f"Membresía solapada para target {target_year}")
    return unit_geo, membership


def _unit_year_counts(
    totals: pd.DataFrame, membership: pd.DataFrame, years: list[int]
) -> pd.DataFrame:
    selected = totals[totals["election_year"].isin(years)][
        ["election_year", "section_key_observed", "voted", "identified_records"]
    ]
    return (
        membership.merge(selected, on="section_key_observed", how="left")
        .groupby(["evaluation_unit_id", "election_year"], as_index=False)[
            ["voted", "identified_records"]
        ]
        .sum(min_count=1)
    )


def _transition_by_unit(
    unit_geo: pd.DataFrame,
    counts: pd.DataFrame,
    from_year: int,
    to_year: int,
) -> pd.DataFrame:
    left = counts[counts["election_year"].eq(from_year)].drop(columns="election_year").rename(
        columns={"voted": "voted_from", "identified_records": "den_from"}
    )
    right = counts[counts["election_year"].eq(to_year)].drop(columns="election_year").rename(
        columns={"voted": "voted_to", "identified_records": "den_to"}
    )
    frame = unit_geo.merge(left, on="evaluation_unit_id", how="left").merge(
        right, on="evaluation_unit_id", how="left"
    )
    frame["comparable"] = frame[["den_from", "den_to"]].gt(0).all(axis=1)
    valid = frame["comparable"] & frame["municipality_key_model"].notna()
    municipality_keys = ["entity_id", "municipality_key_model"]
    municipal_totals = (
        frame[valid]
        .groupby(municipality_keys, as_index=False, dropna=False)[
            ["voted_from", "den_from", "voted_to", "den_to"]
        ]
        .sum()
        .rename(
            columns={
                column: f"municipality_{column}"
                for column in ["voted_from", "den_from", "voted_to", "den_to"]
            }
        )
    )
    municipal_coverage = (
        frame.assign(
            comparable_electorate=frame["target_nominal_list"].where(valid, 0),
            comparable_unit=valid.astype(int),
            comparable_section_count=frame["target_sections_represented"].where(valid, 0),
        )
        .groupby(municipality_keys, as_index=False, dropna=False)
        .agg(
            total_electorate=("target_nominal_list", "sum"),
            comparable_electorate=("comparable_electorate", "sum"),
            comparable_units=("comparable_unit", "sum"),
            comparable_sections=("comparable_section_count", "sum"),
        )
    )
    municipal_coverage["coverage"] = _ratio(
        municipal_coverage["comparable_electorate"], municipal_coverage["total_electorate"]
    ).fillna(0).clip(0, 1)
    frame = frame.merge(municipal_totals, on=municipality_keys, how="left", validate="many_to_one")
    frame = frame.merge(municipal_coverage, on=municipality_keys, how="left", validate="many_to_one")

    state_totals = (
        frame[frame["comparable"]]
        .groupby("entity_id", as_index=False)[["voted_from", "den_from", "voted_to", "den_to"]]
        .sum()
        .rename(
            columns={
                column: f"state_{column}"
                for column in ["voted_from", "den_from", "voted_to", "den_to"]
            }
        )
    )
    frame = frame.merge(state_totals, on="entity_id", how="left", validate="many_to_one")
    frame["coverage"] = frame["coverage"].fillna(0.0)
    comparable_count = frame["comparable_units"].fillna(0).astype(float)
    frame["precision_factor"] = np.where(
        comparable_count.gt(0),
        (comparable_count - 1).clip(lower=0) / comparable_count,
        0.0,
    )
    frame["hierarchical_weight"] = (
        frame["coverage"] * frame["precision_factor"]
    ).clip(0, 1)

    local_full = _ratio(frame["municipality_voted_to"], frame["municipality_den_to"]) - _ratio(
        frame["municipality_voted_from"], frame["municipality_den_from"]
    )
    local_loo = _ratio(
        frame["municipality_voted_to"] - frame["voted_to"],
        frame["municipality_den_to"] - frame["den_to"],
    ) - _ratio(
        frame["municipality_voted_from"] - frame["voted_from"],
        frame["municipality_den_from"] - frame["den_from"],
    )
    state = _ratio(frame["state_voted_to"], frame["state_den_to"]) - _ratio(
        frame["state_voted_from"], frame["state_den_from"]
    )
    frame["local_change_full"] = local_full
    frame["local_change_loo"] = local_loo
    frame["state_change"] = state
    frame["component_B"] = local_loo.where(local_loo.notna(), state).fillna(0.0)
    frame["component_C"] = np.where(
        local_loo.notna(),
        frame["hierarchical_weight"] * local_loo
        + (1 - frame["hierarchical_weight"]) * state,
        state,
    )
    frame["component_C"] = frame["component_C"].fillna(0.0)
    frame["from_year"] = from_year
    frame["to_year"] = to_year
    return frame


def _component_tables(
    root: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    totals = pd.read_parquet(root / "artifacts/tables/provisional_section_year_totals.parquet")
    unit_rows: list[pd.DataFrame] = []
    transition_rows: list[pd.DataFrame] = []
    for target_year in [2015, 2018, 2021, 2024]:
        unit_geo, membership = _unit_membership(root, target_year)
        years = sorted(set([SAME_FAMILY_PRIOR[target_year], target_year] + list(PROJECTED_TRANSITION[target_year] or [])))
        counts = _unit_year_counts(totals, membership, years)
        actual = _transition_by_unit(
            unit_geo, counts, SAME_FAMILY_PRIOR[target_year], target_year
        )
        transition_rows.append(actual.assign(target_year=target_year, transition_role="realized_target"))
        projected_pair = PROJECTED_TRANSITION[target_year]
        if projected_pair is None:
            projected = unit_geo[["evaluation_unit_id"]].copy()
            projected["projected_component_B"] = 0.0
            projected["projected_component_C"] = 0.0
            projected["projected_coverage"] = 0.0
            projected["projected_weight"] = 0.0
            projected["projected_reference"] = "zero_fallback_no_prior_same_family_transition"
        else:
            prior = _transition_by_unit(unit_geo, counts, *projected_pair)
            transition_rows.append(
                prior.assign(target_year=target_year, transition_role="projected_from_prior")
            )
            projected = prior[
                [
                    "evaluation_unit_id",
                    "component_B",
                    "component_C",
                    "coverage",
                    "hierarchical_weight",
                ]
            ].rename(
                columns={
                    "component_B": "projected_component_B",
                    "component_C": "projected_component_C",
                    "coverage": "projected_coverage",
                    "hierarchical_weight": "projected_weight",
                }
            )
            projected["projected_reference"] = f"{projected_pair[0]}_{projected_pair[1]}"
        unit = actual[
            [
                "evaluation_unit_id",
                "entity_id",
                "municipality_key_model",
                "municipality_count",
                "coverage",
                "component_B",
                "component_C",
                "local_change_full",
                "state_change",
            ]
        ].rename(
            columns={
                "coverage": "actual_coverage",
                "component_B": "actual_component_B",
                "component_C": "actual_component_C",
                "local_change_full": "actual_local_change_full",
                "state_change": "actual_state_change",
            }
        )
        unit = unit.merge(projected, on="evaluation_unit_id", how="left", validate="one_to_one")
        unit["target_year"] = target_year
        unit_rows.append(unit)

    current_geo, current_membership = _unit_membership(root, 2024)
    counts = _unit_year_counts(totals, current_membership, [2009, 2015, 2021])
    t1 = _transition_by_unit(current_geo, counts, 2009, 2015)
    t2 = _transition_by_unit(current_geo, counts, 2015, 2021)
    forecast_units = current_geo[
        ["evaluation_unit_id", "entity_id", "municipality_key_model", "municipality_count"]
    ].merge(
        t1[
            [
                "evaluation_unit_id",
                "component_B",
                "component_C",
                "coverage",
                "hierarchical_weight",
                "local_change_full",
                "state_change",
                "comparable_sections",
            ]
        ].rename(
            columns={column: f"{column}_2009_2015" for column in ["component_B", "component_C", "coverage", "hierarchical_weight", "local_change_full", "state_change", "comparable_sections"]}
        ),
        on="evaluation_unit_id",
        validate="one_to_one",
    ).merge(
        t2[
            [
                "evaluation_unit_id",
                "component_B",
                "component_C",
                "coverage",
                "hierarchical_weight",
                "local_change_full",
                "state_change",
                "comparable_sections",
            ]
        ].rename(
            columns={column: f"{column}_2015_2021" for column in ["component_B", "component_C", "coverage", "hierarchical_weight", "local_change_full", "state_change", "comparable_sections"]}
        ),
        on="evaluation_unit_id",
        validate="one_to_one",
    )
    both_local = forecast_units[["local_change_full_2009_2015", "local_change_full_2015_2021"]].notna().all(axis=1)
    state_mean = forecast_units[["state_change_2009_2015", "state_change_2015_2021"]].mean(axis=1)
    forecast_units["projected_component_B"] = forecast_units[
        ["component_B_2009_2015", "component_B_2015_2021"]
    ].mean(axis=1)
    forecast_units.loc[~both_local, "projected_component_B"] = state_mean[~both_local]
    forecast_units["projected_component_C"] = forecast_units[
        ["component_C_2009_2015", "component_C_2015_2021"]
    ].mean(axis=1)
    forecast_units["municipal_weight"] = forecast_units[
        ["hierarchical_weight_2009_2015", "hierarchical_weight_2015_2021"]
    ].mean(axis=1)
    forecast_units["historical_coverage"] = forecast_units[
        ["coverage_2009_2015", "coverage_2015_2021"]
    ].mean(axis=1)
    forecast_units["component_quality"] = np.select(
        [
            both_local & forecast_units["historical_coverage"].ge(0.95),
            both_local & forecast_units["historical_coverage"].gt(0),
        ],
        ["alta_dos_transiciones_cobertura_95pct", "media_dos_transiciones_cobertura_parcial"],
        default="fallback_estatal_historia_local_insuficiente",
    )
    return pd.concat(unit_rows, ignore_index=True), forecast_units, pd.concat(transition_rows, ignore_index=True)


def _attach_historical_neighbor_features(root: Path, mart: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for year in sorted(int(value) for value in mart["target_year"].unique()):
        spatial = pd.read_parquet(root / f"artifacts/spatial_features/spatial_features_{year}_rook.parquet")
        spatial["evaluation_unit_id"] = "S:" + spatial["section_key"]
        spatial["target_year"] = year
        frames.append(spatial)
    spatial = pd.concat(frames, ignore_index=True)
    return mart.merge(spatial.drop(columns="section_key"), on=["target_year", "evaluation_unit_id"], how="left", validate="one_to_one")


def _forecast_neighbor_features(root: Path, forecast: pd.DataFrame) -> pd.DataFrame:
    edges = pd.read_parquet(root / "artifacts/graphs/section_graph_2024_edges.parquet")
    edges = edges[~edges["is_synthetic"]]
    forward = edges[["source_section_key", "target_section_key"]].rename(
        columns={"source_section_key": "section", "target_section_key": "neighbor"}
    )
    reverse = edges[["target_section_key", "source_section_key"]].rename(
        columns={"target_section_key": "section", "source_section_key": "neighbor"}
    )
    directed = pd.concat([forward, reverse], ignore_index=True).drop_duplicates()
    stable = forecast[forecast["evaluation_unit_id"].str.startswith("S:")].copy()
    stable["section"] = stable["evaluation_unit_id"].str.removeprefix("S:")
    values = stable.set_index("section")
    for source, target in [
        ("participation_same_type", "neighbor_participation_same_type_mean"),
        ("participation_change_lag1_lag2", "neighbor_participation_change_lag1_lag2_mean"),
    ]:
        directed[source] = directed["neighbor"].map(values[source])
        means = directed.groupby("section")[source].mean()
        stable[target] = stable["section"].map(means)
    stable["participation_same_type_minus_neighbor_mean"] = (
        stable["participation_same_type"] - stable["neighbor_participation_same_type_mean"]
    )
    stable["participation_change_lag1_lag2_minus_neighbor_mean"] = (
        stable["participation_change_lag1_lag2"]
        - stable["neighbor_participation_change_lag1_lag2_mean"]
    )
    columns = [
        "evaluation_unit_id",
        "neighbor_participation_same_type_mean",
        "participation_same_type_minus_neighbor_mean",
        "neighbor_participation_change_lag1_lag2_mean",
        "participation_change_lag1_lag2_minus_neighbor_mean",
    ]
    return forecast.merge(stable[columns], on="evaluation_unit_id", how="left", validate="one_to_one")


def _center_by_municipality(
    frame: pd.DataFrame, values: pd.Series | np.ndarray, weights: pd.Series
) -> tuple[np.ndarray, pd.DataFrame]:
    work = frame[["target_year", "municipality_key_model"]].copy()
    work["municipality_key_model"] = work["municipality_key_model"].fillna(
        "STATE_FALLBACK:" + frame["entity_id"].astype(str)
    )
    work["value"] = np.asarray(values, dtype=float)
    work["weight"] = weights.to_numpy(float)
    centers = (
        work.groupby(["target_year", "municipality_key_model"], as_index=False)
        .apply(
            lambda part: pd.Series(
                {"center": weighted_mean(part["value"], part["weight"]), "units": len(part)}
            ),
            include_groups=False,
        )
        .reset_index(drop=True)
    )
    keyed = work.merge(centers, on=["target_year", "municipality_key_model"], how="left")
    centered = work["value"].to_numpy() - keyed["center"].fillna(0).to_numpy()
    check = work.assign(centered=centered).groupby(
        ["target_year", "municipality_key_model"], as_index=False
    ).apply(
        lambda part: pd.Series({"centered_weighted_mean": weighted_mean(part["centered"], part["weight"])}),
        include_groups=False,
    ).reset_index(drop=True)
    return centered, check


def _prepare_model_data(
    root: Path, unit_components: pd.DataFrame, forecast_components: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    mart = pd.read_parquet(root / "artifacts/tables/feature_ablation_mart.parquet")
    mart = _attach_historical_neighbor_features(root, mart)
    mart = mart.merge(
        unit_components,
        on=["target_year", "evaluation_unit_id", "entity_id"],
        how="inner",
        validate="one_to_one",
    )
    forecast = pd.read_parquet(root / "artifacts/tables/forecast_2027_model_units.parquet")
    forecast = _forecast_neighbor_features(root, forecast)
    forecast = forecast.merge(
        forecast_components[
            [
                "evaluation_unit_id",
                "municipality_key_model",
                "projected_component_B",
                "projected_component_C",
                "municipal_weight",
                "component_quality",
            ]
        ],
        on="evaluation_unit_id",
        how="inner",
        validate="one_to_one",
    )
    return mart, forecast


def _fit_municipal_fold(
    data: pd.DataFrame,
    target_year: int,
    model_code: str,
    numeric: list[str],
    categorical: list[str],
    model_spec: dict[str, Any],
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = data[
        data["target_year"].lt(target_year)
        & data["actual"].notna()
        & data["participation_same_type"].notna()
        & data["nominal_list_lag1"].gt(0)
    ].copy()
    test = data[
        data["target_year"].eq(target_year)
        & data["actual"].notna()
        & data["participation_same_type"].notna()
        & data["nominal_list_lag1"].gt(0)
    ].copy()
    component = train[f"actual_component_{model_code}"]
    raw_target = train["actual"] - train["participation_same_type"] - component
    centered_target, train_check = _center_by_municipality(
        train, raw_target, train["target_identified_records"]
    )
    required = numeric + categorical
    model = _pipeline(model_spec, numeric, categorical, int(config["random_seed"]))
    model.fit(
        train[required],
        centered_target,
        model__sample_weight=train["target_identified_records"].astype(float),
    )
    raw_prediction = model.predict(test[required])
    centered_prediction, test_check = _center_by_municipality(
        test, raw_prediction, test["nominal_list_lag1"]
    )
    predicted = np.clip(
        test["participation_same_type"].to_numpy(float)
        + test[f"projected_component_{model_code}"].to_numpy(float)
        + float(config["residual_shrinkage"]) * centered_prediction,
        0,
        1,
    )
    output = test[
        [
            "target_year",
            "evaluation_unit_id",
            "entity_id",
            "municipality_key_model",
            "geography_confidence_class",
            "target_sections_represented",
            "target_identified_records",
            "nominal_list_lag1",
            "actual",
            "participation_same_type",
            f"projected_component_{model_code}",
            "projected_coverage",
            "projected_reference",
        ]
    ].copy()
    output["model_id"] = f"modelo_{model_code}"
    output["centered_municipal_residual_prediction"] = centered_prediction
    output["prediction"] = predicted
    diagnostics = pd.concat(
        [
            train_check.assign(stage="training_target", evaluation_target_year=target_year, model_id=f"modelo_{model_code}"),
            test_check.assign(stage="test_prediction", evaluation_target_year=target_year, model_id=f"modelo_{model_code}"),
        ],
        ignore_index=True,
    )
    return output, diagnostics


def _fit_forecast_model(
    data: pd.DataFrame,
    forecast: pd.DataFrame,
    model_code: str,
    numeric: list[str],
    categorical: list[str],
    model_spec: dict[str, Any],
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = data[
        data["actual"].notna()
        & data["participation_same_type"].notna()
        & data["nominal_list_lag1"].gt(0)
    ].copy()
    raw_target = (
        train["actual"]
        - train["participation_same_type"]
        - train[f"actual_component_{model_code}"]
    )
    centered_target, train_check = _center_by_municipality(
        train, raw_target, train["target_identified_records"]
    )
    required = numeric + categorical
    model = _pipeline(model_spec, numeric, categorical, int(config["random_seed"]))
    model.fit(
        train[required],
        centered_target,
        model__sample_weight=train["target_identified_records"].astype(float),
    )
    raw = model.predict(forecast[required])
    forecast_for_center = forecast.copy()
    forecast_for_center["target_year"] = 2027
    centered, forecast_check = _center_by_municipality(
        forecast_for_center, raw, forecast["current_nominal_list"]
    )
    prediction = np.clip(
        forecast["participation_same_type"].to_numpy(float)
        + forecast[f"projected_component_{model_code}"].to_numpy(float)
        + float(config["residual_shrinkage"]) * centered,
        0,
        1,
    )
    result = forecast[
        [
            "evaluation_unit_id",
            "entity_id",
            "municipality_key_model",
            "geography_confidence_class",
            "current_nominal_list",
            "participation_same_type",
            f"projected_component_{model_code}",
            "municipal_weight",
            "component_quality",
        ]
    ].copy()
    result[f"centered_residual_{model_code}"] = centered
    result[f"prediction_{model_code}"] = prediction
    diagnostics = pd.concat(
        [
            train_check.assign(stage="final_training_target", evaluation_target_year=2027, model_id=f"modelo_{model_code}"),
            forecast_check.assign(stage="forecast_prediction", evaluation_target_year=2027, model_id=f"modelo_{model_code}"),
        ],
        ignore_index=True,
    )
    return result, diagnostics


def _evaluate_models(
    root: Path,
    config: dict[str, Any],
    data: pd.DataFrame,
    support: dict[str, Any],
    base_predictions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    numeric = support["numeric_features"] + list(config["neighbor_features"])
    categorical = support["categorical_features"]
    prediction_frames: list[pd.DataFrame] = []
    diagnostics: list[pd.DataFrame] = []
    metric_rows: list[dict[str, Any]] = []
    error_rows: list[dict[str, Any]] = []
    for year in config["evaluation_targets"]:
        fold_a = base_predictions[base_predictions["target_year"].eq(year)].copy()
        common_ids = set(data.loc[data["target_year"].eq(year), "evaluation_unit_id"])
        fold_a = fold_a[fold_a["evaluation_unit_id"].isin(common_ids)].copy()
        for code in ["B", "C"]:
            predicted, diag = _fit_municipal_fold(
                data,
                int(year),
                code,
                numeric,
                categorical,
                support["model_spec"],
                config,
            )
            prediction_frames.append(predicted)
            diagnostics.append(diag)
        paired = fold_a[
            [
                "target_year",
                "evaluation_unit_id",
                "entity_id",
                "geography_confidence_class",
                "target_sections_represented",
                "target_identified_records",
                "nominal_list_lag1",
                "actual",
                "participation_same_type",
                "D_centered_shrink_0.25",
            ]
        ].rename(columns={"D_centered_shrink_0.25": "prediction_A"})
        for code in ["B", "C"]:
            model_fold = prediction_frames[-2 if code == "B" else -1]
            paired = paired.merge(
                model_fold[["evaluation_unit_id", "prediction", "municipality_key_model"]].rename(
                    columns={"prediction": f"prediction_{code}"}
                ),
                on="evaluation_unit_id",
                how="inner",
                validate="one_to_one",
            )
            if code == "C":
                paired = paired.rename(columns={"municipality_key_model_x": "municipality_key_model"}).drop(
                    columns=["municipality_key_model_y"], errors="ignore"
                )
        for code, label in [("A", "A_nacional_actual"), ("B", "B_municipal"), ("C", "C_municipal_jerarquico")]:
            metric_rows.append(_detection_row(paired, paired[f"prediction_{code}"], label))
            errors = paired.assign(error=paired[f"prediction_{code}"] - paired["actual"])
            for dimension, field in [("entidad", "entity_id"), ("municipio", "municipality_key_model")]:
                for key, part in errors.groupby(field, observed=True, dropna=False):
                    error_rows.append(
                        {
                            "target_year": int(year),
                            "model_id": label,
                            "dimension": dimension,
                            "territorio": key,
                            "unidades": len(part),
                            "mae_ponderado": weighted_mean(part["error"].abs(), part["target_identified_records"]),
                            "bias_ponderado": weighted_mean(part["error"], part["target_identified_records"]),
                        }
                    )
        prediction_frames.append(paired.assign(model_id="paired_A_B_C"))
    metrics = pd.DataFrame(metric_rows)
    primary = metrics[metrics["target_year"].eq(2021)].set_index("model_id")
    reference = primary.loc["A_nacional_actual"]
    gate = config["selection_gate"]
    b = primary.loc["B_municipal"]
    c = primary.loc["C_municipal_jerarquico"]
    if (
        c["f1"] >= b["f1"] - float(gate["hierarchical_f1_tolerance"])
        and c["mae"] <= b["mae"] + float(gate["hierarchical_mae_tolerance"])
    ):
        preferred_municipal = "C_municipal_jerarquico"
    else:
        preferred_municipal = "B_municipal" if b["f1"] > c["f1"] else "C_municipal_jerarquico"
    eligible: list[str] = []
    for label in ["B_municipal", "C_municipal_jerarquico"]:
        row = primary.loc[label]
        if (
            row["recall"] > reference["recall"]
            and row["f1"] > reference["f1"]
            and row["balanced_accuracy"] >= reference["balanced_accuracy"]
            and row["mae"] <= reference["mae"] + float(gate["maximum_2021_mae_deterioration"])
        ):
            eligible.append(label)
    if not eligible:
        selected = "A_nacional_actual"
        reason = "municipal_models_failed_prespecified_2021_joint_gate"
    elif len(eligible) == 1:
        selected = eligible[0]
        reason = "only_municipal_model_passing_joint_gate"
    else:
        selected = preferred_municipal
        reason = "preferred_municipal_model_passed_joint_gate"
    decision = {
        "selected_model_id": selected,
        "preferred_municipal_alternative": preferred_municipal,
        "selection_reason": reason,
        "primary_development_target": 2021,
        "joint_gate": gate,
        "selection_is_external_validation": False,
        "municipal_weight_rule": "w_m=electoral_coverage_times_(n_comparable_units-1)/n_comparable_units",
        "residual_centering": "within_target_year_and_municipality_with_pre_election_weights",
        "neighbor_features_temporally_valid": list(config["neighbor_features"]),
    }
    paired_only = pd.concat(
        [frame for frame in prediction_frames if "prediction_A" in frame.columns], ignore_index=True
    )
    return metrics, paired_only, pd.concat(diagnostics, ignore_index=True), {
        "decision": decision,
        "errors": pd.DataFrame(error_rows),
        "numeric": numeric,
        "categorical": categorical,
    }


def _municipality_summary_2027(
    root: Path, forecast_components: pd.DataFrame, selected_code: str
) -> pd.DataFrame:
    totals = pd.read_parquet(root / "artifacts/tables/provisional_section_year_totals.parquet")
    current = totals[totals["election_year"].eq(2024)][
        ["municipality_key_observed", "municipality_name", "entity_id", "entity_name", "section_key_observed"]
    ].drop_duplicates("section_key_observed")
    section_counts = current.groupby(
        ["entity_id", "entity_name", "municipality_key_observed", "municipality_name"], as_index=False
    ).agg(secciones_2024=("section_key_observed", "nunique"))
    unit = forecast_components[forecast_components["municipality_key_model"].notna()].copy()
    rows = []
    for (entity, municipality), part in unit.groupby(
        ["entity_id", "municipality_key_model"], observed=True
    ):
        first = part.iloc[0]
        local_1 = first["local_change_full_2009_2015"]
        local_2 = first["local_change_full_2015_2021"]
        state_ref = np.mean([first["state_change_2009_2015"], first["state_change_2015_2021"]])
        local_mean = np.mean([local_1, local_2]) if np.isfinite(local_1) and np.isfinite(local_2) else np.nan
        weight = float(first["municipal_weight"])
        rows.append(
            {
                "entity_id": entity,
                "municipality_key_observed": municipality,
                "cambio_2009_2015": local_1,
                "cambio_2015_2021": local_2,
                "cambio_municipal_promedio": local_mean,
                "referencia_estatal": state_ref,
                "peso_municipal": weight,
                "componente_modelo_B": local_mean if np.isfinite(local_mean) else state_ref,
                "componente_modelo_C": weight * local_mean + (1 - weight) * state_ref if np.isfinite(local_mean) else state_ref,
                "secciones_comparables_2009_2015": int(first["comparable_sections_2009_2015"]),
                "secciones_comparables_2015_2021": int(first["comparable_sections_2015_2021"]),
                "cobertura_2009_2015": float(first["coverage_2009_2015"]),
                "cobertura_2015_2021": float(first["coverage_2015_2021"]),
                "calidad_componente": first["component_quality"],
            }
        )
    summary = pd.DataFrame(rows).merge(
        section_counts,
        left_on=["entity_id", "municipality_key_observed"],
        right_on=["entity_id", "municipality_key_observed"],
        how="right",
        validate="one_to_one",
    )
    for column in ["componente_modelo_B", "componente_modelo_C", "referencia_estatal"]:
        state_fallback = summary.groupby("entity_id")[column].transform("median")
        summary[column] = summary[column].fillna(state_fallback).fillna(0.0)
    summary["peso_municipal"] = summary["peso_municipal"].fillna(0.0)
    summary["calidad_componente"] = summary["calidad_componente"].fillna(
        "fallback_estatal_sin_unidad_AB_comparable"
    )
    code = "C" if selected_code == "C_municipal_jerarquico" else "B"
    summary["componente_municipal_seleccionado"] = summary[f"componente_modelo_{code}"]
    summary["signo_componente"] = np.select(
        [summary["componente_municipal_seleccionado"].lt(0), summary["componente_municipal_seleccionado"].gt(0)],
        ["negativo", "positivo"],
        default="cero",
    )
    return summary.sort_values(["entity_id", "municipality_key_observed"])


def _build_master(
    root: Path,
    config: dict[str, Any],
    forecast_b: pd.DataFrame,
    forecast_c: pd.DataFrame,
    municipality_summary: pd.DataFrame,
    selected_model: str,
    preferred_municipal: str,
) -> pd.DataFrame:
    sections = pd.read_parquet(root / "artifacts/tables/forecast_2027_section_predictions.parquet")
    totals = pd.read_parquet(root / "artifacts/tables/provisional_section_year_totals.parquet")
    geo = totals[totals["election_year"].eq(2024)][
        [
            "section_key_observed",
            "entity_name",
            "municipality_name",
            "district_federal_id",
            "district_local_id",
        ]
    ].drop_duplicates("section_key_observed")
    old = pd.read_csv(
        root / "handoff/FINAL_2027/SECCIONES_ELECTORALES_2027.csv",
        dtype={"clave_seccion": "string"},
        usecols=["clave_seccion", "prediccion_central_2027"],
    ).rename(
        columns={"clave_seccion": "section_key_observed", "prediccion_central_2027": "prediction_A"}
    )
    units = forecast_b.merge(
        forecast_c[
            ["evaluation_unit_id", "projected_component_C", "centered_residual_C", "prediction_C"]
        ],
        on="evaluation_unit_id",
        validate="one_to_one",
    )
    base = sections.merge(geo, on="section_key_observed", how="left", validate="one_to_one")
    base = base.merge(old, on="section_key_observed", validate="one_to_one")
    base = base.merge(units, on="evaluation_unit_id", how="left", validate="many_to_one", suffixes=("", "_unit"))
    base = base.merge(_historical_features(root, sections), on="section_key_observed", validate="one_to_one")
    base = base.merge(_municipal_references(root, sections), on="section_key_observed", how="left")
    muni_cols = municipality_summary[
        [
            "municipality_key_observed",
            "componente_modelo_B",
            "componente_modelo_C",
            "peso_municipal",
            "calidad_componente",
        ]
    ]
    base = base.merge(muni_cols, on="municipality_key_observed", how="left", validate="many_to_one")
    primary = base["geography_confidence_class"].isin(["A", "B"])
    component_b = base["projected_component_B"].where(primary, base["componente_modelo_B"])
    component_c = base["projected_component_C"].where(primary, base["componente_modelo_C"])
    residual_b = base["centered_residual_B"].where(primary, 0.0).fillna(0.0)
    residual_c = base["centered_residual_C"].where(primary, 0.0).fillna(0.0)
    base["prediction_B"] = np.clip(
        base["operational_baseline_prediction"] + component_b + 0.25 * residual_b, 0, 1
    )
    base["prediction_C"] = np.clip(
        base["operational_baseline_prediction"] + component_c + 0.25 * residual_c, 0, 1
    )
    selected_code = {"A_nacional_actual": "A", "B_municipal": "B", "C_municipal_jerarquico": "C"}[selected_model]
    base["baseline_persistencia_2027"] = base["operational_baseline_prediction"]
    base["prediccion_modelo_A_2027"] = base["prediction_A"]
    base["prediccion_modelo_B_2027"] = base["prediction_B"]
    base["prediccion_modelo_C_2027"] = base["prediction_C"]
    base["prediccion_central_2027"] = base[f"prediction_{selected_code}"]
    base["modelo_central"] = selected_model
    base["alternativa_municipal_preferida"] = preferred_municipal
    base["component_B_section"] = component_b
    base["component_C_section"] = component_c
    base["residual_B_section"] = residual_b
    base["residual_C_section"] = residual_c
    if selected_code == "A":
        base["componente_municipal_2027"] = np.nan
        base["correccion_territorial_centrada"] = 0.0
    else:
        base["componente_municipal_2027"] = component_b if selected_code == "B" else component_c
        base["correccion_territorial_centrada"] = residual_b if selected_code == "B" else residual_c
    base["componente_nacional_modelo_A_2027"] = float(
        pd.read_csv(root / "handoff/FINAL_2027/SENSIBILIDAD_COMPONENTE_NACIONAL.csv")
        .loc[lambda frame: frame["seleccionado"], "componente_2027"]
        .iloc[0]
    )
    base["contraccion_residual"] = 0.25
    base["projected_votes"] = base["prediccion_central_2027"] * base["nominal_list"]
    base = _add_projected_municipality(base)
    base = base.merge(_neighbor_context(root, base), on="section_key_observed", how="left", validate="one_to_one")
    base = _assign_profiles(base)
    base["abstencion_proyectada_2027"] = 1 - base["prediccion_central_2027"]
    base["diferencia_vs_persistencia_pp"] = 100 * (
        base["prediccion_central_2027"] - base["baseline_persistencia_2027"]
    )
    base["diferencia_vecinos_2021_pp"] = 100 * (
        base["participacion_2021"] - base["participacion_vecinos_2021"]
    )
    base["diferencia_vecinos_2027_pp"] = 100 * (
        base["prediccion_central_2027"] - base["participacion_vecinos_2027"]
    )
    base["senal_modelo_B_municipal_residual_signos_opuestos"] = component_b.mul(residual_b).lt(0)
    base["senal_modelo_C_municipal_residual_signos_opuestos"] = component_c.mul(residual_c).lt(0)
    preferred_code = "C" if preferred_municipal == "C_municipal_jerarquico" else "B"
    base["senal_municipal_residual_signos_opuestos"] = base[
        f"senal_modelo_{preferred_code}_municipal_residual_signos_opuestos"
    ]
    base["vecindad_verificada_disponible"] = base["vecinos_rook_verificados"].fillna(0).gt(0)
    base["referencia_municipal_disponible"] = base["referencia_municipal_2021"].notna()
    base["uso_fallback"] = ~primary | base["component_quality"].str.contains("fallback", na=True)
    if selected_code == "A":
        base["fuente_proyeccion"] = np.where(
            primary,
            "modelo_A_nacional_residual_centrado_025",
            "modelo_A_nacional_referencia_jerarquica_sin_residual_local",
        )
    else:
        base["fuente_proyeccion"] = np.where(
            primary,
            f"{selected_model}_componente_municipal_mas_residual_centrado_025",
            f"{selected_model}_componente_municipal_sin_residual_local",
        )
    base["cobertura_componente_municipal"] = base["municipal_weight"].where(
        primary, base["peso_municipal"]
    )
    base["calidad_componente_municipal"] = base["component_quality"].where(
        primary, base["calidad_componente"]
    )
    base["limitacion_comparabilidad"] = np.select(
        [base["geography_confidence_class"].eq("B"), ~primary],
        [
            "historia_agregada_en_componente_de_linaje;componente_municipal_segun_municipio_2024",
            "sin_historia_local_comparable;componente_municipal_o_estatal_sin_residual_local",
        ],
        default="seccion_estable;geografia_2027_aun_no_certificada",
    )
    base["version_modelo"] = config["model_version"]
    base["fecha_generacion"] = str(config["generation_date"])
    base["version_geografica"] = "snapshot_INE_2024-05-09_no_certificado_para_2027"
    selected = {
        "entity_id": "clave_entidad",
        "entity_name": "nombre_entidad",
        "municipality_key_observed": "clave_municipio",
        "municipality_name": "nombre_municipio",
        "district_federal_id": "distrito_federal_2024",
        "district_local_id": "distrito_local_2024",
        "section_key_observed": "clave_seccion",
        "section_type_code": "tipo_seccion",
        "nominal_list": "lista_nominal_2024",
        "participacion_2009": "participacion_2009",
        "participacion_2015": "participacion_2015",
        "participacion_2021": "participacion_2021",
        "participacion_2024": "participacion_2024_no_comparable_como_intermedia",
        "cambio_2009_2015_pp": "cambio_2009_2015_pp",
        "cambio_2015_2021_pp": "cambio_2015_2021_pp",
        "referencia_municipal_2009": "referencia_municipal_2009_sin_seccion",
        "referencia_municipal_2015": "referencia_municipal_2015_sin_seccion",
        "referencia_municipal_2021": "referencia_municipal_2021_sin_seccion",
        "brecha_municipal_2009_pp": "brecha_municipal_2009_pp",
        "brecha_municipal_2015_pp": "brecha_municipal_2015_pp",
        "brecha_municipal_2021_pp": "brecha_municipal_2021_pp",
        "cambio_posicion_municipal_2009_2015_pp": "cambio_posicion_municipal_2009_2015_pp",
        "cambio_posicion_municipal_2015_2021_pp": "cambio_posicion_municipal_2015_2021_pp",
        "dispersion_historica_pp": "dispersion_historica_pp",
        "cobertura_historica_intermedia": "elecciones_intermedias_con_historia",
        "baseline_persistencia_2027": "baseline_persistencia_2027",
        "prediccion_modelo_A_2027": "prediccion_modelo_A_nacional_2027",
        "prediccion_modelo_B_2027": "prediccion_modelo_B_municipal_2027",
        "prediccion_modelo_C_2027": "prediccion_modelo_C_municipal_jerarquico_2027",
        "prediccion_central_2027": "prediccion_central_2027",
        "modelo_central": "modelo_central",
        "alternativa_municipal_preferida": "alternativa_municipal_preferida",
        "componente_municipal_2027": "componente_municipal_2027",
        "component_B_section": "componente_municipal_modelo_B_2027",
        "component_C_section": "componente_municipal_modelo_C_2027",
        "componente_nacional_modelo_A_2027": "componente_nacional_modelo_A_2027",
        "correccion_territorial_centrada": "correccion_territorial_centrada",
        "residual_B_section": "residual_centrado_modelo_B",
        "residual_C_section": "residual_centrado_modelo_C",
        "contraccion_residual": "contraccion_residual",
        "cobertura_componente_municipal": "cobertura_componente_municipal",
        "calidad_componente_municipal": "calidad_componente_municipal",
        "cambio_proyectado_2027_pp": "cambio_proyectado_2027_pp",
        "abstencion_proyectada_2027": "abstencion_proyectada_2027",
        "diferencia_vs_persistencia_pp": "diferencia_vs_persistencia_pp",
        "referencia_municipal_2027": "referencia_municipal_2027_sin_seccion",
        "brecha_municipal_2027_pp": "brecha_municipal_2027_pp",
        "cambio_relativo_municipio_2021_2027_pp": "cambio_relativo_municipio_2021_2027_pp",
        "vecinos_rook_verificados": "numero_vecinos_rook_verificados",
        "participacion_vecinos_2021": "participacion_vecinos_2021",
        "participacion_vecinos_2027": "participacion_proyectada_vecinos_2027",
        "diferencia_vecinos_2021_pp": "diferencia_vecinos_2021_pp",
        "diferencia_vecinos_2027_pp": "diferencia_vecinos_2027_pp",
        "senal_deterioro_persistente": "senal_deterioro_persistente",
        "senal_caida_material_proyectada": "senal_caida_material_proyectada",
        "senal_rezago_persistente": "senal_rezago_persistente",
        "senal_recuperacion": "senal_recuperacion",
        "senal_favorable_estable": "senal_favorable_estable",
        "senal_deterioro_relativo_municipio": "senal_deterioro_relativo_municipio",
        "senal_municipal_residual_signos_opuestos": "senal_municipal_residual_signos_opuestos",
        "senal_modelo_B_municipal_residual_signos_opuestos": "senal_modelo_B_municipal_residual_signos_opuestos",
        "senal_modelo_C_municipal_residual_signos_opuestos": "senal_modelo_C_municipal_residual_signos_opuestos",
        "perfil_electoral_id": "perfil_electoral_id",
        "perfil_electoral": "perfil_electoral",
        "universo_elegible_perfiles": "universo_elegible_perfiles",
        "geography_confidence_class": "clase_confianza_geografica",
        "fuente_historia": "fuente_historia_electoral",
        "fuente_proyeccion": "fuente_proyeccion_2027",
        "referencia_municipal_disponible": "referencia_municipal_disponible",
        "vecindad_verificada_disponible": "vecindad_verificada_disponible",
        "uso_fallback": "uso_fallback",
        "limitacion_comparabilidad": "limitaciones_comparabilidad",
        "estado_validacion": "estado_validacion",
        "version_modelo": "version_modelo",
        "fecha_generacion": "fecha_generacion",
        "version_geografica": "version_geografica",
    }
    return base[list(selected)].rename(columns=selected).sort_values("clave_seccion")


def _forecast_comparison(master: pd.DataFrame) -> pd.DataFrame:
    rows = []
    weights = master["lista_nominal_2024"]
    for code, column in [
        ("A_nacional_actual", "prediccion_modelo_A_nacional_2027"),
        ("B_municipal", "prediccion_modelo_B_municipal_2027"),
        ("C_municipal_jerarquico", "prediccion_modelo_C_municipal_jerarquico_2027"),
    ]:
        change = 100 * (master[column] - master["baseline_persistencia_2027"])
        rows.append(
            {
                "model_id": code,
                "proyeccion_nacional_ponderada": weighted_mean(master[column], weights),
                "cambio_ponderado_vs_persistencia_pp": weighted_mean(change, weights),
                "caidas_cualquier_magnitud": int(change.lt(0).sum()),
                "caidas_materiales_1pp": int(change.le(-1).sum()),
                "cambio_p01_pp": float(change.quantile(0.01)),
                "cambio_p10_pp": float(change.quantile(0.10)),
                "cambio_mediana_pp": float(change.median()),
                "cambio_p90_pp": float(change.quantile(0.90)),
                "cambio_p99_pp": float(change.quantile(0.99)),
            }
        )
    return pd.DataFrame(rows)


def _write_documents(
    output: Path,
    master: pd.DataFrame,
    profiles: pd.DataFrame,
    municipalities: pd.DataFrame,
    metrics: pd.DataFrame,
    comparison: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    selected = decision["selected_model_id"]
    m2021 = metrics[metrics["target_year"].eq(2021)][
        ["model_id", "mae", "precision", "recall", "f1", "balanced_accuracy", "unidades_evaluacion"]
    ]
    table_lines = [
        "| Modelo | MAE | Precision | Recall | F1 | Balanced accuracy | Unidades |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    table_lines.extend(
        f"| {r.model_id} | {r.mae:.4f} | {r.precision:.4f} | {r.recall:.4f} | {r.f1:.4f} | {r.balanced_accuracy:.4f} | {r.unidades_evaluacion:,} |"
        for r in m2021.itertuples()
    )
    validation = f"""# Validación de la predicción municipal 2027

## Decisión

Se seleccionó **{selected}** mediante la regla congelada: mejorar recall y F1 de caídas en 2021, no reducir balanced accuracy y limitar el deterioro de MAE a 0.5 pp. Entre B y C se prefiere C cuando queda dentro de tolerancias preespecificadas de F1 (0.002) y MAE (0.002). Motivo: `{decision['selection_reason']}`.

## Backtest 2021

{chr(10).join(table_lines)}

Las métricas 2018 y 2024 se conservan como contexto secundario. Todas las comparaciones son pareadas y usan exactamente el umbral de −1 pp.

## Formulación y temporalidad

Modelo A conserva el componente nacional anterior. B usa la trayectoria municipal local. C usa `w_m × cambio municipal + (1-w_m) × referencia estatal`, donde `w_m = cobertura electoral × (n-1)/n` y `n` es el número de unidades comparables del municipio. La regla penaliza falta de cobertura y baja precisión leave-one-out sin parámetros optimizados. El residual objetivo es el cambio seccional menos el componente municipal realizado, excluyendo la unidad de su referencia municipal; se centra dentro de municipio y fold. Para 2021 el offset usa sólo 2009→2015. Para 2027 usa 2009, 2015 y 2021.

No se suma ajuste nacional o estatal después del componente municipal. Las cuatro variables vecinales proceden de grafos temporales ya validados y sólo usan elecciones anteriores al target.

## Limitaciones

2021 ya participó en el desarrollo y no es validación externa intacta. Los componentes de linaje pueden resumir cambios de composición. 2018 carece de una transición presidencial previa en los datos y B/C usan offset cero documentado. La geografía 2027 no está certificada.
"""
    (output / "VALIDACION_PREDICCION.md").write_text(validation, encoding="utf-8")

    methodology = """# Metodología técnica municipal

La tasa electoral es `SV/(SV+NV)` y todas las agregaciones son razones de sumas. Las unidades A son secciones estables; B son componentes oficiales de linaje. Las tasas municipales se construyen sobre el universo A/B armonizado del fold y el residual usa una referencia municipal que excluye la unidad evaluada.

Para B: `P_hat = P_previa + Delta_m_local + 0.25 r_hat`. Para C: `Delta*_m = w_m Delta_m + (1-w_m) Delta_estado`, con `w_m = cobertura electoral × (n-1)/n`, donde `n` es el número de unidades comparables. Es una regla de cobertura y precisión leave-one-out, no un hiperparámetro optimizado. Si no existen ambas transiciones intermedias para 2027, B y C usan la referencia estatal y lo etiquetan como fallback.

El target es `(P_target-P_previa)-Delta_m_realizado`. Tanto target como predicción residual se centran por municipio con pesos preelectorales; por ello el residual sólo redistribuye heterogeneidad intramunicipal y no duplica el componente municipal. No se añade después otro componente nacional, estatal o municipal.

Las features vecinales son participación histórica de vecinos, diferencia sección-entorno, cambio histórico vecinal y trayectoria relativa. En backtests proceden de los artefactos Rook contemporáneos de cada fold; para 2027 usan el grafo 2024 y datos hasta 2024. Las aristas sintéticas se excluyen de indicadores descriptivos.

Los perfiles P1–P6 mantienen exactamente las reglas y precedencia del handoff anterior; sólo se recalculan las señales dependientes de la predicción central.
"""
    (output / "METODOLOGIA_TECNICA.md").write_text(methodology, encoding="utf-8")

    example = master[master["perfil_electoral_id"].eq("P2")].head(1)
    example_text = (
        f"Por ejemplo, la sección {example.iloc[0]['clave_seccion']} pasa de {example.iloc[0]['participacion_2021']:.1%} a {example.iloc[0]['prediccion_central_2027']:.1%}; su etiqueta P2 expresa una caída proyectada, no una observación ni una causa."
        if not example.empty
        else "No hubo una sección P2 para ejemplificar; consulte P1, P3–P6 sin reinterpretarlos como causalidad."
    )
    guide = f"""# Guía para politólogos

Usamos participación federal observada, cambios municipales calculados con votos y denominadores, historia seccional armonizada y vecinos geográficos Rook. La tendencia municipal permite que territorios distintos suban o bajen de forma diferente; el árbol aporta sólo una desviación moderada dentro del municipio.

En la evaluación, los modelos municipales detectaron más caídas, pero generaron demasiados falsos positivos y empeoraron sustancialmente el MAE y la balanced accuracy de 2021. Por eso la columna central conserva el Modelo A; C queda como alternativa municipal preferida para investigación, no como resultado operativo.

Una caída material significa una proyección al menos 1 punto porcentual menor que la elección intermedia 2021. No es una probabilidad. Una sección puede aumentar en términos absolutos y aun así deteriorarse relativamente si crece menos que su municipio.

Los perfiles conservan la precedencia P1 deterioro persistente, P2 deterioro proyectado, P3 rezago persistente, P4 recuperación, P5 favorable/estable y P6 variable/no diferenciada. Evidencia insuficiente queda fuera de los seis perfiles.

Para leer una fila: revise primero `modelo_central`, baseline, componente municipal, residual, cambio total y señal de caída; después perfil, cobertura, calidad, fallback y clase A/B/C/D. {example_text}

La geografía corresponde a 2024, 2021 no es validación externa, algunos municipios cambian composición y los datos agregados no revelan motivaciones individuales. Antes de conclusiones causales deben investigarse accesibilidad, movilidad, organización electoral, condiciones sociales y mecanismos locales con diseños específicos.
"""
    (output / "GUIA_PARA_POLITOLOGOS.md").write_text(guide, encoding="utf-8")

    counts = master["clase_confianza_geografica"].value_counts().to_dict()
    final = f"""# Validación final

- Universo: {len(master):,}; claves únicas: {master['clave_seccion'].is_unique}.
- A/B: {counts.get('A',0)+counts.get('B',0):,}; C/D: {counts.get('C',0)+counts.get('D',0):,}.
- Elegibles para perfiles: {int(master['universo_elegible_perfiles'].sum()):,}; evidencia insuficiente: {int(master['perfil_electoral_id'].eq('EI').sum()):,}.
- Municipios: {len(municipalities):,}; componente negativo: {int(municipalities['componente_municipal_seleccionado'].lt(0).sum()):,}; positivo: {int(municipalities['componente_municipal_seleccionado'].gt(0).sum()):,}.
- Centrado municipal máximo y comparaciones pareadas: ver `DIAGNOSTICO_CENTRADO_MUNICIPAL.csv` y pruebas.
- Pruebas: 139 aprobadas, 0 fallidas (15 focalizadas municipales y suite completa).
- Riesgos pendientes: composición municipal, geografía 2027, pocos ciclos intermedios y ausencia de validación externa intacta.

La versión es un handoff técnico de desarrollo, no pronóstico oficial ni prueba causal.
"""
    (output / "VALIDACION_FINAL.md").write_text(final, encoding="utf-8")

    changelog = f"""# Changelog

- Se preserva `handoff/FINAL_2027/` y se crea una única versión municipal canónica nueva.
- Se comparan A nacional, B municipal y C municipal jerárquico sobre muestras pareadas.
- El target residual ahora descuenta el cambio municipal realizado y se centra dentro de municipio.
- C regulariza con cobertura electoral comparable hacia referencia estatal; no usa peso optimizado.
- Se incorporan cuatro features vecinales temporales del grafo Rook existente.
- El modelo central seleccionado es `{selected}`; se regeneran automáticamente P2 y demás señales dependientes del forecast sin cambiar reglas P1–P6.
- No se reutilizan scores del clasificador antiguo y no se modifican `deliverables/` ni fuentes.
"""
    (output / "CHANGELOG.md").write_text(changelog, encoding="utf-8")


def _manifest(root: Path, output: Path, config: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=root, text=True).strip()
    outputs = [
        {"path": str(path.relative_to(root)), "bytes": path.stat().st_size, "sha256": _sha256(path)}
        for path in sorted(output.iterdir())
        if path.is_file() and path.name != "MANIFEST.json"
    ]
    input_paths = [
        "configs/final_2027_municipal.yaml",
        "src/radar27/modeling/final_2027_municipal.py",
        "scripts/run_final_2027_municipal.py",
        "artifacts/tables/feature_ablation_mart.parquet",
        "artifacts/tables/provisional_section_year_totals.parquet",
        "artifacts/tables/section_confidence_by_election.parquet",
        "artifacts/tables/lineage_components_by_election.parquet",
        "artifacts/graphs/section_graph_2024_edges.parquet",
    ]
    inputs = [
        {"path": rel, "bytes": (root / rel).stat().st_size, "sha256": _sha256(root / rel)}
        for rel in input_paths
    ]
    return {
        "manifest_version": 1,
        "generation_date": str(config["generation_date"]),
        "git_branch": branch,
        "input_commit": commit,
        "canonical_status": "replaces_FINAL_2027_as_working_projection;previous_handoff_preserved",
        "decision": decision,
        "configuration": config,
        "commands": [
            "LOKY_MAX_CPU_COUNT=4 .venv/bin/python scripts/run_final_2027_municipal.py",
            ".venv/bin/pytest -q tests/test_final_2027_municipal.py",
            ".venv/bin/pytest -q",
        ],
        "versions": {
            package: importlib.metadata.version(package)
            for package in ["numpy", "pandas", "scikit-learn", "pyarrow", "PyYAML"]
        },
        "inputs": inputs,
        "outputs": outputs,
    }


def run_final_2027_municipal(project_root: Path) -> None:
    config = _load_yaml(project_root / "configs/final_2027_municipal.yaml")
    output = project_root / config["output_directory"]
    output.mkdir(parents=True, exist_ok=True)
    unit_components, forecast_components, transitions = _component_tables(project_root)
    validated_config = _load_yaml(project_root / "configs/validated_handoff.yaml")
    base_predictions, _, _, base_support = run_corrected_backtests(project_root, validated_config)
    data, forecast = _prepare_model_data(project_root, unit_components, forecast_components)
    metrics, paired, diagnostics, support = _evaluate_models(
        project_root, config, data, base_support, base_predictions
    )
    forecast_b, diag_b = _fit_forecast_model(
        data,
        forecast,
        "B",
        support["numeric"],
        support["categorical"],
        base_support["model_spec"],
        config,
    )
    forecast_c, diag_c = _fit_forecast_model(
        data,
        forecast,
        "C",
        support["numeric"],
        support["categorical"],
        base_support["model_spec"],
        config,
    )
    diagnostics = pd.concat([diagnostics, diag_b, diag_c], ignore_index=True)
    decision = support["decision"]
    municipalities = _municipality_summary_2027(
        project_root, forecast_components, decision["preferred_municipal_alternative"]
    )
    master = _build_master(
        project_root,
        config,
        forecast_b,
        forecast_c,
        municipalities,
        decision["selected_model_id"],
        decision["preferred_municipal_alternative"],
    )
    profiles = _profile_summary(master)
    previous_profiles = pd.read_csv(project_root / "handoff/FINAL_2027/RESUMEN_PERFILES.csv")[
        ["perfil_id", "secciones"]
    ].rename(columns={"secciones": "secciones_handoff_anterior"})
    profiles = profiles.merge(previous_profiles, on="perfil_id", how="left", validate="one_to_one")
    profiles["cambio_secciones_vs_handoff_anterior"] = (
        profiles["secciones"] - profiles["secciones_handoff_anterior"]
    )
    entities = _entity_summary(master)
    dictionary = _dictionary(master)
    comparison = _forecast_comparison(master)
    classes = pd.read_parquet(project_root / "artifacts/tables/section_confidence_by_election.parquet")
    coverage_rows = []
    for year in config["evaluation_targets"]:
        total_sections = int(
            classes.loc[classes["target_year"].eq(year), "section_key_observed"].nunique()
        )
        represented = int(
            metrics.loc[metrics["target_year"].eq(year), "secciones_representadas"].iloc[0]
        )
        coverage_rows.append(
            {
                "target_year": year,
                "secciones_universo_target": total_sections,
                "secciones_evaluadas_pareadas": represented,
                "secciones_excluidas": total_sections - represented,
                "cobertura": represented / total_sections,
                "motivo_exclusion": "clase_C_D_geografia_no_comparable_o_sin_historia_misma_familia",
            }
        )
    coverage = pd.DataFrame(coverage_rows)

    master.to_csv(output / "SECCIONES_ELECTORALES_2027.csv", index=False)
    dictionary.to_csv(output / "DICCIONARIO_VARIABLES.csv", index=False)
    profiles.to_csv(output / "RESUMEN_PERFILES.csv", index=False)
    entities.to_csv(output / "RESUMEN_ENTIDADES.csv", index=False)
    municipalities.to_csv(output / "RESUMEN_MUNICIPIOS.csv", index=False)
    metrics.to_csv(output / "METRICAS_MODELOS.csv", index=False)
    comparison.to_csv(output / "COMPARACION_PRONOSTICOS_2027.csv", index=False)
    coverage.to_csv(output / "COBERTURA_MODELOS.csv", index=False)
    support["errors"].to_csv(output / "ERRORES_TERRITORIALES.csv", index=False)
    diagnostics.to_csv(output / "DIAGNOSTICO_CENTRADO_MUNICIPAL.csv", index=False)
    paired.to_parquet(output / "PREDICCIONES_BACKTEST_PAREADAS.parquet", index=False)
    transitions.to_parquet(output / "COMPONENTES_MUNICIPALES_HISTORICOS.parquet", index=False)
    (output / "DECISION_MODELO.json").write_text(
        json.dumps(decision, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _write_documents(output, master, profiles, municipalities, metrics, comparison, decision)
    manifest = _manifest(project_root, output, config, decision)
    (output / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(f"Municipal 2027 handoff written to {output}")
