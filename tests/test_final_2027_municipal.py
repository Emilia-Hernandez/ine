from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "handoff/FINAL_2027_MUNICIPAL"


def _master() -> pd.DataFrame:
    return pd.read_csv(
        OUT / "SECCIONES_ELECTORALES_2027.csv",
        dtype={"clave_entidad": "string", "clave_municipio": "string", "clave_seccion": "string"},
    )


def test_universe_unique_keys_and_prediction_ranges() -> None:
    master = _master()
    assert len(master) == 70_751
    assert master["clave_seccion"].is_unique
    for column in [
        "baseline_persistencia_2027",
        "prediccion_modelo_A_nacional_2027",
        "prediccion_modelo_B_municipal_2027",
        "prediccion_modelo_C_municipal_jerarquico_2027",
        "prediccion_central_2027",
    ]:
        assert master[column].between(0, 1).all()


def test_three_models_are_paired_in_every_fold() -> None:
    metrics = pd.read_csv(OUT / "METRICAS_MODELOS.csv")
    assert set(metrics["model_id"]) == {
        "A_nacional_actual",
        "B_municipal",
        "C_municipal_jerarquico",
    }
    assert metrics.groupby("target_year")["unidades_evaluacion"].nunique().eq(1).all()
    assert metrics.groupby("target_year")["secciones_representadas"].nunique().eq(1).all()


def test_2021_component_uses_only_2009_to_2015() -> None:
    components = pd.read_parquet(OUT / "COMPONENTES_MUNICIPALES_HISTORICOS.parquet")
    projected = components[
        components["target_year"].eq(2021)
        & components["transition_role"].eq("projected_from_prior")
    ]
    assert set(projected["from_year"]) == {2009}
    assert set(projected["to_year"]) == {2015}
    assert projected["to_year"].max() < 2021


def test_neighbor_features_are_temporally_valid() -> None:
    for year in [2015, 2018, 2021, 2024]:
        nodes = pd.read_parquet(ROOT / f"artifacts/gnn_dataset/nodes_{year}.parquet")
        assert nodes["max_electoral_feature_year"].max() < year
        assert nodes["context_source_max_year"].max() < year
    decision = json.loads((OUT / "DECISION_MODELO.json").read_text(encoding="utf-8"))
    assert len(decision["neighbor_features_temporally_valid"]) == 4


def test_hierarchical_component_uses_documented_weight_and_is_bounded() -> None:
    municipalities = pd.read_csv(OUT / "RESUMEN_MUNICIPIOS.csv")
    valid = municipalities[municipalities["cambio_municipal_promedio"].notna()].copy()
    expected = (
        valid["peso_municipal"] * valid["cambio_municipal_promedio"]
        + (1 - valid["peso_municipal"]) * valid["referencia_estatal"]
    )
    assert valid["peso_municipal"].between(0, 1).all()
    assert np.allclose(valid["componente_modelo_C"], expected)
    assert (
        (valid["componente_modelo_C"] - valid["referencia_estatal"]).abs()
        <= (valid["componente_modelo_B"] - valid["referencia_estatal"]).abs() + 1e-12
    ).all()


def test_residual_is_centered_within_municipality_and_fold() -> None:
    diagnostics = pd.read_csv(OUT / "DIAGNOSTICO_CENTRADO_MUNICIPAL.csv")
    assert diagnostics["centered_weighted_mean"].abs().max() < 1e-12
    assert set(diagnostics["model_id"]) == {"modelo_B", "modelo_C"}


def test_no_double_counting_in_municipal_predictions() -> None:
    master = _master()
    expected_b = np.clip(
        master["baseline_persistencia_2027"]
        + master["componente_municipal_modelo_B_2027"]
        + 0.25 * master["residual_centrado_modelo_B"],
        0,
        1,
    )
    expected_c = np.clip(
        master["baseline_persistencia_2027"]
        + master["componente_municipal_modelo_C_2027"]
        + 0.25 * master["residual_centrado_modelo_C"],
        0,
        1,
    )
    assert np.allclose(master["prediccion_modelo_B_municipal_2027"], expected_b)
    assert np.allclose(master["prediccion_modelo_C_municipal_jerarquico_2027"], expected_c)


def test_model_a_retained_after_municipal_joint_gate_failure() -> None:
    decision = json.loads((OUT / "DECISION_MODELO.json").read_text(encoding="utf-8"))
    master = _master()
    assert decision["selected_model_id"] == "A_nacional_actual"
    assert decision["preferred_municipal_alternative"] == "C_municipal_jerarquico"
    assert master["modelo_central"].eq("A_nacional_actual").all()
    assert np.allclose(master["prediccion_central_2027"], master["prediccion_modelo_A_nacional_2027"])


def test_decline_threshold_is_exactly_minus_one_pp() -> None:
    master = _master()
    expected = master["cambio_proyectado_2027_pp"].le(-1.0)
    assert master["senal_caida_material_proyectada"].eq(expected).all()


def test_profiles_keep_original_rules_and_precedence() -> None:
    master = _master()
    eligible = master["universo_elegible_perfiles"]
    assert set(master.loc[eligible, "perfil_electoral_id"]) == {"P1", "P2", "P3", "P4", "P5", "P6"}
    assert master.loc[~eligible, "perfil_electoral_id"].eq("EI").all()
    assert master.loc[eligible & master["senal_deterioro_persistente"], "perfil_electoral_id"].eq("P1").all()
    p2 = eligible & ~master["senal_deterioro_persistente"] & master["senal_caida_material_proyectada"]
    assert master.loc[p2, "perfil_electoral_id"].eq("P2").all()


def test_profile_summary_reports_changes_against_previous_handoff() -> None:
    summary = pd.read_csv(OUT / "RESUMEN_PERFILES.csv")
    assert summary["secciones"].sum() == 70_751
    assert (
        summary["cambio_secciones_vs_handoff_anterior"]
        == summary["secciones"] - summary["secciones_handoff_anterior"]
    ).all()


def test_geography_fallbacks_and_coverage_are_explicit() -> None:
    master = _master()
    cd = master["clase_confianza_geografica"].isin(["C", "D"])
    assert master.loc[cd, "perfil_electoral_id"].eq("EI").all()
    assert master.loc[cd, "uso_fallback"].all()
    coverage = pd.read_csv(OUT / "COBERTURA_MODELOS.csv")
    assert (coverage["secciones_evaluadas_pareadas"] + coverage["secciones_excluidas"] == coverage["secciones_universo_target"]).all()
    assert coverage["motivo_exclusion"].notna().all()


def test_municipality_summary_is_complete_and_signs_reconcile() -> None:
    municipalities = pd.read_csv(OUT / "RESUMEN_MUNICIPIOS.csv")
    master = _master()
    assert len(municipalities) == master["clave_municipio"].nunique()
    expected_sign = np.select(
        [municipalities["componente_municipal_seleccionado"].lt(0), municipalities["componente_municipal_seleccionado"].gt(0)],
        ["negativo", "positivo"],
        default="cero",
    )
    assert (municipalities["signo_componente"] == expected_sign).all()


def test_dictionary_exactly_describes_master() -> None:
    master = _master()
    dictionary = pd.read_csv(OUT / "DICCIONARIO_VARIABLES.csv")
    assert list(dictionary["nombre"]) == list(master.columns)
    assert dictionary["nombre"].is_unique


def test_manifest_hashes_outputs_and_preserves_previous_handoff() -> None:
    manifest = json.loads((OUT / "MANIFEST.json").read_text(encoding="utf-8"))
    assert "previous_handoff_preserved" in manifest["canonical_status"]
    for row in manifest["outputs"]:
        path = ROOT / row["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
    assert (ROOT / "handoff/FINAL_2027/SECCIONES_ELECTORALES_2027.csv").exists()
