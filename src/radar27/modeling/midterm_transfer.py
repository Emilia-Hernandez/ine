from __future__ import annotations

import json
import time
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from radar27.modeling.feature_enrichment import _resolve_feature_group
from radar27.modeling.feature_models import (
    _aggregate_history,
    _derive_lag_rates,
    _load_yaml,
    _target_units,
)
from radar27.modeling.tabular_challengers import _predict_residual_correction


def _family_year_map(section_year: pd.DataFrame) -> dict[int, str]:
    pairs = section_year[["election_year", "election_family"]].drop_duplicates()
    counts = pairs.groupby("election_year")["election_family"].nunique()
    if counts.gt(1).any():
        raise ValueError("Una elección aparece con más de una familia")
    return {
        int(row.election_year): str(row.election_family)
        for row in pairs.itertuples(index=False)
    }


def _latest_transition(
    rates: pd.DataFrame,
    target_year: int,
    family_by_year: dict[int, str],
    source_family: str,
    target_family: str,
) -> tuple[pd.Series, int | None]:
    years = sorted(year for year in family_by_year if year < target_year)
    candidates = [
        (left, right)
        for left, right in pairwise(years)
        if family_by_year[left] == source_family
        and family_by_year[right] == target_family
    ]
    if not candidates:
        return pd.Series(dtype=float), None
    source_year, destination_year = candidates[-1]
    wide = rates[rates["election_year"].isin([source_year, destination_year])].pivot(
        index="evaluation_unit_id", columns="election_year", values="participation"
    )
    if source_year not in wide or destination_year not in wide:
        return pd.Series(dtype=float), destination_year
    return wide[destination_year] - wide[source_year], destination_year


def derive_cycle_features(
    history: pd.DataFrame,
    target_year: int,
    family_by_year: dict[int, str],
) -> pd.DataFrame:
    """Create family-aligned features using elections strictly before target_year."""
    rates = _derive_lag_rates(history)
    rates = rates[["evaluation_unit_id", "election_year", "participation"]].copy()
    rates["election_family"] = rates["election_year"].map(family_by_year)
    if rates["election_family"].isna().any():
        missing = sorted(rates.loc[rates["election_family"].isna(), "election_year"].unique())
        raise ValueError(f"Falta familia para los años {missing}")
    if not rates["election_year"].lt(target_year).all():
        raise ValueError("Las variables de ciclo contienen la elección objetivo o una posterior")

    units = pd.DataFrame(
        {"evaluation_unit_id": rates["evaluation_unit_id"].drop_duplicates()}
    )
    result = units.copy()
    for family in ["midterm", "presidential"]:
        family_rates = rates[rates["election_family"].eq(family)].sort_values(
            ["evaluation_unit_id", "election_year"], ascending=[True, False]
        )
        family_rates["recency_rank"] = family_rates.groupby(
            "evaluation_unit_id"
        ).cumcount()
        latest = family_rates[family_rates["recency_rank"].eq(0)][
            ["evaluation_unit_id", "participation", "election_year"]
        ].rename(
            columns={
                "participation": f"latest_{family}_participation",
                "election_year": f"latest_{family}_year",
            }
        )
        previous = family_rates[family_rates["recency_rank"].eq(1)][
            ["evaluation_unit_id", "participation"]
        ].rename(columns={"participation": f"previous_{family}_participation"})
        stats = (
            family_rates.groupby("evaluation_unit_id", as_index=False)["participation"]
            .agg(["mean", "std"])
            .reset_index()
            .rename(
                columns={
                    "mean": f"{family}_history_mean",
                    "std": f"{family}_history_std",
                }
            )
        )
        result = result.merge(latest, on="evaluation_unit_id", how="left")
        result = result.merge(previous, on="evaluation_unit_id", how="left")
        result = result.merge(stats, on="evaluation_unit_id", how="left")
        result[f"{family}_change_latest"] = (
            result[f"latest_{family}_participation"]
            - result[f"previous_{family}_participation"]
        )
        result[f"years_since_latest_{family}"] = (
            target_year - result[f"latest_{family}_year"]
        )

    result["latest_midterm_minus_latest_presidential"] = (
        result["latest_midterm_participation"]
        - result["latest_presidential_participation"]
    )
    p_to_m, p_to_m_year = _latest_transition(
        rates, target_year, family_by_year, "presidential", "midterm"
    )
    m_to_p, m_to_p_year = _latest_transition(
        rates, target_year, family_by_year, "midterm", "presidential"
    )
    result["latest_completed_presidential_to_midterm_change"] = result[
        "evaluation_unit_id"
    ].map(p_to_m)
    result["latest_completed_midterm_to_presidential_change"] = result[
        "evaluation_unit_id"
    ].map(m_to_p)
    result["latest_completed_presidential_to_midterm_year"] = p_to_m_year
    result["latest_completed_midterm_to_presidential_year"] = m_to_p_year
    result["cycle_source_max_year"] = rates.groupby("evaluation_unit_id")[
        "election_year"
    ].max().reindex(result["evaluation_unit_id"]).to_numpy()
    if not result["cycle_source_max_year"].lt(target_year).all():
        raise ValueError("Se detectó fuga temporal en las variables por familia")
    return result


def add_cycle_territorial_context(
    frame: pd.DataFrame, sources: list[str]
) -> tuple[pd.DataFrame, list[str]]:
    enriched = frame.copy()
    created: list[str] = []
    for source in sources:
        entity = enriched.groupby(["target_year", "entity_id"])[source]
        names = {
            f"entity_{source}_mean": entity.transform("mean"),
            f"entity_{source}_std": entity.transform("std"),
            f"{source}_minus_entity_mean": None,
            f"national_{source}_mean": enriched.groupby("target_year")[source].transform(
                "mean"
            ),
            f"{source}_minus_national_mean": None,
        }
        names[f"{source}_minus_entity_mean"] = (
            enriched[source] - names[f"entity_{source}_mean"]
        )
        names[f"{source}_minus_national_mean"] = (
            enriched[source] - names[f"national_{source}_mean"]
        )
        for name, values in names.items():
            enriched[name] = values
            created.append(name)
    return enriched, created


def build_midterm_cycle_mart(
    project_root: Path, config: dict[str, Any]
) -> tuple[pd.DataFrame, list[str]]:
    base = pd.read_parquet(
        project_root / "artifacts/tables/feature_ablation_mart.parquet"
    )
    section_year = pd.read_parquet(
        project_root / "artifacts/tables/section_year_behavioral_features.parquet"
    )
    classes = pd.read_parquet(
        project_root / "artifacts/tables/section_confidence_by_election.parquet"
    )
    components = pd.read_parquet(
        project_root / "artifacts/tables/lineage_components_by_election.parquet"
    )
    evaluation = _load_yaml(project_root / "configs/evaluation.yaml")
    family_by_year = _family_year_map(section_year)
    cycle_rows: list[pd.DataFrame] = []
    for fold in evaluation["folds"]:
        target_year = int(fold["target_year"])
        target = classes[classes["target_year"].eq(target_year)].copy()
        memberships = components[components["target_year"].eq(target_year)].copy()
        _, members = _target_units(target, memberships)
        history = _aggregate_history(members, section_year, target_year)
        cycle = derive_cycle_features(history, target_year, family_by_year)
        cycle["target_year"] = target_year
        cycle_rows.append(cycle)
    cycle_mart = pd.concat(cycle_rows, ignore_index=True)
    enriched = base.merge(
        cycle_mart,
        on=["target_year", "evaluation_unit_id"],
        how="left",
        validate="one_to_one",
    )
    if enriched["cycle_source_max_year"].isna().any():
        raise ValueError("Faltan variables de ciclo para unidades del mart")
    if not enriched["cycle_source_max_year"].lt(enriched["target_year"]).all():
        raise ValueError("El mart de ciclo contiene fuga temporal")
    raw_features = list(config["cycle_features"]["raw"])
    enriched, contextual = add_cycle_territorial_context(
        enriched, list(config["cycle_features"]["territorial_sources"])
    )
    cycle_features = [*raw_features, *contextual]
    missing = set(cycle_features) - set(enriched.columns)
    if missing:
        raise ValueError(f"Variables de ciclo ausentes: {sorted(missing)}")
    output = project_root / config["outputs"]["mart"]
    output.parent.mkdir(parents=True, exist_ok=True)
    enriched.to_parquet(output, index=False)
    return enriched, cycle_features


def _prediction_frame(
    test: pd.DataFrame,
    variant: str,
    before_shift: np.ndarray,
    residual: np.ndarray,
    national_shift: float,
) -> pd.DataFrame:
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
    predicted["variant"] = variant
    predicted["model_prediction_before_national_shift"] = before_shift
    predicted["predicted_residual_unshrunk"] = residual
    predicted["national_shift_correction"] = national_shift
    predicted["prediction"] = np.clip(before_shift + national_shift, 0.0, 1.0)
    return predicted


def _metric(predicted: pd.DataFrame, label: str) -> dict[str, Any]:
    valid = predicted.dropna(subset=["actual", "prediction"]).copy()
    weights = valid["target_identified_records"].to_numpy(float)
    error = valid["prediction"].to_numpy(float) - valid["actual"].to_numpy(float)
    return {
        "target_year": int(valid["target_year"].iloc[0]),
        "variant": str(valid["variant"].iloc[0]),
        "variant_label": label,
        "evaluation_units": len(valid),
        "identified_weighted_mae": float(np.average(np.abs(error), weights=weights)),
        "weighted_bias": float(np.average(error, weights=weights)),
        "mae": float(np.mean(np.abs(error))),
        "share_within_5pp": float(np.mean(np.abs(error) <= 0.05)),
    }


def _entity_bootstrap_delta(
    predictions: pd.DataFrame,
    candidate: str,
    reference: str,
    repetitions: int,
    seed: int,
) -> tuple[float, float, float, int, int]:
    columns = [
        "evaluation_unit_id",
        "entity_id",
        "actual",
        "target_identified_records",
        "prediction",
    ]
    left = predictions[predictions["variant"].eq(reference)][columns].rename(
        columns={"prediction": "reference_prediction"}
    )
    right = predictions[predictions["variant"].eq(candidate)][
        ["evaluation_unit_id", "prediction"]
    ].rename(columns={"prediction": "candidate_prediction"})
    paired = left.merge(right, on="evaluation_unit_id", validate="one_to_one").dropna()
    paired["reference_weighted_error"] = (
        (paired["reference_prediction"] - paired["actual"]).abs()
        * paired["target_identified_records"]
    )
    paired["candidate_weighted_error"] = (
        (paired["candidate_prediction"] - paired["actual"]).abs()
        * paired["target_identified_records"]
    )
    entity = paired.groupby("entity_id", as_index=False).agg(
        weight=("target_identified_records", "sum"),
        reference_error=("reference_weighted_error", "sum"),
        candidate_error=("candidate_weighted_error", "sum"),
    )
    entity["reference_mae"] = entity["reference_error"] / entity["weight"]
    entity["candidate_mae"] = entity["candidate_error"] / entity["weight"]
    entities_better = int(entity["candidate_mae"].lt(entity["reference_mae"]).sum())
    rng = np.random.default_rng(seed)
    count = len(entity)
    draws = rng.integers(0, count, size=(repetitions, count))
    weights = entity["weight"].to_numpy(float)[draws]
    reference_error = entity["reference_error"].to_numpy(float)[draws]
    candidate_error = entity["candidate_error"].to_numpy(float)[draws]
    delta = candidate_error.sum(axis=1) / weights.sum(axis=1) - (
        reference_error.sum(axis=1) / weights.sum(axis=1)
    )
    point = float(
        entity["candidate_error"].sum() / entity["weight"].sum()
        - entity["reference_error"].sum() / entity["weight"].sum()
    )
    low, high = np.quantile(delta, [0.025, 0.975])
    return point, float(low), float(high), entities_better, count


def run_midterm_transfer_experiment(
    project_root: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    config = _load_yaml(project_root / "configs/midterm_transfer_experiment.yaml")
    feature_config = _load_yaml(project_root / str(config["feature_config"]))
    model_config = _load_yaml(project_root / str(config["reference_model_config"]))
    numeric, categorical = _resolve_feature_group(
        feature_config, str(config["feature_group"])
    )
    spec = model_config["models"][str(config["reference_model_spec"])]
    seed = int(config["random_seed"])
    shrinkage = float(config["residual_shrinkage"])
    target_year = int(config["evaluation_target"])
    target_family = str(config["target_family"])
    mart, cycle_features = build_midterm_cycle_mart(project_root, config)
    train_all = mart[
        mart["target_year"].lt(target_year) & mart["actual"].notna()
    ].copy()
    train_midterm = train_all[train_all["election_family"].eq(target_family)].copy()
    test = mart[mart["target_year"].eq(target_year)].copy()
    if set(test["election_family"]) != {target_family}:
        raise ValueError("El target del experimento no es exclusivamente intermedio")
    national_shift = float(
        pd.read_csv(project_root / "artifacts/tables/national_shift_estimates.csv")
        .set_index("target_year")
        .loc[target_year, "national_shift_correction"]
    )

    predictions: list[pd.DataFrame] = []
    registry_rows: list[dict[str, Any]] = []
    variants = config["variants"]

    def fit_one(
        variant: str,
        train: pd.DataFrame,
        extra_numeric: list[str] | None = None,
    ) -> tuple[np.ndarray, np.ndarray, float]:
        active_numeric = [*numeric, *(extra_numeric or [])]
        before, residual, elapsed = _predict_residual_correction(
            train,
            test,
            active_numeric,
            categorical,
            spec,
            seed,
            shrinkage,
        )
        registry_rows.append(
            {
                "target_year": target_year,
                "variant": variant,
                "head": "single",
                "training_target_years": "|".join(
                    map(str, sorted(int(year) for year in train["target_year"].unique()))
                ),
                "training_families": "|".join(sorted(train["election_family"].unique())),
                "training_units": len(train),
                "base_numeric_features": len(numeric),
                "cycle_features": len(extra_numeric or []),
                "fit_seconds": elapsed,
                "uses_target_or_future_outcomes": False,
            }
        )
        return before, residual, elapsed

    for variant, training in [
        ("shared_all_elections", train_all),
        ("midterm_only", train_midterm),
    ]:
        before, residual, _ = fit_one(variant, training)
        predictions.append(
            _prediction_frame(test, variant, before, residual, national_shift)
        )

    started = time.perf_counter()
    shared_before, shared_residual, _ = _predict_residual_correction(
        train_all,
        test,
        [
            *numeric,
            *[feature for feature in cycle_features if train_all[feature].notna().any()],
        ],
        categorical,
        spec,
        seed,
        shrinkage,
    )
    specialist_before, specialist_residual, _ = _predict_residual_correction(
        train_midterm,
        test,
        [
            *numeric,
            *[
                feature
                for feature in cycle_features
                if train_midterm[feature].notna().any()
            ],
        ],
        categorical,
        spec,
        seed,
        shrinkage,
    )
    shared_weight = float(config["shared_head_weight"])
    specialist_weight = float(config["specialist_head_weight"])
    if not np.isclose(shared_weight + specialist_weight, 1.0):
        raise ValueError("Los pesos de las dos cabezas deben sumar uno")
    transfer_before = shared_weight * shared_before + specialist_weight * specialist_before
    transfer_residual = (
        shared_weight * shared_residual + specialist_weight * specialist_residual
    )
    transfer_variant = "midterm_transfer_two_head"
    predictions.append(
        _prediction_frame(
            test,
            transfer_variant,
            transfer_before,
            transfer_residual,
            national_shift,
        )
    )
    total_transfer_seconds = time.perf_counter() - started
    for head, train, weight in [
        ("shared", train_all, shared_weight),
        ("midterm_specialist", train_midterm, specialist_weight),
    ]:
        available_cycle_features = [
            feature for feature in cycle_features if train[feature].notna().any()
        ]
        registry_rows.append(
            {
                "target_year": target_year,
                "variant": transfer_variant,
                "head": head,
                "head_weight": weight,
                "training_target_years": "|".join(
                    map(str, sorted(int(year) for year in train["target_year"].unique()))
                ),
                "training_families": "|".join(sorted(train["election_family"].unique())),
                "training_units": len(train),
                "base_numeric_features": len(numeric),
                "cycle_features": len(available_cycle_features),
                "cycle_feature_names": "|".join(available_cycle_features),
                "fit_seconds": total_transfer_seconds,
                "uses_target_or_future_outcomes": False,
            }
        )

    prediction_frame = pd.concat(predictions, ignore_index=True)
    metric_rows = [
        _metric(
            prediction_frame[prediction_frame["variant"].eq(variant)],
            str(variant_config["label"]),
        )
        for variant, variant_config in variants.items()
    ]
    metrics = pd.DataFrame(metric_rows)
    reference_variant = "shared_all_elections"
    reference_mae = float(
        metrics.loc[
            metrics["variant"].eq(reference_variant), "identified_weighted_mae"
        ].iloc[0]
    )
    repetitions = int(config["bootstrap_entity_repetitions"])
    for index, row in metrics.iterrows():
        variant = str(row["variant"])
        if variant == reference_variant:
            values = (0.0, 0.0, 0.0, 0, prediction_frame["entity_id"].nunique())
        else:
            values = _entity_bootstrap_delta(
                prediction_frame, variant, reference_variant, repetitions, seed
            )
        point, low, high, entities_better, entity_count = values
        metrics.loc[index, "mae_change_vs_current"] = point
        metrics.loc[index, "mae_change_ci_low"] = low
        metrics.loc[index, "mae_change_ci_high"] = high
        metrics.loc[index, "entities_better_than_current"] = entities_better
        metrics.loc[index, "entities_compared"] = entity_count
    metrics["relative_mae_change_vs_current"] = (
        metrics["identified_weighted_mae"] / reference_mae - 1.0
    )
    metrics = metrics.sort_values("identified_weighted_mae")
    registry = pd.DataFrame(registry_rows)
    outputs = config["outputs"]
    prediction_frame.to_parquet(project_root / outputs["predictions"], index=False)
    metrics.to_csv(project_root / outputs["metrics"], index=False)
    registry.to_csv(project_root / outputs["registry"], index=False)

    best = metrics.iloc[0]
    transfer = metrics[metrics["variant"].eq(transfer_variant)].iloc[0]
    head_diagnostics = {}
    for head, before, residual in [
        ("shared_cycle_head", shared_before, shared_residual),
        ("midterm_cycle_head", specialist_before, specialist_residual),
    ]:
        diagnostic = _metric(
            _prediction_frame(test, head, before, residual, national_shift), head
        )
        head_diagnostics[head] = {
            "identified_weighted_mae": diagnostic["identified_weighted_mae"],
            "weighted_bias": diagnostic["weighted_bias"],
        }
    blend_sensitivity = []
    for specialist_share in [0.25, 0.5, 0.75]:
        shared_share = 1.0 - specialist_share
        before = shared_share * shared_before + specialist_share * specialist_before
        residual = shared_share * shared_residual + specialist_share * specialist_residual
        diagnostic = _metric(
            _prediction_frame(
                test,
                f"diagnostic_blend_{specialist_share:.2f}",
                before,
                residual,
                national_shift,
            ),
            "diagnostic",
        )
        blend_sensitivity.append(
            {
                "shared_weight": shared_share,
                "midterm_specialist_weight": specialist_share,
                "identified_weighted_mae": diagnostic["identified_weighted_mae"],
            }
        )
    decision = {
        "objective": config["objective"],
        "evaluation_target": target_year,
        "reference_variant": reference_variant,
        "best_variant": str(best["variant"]),
        "reference_weighted_mae": reference_mae,
        "best_weighted_mae": float(best["identified_weighted_mae"]),
        "best_mae_change_vs_current": float(best["mae_change_vs_current"]),
        "transfer_weighted_mae": float(transfer["identified_weighted_mae"]),
        "transfer_mae_change_vs_current": float(transfer["mae_change_vs_current"]),
        "transfer_mae_change_ci": [
            float(transfer["mae_change_ci_low"]),
            float(transfer["mae_change_ci_high"]),
        ],
        "automatic_promotion": False,
        "promotion_reason": (
            "Only one strict out-of-time midterm target (2021) is observable; "
            "the experiment is evidence for the 2027 design, not sufficient for automatic promotion."
        ),
        "presidential_role": "auxiliary_shared_head_only",
        "recommended_2027_strategy_from_this_test": str(best["variant"]),
        "cycle_feature_count": len(cycle_features),
        "head_diagnostics": head_diagnostics,
        "blend_sensitivity_posthoc_not_for_selection": blend_sensitivity,
        "limitations": [
            "The 2021 election is the only fully comparable out-of-time midterm target.",
            "Entity-cluster bootstrap measures geographic stability, not uncertainty across election cycles.",
            "The comparison uses classes A and B and does not yet overlay the promoted graph features.",
        ],
    }
    decision_path = project_root / outputs["decision"]
    decision_path.write_text(
        json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return prediction_frame, metrics, registry, decision
