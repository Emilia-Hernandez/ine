from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SECURITY = ROOT / "artifacts/security/radar27-security-municipal-2025.1"


def test_security_artifacts_preserve_keys_rates_and_source_hashes() -> None:
    manifest = json.loads((SECURITY / "MANIFEST.json").read_text(encoding="utf-8"))
    annual = pd.read_parquet(SECURITY / "municipal_security_annual_2015_2025.parquet")
    sections = pd.read_parquet(SECURITY / "section_security_2025.parquet")
    assert manifest["security_version"] == "radar27-security-municipal-2025.1"
    assert manifest["coverage"]["sections_valid_2025"] == 70_450
    assert len(sections) == 70_751
    assert sections["clave_seccion"].is_unique
    assert not annual.duplicated(["clave_municipio", "anio"]).any()
    valid = annual["indicador_disponible"]
    assert annual.loc[valid, "poblacion_mitad_anio"].gt(0).all()
    assert annual.loc[valid, "tasa_incidencia_total_100k"].ge(0).all()
    recomputed = (
        annual.loc[valid, "delitos_registrados"]
        / annual.loc[valid, "poblacion_mitad_anio"]
        * 100_000
    )
    pd.testing.assert_series_equal(
        annual.loc[valid, "tasa_incidencia_total_100k"].reset_index(drop=True),
        recomputed.reset_index(drop=True),
        check_names=False,
    )


def test_security_rate_is_constant_within_municipality() -> None:
    sections = pd.read_parquet(SECURITY / "section_security_2025.parquet")
    valid = sections[sections["security_data_status"].eq("valid")]
    assert valid.groupby("clave_municipio")["tasa_incidencia_total_100k"].nunique().max() == 1
    assert valid.groupby("tasa_incidencia_total_100k")["security_rank_start"].nunique().max() == 1
    assert valid.groupby("tasa_incidencia_total_100k")["security_rank_end"].nunique().max() == 1


def test_security_experiment_is_separate_and_not_promoted() -> None:
    path = ROOT / "artifacts/experiments/security_ablation/radar27-security-ablation.1"
    manifest = json.loads((path / "MANIFEST.json").read_text(encoding="utf-8"))
    predictions = pd.read_parquet(path / "predictions.parquet")
    assert manifest["status"] == "experimental_not_promoted"
    assert manifest["central_model_unchanged"].endswith("A_nacional_actual")
    assert predictions.loc[predictions["target_year"].eq(2018), ["prediction_M2", "prediction_M3", "prediction_M4"]].isna().all().all()
    assert predictions.loc[predictions["target_year"].isin([2021, 2024]), "prediction_M2"].notna().any()
