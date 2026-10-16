from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from radar27.modeling.validated_handoff import (
    COLUMN_DICTIONARY,
    available_national_component,
    center_with_available_weights,
    national_turnout_rates,
)

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "handoff"


def test_national_component_uses_only_prior_same_family_elections() -> None:
    totals = pd.DataFrame(
        {
            "election_year": [2009, 2015, 2021, 2024],
            "election_family": ["midterm", "midterm", "midterm", "presidential"],
            "voted": [40.0, 50.0, 60.0, 90.0],
            "identified_records": [100.0, 100.0, 100.0, 100.0],
        }
    )
    rates = national_turnout_rates(totals)
    result = available_national_component(rates, 2021, "midterm")
    assert result["source_recent_year"] == 2015
    assert result["source_previous_year"] == 2009
    assert np.isclose(result["national_component"], 0.1)


def test_centered_residual_has_zero_available_weighted_mean() -> None:
    centered, removed = center_with_available_weights(
        np.array([0.1, 0.2, -0.1]), np.array([1.0, 2.0, 3.0])
    )
    assert np.isclose(removed, 1 / 30)
    assert abs(np.average(centered, weights=[1.0, 2.0, 3.0])) < 1e-15


def test_master_has_one_unique_row_per_section_and_valid_ranges() -> None:
    master = pd.read_csv(HANDOFF / "SECCIONES_ELECTORALES_CLASIFICADAS.csv", dtype={
        "clave_entidad": "string",
        "clave_municipio": "string",
        "clave_seccion": "string",
    })
    assert len(master) == 70_751
    assert master["clave_seccion"].is_unique
    assert master["prediccion_operativa_2027"].between(0, 1).all()
    assert master["prediccion_exploratoria_centrada_2027"].between(0, 1).all()


def test_dictionary_exactly_describes_master_columns() -> None:
    master = pd.read_csv(HANDOFF / "SECCIONES_ELECTORALES_CLASIFICADAS.csv", nrows=1)
    dictionary = pd.read_csv(HANDOFF / "DICCIONARIO_VARIABLES.csv")
    assert dictionary["variable"].is_unique
    assert list(dictionary["variable"]) == list(master.columns)
    assert set(master.columns) == set(COLUMN_DICTIONARY)


def test_centering_diagnostics_and_paired_samples() -> None:
    diagnostics = pd.read_csv(HANDOFF / "DIAGNOSTICO_CENTRADO_RESIDUAL.csv")
    assert diagnostics["centered_target_weighted_mean"].abs().max() < 1e-12
    assert diagnostics["evaluation_centered_prediction_weighted_mean"].abs().max() < 1e-12
    metrics = pd.read_csv(HANDOFF / "METRICAS_VALIDACION.csv")
    assert metrics.groupby("target_year")["evaluation_units"].nunique().eq(1).all()
    assert metrics.groupby("target_year")["sections_represented"].nunique().eq(1).all()


def test_risk_ties_and_special_38_are_labeled() -> None:
    master = pd.read_csv(HANDOFF / "SECCIONES_ELECTORALES_CLASIFICADAS.csv")
    risk = json.loads((HANDOFF / "REGLA_SCORE_RIESGO.json").read_text(encoding="utf-8"))
    high = master["categoria_score_riesgo_experimental"].eq(
        "high_score_inclusive_p80_with_ties"
    )
    assert int(high.sum()) == int(risk["selected_sections"])
    assert int(risk["ties_at_threshold"]) == 3_867
    special = master[
        master["clase_confianza_geografica"].isin(["A", "B"])
        & master["fuente_caracteristicas_eceg"].eq("entity_reference_fallback")
    ]
    assert len(special) == 38
    assert special["fuente_perfil_electoral"].eq(
        "direct_age_sex_counts_aggregated_to_model_unit"
    ).all()


def test_profiles_require_local_evidence() -> None:
    master = pd.read_csv(HANDOFF / "SECCIONES_ELECTORALES_CLASIFICADAS.csv")
    assigned = master["perfil_exploratorio_id"].notna()
    assert master.loc[assigned, "clase_confianza_geografica"].isin(["A", "B"]).all()
    assert master.loc[~assigned, "estado_validacion_perfil"].eq(
        "not_assigned_insufficient_local_profile_evidence"
    ).all()


def test_entity_summary_reconciles_master() -> None:
    master = pd.read_csv(HANDOFF / "SECCIONES_ELECTORALES_CLASIFICADAS.csv")
    summary = pd.read_csv(HANDOFF / "RESUMEN_ENTIDADES.csv")
    assert int(summary["secciones"].sum()) == len(master)
    assert abs(summary["lista_nominal_2024"].sum() - master["lista_nominal_2024"].sum()) < 1e-6
    assert (
        summary[["secciones_clase_A", "secciones_clase_B", "secciones_clase_C", "secciones_clase_D"]]
        .sum(axis=1)
        .eq(summary["secciones"])
        .all()
    )


def test_previous_results_manifest_matches_current_inputs() -> None:
    manifest = pd.read_csv(HANDOFF / "MANIFIESTO_RESULTADOS_ANTERIORES.csv")
    assert manifest["preservation_status"].eq("read_only_input_not_overwritten").all()
    assert len(manifest) == 6
    for row in manifest.itertuples(index=False):
        digest = hashlib.sha256((ROOT / row.path).read_bytes()).hexdigest()
        assert digest == row.sha256


def test_operational_export_matches_conservative_model_decision() -> None:
    decision = json.loads(
        (HANDOFF / "DECISION_MODELO_OPERATIVO.json").read_text(encoding="utf-8")
    )
    master = pd.read_csv(HANDOFF / "SECCIONES_ELECTORALES_CLASIFICADAS.csv")
    assert decision["operational_model_id"] == "A_persistence"
    assert np.allclose(
        master["prediccion_operativa_2027"],
        master["participacion_referencia_historica_2021"],
    )
    assert master["version_geografica"].eq("2024_snapshot_not_2027_certified").all()
    assert set(master["perfil_exploratorio_id"].dropna()) == {"P1", "P2", "P3"}
