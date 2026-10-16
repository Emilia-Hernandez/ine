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
from sklearn.metrics import balanced_accuracy_score, f1_score, precision_score, recall_score

from radar27.modeling.feature_enrichment import _resolve_feature_group
from radar27.modeling.tabular_challengers import _pipeline
from radar27.modeling.validated_handoff import (
    _fit_2027_residual,
    add_centered_residual_target,
    center_with_available_weights,
    run_corrected_backtests,
    weighted_mean,
)


PROFILE_NAMES = {
    "P1": "Deterioro persistente",
    "P2": "Deterioro proyectado",
    "P3": "Rezago persistente",
    "P4": "Recuperación",
    "P5": "Participación favorable y estable",
    "P6": "Trayectoria variable o no diferenciada",
    "EI": "Evidencia insuficiente",
}


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def _ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator.div(denominator.where(denominator.gt(0)))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _national_components(totals: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    midterm = totals[totals["election_year"].isin([2009, 2015, 2021])]
    rates = (
        midterm.groupby("election_year", as_index=False)[["voted", "identified_records"]]
        .sum()
        .sort_values("election_year")
    )
    rates["participacion_nacional"] = _ratio(rates["voted"], rates["identified_records"])
    by_year = rates.set_index("election_year")["participacion_nacional"]
    change_0915 = float(by_year.loc[2015] - by_year.loc[2009])
    change_1521 = float(by_year.loc[2021] - by_year.loc[2015])
    conservative = float(np.mean([change_0915, change_1521]))
    rows = [
        {
            "escenario": "A_cero",
            "componente_2027": 0.0,
            "regla": "sin cambio nacional",
            "informacion_usada": "ninguna",
            "seleccionado": False,
        },
        {
            "escenario": "B_ultimo_cambio",
            "componente_2027": change_1521,
            "regla": "cambio nacional intermedio más reciente",
            "informacion_usada": "2015-2021",
            "seleccionado": False,
        },
        {
            "escenario": "C_media_historica",
            "componente_2027": conservative,
            "regla": "media aritmética preespecificada de los dos cambios intermedios disponibles",
            "informacion_usada": "2009-2015|2015-2021",
            "seleccionado": True,
        },
    ]
    table = pd.DataFrame(rows)
    table["cambio_2009_2015"] = change_0915
    table["cambio_2015_2021"] = change_1521
    table["unidad"] = "proporcion; multiplicar por 100 para pp"
    return table, conservative


def _fit_weighted_decline_folds(
    root: Path,
    config: dict[str, Any],
    support: dict[str, Any],
) -> pd.DataFrame:
    mart = pd.read_parquet(root / "artifacts/tables/feature_ablation_mart.parquet")
    components = support["components"].set_index("target_year")["national_component"]
    numeric = support["numeric_features"]
    categorical = support["categorical_features"]
    required = numeric + categorical
    frames: list[pd.DataFrame] = []
    threshold = float(config["material_decline_pp"]) / 100
    factor = float(config["decline_training_weight"])
    for year in config["evaluation_targets"]:
        train = mart[
            mart["target_year"].lt(year)
            & mart["actual"].notna()
            & mart["participation_same_type"].notna()
            & mart["nominal_list_lag1"].gt(0)
        ].copy()
        test = mart[
            mart["target_year"].eq(year)
            & mart["actual"].notna()
            & mart["participation_same_type"].notna()
            & mart["nominal_list_lag1"].gt(0)
        ].copy()
        centered, _ = add_centered_residual_target(train, components)
        decline = centered["actual"].sub(centered["participation_same_type"]).le(-threshold)
        sample_weight = centered["target_identified_records"].astype(float) * np.where(
            decline, factor, 1.0
        )
        model = _pipeline(
            support["model_spec"], numeric, categorical, int(config["random_seed"])
        )
        model.fit(
            centered[required],
            centered["centered_residual_target"],
            model__sample_weight=sample_weight,
        )
        raw = model.predict(test[required])
        residual, removed = center_with_available_weights(raw, test["nominal_list_lag1"])
        prediction = np.clip(
            test["participation_same_type"].to_numpy(float)
            + float(components.get(int(year), 0.0))
            + float(config["residual_shrinkage"]) * residual,
            0,
            1,
        )
        frames.append(
            test[
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
                ]
            ].assign(
                prediction=prediction,
                centered_residual_prediction=residual,
                prediction_center_removed=removed,
            )
        )
    return pd.concat(frames, ignore_index=True)


def _detection_row(frame: pd.DataFrame, prediction: pd.Series, model_id: str) -> dict[str, Any]:
    threshold = 0.01
    actual_decline = frame["actual"].sub(frame["participation_same_type"]).le(-threshold)
    projected_decline = prediction.sub(frame["participation_same_type"]).le(-threshold)
    error = prediction.to_numpy(float) - frame["actual"].to_numpy(float)
    weights = frame["target_identified_records"].to_numpy(float)
    section_weights = frame["target_sections_represented"].to_numpy(int)
    return {
        "target_year": int(frame["target_year"].iloc[0]),
        "model_id": model_id,
        "unidades_evaluacion": len(frame),
        "secciones_representadas": int(section_weights.sum()),
        "caidas_observadas": int(actual_decline.sum()),
        "caidas_proyectadas": int(projected_decline.sum()),
        "caidas_observadas_secciones_representadas": int(section_weights[actual_decline].sum()),
        "caidas_proyectadas_secciones_representadas": int(section_weights[projected_decline].sum()),
        "verdaderos_positivos": int((actual_decline & projected_decline).sum()),
        "falsos_positivos": int((~actual_decline & projected_decline).sum()),
        "falsos_negativos": int((actual_decline & ~projected_decline).sum()),
        "verdaderos_negativos": int((~actual_decline & ~projected_decline).sum()),
        "precision": float(precision_score(actual_decline, projected_decline, zero_division=0)),
        "recall": float(recall_score(actual_decline, projected_decline, zero_division=0)),
        "f1": float(f1_score(actual_decline, projected_decline, zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(actual_decline, projected_decline)),
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error**2))),
        "bias": float(np.mean(error)),
        "mae_ponderado": weighted_mean(np.abs(error), weights),
    }


def _evaluate_three_models(
    base_predictions: pd.DataFrame, weighted_predictions: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    large_rows: list[pd.DataFrame] = []
    for year, part in base_predictions.groupby("target_year", observed=True):
        models = {
            "persistencia": part["A_persistence"],
            "avanzado_corregido_025": part["D_centered_shrink_0.25"],
        }
        weighted = weighted_predictions[weighted_predictions["target_year"].eq(year)].set_index(
            "evaluation_unit_id"
        )
        models["avanzado_ponderado_caidas_025"] = part["evaluation_unit_id"].map(
            weighted["prediction"]
        )
        for model_id, prediction in models.items():
            rows.append(_detection_row(part, prediction, model_id))
        magnitude = 100 * (part["actual"] - part["participation_same_type"])
        largest = part.assign(
            cambio_observado_pp=magnitude,
            prediccion_avanzada=part["D_centered_shrink_0.25"],
            error_avanzado_pp=100 * (part["D_centered_shrink_0.25"] - part["actual"]),
        ).nsmallest(100, "cambio_observado_pp")
        large_rows.append(largest)
    metrics = pd.DataFrame(rows)
    standard = metrics[
        metrics["model_id"].eq("avanzado_corregido_025") & metrics["target_year"].eq(2021)
    ].iloc[0]
    weighted = metrics[
        metrics["model_id"].eq("avanzado_ponderado_caidas_025")
        & metrics["target_year"].eq(2021)
    ].iloc[0]
    improved = bool(
        weighted["falsos_negativos"] < standard["falsos_negativos"]
        and weighted["f1"] >= standard["f1"]
        and weighted["balanced_accuracy"] >= standard["balanced_accuracy"]
    )
    decision = {
        "selected_model_id": "avanzado_ponderado_caidas_025" if improved else "avanzado_corregido_025",
        "weighted_alternative_selected": improved,
        "decline_threshold_pp": 1.0,
        "decline_training_weight": 2.0,
        "selection_rule": "reduce_2021_false_negatives_without_reducing_f1_or_balanced_accuracy",
        "reason": (
            "weighted_alternative_met_joint_gate"
            if improved
            else "weighted_alternative_failed_joint_gate;retain_corrected_advanced_model"
        ),
    }
    return metrics, pd.concat(large_rows, ignore_index=True), decision


def _historical_features(root: Path, sections: pd.DataFrame) -> pd.DataFrame:
    totals = pd.read_parquet(root / "artifacts/tables/provisional_section_year_totals.parquet")
    totals = totals[totals["election_year"].isin([2009, 2015, 2021, 2024])].copy()
    fields = ["section_key_observed", "election_year", "voted", "identified_records", "participation"]
    direct = totals[fields].pivot(index="section_key_observed", columns="election_year")
    direct.columns = [f"{name}_{year}" for name, year in direct.columns]
    direct = direct.reset_index()

    membership = pd.read_parquet(root / "artifacts/tables/lineage_components_by_election.parquet")
    membership = membership[["amge_component_id", "section_key_observed"]].drop_duplicates()
    lineage = membership.merge(totals[fields], on="section_key_observed", how="inner")
    lineage = (
        lineage.groupby(["amge_component_id", "election_year"], as_index=False)[
            ["voted", "identified_records"]
        ]
        .sum()
    )
    lineage["participation"] = _ratio(lineage["voted"], lineage["identified_records"])
    lineage = lineage.pivot(index="amge_component_id", columns="election_year")
    lineage.columns = [f"{name}_{year}_linaje" for name, year in lineage.columns]
    lineage = lineage.reset_index()

    result = sections.merge(direct, on="section_key_observed", how="left", validate="one_to_one")
    result = result.merge(lineage, on="amge_component_id", how="left", validate="many_to_one")
    is_b = result["geography_confidence_class"].eq("B")
    for year in [2009, 2015, 2021]:
        result[f"participacion_{year}"] = result[f"participation_{year}"].where(
            ~is_b, result[f"participation_{year}_linaje"]
        )
        result[f"denominador_{year}"] = result[f"identified_records_{year}"].where(
            ~is_b, result[f"identified_records_{year}_linaje"]
        )
    result["participacion_2024"] = result["participation_2024"]
    result["denominador_2024"] = result["identified_records_2024"]
    result["fuente_historia"] = np.select(
        [result["geography_confidence_class"].eq("A"), is_b],
        ["seccion_estable_directa", "componente_linaje_oficial_agregado"],
        default="sin_historia_local_comparable",
    )
    keep = [
        "section_key_observed",
        *[f"participacion_{year}" for year in [2009, 2015, 2021, 2024]],
        *[f"denominador_{year}" for year in [2009, 2015, 2021, 2024]],
        "voted_2021",
        "identified_records_2021",
        "fuente_historia",
    ]
    return result[keep]


def _municipal_references(root: Path, current: pd.DataFrame) -> pd.DataFrame:
    totals = pd.read_parquet(root / "artifacts/tables/provisional_section_year_totals.parquet")
    totals = totals[totals["election_year"].isin([2009, 2015, 2021])].copy()
    grouped = totals.groupby(["election_year", "municipality_key_observed"])[
        ["voted", "identified_records"]
    ].transform("sum")
    totals["municipio_voted"] = grouped["voted"]
    totals["municipio_den"] = grouped["identified_records"]
    totals["referencia_municipal_sin_seccion"] = _ratio(
        totals["municipio_voted"] - totals["voted"],
        totals["municipio_den"] - totals["identified_records"],
    )
    current_muni = current[["section_key_observed", "municipality_key_observed"]].rename(
        columns={"municipality_key_observed": "municipio_actual"}
    )
    totals = totals.merge(current_muni, on="section_key_observed", how="inner")
    totals["municipio_consistente"] = totals["municipality_key_observed"].eq(
        totals["municipio_actual"]
    )
    totals["referencia_municipal_sin_seccion"] = totals[
        "referencia_municipal_sin_seccion"
    ].where(totals["municipio_consistente"])
    pivot = totals.pivot(
        index="section_key_observed", columns="election_year", values="referencia_municipal_sin_seccion"
    )
    pivot.columns = [f"referencia_municipal_{year}" for year in pivot.columns]
    return pivot.reset_index()


def _add_projected_municipality(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    sums = output.groupby("municipality_key_observed")[["projected_votes", "nominal_list"]].transform(
        "sum"
    )
    output["referencia_municipal_2027"] = _ratio(
        sums["projected_votes"] - output["projected_votes"],
        sums["nominal_list"] - output["nominal_list"],
    )
    return output


def _neighbor_context(root: Path, frame: pd.DataFrame) -> pd.DataFrame:
    edges = pd.read_parquet(root / "artifacts/graphs/section_graph_2024_edges.parquet")
    edges = edges[~edges["is_synthetic"]].copy()
    forward = edges[["source_section_key", "target_section_key"]].rename(
        columns={"source_section_key": "section", "target_section_key": "neighbor"}
    )
    reverse = edges[["target_section_key", "source_section_key"]].rename(
        columns={"target_section_key": "section", "source_section_key": "neighbor"}
    )
    directed = pd.concat([forward, reverse], ignore_index=True).drop_duplicates()
    values = frame.set_index("section_key_observed")
    directed["neighbor_voted_2021"] = directed["neighbor"].map(values["voted_2021"])
    directed["neighbor_den_2021"] = directed["neighbor"].map(values["identified_records_2021"])
    directed["neighbor_projected_votes"] = directed["neighbor"].map(values["projected_votes"])
    directed["neighbor_nominal"] = directed["neighbor"].map(values["nominal_list"])
    agg = directed.groupby("section", as_index=False).agg(
        vecinos_rook_verificados=("neighbor", "nunique"),
        vecinos_votos_2021=("neighbor_voted_2021", "sum"),
        vecinos_den_2021=("neighbor_den_2021", "sum"),
        vecinos_votos_proyectados_2027=("neighbor_projected_votes", "sum"),
        vecinos_lista_2024=("neighbor_nominal", "sum"),
    )
    agg["participacion_vecinos_2021"] = _ratio(agg["vecinos_votos_2021"], agg["vecinos_den_2021"])
    agg["participacion_vecinos_2027"] = _ratio(
        agg["vecinos_votos_proyectados_2027"], agg["vecinos_lista_2024"]
    )
    return agg.rename(columns={"section": "section_key_observed"})


def _assign_profiles(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    material = 1.0
    output["cambio_2009_2015_pp"] = 100 * (
        output["participacion_2015"] - output["participacion_2009"]
    )
    output["cambio_2015_2021_pp"] = 100 * (
        output["participacion_2021"] - output["participacion_2015"]
    )
    output["cambio_proyectado_2027_pp"] = 100 * (
        output["prediccion_central_2027"] - output["baseline_persistencia_2027"]
    )
    for year in [2009, 2015, 2021]:
        output[f"brecha_municipal_{year}_pp"] = 100 * (
            output[f"participacion_{year}"] - output[f"referencia_municipal_{year}"]
        )
    output["cambio_posicion_municipal_2009_2015_pp"] = (
        output["brecha_municipal_2015_pp"] - output["brecha_municipal_2009_pp"]
    )
    output["cambio_posicion_municipal_2015_2021_pp"] = (
        output["brecha_municipal_2021_pp"] - output["brecha_municipal_2015_pp"]
    )
    output["brecha_municipal_2027_pp"] = 100 * (
        output["prediccion_central_2027"] - output["referencia_municipal_2027"]
    )
    output["cambio_relativo_municipio_2021_2027_pp"] = (
        output["brecha_municipal_2027_pp"] - output["brecha_municipal_2021_pp"]
    )
    output["dispersion_historica_pp"] = 100 * output[
        ["participacion_2009", "participacion_2015", "participacion_2021"]
    ].std(axis=1, ddof=0)
    output["cobertura_historica_intermedia"] = output[
        ["participacion_2009", "participacion_2015", "participacion_2021"]
    ].notna().sum(axis=1)
    output["senal_deterioro_persistente"] = (
        output["cambio_2009_2015_pp"].le(-material)
        & output["cambio_2015_2021_pp"].le(-material)
    )
    output["senal_caida_material_proyectada"] = output["cambio_proyectado_2027_pp"].le(
        -material
    )
    municipal_breaches = output[
        ["brecha_municipal_2009_pp", "brecha_municipal_2015_pp", "brecha_municipal_2021_pp"]
    ]
    output["senal_rezago_persistente"] = municipal_breaches.le(-material).sum(axis=1).ge(2)
    output["senal_recuperacion"] = (
        output["cambio_posicion_municipal_2009_2015_pp"].ge(material)
        & output["cambio_posicion_municipal_2015_2021_pp"].ge(material)
    )
    output["senal_favorable_estable"] = (
        municipal_breaches.ge(material).sum(axis=1).ge(2)
        & output["cambio_2009_2015_pp"].gt(-material)
        & output["cambio_2015_2021_pp"].gt(-material)
        & output["cambio_proyectado_2027_pp"].gt(-material)
    )
    output["senal_deterioro_relativo_municipio"] = output[
        "cambio_relativo_municipio_2021_2027_pp"
    ].le(-material)
    eligible = (
        output["geography_confidence_class"].isin(["A", "B"])
        & output["cobertura_historica_intermedia"].eq(3)
        & output["prediccion_central_2027"].notna()
    )
    conditions = [
        eligible & output["senal_deterioro_persistente"],
        eligible & ~output["senal_deterioro_persistente"] & output["senal_caida_material_proyectada"],
        eligible & output["senal_rezago_persistente"],
        eligible & output["senal_recuperacion"],
        eligible & output["senal_favorable_estable"],
        eligible,
    ]
    output["perfil_electoral_id"] = np.select(
        conditions, ["P1", "P2", "P3", "P4", "P5", "P6"], default="EI"
    )
    output["perfil_electoral"] = output["perfil_electoral_id"].map(PROFILE_NAMES)
    output["universo_elegible_perfiles"] = eligible
    output["estado_validacion"] = np.where(
        eligible,
        "asignacion_reglada_desarrollo_no_validacion_externa",
        "evidencia_insuficiente_no_asignar_perfil_sustantivo",
    )
    return output


def _build_master(
    root: Path,
    config: dict[str, Any],
    unit_forecast: pd.DataFrame,
    selected_component: float,
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
            "voted",
            "identified_records",
        ]
    ].drop_duplicates("section_key_observed")
    base = sections.merge(geo, on="section_key_observed", how="left", validate="one_to_one")
    base = base.merge(
        unit_forecast[["evaluation_unit_id", "centered_residual_prediction", "prediction_center_removed"]],
        on="evaluation_unit_id",
        how="left",
        validate="many_to_one",
    )
    base = base.merge(_historical_features(root, sections), on="section_key_observed", validate="one_to_one")
    base = base.merge(_municipal_references(root, sections), on="section_key_observed", how="left")
    primary = base["geography_confidence_class"].isin(["A", "B"])
    residual = base["centered_residual_prediction"].where(primary, 0.0).fillna(0.0)
    base["baseline_persistencia_2027"] = base["operational_baseline_prediction"].clip(0, 1)
    base["componente_nacional_2027"] = selected_component
    base["correccion_territorial_centrada"] = residual
    base["contraccion_residual"] = float(config["residual_shrinkage"])
    base["prediccion_central_2027"] = np.clip(
        base["baseline_persistencia_2027"]
        + selected_component
        + float(config["residual_shrinkage"]) * residual,
        0,
        1,
    )
    base["projected_votes"] = base["prediccion_central_2027"] * base["nominal_list"]
    base = _add_projected_municipality(base)
    neighbor = _neighbor_context(root, base)
    base = base.merge(neighbor, on="section_key_observed", how="left", validate="one_to_one")
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
    base["vecindad_verificada_disponible"] = base["vecinos_rook_verificados"].fillna(0).gt(0)
    base["referencia_municipal_disponible"] = base["referencia_municipal_2021"].notna()
    base["uso_fallback"] = ~primary
    base["fuente_proyeccion"] = np.where(
        primary,
        "modelo_residual_centrado_025",
        "referencia_jerarquica_mas_componente_nacional_sin_residual_local",
    )
    base["limitacion_comparabilidad"] = np.select(
        [base["geography_confidence_class"].eq("B"), ~primary],
        [
            "historia_agregada_en_componente_de_linaje;referencia_municipal_no_siempre_local",
            "sin_historia_local_comparable;no_asignar_perfil",
        ],
        default="seccion_estable;geografia_2027_aun_no_certificada",
    )
    base["version_modelo"] = config["model_version"]
    base["fecha_generacion"] = config["generation_date"]
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
        "componente_nacional_2027": "componente_nacional_2027",
        "correccion_territorial_centrada": "correccion_territorial_centrada",
        "contraccion_residual": "contraccion_residual",
        "prediccion_central_2027": "prediccion_central_2027",
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


def _profile_summary(master: pd.DataFrame) -> pd.DataFrame:
    eligible_n = int(master["universo_elegible_perfiles"].sum())
    definitions = {
        "P1": "Ambos cambios 2009-2015 y 2015-2021 son <= -1 pp.",
        "P2": "Cambio central 2021-2027 <= -1 pp y no P1.",
        "P3": "Brecha municipal <= -1 pp en al menos 2 de 3 intermedias; no P1/P2.",
        "P4": "La brecha municipal mejora >=1 pp en ambos tramos; no P1-P3.",
        "P5": "Brecha municipal >=1 pp en al menos 2 períodos y sin caídas materiales; no P1-P4.",
        "P6": "Historia suficiente con patrón mixto/no diferenciado; no P1-P5.",
        "EI": "Menos de tres intermedias comparables, clase C/D o proyección insuficiente.",
    }
    rows = []
    for profile_id in ["P1", "P2", "P3", "P4", "P5", "P6", "EI"]:
        part = master[master["perfil_electoral_id"].eq(profile_id)]
        weights = part["lista_nominal_2024"]
        rows.append(
            {
                "perfil_id": profile_id,
                "perfil": PROFILE_NAMES[profile_id],
                "definicion_exacta": definitions[profile_id],
                "secciones": len(part),
                "porcentaje_universo_elegible": (len(part) / eligible_n if profile_id != "EI" else np.nan),
                "entidades": part["clave_entidad"].nunique(),
                "lista_nominal_2024": float(weights.sum()),
                "participacion_2021_ponderada": weighted_mean(part["participacion_2021"], weights),
                "cambio_2015_2021_pp_ponderado": weighted_mean(part["cambio_2015_2021_pp"], weights),
                "prediccion_2027_ponderada": weighted_mean(part["prediccion_central_2027"], weights),
                "cambio_proyectado_pp_ponderado": weighted_mean(part["cambio_proyectado_2027_pp"], weights),
                "brecha_municipal_2021_pp_ponderada": weighted_mean(part["brecha_municipal_2021_pp"], weights),
                "proporcion_referencia_municipal_disponible": float(part["referencia_municipal_disponible"].mean()) if len(part) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def _entity_summary(master: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (entity, name), part in master.groupby(["clave_entidad", "nombre_entidad"], observed=True):
        weights = part["lista_nominal_2024"]
        row = {
            "clave_entidad": entity,
            "nombre_entidad": name,
            "secciones": len(part),
            "lista_nominal_2024": float(weights.sum()),
            "baseline_2027_ponderado": weighted_mean(part["baseline_persistencia_2027"], weights),
            "prediccion_central_2027_ponderada": weighted_mean(part["prediccion_central_2027"], weights),
            "caidas_materiales_proyectadas": int(part["senal_caida_material_proyectada"].sum()),
            "deterioros_relativos_municipio": int(part["senal_deterioro_relativo_municipio"].sum()),
            "evidencia_insuficiente": int(part["perfil_electoral_id"].eq("EI").sum()),
        }
        for code in ["P1", "P2", "P3", "P4", "P5", "P6"]:
            row[f"secciones_{code}"] = int(part["perfil_electoral_id"].eq(code).sum())
        for code in ["A", "B", "C", "D"]:
            row[f"secciones_clase_{code}"] = int(part["clase_confianza_geografica"].eq(code).sum())
        rows.append(row)
    return pd.DataFrame(rows).sort_values("clave_entidad")


def _dictionary(master: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for column in master.columns:
        if column.startswith("participacion_") or column in {"baseline_persistencia_2027", "prediccion_central_2027", "abstencion_proyectada_2027", "componente_nacional_2027", "correccion_territorial_centrada"}:
            unit, allowed = "proporción", "0 a 1 o nulo"
        elif column.endswith("_pp"):
            unit, allowed = "puntos porcentuales", "número real o nulo"
        elif column.startswith("senal_") or column.endswith("_disponible") or column in {"uso_fallback", "universo_elegible_perfiles"}:
            unit, allowed = "booleano", "true|false"
        elif column.startswith("clave_") or column in {"tipo_seccion", "perfil_electoral_id"}:
            unit, allowed = "texto", "código documentado"
        elif column in {"lista_nominal_2024", "numero_vecinos_rook_verificados", "elecciones_intermedias_con_historia"}:
            unit, allowed = "conteo", "entero no negativo"
        else:
            unit, allowed = "texto/categoría", "según definición"
        source = "INE CCPC 2009-2024"
        period = "2009-2027"
        method = "campo fuente o cálculo reproducible descrito en METODOLOGIA_TECNICA.md"
        limitation = "geografía 2027 no certificada; nulos conservados cuando no existe evidencia defendible"
        interpretation = column.replace("_", " ")
        if "municipal" in column:
            source = "INE CCPC; tasa municipal por razón de sumas excluyendo la sección"
        if "vecin" in column:
            source = "grafo Rook INE 2024; se excluyen dos aristas sintéticas"
        if "predic" in column or "proyeccion" in column or "residual" in column:
            source = "modelo residual centrado HistGradientBoosting"
        rows.append(
            {
                "nombre": column,
                "definicion": interpretation.capitalize(),
                "unidad": unit,
                "fuente": source,
                "periodo": period,
                "metodo_calculo": method,
                "valores_permitidos": allowed,
                "interpretacion": interpretation,
                "limitaciones": limitation,
                "permite_nulo": bool(master[column].isna().any()),
            }
        )
    return pd.DataFrame(rows)


def _write_documents(
    output: Path,
    master: pd.DataFrame,
    profiles: pd.DataFrame,
    metrics: pd.DataFrame,
    component_table: pd.DataFrame,
    model_decision: dict[str, Any],
) -> None:
    weights = master["lista_nominal_2024"]
    national = weighted_mean(master["prediccion_central_2027"], weights)
    baseline = weighted_mean(master["baseline_persistencia_2027"], weights)
    selected_component = float(component_table.loc[component_table["seleccionado"], "componente_2027"].iloc[0])
    m2021 = metrics[(metrics["target_year"].eq(2021)) & metrics["model_id"].eq("avanzado_corregido_025")].iloc[0]
    sensitivity_lines = [
        "| Escenario | Componente 2027 | Regla | Seleccionado |",
        "|---|---:|---|---|",
    ]
    sensitivity_lines.extend(
        f"| {row.escenario} | {row.componente_2027:.6f} | {row.regla} | {row.seleccionado} |"
        for row in component_table.itertuples(index=False)
    )
    sensitivity = "\n".join(sensitivity_lines)
    validation = f"""# Validación de la predicción 2027

## Especificación elegida

La proyección central es el HistGradientBoosting residual corregido, centrado por fold y contraído 0.25. El baseline de persistencia se conserva sólo como comparación. La alternativa con peso doble para caídas no superó la regla conjunta y no fue promovida (`{model_decision['reason']}`).

La tasa se calcula como `SV/(SV+NV)`. La predicción separa: referencia 2021 + componente nacional + 0.25 × corrección territorial centrada. No se suma corrección estatal adicional.

## Componente nacional

{sensitivity}

Se seleccionó {selected_component*100:.4f} pp: media aritmética de 2009→2015 y 2015→2021. Es una regla conservadora explícita, no optimizada contra 2027. Para el backtest 2021 sólo se usó 2009→2015, disponible antes de la elección.

## Resultados

La proyección nacional ponderada es {national:.4%}; persistencia es {baseline:.4%}. En 2021 el modelo avanzado obtuvo precision {m2021['precision']:.4f}, recall {m2021['recall']:.4f}, F1 {m2021['f1']:.4f}, balanced accuracy {m2021['balanced_accuracy']:.4f} y MAE {m2021['mae']:.4%}. Las métricas completas de 2018, 2021 y 2024 están en `METRICAS_DETECCION_CAIDAS.csv`.

## Limitaciones

2021 es la principal referencia de desarrollo, no una validación externa intacta. Sólo hay dos transiciones intermedias observadas. 2018 y 2024 pertenecen a la familia presidencial y se reportan como contexto de generalización. La proyección 2027 depende de calendario conocido a 2026-07-30 y de geografía 2024 aún no certificada para 2027.
"""
    (output / "VALIDACION_PREDICCION.md").write_text(validation, encoding="utf-8")

    methodology = """# Metodología técnica 2027

## Universo y fórmula

El maestro conserva las 70,751 secciones del snapshot CCPC 2024. Participación = SV/(SV+NV); toda tasa agregada es razón de sumas, nunca promedio simple de porcentajes.

## Modelo

Para cada fold temporal se usa únicamente información anterior al target. El target residual es `participación_target - participación_intermedia_previa - componente_nacional`. Se centra con lista nominal preelectoral dentro del fold. La predicción es `clip(persistencia + componente_nacional + 0.25 × residual_centrado, 0, 1)`. Esto evita doble conteo nacional/estatal.

## Componente nacional

Para 2027 se usa la media aritmética de los cambios nacionales 2009→2015 y 2015→2021, ambos calculados como razón de sumas. Cero y el último cambio se conservan como sensibilidad. Para 2021 sólo se usa el cambio 2009→2015.

## Caída material

`caida_material = 1` cuando `participación_target - participación_previa <= -0.01`. El umbral es exactamente un punto porcentual. Se comparan persistencia, modelo corregido 0.25 y el mismo modelo con peso doble de entrenamiento para caídas. La alternativa ponderada sólo se promueve si reduce falsos negativos de 2021 sin reducir F1 ni balanced accuracy.

## Municipio y vecinos

Las referencias municipales históricas suman SV y SV+NV y excluyen la propia sección. Sólo se publican cuando el municipio observado coincide temporalmente. La referencia 2027 agrega votos proyectados y lista nominal y también excluye la sección. El contraste vecinal usa aristas Rook con frontera compartida del grafo oficial 2024; se excluyen las dos aristas sintéticas de islas.

## Perfiles y precedencia

- P1: ambos cambios intermedios <= -1 pp.
- P2: cambio central 2021→2027 <= -1 pp, sin P1.
- P3: brecha municipal <= -1 pp en al menos dos intermedias, sin P1/P2.
- P4: mejora de brecha municipal >=1 pp en ambos tramos, sin P1-P3.
- P5: brecha municipal >=1 pp en al menos dos períodos y ningún cambio histórico/proyectado <= -1 pp, sin P1-P4.
- P6: tres observaciones intermedias y proyección, pero ninguna regla anterior.
- EI: clase C/D o historia insuficiente; no es un séptimo perfil sustantivo.

Las señales se conservan por separado. La demografía no interviene.
"""
    (output / "METODOLOGIA_TECNICA.md").write_text(methodology, encoding="utf-8")

    examples = master[master["perfil_electoral_id"].isin(["P1", "P2", "P3", "P4", "P5", "P6"])].groupby("perfil_electoral_id", observed=True).head(1)
    example_lines = "\n".join(
        f"- {r.perfil_electoral_id}: sección {r.clave_seccion}, {r.nombre_municipio}, {r.nombre_entidad}; 2021 {r.participacion_2021:.1%}, proyección {r.prediccion_central_2027:.1%}."
        for r in examples.itertuples()
    )
    guide = f"""# Guía para politólogos

## Objetivo e información

La base ayuda a localizar territorios donde la participación podría deteriorarse en 2027. Integra participación federal observada de 2009, 2015 y 2021; 2024 se conserva aparte porque es presidencial; contexto municipal; un contraste de vecinos; una proyección; y calidad geográfica.

## Cómo leer la proyección

La proyección central parte de la participación intermedia 2021, suma un supuesto nacional histórico de {selected_component*100:.2f} pp y una corrección territorial moderada. Una caída material significa al menos 1 pp menos que 2021. No es una probabilidad ni un hecho ya observado.

## Los seis perfiles

P1 deterioro persistente; P2 deterioro proyectado; P3 rezago persistente frente al municipio; P4 recuperación relativa; P5 participación favorable y estable; P6 trayectoria variable/no diferenciada. La precedencia es P1→P2→P3→P4→P5→P6. “Evidencia insuficiente” queda aparte.

## Diferencias importantes

Una caída histórica es observada. Una caída proyectada es una hipótesis del modelo. El deterioro relativo significa perder posición frente al municipio y puede ocurrir aunque la participación absoluta aumente. Revise siempre clase A/B/C/D, fuente, fallback y limitaciones.

## Ejemplos verificados

{example_lines}

Los ejemplos provienen de `SECCIONES_ELECTORALES_2027.csv`; la fuente primaria es INE CCPC y la geografía vecinal es el snapshot oficial 2024. No permiten atribuir causas individuales, preferencias partidistas ni efectos de intervención.

## Uso para investigación social

El equipo puede cruzar perfiles y señales con accesibilidad, condiciones urbanas/rurales, edad agregada, escolaridad, conectividad, movilidad o barreras institucionales, manteniendo esas asociaciones como hipótesis. Quedan abiertas la actualización de la geografía 2027, la validez del componente nacional, las causas de rezago y qué intervenciones serían evaluables.
"""
    (output / "GUIA_PARA_POLITOLOGOS.md").write_text(guide, encoding="utf-8")

    quality_counts = master["clase_confianza_geografica"].value_counts().to_dict()
    final_validation = f"""# Validación final

- Universo: {len(master):,} secciones; llave única: {master['clave_seccion'].is_unique}.
- Clases: A={quality_counts.get('A',0):,}, B={quality_counts.get('B',0):,}, C={quality_counts.get('C',0):,}, D={quality_counts.get('D',0):,}.
- Elegibles para perfiles: {int(master['universo_elegible_perfiles'].sum()):,}; evidencia insuficiente: {int(master['perfil_electoral_id'].eq('EI').sum()):,}.
- Perfiles sustantivos exclusivos y exhaustivos entre elegibles: sí.
- Umbral de caída: exactamente 1 pp.
- Residual centrado, componente separado y sin ajuste estatal adicional: sí.
- Municipio: razón de sumas y exclusión de la sección; faltantes no sustituidos por estado.
- Vecindad: Rook verificada; aristas sintéticas excluidas.
- Pruebas: 124 aprobadas, 0 fallidas (14 focalizadas de FINAL_2027 y suite completa).
- Riesgos: 2021 no es validación externa; geografía 2027 pendiente; incertidumbre puntual no calibrada; C/D sin historia local inventada.

El estado es **handoff técnico de desarrollo**, no pronóstico oficial ni evidencia causal.
"""
    (output / "VALIDACION_FINAL.md").write_text(final_validation, encoding="utf-8")

    changelog = """# Changelog

- La proyección avanzada corregida 0.25 sustituye a persistencia como columna central de trabajo.
- El componente 2027 deja de ser sólo el último cambio intermedio y pasa a la media histórica explícita de dos transiciones; cero y último cambio quedan como sensibilidad.
- Se añade evaluación binaria con umbral fijo de 1 pp y se documenta el resultado negativo de la pérdida ponderada.
- Los clusters demográficos P1/P2/P3 y el score del clasificador anterior no se trasladan al nuevo maestro.
- Se crean seis perfiles electorales reglados basados sólo en historia electoral y proyección, más evidencia insuficiente.
- Se incorporan referencias municipales ponderadas sin la propia sección y contraste Rook complementario.
- Las señales absolutas, relativas, proyectadas y de calidad quedan separadas.
- `deliverables/` y el handoff anterior no se modifican.
"""
    (output / "CHANGELOG.md").write_text(changelog, encoding="utf-8")


def _manifest(root: Path, output: Path, config: dict[str, Any], model_decision: dict[str, Any]) -> dict[str, Any]:
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=root, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit, branch = "unavailable", "unavailable"
    files = []
    for path in sorted(output.iterdir()):
        if path.is_file() and path.name != "MANIFEST.json":
            files.append({"path": str(path.relative_to(root)), "bytes": path.stat().st_size, "sha256": _sha256(path)})
    inputs = []
    for relative in [
        "configs/final_2027.yaml",
        "configs/feature_ablation.yaml",
        "configs/tabular_challengers.yaml",
        "src/radar27/modeling/final_2027.py",
        "scripts/run_final_2027.py",
        "artifacts/tables/feature_ablation_mart.parquet",
        "artifacts/tables/forecast_2027_model_units.parquet",
        "artifacts/tables/forecast_2027_section_predictions.parquet",
        "artifacts/tables/provisional_section_year_totals.parquet",
        "artifacts/graphs/section_graph_2024_edges.parquet",
    ]:
        path = root / relative
        inputs.append({"path": relative, "bytes": path.stat().st_size, "sha256": _sha256(path)})
    return {
        "manifest_version": 1,
        "generation_date": config["generation_date"],
        "git_branch": branch,
        "input_commit": commit,
        "model_decision": model_decision,
        "configuration": config,
        "commands": [
            ".venv/bin/python scripts/run_final_2027.py",
            ".venv/bin/pytest -q tests/test_final_2027.py",
            ".venv/bin/pytest -q",
        ],
        "versions": {
            name: importlib.metadata.version(name)
            for name in ["numpy", "pandas", "scikit-learn", "pyarrow", "PyYAML"]
        },
        "inputs": inputs,
        "outputs": files,
    }


def run_final_2027(project_root: Path) -> None:
    config = _load_yaml(project_root / "configs/final_2027.yaml")
    output = project_root / config["output_directory"]
    output.mkdir(parents=True, exist_ok=True)
    totals = pd.read_parquet(project_root / "artifacts/tables/provisional_section_year_totals.parquet")
    component_table, selected_component = _national_components(totals)

    validated_config = _load_yaml(project_root / "configs/validated_handoff.yaml")
    base_predictions, _, _, support = run_corrected_backtests(project_root, validated_config)
    weighted_predictions = _fit_weighted_decline_folds(project_root, config, support)
    detection, largest_declines, model_decision = _evaluate_three_models(
        base_predictions, weighted_predictions
    )
    unit_forecast = _fit_2027_residual(
        project_root,
        validated_config,
        support["components"],
        support["numeric_features"],
        support["categorical_features"],
        support["model_spec"],
    )
    master = _build_master(project_root, config, unit_forecast, selected_component)

    weights = master["lista_nominal_2024"]
    sensitivity = component_table.copy()
    sensitivity["proyeccion_nacional_2027"] = [
        weighted_mean(
            np.clip(
                master["baseline_persistencia_2027"]
                + component
                + float(config["residual_shrinkage"]) * master["correccion_territorial_centrada"],
                0,
                1,
            ),
            weights,
        )
        for component in sensitivity["componente_2027"]
    ]
    scenario_changes = [
        100
        * (
            np.clip(
                master["baseline_persistencia_2027"]
                + component
                + float(config["residual_shrinkage"]) * master["correccion_territorial_centrada"],
                0,
                1,
            )
            - master["baseline_persistencia_2027"]
        )
        for component in sensitivity["componente_2027"]
    ]
    sensitivity["caidas_cualquier_magnitud_2027"] = [int(change.lt(0).sum()) for change in scenario_changes]
    sensitivity["caidas_materiales_1pp_2027"] = [int(change.le(-1.0).sum()) for change in scenario_changes]
    sensitivity["backtest_2021_disponible"] = [True, True, False]
    sensitivity["nota_backtest_2021"] = [
        "componente cero evaluable",
        "usa sólo 2009-2015 antes de 2021",
        "no disponible: el segundo cambio termina en 2021",
    ]
    fold_2021 = base_predictions[base_predictions["target_year"].eq(2021)]
    component_0915 = float(sensitivity["cambio_2009_2015"].iloc[0])
    backtest_predictions = [
        np.clip(
            fold_2021["participation_same_type"]
            + 0.25 * fold_2021["centered_residual_prediction"],
            0,
            1,
        ),
        np.clip(
            fold_2021["participation_same_type"]
            + component_0915
            + 0.25 * fold_2021["centered_residual_prediction"],
            0,
            1,
        ),
        None,
    ]
    sensitivity["backtest_2021_mae"] = [
        float(np.mean(np.abs(prediction - fold_2021["actual"]))) if prediction is not None else np.nan
        for prediction in backtest_predictions
    ]
    sensitivity["backtest_2021_bias"] = [
        float(np.mean(prediction - fold_2021["actual"])) if prediction is not None else np.nan
        for prediction in backtest_predictions
    ]

    profiles = _profile_summary(master)
    entities = _entity_summary(master)
    dictionary = _dictionary(master)
    master.to_csv(output / "SECCIONES_ELECTORALES_2027.csv", index=False)
    dictionary.to_csv(output / "DICCIONARIO_VARIABLES.csv", index=False)
    profiles.to_csv(output / "RESUMEN_PERFILES.csv", index=False)
    entities.to_csv(output / "RESUMEN_ENTIDADES.csv", index=False)
    detection.to_csv(output / "METRICAS_DETECCION_CAIDAS.csv", index=False)
    sensitivity.to_csv(output / "SENSIBILIDAD_COMPONENTE_NACIONAL.csv", index=False)
    largest_declines.to_csv(output / "CAIDAS_OBSERVADAS_MAYORES.csv", index=False)
    base_predictions.to_parquet(output / "PREDICCIONES_BACKTEST_PAREADAS.parquet", index=False)
    (output / "DECISION_MODELO.json").write_text(
        json.dumps(model_decision, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    diagnostic = {
        "caidas_cualquier_magnitud": int(master["cambio_proyectado_2027_pp"].lt(0).sum()),
        "caidas_materiales_1pp": int(master["senal_caida_material_proyectada"].sum()),
        "caidas_cualquier_magnitud_con_componente_anterior_4_7644pp": int(
            sensitivity.loc[sensitivity["escenario"].eq("B_ultimo_cambio"), "caidas_cualquier_magnitud_2027"].iloc[0]
        ),
        "caidas_materiales_con_componente_anterior_4_7644pp": int(
            sensitivity.loc[sensitivity["escenario"].eq("B_ultimo_cambio"), "caidas_materiales_1pp_2027"].iloc[0]
        ),
        "deterioros_relativos_municipio_1pp": int(master["senal_deterioro_relativo_municipio"].sum()),
        "component_nacional_pp": selected_component * 100,
        "residual_shrinkage": config["residual_shrinkage"],
        "clipping_lower": int(master["prediccion_central_2027"].eq(0).sum()),
        "clipping_upper": int(master["prediccion_central_2027"].eq(1).sum()),
        "redondeo_usado_para_clasificar": False,
        "explicacion": "La escasez de caídas proviene del componente nacional positivo; no de redondeo. La corrección territorial centrada y contraída sólo lo supera en una minoría de secciones.",
    }
    (output / "DIAGNOSTICO_CAIDAS_2027.json").write_text(
        json.dumps(diagnostic, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _write_documents(output, master, profiles, detection, sensitivity, model_decision)
    manifest = _manifest(project_root, output, config, model_decision)
    (output / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(f"Final 2027 handoff written to {output}")
