from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "handoff/FINAL_2027"


def _master() -> pd.DataFrame:
    return pd.read_csv(
        OUT / "SECCIONES_ELECTORALES_2027.csv",
        dtype={"clave_entidad": "string", "clave_municipio": "string", "clave_seccion": "string"},
    )


def test_master_universe_keys_ranges_and_no_silent_loss() -> None:
    master = _master()
    source = pd.read_parquet(ROOT / "artifacts/tables/forecast_2027_section_predictions.parquet")
    assert len(master) == len(source) == 70_751
    assert master["clave_seccion"].is_unique
    assert set(master["clave_seccion"]) == set(source["section_key_observed"])
    assert master["prediccion_central_2027"].between(0, 1).all()
    assert master["baseline_persistencia_2027"].between(0, 1).all()


def test_advanced_corrected_model_is_central_and_components_reconcile() -> None:
    master = _master()
    expected = np.clip(
        master["baseline_persistencia_2027"]
        + master["componente_nacional_2027"]
        + master["contraccion_residual"] * master["correccion_territorial_centrada"],
        0,
        1,
    )
    assert np.allclose(master["prediccion_central_2027"], expected)
    assert master["contraccion_residual"].eq(0.25).all()
    assert not np.allclose(master["prediccion_central_2027"], master["baseline_persistencia_2027"])


def test_material_decline_threshold_is_exactly_one_pp_with_correct_sign() -> None:
    master = _master()
    expected = master["cambio_proyectado_2027_pp"].le(-1.0)
    assert master["senal_caida_material_proyectada"].eq(expected).all()
    assert master.loc[expected, "prediccion_central_2027"].le(
        master.loc[expected, "baseline_persistencia_2027"] - 0.01 + 1e-12
    ).all()


def test_national_component_is_conservative_mean_and_temporally_valid() -> None:
    table = pd.read_csv(OUT / "SENSIBILIDAD_COMPONENTE_NACIONAL.csv")
    chosen = table[table["seleccionado"]].iloc[0]
    expected = np.mean([chosen["cambio_2009_2015"], chosen["cambio_2015_2021"]])
    assert np.isclose(chosen["componente_2027"], expected)
    assert not bool(chosen["backtest_2021_disponible"])
    prior = table[table["escenario"].eq("B_ultimo_cambio")].iloc[0]
    assert bool(prior["backtest_2021_disponible"])
    assert np.isfinite(prior["backtest_2021_mae"])


def test_detection_metrics_use_paired_samples_and_fixed_models() -> None:
    metrics = pd.read_csv(OUT / "METRICAS_DETECCION_CAIDAS.csv")
    assert set(metrics["model_id"]) == {
        "persistencia",
        "avanzado_corregido_025",
        "avanzado_ponderado_caidas_025",
    }
    assert metrics.groupby("target_year")["unidades_evaluacion"].nunique().eq(1).all()
    confusion = metrics[["verdaderos_positivos", "falsos_positivos", "falsos_negativos", "verdaderos_negativos"]].sum(axis=1)
    assert confusion.eq(metrics["unidades_evaluacion"]).all()


def test_weighted_decline_alternative_not_promoted_after_failed_joint_gate() -> None:
    decision = json.loads((OUT / "DECISION_MODELO.json").read_text(encoding="utf-8"))
    assert decision["selected_model_id"] == "avanzado_corregido_025"
    assert decision["weighted_alternative_selected"] is False
    assert decision["decline_threshold_pp"] == 1.0


def test_profiles_are_exclusive_exhaustive_and_precedence_is_respected() -> None:
    master = _master()
    eligible = master["universo_elegible_perfiles"]
    assert set(master.loc[eligible, "perfil_electoral_id"]) == {"P1", "P2", "P3", "P4", "P5", "P6"}
    assert master.loc[~eligible, "perfil_electoral_id"].eq("EI").all()
    assert master.loc[master["senal_deterioro_persistente"] & eligible, "perfil_electoral_id"].eq("P1").all()
    p2 = eligible & ~master["senal_deterioro_persistente"] & master["senal_caida_material_proyectada"]
    assert master.loc[p2, "perfil_electoral_id"].eq("P2").all()


def test_underlying_signals_are_preserved_independently() -> None:
    master = _master()
    signal_columns = [
        "senal_deterioro_persistente",
        "senal_caida_material_proyectada",
        "senal_rezago_persistente",
        "senal_recuperacion",
        "senal_favorable_estable",
        "senal_deterioro_relativo_municipio",
    ]
    assert master[signal_columns].notna().all().all()
    # Las señales no se colapsan en la etiqueta: puede haber varias activas y
    # aun así cada sección recibe un solo perfil por precedencia.
    assert master[signal_columns].sum(axis=1).gt(1).any()
    assert master["perfil_electoral_id"].notna().all()


def test_municipal_reference_is_ratio_of_sums_excluding_section() -> None:
    master = _master().set_index("clave_seccion")
    totals = pd.read_parquet(ROOT / "artifacts/tables/provisional_section_year_totals.parquet")
    row = totals[(totals["election_year"].eq(2021)) & totals["section_key_observed"].eq("01:0001")].iloc[0]
    muni = totals[(totals["election_year"].eq(2021)) & totals["municipality_key_observed"].eq(row["municipality_key_observed"])]
    expected = (muni["voted"].sum() - row["voted"]) / (muni["identified_records"].sum() - row["identified_records"])
    assert np.isclose(master.loc["01:0001", "referencia_municipal_2021_sin_seccion"], expected)


def test_neighbors_are_verified_rook_only_and_synthetic_islands_not_counted() -> None:
    master = _master()
    edges = pd.read_parquet(ROOT / "artifacts/graphs/section_graph_2024_edges.parquet")
    assert edges["is_synthetic"].sum() == 2
    assert master["vecindad_verificada_disponible"].sum() == 70_749
    assert master.loc[master["vecindad_verificada_disponible"], "numero_vecinos_rook_verificados"].ge(1).all()


def test_geography_classes_and_insufficient_evidence_are_not_overwritten() -> None:
    master = _master()
    assert master["clase_confianza_geografica"].value_counts().to_dict() == {
        "A": 58_534,
        "B": 6_561,
        "D": 3_791,
        "C": 1_865,
    }
    cd = master["clase_confianza_geografica"].isin(["C", "D"])
    assert master.loc[cd, "perfil_electoral_id"].eq("EI").all()
    assert master.loc[cd, "uso_fallback"].all()


def test_dictionary_exactly_matches_master_columns() -> None:
    master = _master()
    dictionary = pd.read_csv(OUT / "DICCIONARIO_VARIABLES.csv")
    assert dictionary["nombre"].is_unique
    assert list(dictionary["nombre"]) == list(master.columns)
    required = {"definicion", "unidad", "fuente", "periodo", "metodo_calculo", "valores_permitidos", "interpretacion", "limitaciones"}
    assert required.issubset(dictionary.columns)


def test_summaries_reconcile_to_master() -> None:
    master = _master()
    profiles = pd.read_csv(OUT / "RESUMEN_PERFILES.csv")
    entities = pd.read_csv(OUT / "RESUMEN_ENTIDADES.csv")
    assert profiles["secciones"].sum() == len(master)
    assert entities["secciones"].sum() == len(master)
    assert np.isclose(entities["lista_nominal_2024"].sum(), master["lista_nominal_2024"].sum())


def test_manifest_hashes_all_canonical_outputs() -> None:
    manifest = json.loads((OUT / "MANIFEST.json").read_text(encoding="utf-8"))
    names = {Path(row["path"]).name for row in manifest["outputs"]}
    canonical = {
        "SECCIONES_ELECTORALES_2027.csv",
        "DICCIONARIO_VARIABLES.csv",
        "RESUMEN_PERFILES.csv",
        "RESUMEN_ENTIDADES.csv",
        "VALIDACION_PREDICCION.md",
        "METODOLOGIA_TECNICA.md",
        "GUIA_PARA_POLITOLOGOS.md",
        "VALIDACION_FINAL.md",
        "CHANGELOG.md",
    }
    assert canonical.issubset(names)
    for row in manifest["outputs"]:
        path = ROOT / row["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
