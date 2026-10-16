from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    log_loss,
    mean_absolute_error,
    mean_squared_error,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from radar27.modeling.feature_enrichment import _resolve_feature_group
from radar27.modeling.tabular_challengers import _pipeline

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "audit" / "results"
OUT.mkdir(parents=True, exist_ok=True)
SEED = 2701


def weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    return float(np.average(values, weights=weights))


def regression_metrics(frame: pd.DataFrame, prediction: str, model: str) -> dict[str, object]:
    valid = frame.dropna(subset=["actual", prediction, "target_identified_records"]).copy()
    y = valid["actual"].to_numpy(float)
    p = valid[prediction].to_numpy(float)
    w = valid["target_identified_records"].to_numpy(float)
    e = p - y
    return {
        "target_year": int(valid["target_year"].iloc[0]),
        "model": model,
        "evaluation_units": len(valid),
        "sections_represented": int(valid["target_sections_represented"].sum()),
        "mae": mean_absolute_error(y, p),
        "rmse": math.sqrt(mean_squared_error(y, p)),
        "bias": float(e.mean()),
        "weighted_mae": weighted_mean(np.abs(e), w),
        "weighted_rmse": math.sqrt(weighted_mean(e**2, w)),
        "weighted_bias_national_error": weighted_mean(e, w),
        "actual_national": weighted_mean(y, w),
        "predicted_national": weighted_mean(p, w),
    }


def cluster_bootstrap_delta(
    paired: pd.DataFrame,
    candidate: str,
    reference: str,
    repetitions: int = 500,
) -> dict[str, object]:
    paired = paired.dropna(
        subset=["actual", "target_identified_records", candidate, reference]
    ).copy()
    rows = []
    for entity, part in paired.groupby("entity_id", observed=True):
        w = part["target_identified_records"].to_numpy(float)
        y = part["actual"].to_numpy(float)
        rows.append(
            {
                "entity_id": entity,
                "weight": w.sum(),
                "candidate_error": np.sum(w * np.abs(part[candidate].to_numpy(float) - y)),
                "reference_error": np.sum(w * np.abs(part[reference].to_numpy(float) - y)),
            }
        )
    entity = pd.DataFrame(rows)
    rng = np.random.default_rng(SEED + int(paired["target_year"].iloc[0]))
    draw = rng.integers(0, len(entity), size=(repetitions, len(entity)))
    weight = entity["weight"].to_numpy()[draw]
    cand = entity["candidate_error"].to_numpy()[draw]
    ref = entity["reference_error"].to_numpy()[draw]
    delta = cand.sum(axis=1) / weight.sum(axis=1) - ref.sum(axis=1) / weight.sum(axis=1)
    point = entity["candidate_error"].sum() / entity["weight"].sum() - entity[
        "reference_error"
    ].sum() / entity["weight"].sum()
    low, high = np.quantile(delta, [0.025, 0.975])
    return {
        "target_year": int(paired["target_year"].iloc[0]),
        "candidate": candidate,
        "reference": reference,
        "delta_weighted_mae": float(point),
        "bootstrap_ci_low": float(low),
        "bootstrap_ci_high": float(high),
        "entities_candidate_better": int((entity["candidate_error"] / entity["weight"] < entity["reference_error"] / entity["weight"]).sum()),
        "entities_total": len(entity),
        "bootstrap_repetitions": repetitions,
    }


def national_shift_definition() -> None:
    totals = pd.read_parquet(ROOT / "artifacts/tables/provisional_section_year_totals.parquet")
    rates = {}
    for year in [2015, 2021]:
        year_data = totals[totals["election_year"].eq(year)]
        rates[year] = float(year_data["voted"].sum() / year_data["identified_records"].sum())
    national_ratio_of_sums = rates[2021] - rates[2015]
    estimates = pd.read_csv(ROOT / "artifacts/tables/national_shift_estimates.csv")
    repository_panel_shift = float(
        estimates.loc[estimates["target_year"].eq(2027), "national_shift_correction"].iloc[0]
    )
    sections = pd.read_parquet(ROOT / "artifacts/tables/forecast_2027_section_predictions.parquet")
    weights = sections["nominal_list"].to_numpy(float)
    current = sections["experimental_prediction"].to_numpy(float)
    alternative = np.clip(
        sections["forecast_without_national_shift"].to_numpy(float)
        + national_ratio_of_sums
        + sections["entity_cycle_correction"].to_numpy(float),
        0,
        1,
    )
    result = pd.DataFrame(
        [
            {
                "source_year": 2015,
                "target_year": 2021,
                "source_national_turnout_ratio_of_sums": rates[2015],
                "target_national_turnout_ratio_of_sums": rates[2021],
                "national_shift_ratio_of_sums": national_ratio_of_sums,
                "repository_panel_weighted_shift": repository_panel_shift,
                "shift_definition_difference": repository_panel_shift - national_ratio_of_sums,
                "current_2027_weighted_forecast": weighted_mean(current, weights),
                "alternative_2027_weighted_forecast": weighted_mean(alternative, weights),
                "forecast_difference": weighted_mean(alternative - current, weights),
                "sections_changed": int((np.abs(alternative - current) > 1e-15).sum()),
                "sections_total": len(sections),
            }
        ]
    )
    result.to_csv(OUT / "national_shift_definition.csv", index=False)


def national_adjustment_experiment() -> None:
    mart = pd.read_parquet(ROOT / "artifacts/tables/feature_ablation_mart.parquet")
    current = pd.read_parquet(ROOT / "artifacts/tables/entity_cycle_adaptation_predictions.parquet")
    shifts = pd.read_csv(ROOT / "artifacts/tables/national_shift_estimates.csv").set_index(
        "target_year"
    )["national_shift_correction"]
    with (ROOT / "configs/feature_ablation.yaml").open(encoding="utf-8") as stream:
        feature_cfg = yaml.safe_load(stream)
    numeric, categorical = _resolve_feature_group(feature_cfg, "competition_concurrency")
    required = numeric + categorical
    with (ROOT / "configs/tabular_challengers.yaml").open(encoding="utf-8") as stream:
        model_cfg = yaml.safe_load(stream)
    spec = model_cfg["models"]["hist_gradient_boosting"]
    rows = []
    entity_rows = []
    level_rows = []
    bootstrap_rows = []
    prediction_outputs = []
    for target_year in [2018, 2021, 2024]:
        train = mart[mart["target_year"].lt(target_year) & mart["actual"].notna()].copy()
        test = mart[mart["target_year"].eq(target_year) & mart["actual"].notna()].copy()
        c = current[current["target_year"].eq(target_year)].copy()
        keep_ids = set(c["evaluation_unit_id"])
        test = test[test["evaluation_unit_id"].isin(keep_ids)].copy()
        test = test[test["participation_same_type"].notna()].copy()
        train = train[train["participation_same_type"].notna()].copy()

        # A: aprende el cambio completo y lo aplica completo; no añade ajustes externos.
        a = _pipeline(spec, numeric, categorical, SEED)
        a.fit(
            train[required],
            train["actual"] - train["participation_same_type"],
            model__sample_weight=train["target_identified_records"].astype(float),
        )
        pred_a = np.clip(test["participation_same_type"].to_numpy(float) + a.predict(test[required]), 0, 1)

        # B: descuenta de cada target de entrenamiento sólo el desplazamiento nacional
        # que habría estado disponible en ese año, predice el residuo y reañade el
        # desplazamiento disponible para el target de evaluación.
        train_shift = train["target_year"].map(shifts).fillna(0.0).to_numpy(float)
        b = _pipeline(spec, numeric, categorical, SEED)
        b.fit(
            train[required],
            train["actual"] - train["participation_same_type"] - train_shift,
            model__sample_weight=train["target_identified_records"].astype(float),
        )
        target_shift = float(shifts.get(target_year, 0.0))
        pred_b = np.clip(
            test["participation_same_type"].to_numpy(float) + b.predict(test[required]) + target_shift,
            0,
            1,
        )

        frame = test[
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
        frame["model_a_direct_full_change"] = pred_a
        frame["model_b_national_residual"] = pred_b
        frame = frame.merge(
            c[["evaluation_unit_id", "prediction"]].rename(columns={"prediction": "model_c_repository"}),
            on="evaluation_unit_id",
            validate="one_to_one",
        )
        frame["model_d_persistence"] = frame["participation_same_type"]
        prediction_outputs.append(frame)
        for column, label in [
            ("model_a_direct_full_change", "A_direct_full_change_no_external_adjustment"),
            ("model_b_national_residual", "B_residualized_national_component"),
            ("model_c_repository", "C_current_repository"),
            ("model_d_persistence", "D_same_family_persistence"),
        ]:
            rows.append(regression_metrics(frame, column, label))
            tmp = frame.copy()
            tmp["error"] = tmp[column] - tmp["actual"]
            for entity, part in tmp.groupby("entity_id", observed=True):
                w = part["target_identified_records"].to_numpy(float)
                e = part["error"].to_numpy(float)
                entity_rows.append(
                    {
                        "target_year": target_year,
                        "model": label,
                        "entity_id": entity,
                        "units": len(part),
                        "weighted_mae": weighted_mean(np.abs(e), w),
                        "weighted_bias": weighted_mean(e, w),
                    }
                )
            tmp["prior_turnout_band"] = pd.cut(
                tmp["participation_same_type"],
                bins=[-np.inf, 0.4, 0.5, 0.6, np.inf],
                labels=["<40%", "40-50%", "50-60%", ">=60%"],
            )
            for band, part in tmp.groupby("prior_turnout_band", observed=True):
                w = part["target_identified_records"].to_numpy(float)
                e = part["error"].to_numpy(float)
                level_rows.append(
                    {
                        "target_year": target_year,
                        "model": label,
                        "prior_turnout_band": str(band),
                        "units": len(part),
                        "weighted_mae": weighted_mean(np.abs(e), w),
                        "weighted_bias": weighted_mean(e, w),
                    }
                )
        for candidate in ["model_a_direct_full_change", "model_b_national_residual", "model_c_repository"]:
            bootstrap_rows.append(cluster_bootstrap_delta(frame, candidate, "model_d_persistence"))
    predictions = pd.concat(prediction_outputs, ignore_index=True)
    predictions.to_parquet(OUT / "national_adjustment_predictions.parquet", index=False)
    pd.DataFrame(rows).to_csv(OUT / "national_adjustment_metrics.csv", index=False)
    pd.DataFrame(entity_rows).to_csv(OUT / "national_adjustment_by_entity.csv", index=False)
    pd.DataFrame(level_rows).to_csv(OUT / "national_adjustment_by_prior_turnout.csv", index=False)
    pd.DataFrame(bootstrap_rows).to_csv(OUT / "national_adjustment_bootstrap.csv", index=False)


def classification_row(
    y: np.ndarray, p: np.ndarray, w: np.ndarray, label: str, target_year: int
) -> dict[str, object]:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    predicted = (p >= 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, predicted, labels=[0, 1], sample_weight=w).ravel()
    return {
        "target_year": target_year,
        "model": label,
        "evaluation_units": len(y),
        "prevalence_weighted": weighted_mean(y, w),
        "roc_auc_weighted": roc_auc_score(y, p, sample_weight=w),
        "pr_auc_weighted": average_precision_score(y, p, sample_weight=w),
        "brier_weighted": brier_score_loss(y, p, sample_weight=w),
        "log_loss_weighted": log_loss(y, p, sample_weight=w, labels=[0, 1]),
        "accuracy_weighted": accuracy_score(y, predicted, sample_weight=w),
        "balanced_accuracy_unweighted": balanced_accuracy_score(y, predicted),
        "sensitivity_weighted": tp / (tp + fn),
        "specificity_weighted": tn / (tn + fp),
        "tn_weighted": tn,
        "fp_weighted": fp,
        "fn_weighted": fn,
        "tp_weighted": tp,
        "threshold": 0.5,
    }


def auc_entity_bootstrap(frame: pd.DataFrame, probability: str, repetitions: int = 500) -> dict[str, object]:
    entities = sorted(frame["entity_id"].unique())
    groups = {entity: frame.index[frame["entity_id"].eq(entity)].to_numpy() for entity in entities}
    rng = np.random.default_rng(SEED + 2024)
    aucs = []
    for _ in range(repetitions):
        selected = rng.choice(entities, size=len(entities), replace=True)
        idx = np.concatenate([groups[e] for e in selected])
        sample = frame.loc[idx]
        y = sample["risk_actual"].to_numpy(int)
        if np.unique(y).size < 2:
            continue
        aucs.append(
            roc_auc_score(
                y,
                sample[probability].to_numpy(float),
                sample_weight=sample["target_identified_records"].to_numpy(float),
            )
        )
    low, high = np.quantile(aucs, [0.025, 0.975])
    return {
        "probability": probability,
        "bootstrap_repetitions": len(aucs),
        "auc_ci_low": float(low),
        "auc_ci_high": float(high),
        "probability_auc_below_0_5": float(np.mean(np.asarray(aucs) < 0.5)),
    }


def classifier_experiment() -> None:
    mart = pd.read_parquet(ROOT / "artifacts/tables/feature_ablation_mart.parquet")
    pred = pd.read_parquet(ROOT / "artifacts/tables/turnout_decline_risk_backtest_predictions.parquet")
    pred = pred[
        pred["feature_group"].eq("competition_concurrency")
        & pred["decline_threshold"].eq(0.02)
    ].copy()
    simple_features = [
        "participation_same_type",
        "participation_lag1",
        "participation_change_lag1_lag2",
        "participation_historical_std",
        "identified_coverage_lag1",
    ]
    rows = []
    detailed = []
    for target_year in [2018, 2021, 2024]:
        pyear = pred[pred["target_year"].eq(target_year)].copy()
        test = mart[mart["target_year"].eq(target_year)].merge(
            pyear[["evaluation_unit_id"]], on="evaluation_unit_id", validate="one_to_one"
        )
        train = mart[
            mart["target_year"].lt(target_year)
            & mart["actual"].notna()
            & mart["participation_same_type"].notna()
        ].copy()
        y_train = (train["participation_same_type"] - train["actual"] >= 0.02).astype(int)
        w_train = train["target_identified_records"].to_numpy(float)
        prevalence_train = weighted_mean(y_train.to_numpy(int), w_train)
        history_model = Pipeline(
            [
                ("impute", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
                ("model", LogisticRegression(max_iter=1000, random_state=SEED)),
            ]
        )
        history_model.fit(
            train[["participation_same_type_minus_lag1"]],
            y_train,
            model__sample_weight=w_train,
        )
        simple_model = Pipeline(
            [
                ("impute", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
                ("model", LogisticRegression(max_iter=1000, random_state=SEED)),
            ]
        )
        simple_model.fit(train[simple_features], y_train, model__sample_weight=w_train)
        extra_features = [
            "participation_same_type_minus_lag1",
            *[column for column in simple_features if column not in pyear.columns],
        ]
        pyear = pyear.merge(
            test[["evaluation_unit_id", *extra_features]],
            on="evaluation_unit_id",
            validate="one_to_one",
        )
        y = pyear["risk_actual"].to_numpy(int)
        w = pyear["target_identified_records"].to_numpy(float)
        probabilities = {
            "constant_train_prevalence": np.full(len(pyear), prevalence_train),
            "constant_test_prevalence_retrospective_not_predictive": np.full(len(pyear), weighted_mean(y, w)),
            "historical_single_feature_logit": history_model.predict_proba(
                pyear[["participation_same_type_minus_lag1"]]
            )[:, 1],
            "simple_logistic": simple_model.predict_proba(pyear[simple_features])[:, 1],
            "current_raw": pyear["probability_raw"].to_numpy(float),
            "current_time_calibrated": pyear["probability_time_calibrated"].to_numpy(float),
            "current_inverted_diagnostic": 1 - pyear["probability_time_calibrated"].to_numpy(float),
        }
        for label, probability in probabilities.items():
            rows.append(classification_row(y, probability, w, label, target_year))
        if target_year == 2024:
            for label, probability in probabilities.items():
                pyear[label] = probability
            detailed.append(pyear)
    frame_2024 = pd.concat(detailed, ignore_index=True)
    pd.DataFrame(rows).to_csv(OUT / "classifier_benchmarks.csv", index=False)
    frame_2024.to_parquet(OUT / "classifier_2024_predictions.parquet", index=False)
    ci = [
        auc_entity_bootstrap(frame_2024, "probability_time_calibrated"),
        auc_entity_bootstrap(frame_2024, "probability_raw"),
    ]
    pd.DataFrame(ci).to_csv(OUT / "classifier_2024_auc_bootstrap.csv", index=False)
    calibration = []
    frame_2024["calibration_bin"] = pd.qcut(
        frame_2024["probability_time_calibrated"].rank(method="first"), 10, labels=False
    )
    for bin_id, part in frame_2024.groupby("calibration_bin", observed=True):
        w = part["target_identified_records"].to_numpy(float)
        calibration.append(
            {
                "bin": int(bin_id) + 1,
                "units": len(part),
                "mean_probability": weighted_mean(part["probability_time_calibrated"].to_numpy(float), w),
                "observed_rate": weighted_mean(part["risk_actual"].to_numpy(int), w),
            }
        )
    pd.DataFrame(calibration).to_csv(OUT / "classifier_2024_calibration.csv", index=False)


def eceg_reconciliation() -> None:
    sections = pd.read_parquet(ROOT / "artifacts/tables/section_risk_profiles_2027.parquet")
    ab = sections[sections["geography_confidence_class"].isin(["A", "B"])].copy()
    discrepancy = ab[ab["eceg_profile_source"].ne("aggregated_eceg_2020_to_model_unit")].copy()
    output = discrepancy[
        [
            "section_key_observed",
            "entity_id",
            "geography_confidence_class",
            "profile_data_source",
            "eceg_profile_source",
            "archetype_evidence_source",
            "evaluation_unit_id",
        ]
    ].rename(
        columns={
            "section_key_observed": "section_id",
            "geography_confidence_class": "original_classification",
            "profile_data_source": "local_ccpc_profile_source",
            "eceg_profile_source": "effective_eceg_source",
            "archetype_evidence_source": "final_archetype_source",
        }
    )
    output["local_eceg_available"] = False
    output["discrepancy_reason"] = "A/B unit has no complete matched ECEG 2020 descriptor; entity reference used"
    output["correct_treatment"] = "Keep A/B for electoral model; label ECEG descriptor as entity fallback"
    output.to_csv(OUT / "eceg_38_section_reconciliation.csv", index=False)
    summary = (
        sections.groupby(
            ["geography_confidence_class", "eceg_profile_source", "archetype_evidence_source"],
            dropna=False,
            observed=True,
        )
        .size()
        .reset_index(name="sections")
    )
    summary.to_csv(OUT / "eceg_reconciliation_summary.csv", index=False)
    assertions = {
        "section_rows": len(sections),
        "unique_section_ids": int(sections["section_key_observed"].nunique()),
        "duplicate_section_ids": int(sections["section_key_observed"].duplicated().sum()),
        "ab_sections": len(ab),
        "cd_sections": int((~sections["geography_confidence_class"].isin(["A", "B"])).sum()),
        "ab_with_local_eceg": int(ab["eceg_profile_source"].eq("aggregated_eceg_2020_to_model_unit").sum()),
        "ab_with_entity_eceg_fallback": len(discrepancy),
        "counts_reconcile": bool(len(ab) + (~sections["geography_confidence_class"].isin(["A", "B"])).sum() == len(sections)),
    }
    (OUT / "eceg_reconciliation_assertions.json").write_text(
        json.dumps(assertions, indent=2), encoding="utf-8"
    )


def percentile_experiment() -> None:
    sections = pd.read_parquet(ROOT / "artifacts/tables/section_risk_profiles_2027.parquet")
    n = len(sections)
    metrics = {
        "risk": "risk_probability_02pp",
        "volume": "predicted_additional_nonvoters",
    }
    rows = []
    assignment_rows = []
    for name, column in metrics.items():
        values = sections[column]
        threshold = float(values.quantile(0.8, interpolation="linear"))
        current = sections[f"{name}_percentile"].ge(0.8)
        strict = values.gt(threshold)
        inclusive = values.ge(threshold)
        order = sections.assign(_value=values).sort_values(
            ["_value", "section_key_observed"], ascending=[False, True]
        )
        exact_ids = set(order.head(math.ceil(0.2 * n))["section_key_observed"])
        exact = sections["section_key_observed"].isin(exact_ids)
        positive_operational = values.gt(0) if name == "volume" else inclusive
        alternatives = {
            "A_current_rank_average_ge_80": current,
            "B_raw_p80_strict": strict,
            "C_raw_p80_inclusive": inclusive,
            "D_exact_top_20_rank_section_id_tiebreak": exact,
            "E_operational_positive_volume_or_inclusive_risk": positive_operational,
        }
        for alternative, selected in alternatives.items():
            rows.append(
                {
                    "indicator": name,
                    "alternative": alternative,
                    "threshold_value": threshold,
                    "reference_population": n,
                    "selected_sections": int(selected.sum()),
                    "selected_share": float(selected.mean()),
                    "ties_at_threshold": int(values.eq(threshold).sum()),
                    "missing_values": int(values.isna().sum()),
                    "zero_values": int(values.eq(0).sum()),
                    "changes_vs_current": int((selected != current).sum()),
                }
            )
            for section_id, flag in zip(sections["section_key_observed"], selected, strict=True):
                assignment_rows.append(
                    {
                        "section_id": section_id,
                        "indicator": name,
                        "alternative": alternative,
                        "selected": bool(flag),
                    }
                )
    pd.DataFrame(rows).to_csv(OUT / "percentile_alternatives.csv", index=False)
    pd.DataFrame(assignment_rows).to_parquet(OUT / "percentile_assignments.parquet", index=False)


def integrity_checks() -> None:
    rows = []
    def add(check: str, passed: bool, evidence: object) -> None:
        rows.append({"check": check, "status": "PASS" if passed else "FAIL", "evidence": str(evidence)})

    sections = pd.read_parquet(ROOT / "artifacts/tables/section_risk_profiles_2027.parquet")
    add("final section key unique", not sections["section_key_observed"].duplicated().any(), sections["section_key_observed"].nunique())
    add("final section count", len(sections) == 70751, len(sections))
    add("confidence classes exhaustive", set(sections["geography_confidence_class"]) == {"A", "B", "C", "D"}, sections["geography_confidence_class"].value_counts().to_dict())
    add("probabilities bounded", sections["risk_probability_02pp"].between(0, 1).all(), sections["risk_probability_02pp"].agg(["min", "max"]).to_dict())
    add("turnout forecasts bounded", sections["experimental_prediction"].between(0, 1).all(), sections["experimental_prediction"].agg(["min", "max"]).to_dict())
    add("priority exhaustive", sections["priority_tier"].notna().all(), sections["priority_tier"].value_counts().to_dict())
    mart = pd.read_parquet(ROOT / "artifacts/tables/feature_ablation_mart.parquet")
    add("feature mart key unique", not mart.duplicated(["target_year", "evaluation_unit_id"]).any(), len(mart))
    add("feature temporal order", (mart["max_electoral_feature_year"] < mart["target_year"]).all(), int((mart["max_electoral_feature_year"] >= mart["target_year"]).sum()))
    raw = pd.read_csv(ROOT / "data/manifests/source_manifest.csv")
    for row in raw.itertuples(index=False):
        path = ROOT / row.local_path
        if not path.exists():
            add(f"source exists {row.local_path}", False, "missing")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        add(f"source hash {row.local_path}", digest == row.sha256, digest)
    pd.DataFrame(rows).to_csv(OUT / "integrity_checks.csv", index=False)


def main() -> None:
    national_shift_definition()
    national_adjustment_experiment()
    classifier_experiment()
    eceg_reconciliation()
    percentile_experiment()
    integrity_checks()
    print(f"Audit results written to {OUT}")


if __name__ == "__main__":
    main()
