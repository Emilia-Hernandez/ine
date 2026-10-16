"""Prepara una capa ligera y reproducible para el dashboard.

El script no recalcula predicciones ni perfiles. Solo une artefactos existentes,
preserva las claves territoriales y crea geometrías simplificadas para visualización.
"""

from __future__ import annotations

import html
import json
import sys
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely import union_all
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard"
DATA_DIR = DASHBOARD / "data"
ASSETS_DIR = DASHBOARD / "assets"
HANDOFF = ROOT / "handoff" / "FINAL_2027_MUNICIPAL"
GEOMETRY_ARCHIVE = ROOT / "data" / "raw" / "public_ine" / "ine_secciones_2025_portal.zip"
GEOMETRY_MEMBER = "SECCION/SECCION.shp"
YEARS = [2009, 2012, 2015, 2018, 2021, 2024]

PROFILE_LABELS = {
    "P1": "Deterioro persistente",
    "P2": "Deterioro proyectado",
    "P3": "Rezago persistente",
    "P4": "Recuperación",
    "P5": "Favorable y estable",
    "P6": "Variable o no diferenciada",
    "EI": "Evidencia insuficiente",
}


def _read_handoff() -> pd.DataFrame:
    path = HANDOFF / "SECCIONES_ELECTORALES_2027.csv"
    frame = pd.read_csv(
        path,
        dtype={
            "clave_entidad": "string",
            "clave_municipio": "string",
            "clave_seccion": "string",
            "distrito_federal_2024": "string",
            "distrito_local_2024": "string",
        },
        low_memory=False,
    )
    assert len(frame) == 70_751
    assert frame["clave_seccion"].is_unique
    assert frame["perfil_electoral_id"].isin(PROFILE_LABELS).all()
    return frame


def _historical_wide() -> pd.DataFrame:
    cols = [
        "election_year",
        "section_key_observed",
        "voted",
        "did_not_vote",
        "identified_records",
    ]
    frame = pd.read_parquet(
        ROOT / "artifacts" / "tables" / "provisional_section_year_totals.parquet",
        columns=cols,
    )
    frame = frame[frame["election_year"].isin(YEARS)].copy()
    assert not frame.duplicated(["election_year", "section_key_observed"]).any()
    frame["participation_denominator"] = frame["voted"] + frame["did_not_vote"]
    pieces = []
    for value, prefix in [
        ("voted", "voted"),
        ("participation_denominator", "denom"),
        ("identified_records", "identified"),
    ]:
        wide = frame.pivot(index="section_key_observed", columns="election_year", values=value)
        wide.columns = [f"{prefix}_{int(year)}" for year in wide.columns]
        pieces.append(wide)
    return (
        pd.concat(pieces, axis=1)
        .reset_index()
        .rename(columns={"section_key_observed": "clave_seccion"})
    )


def _electoral_demographics() -> pd.DataFrame:
    path = ROOT / "artifacts" / "tables" / "model_unit_demographic_profiles_2027.parquet"
    keep = [
        "evaluation_unit_id",
        "female_identified_2024",
        "male_identified_2024",
        "age_18_29_identified_2024",
        "age_30_44_identified_2024",
        "age_45_64_identified_2024",
        "age_65_plus_identified_2024",
        "female_turnout_2024",
        "male_turnout_2024",
        "age_18_29_turnout_2024",
        "age_30_44_turnout_2024",
        "age_45_64_turnout_2024",
        "age_65_plus_turnout_2024",
    ]
    frame = pd.read_parquet(path, columns=keep)
    # Solo S: es una medición seccional directa. Componentes de linaje no se
    # presentan como si fueran mediciones de una sección individual.
    frame = frame[frame["evaluation_unit_id"].str.startswith("S:")].copy()
    frame["clave_seccion"] = frame["evaluation_unit_id"].str.removeprefix("S:")
    assert frame["clave_seccion"].is_unique
    return frame.drop(columns="evaluation_unit_id")


def _eceg_demographics() -> pd.DataFrame:
    path = ROOT / "artifacts" / "tables" / "eceg_2020_section_features.parquet"
    frame = pd.read_parquet(path)
    frame = frame.rename(columns={"section_key_observed": "clave_seccion"})
    assert frame["clave_seccion"].is_unique
    return frame.drop(
        columns=[
            "entity_id",
            "section_number",
            "municipality_id_inegi",
            "eceg_section_type_code",
        ]
    )


def build_section_table() -> pd.DataFrame:
    frame = _read_handoff()
    frame = frame.merge(_historical_wide(), on="clave_seccion", how="left", validate="1:1")
    frame = frame.merge(_electoral_demographics(), on="clave_seccion", how="left", validate="1:1")
    frame = frame.merge(_eceg_demographics(), on="clave_seccion", how="left", validate="1:1")
    assert len(frame) == 70_751
    assert frame["clave_seccion"].is_unique
    return frame


def _format_percent(value: object) -> str:
    if pd.isna(value):
        return "No disponible"
    return f"{float(value):.1%}"


def _format_pp(value: object) -> str:
    if pd.isna(value):
        return "No disponible"
    return f"{float(value):+.1f} pp"


def _tooltip(row: pd.Series) -> str:
    label = PROFILE_LABELS[str(row.perfil_electoral_id)]
    items = [
        f"<strong>Sección {html.escape(str(row.clave_seccion))}</strong>",
        f"{html.escape(str(row.nombre_entidad).title())} · {html.escape(str(row.nombre_municipio))}",
        f"<span>{html.escape(str(row.perfil_electoral_id))} — {html.escape(label)}</span>",
        f"2021 observado: {_format_percent(row.participacion_2021)}",
        f"2027 proyectado: {_format_percent(row.prediccion_central_2027)}",
        f"Cambio: {_format_pp(row.cambio_proyectado_2027_pp)}",
    ]
    return "<br>".join(items)


def _read_geometry() -> gpd.GeoDataFrame:
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(GEOMETRY_ARCHIVE) as archive:
            archive.extractall(tmp)
        source = Path(tmp) / GEOMETRY_MEMBER
        geometry = gpd.read_file(source)
    geometry["clave_seccion"] = (
        geometry["ENTIDAD"].astype("int64").astype("string").str.zfill(2)
        + ":"
        + geometry["SECCION"].astype("int64").astype("string").str.zfill(4)
    )
    assert len(geometry) == 70_753
    assert geometry["clave_seccion"].is_unique
    return geometry


def _state_outline(geometry: object) -> object:
    """Conserva contornos exteriores y elimina huecos cartográficos internos."""
    parts = [geometry] if geometry.geom_type == "Polygon" else list(geometry.geoms)
    return union_all([Polygon(part.exterior) for part in parts])


def build_geometry(section_table: pd.DataFrame) -> dict[str, int]:
    geometry = _read_geometry()
    geometry = geometry.merge(
        section_table[
            [
                "clave_seccion",
                "nombre_entidad",
                "nombre_municipio",
                "perfil_electoral_id",
                "participacion_2021",
                "prediccion_central_2027",
                "cambio_proyectado_2027_pp",
            ]
        ],
        on="clave_seccion",
        how="inner",
        validate="1:1",
    )
    assert len(geometry) == 70_751
    assert geometry["clave_seccion"].is_unique

    geometry = geometry.to_crs(4326)
    geometry["tooltip"] = geometry.apply(_tooltip, axis=1)
    geometry = geometry.rename(columns={"clave_seccion": "k", "perfil_electoral_id": "p"})[
        ["k", "p", "tooltip", "geometry"]
    ]

    # Simplificación en el CRS métrico de origen. Se conserva el polígono y su
    # identificador; las fuentes originales no se alteran.
    metric = geometry.to_crs(_read_geometry().crs)
    outputs = {"overview": 900.0, "detail": 75.0}
    sizes: dict[str, int] = {}
    for name, tolerance in outputs.items():
        layer = metric.copy()
        layer.geometry = layer.geometry.simplify(tolerance, preserve_topology=True)
        layer = layer.to_crs(4326)
        if name == "overview":
            # En la escala nacional las secciones no son identificables. Omitir
            # el tooltip reduce de forma importante la transferencia inicial;
            # reaparece en la capa detallada al hacer zoom.
            layer = layer.drop(columns="tooltip")
        target = ASSETS_DIR / f"sections_{name}.fgb"
        layer.to_file(target, driver="FlatGeobuf", spatial_index=True)
        sizes[name] = target.stat().st_size

    state_source = _read_geometry()
    states = state_source.dissolve(by="ENTIDAD", as_index=False)[["ENTIDAD", "geometry"]]
    states.geometry = states.geometry.apply(_state_outline)
    states.geometry = states.geometry.simplify(500.0, preserve_topology=True)
    assert states.geometry.is_valid.all()
    states = states.to_crs(4326).rename(columns={"ENTIDAD": "entidad"})
    states.to_file(ASSETS_DIR / "state_boundaries.geojson", driver="GeoJSON")
    return sizes


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    table = build_section_table()
    table.to_parquet(DATA_DIR / "dashboard_sections.parquet", index=False, compression="zstd")
    geometry_sizes = build_geometry(table)

    profile_counts = table["perfil_electoral_id"].value_counts().reindex(PROFILE_LABELS).to_dict()
    manifest = {
        "handoff": "handoff/FINAL_2027_MUNICIPAL",
        "handoff_version": str(table["version_modelo"].iloc[0]),
        "geometry_source": "data/raw/public_ine/ine_secciones_2025_portal.zip",
        "geometry_version": str(table["version_geografica"].iloc[0]),
        "sections": len(table),
        "profile_counts": {key: int(value) for key, value in profile_counts.items()},
        "geometry_files_bytes": geometry_sizes,
        "electoral_demography_sections": int(table["female_identified_2024"].notna().sum()),
        "eceg_sections": int(table["eceg_population_total"].notna().sum()),
        "notes": [
            "No se recalcularon predicciones ni perfiles.",
            "La cartografía es el snapshot INE 2024-05-09, no geometría certificada para 2027.",
            "Las geometrías overview/detail fueron simplificadas solo para visualización.",
        ],
    }
    (DATA_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"Error de validación: {exc}", file=sys.stderr)
        raise
