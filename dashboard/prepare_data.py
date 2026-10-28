"""Prepara una capa ligera y reproducible para el dashboard.

El script no recalcula predicciones ni perfiles. Solo une artefactos existentes,
preserva las claves territoriales y crea geometrías simplificadas para visualización.
"""

from __future__ import annotations

import hashlib
import html
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow
import shapely
from shapely import union_all
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard"
DATA_DIR = DASHBOARD / "data"
ASSETS_DIR = DASHBOARD / "assets"
HANDOFF = ROOT / "handoff" / "FINAL_2027_MUNICIPAL"
SECURITY_DIR = ROOT / "artifacts" / "security" / "radar27-security-municipal-2025.1"
VEB_DIR = (
    ROOT / "artifacts" / "security" / "radar27-votar-entre-balas-2026-10-24.1"
)
GEOMETRY_ARCHIVE = ROOT / "data" / "raw" / "public_ine" / "ine_secciones_2025_portal.zip"
GEOMETRY_MEMBER = "SECCION/SECCION.shp"
YEARS = [2009, 2012, 2015, 2018, 2021, 2024]
DENSITY_AREA_CRS = "EPSG:6933"
DENSITY_SOURCE_YEAR = 2020

PROFILE_LABELS = {
    "P1": "Deterioro persistente",
    "P2": "Deterioro proyectado",
    "P3": "Rezago persistente",
    "P4": "Recuperación",
    "P5": "Favorable y estable",
    "P6": "Variable o no diferenciada",
    "EI": "Evidencia insuficiente",
}

VISUAL_PROFILE_LABELS = {
    **{key: value for key, value in PROFILE_LABELS.items() if key != "EI"},
    "EI_AB": "EI — Historia incompleta (A/B)",
    "EI_CD": "EI — Comparabilidad no validada (C/D)",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_state() -> dict[str, object]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=False, capture_output=True, text=True
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    return {"input_commit": commit or None, "working_tree_dirty": dirty}


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
        "unspecified",
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
        ("did_not_vote", "did_not_vote"),
        ("unspecified", "unspecified"),
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
    history_years = [2009, 2015, 2021]
    available = frame[[f"participacion_{year}" for year in history_years]].notna()
    frame["anios_historia_disponibles"] = available.apply(
        lambda row: ",".join(
            str(year) for year, present in zip(history_years, row) if present
        ),
        axis=1,
    )
    frame["anios_historia_faltantes"] = available.apply(
        lambda row: ",".join(
            str(year) for year, present in zip(history_years, row) if not present
        ),
        axis=1,
    )
    is_ei = frame["perfil_electoral_id"].eq("EI")
    ei_ab = is_ei & frame["clase_confianza_geografica"].isin(["A", "B"])
    ei_cd = is_ei & frame["clase_confianza_geografica"].isin(["C", "D"])
    unexplained = is_ei & ~(ei_ab | ei_cd)
    if unexplained.any():
        keys = frame.loc[unexplained, "clave_seccion"].head(10).tolist()
        raise ValueError(f"Secciones EI fuera del contrato A/B/C/D: {keys}")
    frame["subcategoria_evidencia"] = pd.NA
    frame.loc[ei_ab, "subcategoria_evidencia"] = "EI-A/B"
    frame.loc[ei_cd, "subcategoria_evidencia"] = "EI-C/D"
    frame["motivo_evidencia_insuficiente"] = pd.NA
    frame.loc[ei_ab, "motivo_evidencia_insuficiente"] = (
        "Historia electoral intermedia incompleta; faltan: "
        + frame.loc[ei_ab, "anios_historia_faltantes"].replace("", "ninguno")
    )
    frame.loc[ei_cd, "motivo_evidencia_insuficiente"] = (
        "Comparabilidad territorial no validada: "
        + frame.loc[ei_cd, "limitaciones_comparabilidad"].fillna(
            "limitación C/D registrada"
        )
    )
    frame["perfil_visual_id"] = frame["perfil_electoral_id"]
    frame.loc[ei_ab, "perfil_visual_id"] = "EI_AB"
    frame.loc[ei_cd, "perfil_visual_id"] = "EI_CD"
    if not frame["perfil_visual_id"].isin(VISUAL_PROFILE_LABELS).all():
        raise ValueError("La categoría visual de perfiles no cumple el contrato")
    frame["fuente_demografia_electoral"] = np.where(
        frame["female_identified_2024"].notna(),
        "INE conteos censales 2024; medición seccional directa",
        "no_disponible",
    )
    frame["fuente_demografia_eceg"] = np.where(
        frame["eceg_population_total"].notna(), "INEGI ECEG 2020", "no_disponible"
    )
    frame["nivel_demografia_eceg"] = "no_disponible"
    eceg_available = frame["eceg_population_total"].notna()
    frame.loc[
        eceg_available & frame["clase_confianza_geografica"].eq("A"),
        "nivel_demografia_eceg",
    ] = "seccion_codigo_directo_clase_A"
    frame.loc[
        eceg_available & ~frame["clase_confianza_geografica"].eq("A"),
        "nivel_demografia_eceg",
    ] = "coincidencia_codigo_continuidad_no_validada"
    assert len(frame) == 70_751
    assert frame["clave_seccion"].is_unique
    return frame


def _rank_density(frame: pd.DataFrame) -> pd.DataFrame:
    """Asigna un orden nacional estable: densidad descendente y clave ascendente."""
    ranked = frame.copy()
    ranked["density_rank"] = pd.Series(pd.NA, index=ranked.index, dtype="Int64")
    valid = ranked["density_data_status"].eq("valid")
    order = ranked.loc[valid].sort_values(
        ["densidad_viviendas_km2", "section_id"],
        ascending=[False, True],
        kind="mergesort",
    )
    ranked.loc[order.index, "density_rank"] = np.arange(1, len(order) + 1, dtype="int64")
    return ranked


def build_density_table(
    section_table: pd.DataFrame, geometry: gpd.GeoDataFrame | None = None
) -> pd.DataFrame:
    """Construye la tabla canónica de densidad sin interpolar geografías 2020→2024.

    ECEG 2020 se vincula sólo a secciones clase A del contrato territorial del
    proyecto. Las clases B–D se conservan con área, pero su densidad queda nula
    porque una coincidencia nominal de clave no demuestra equivalencia geométrica.
    """
    source = _read_geometry() if geometry is None else geometry.copy()
    if source.crs is None:
        raise ValueError("La cartografía seccional no declara un sistema de coordenadas")
    if source["clave_seccion"].duplicated().any():
        raise ValueError("La cartografía contiene claves de sección duplicadas")

    source = source[source["clave_seccion"].isin(section_table["clave_seccion"])].copy()
    if len(source) != len(section_table):
        raise ValueError("La cartografía no cubre exactamente el universo canónico")

    metric = source.to_crs(DENSITY_AREA_CRS)
    duplicate_geometry = metric.geometry.to_wkb(hex=True).duplicated(keep=False)
    metric["area_km2"] = metric.geometry.area / 1_000_000.0
    geometry_valid = (
        metric.geometry.notna()
        & ~metric.geometry.is_empty
        & metric.geometry.is_valid
        & metric["area_km2"].notna()
        & np.isfinite(metric["area_km2"])
        & metric["area_km2"].gt(0)
        & ~duplicate_geometry
    )

    density = section_table[
        [
            "clave_seccion",
            "clave_entidad",
            "clase_confianza_geografica",
            "eceg_inhabited_private_dwellings",
        ]
    ].merge(
        metric[["clave_seccion", "area_km2"]].assign(_geometry_valid=geometry_valid.to_numpy()),
        on="clave_seccion",
        how="left",
        validate="1:1",
    )
    density = density.rename(
        columns={
            "clave_seccion": "section_id",
            "clave_entidad": "entidad",
            "eceg_inhabited_private_dwellings": "viviendas_habitadas_2020",
        }
    )
    density["seccion"] = density["section_id"].str.split(":", n=1).str[1]
    density["density_data_status"] = "valid"
    density.loc[~density["_geometry_valid"].fillna(False), "density_data_status"] = (
        "invalid_or_duplicate_geometry"
    )
    eceg_missing = density["viviendas_habitadas_2020"].isna()
    density.loc[eceg_missing, "density_data_status"] = "eceg_not_available"
    eceg_invalid = density["viviendas_habitadas_2020"].notna() & density[
        "viviendas_habitadas_2020"
    ].lt(0)
    density.loc[eceg_invalid, "density_data_status"] = "invalid_eceg_value"
    incompatible = density["clase_confianza_geografica"].ne("A")
    density.loc[incompatible, "density_data_status"] = "incompatible_2020_2024_geography"

    valid = density["density_data_status"].eq("valid")
    density["densidad_viviendas_km2"] = np.nan
    density.loc[valid, "densidad_viviendas_km2"] = (
        density.loc[valid, "viviendas_habitadas_2020"] / density.loc[valid, "area_km2"]
    )
    density["density_source_year"] = DENSITY_SOURCE_YEAR
    density = _rank_density(density)
    result = density[
        [
            "section_id",
            "entidad",
            "seccion",
            "viviendas_habitadas_2020",
            "area_km2",
            "densidad_viviendas_km2",
            "density_data_status",
            "density_source_year",
            "density_rank",
        ]
    ].sort_values("section_id")
    if not result["section_id"].is_unique:
        raise ValueError("La tabla canónica de densidad contiene secciones duplicadas")
    return result.reset_index(drop=True)


def _format_percent(value: object) -> str:
    if pd.isna(value):
        return "No disponible"
    return f"{float(value):.1%}"


def _format_pp(value: object) -> str:
    if pd.isna(value):
        return "No disponible"
    return f"{float(value):+.1f} pp"


def _tooltip(row: pd.Series) -> str:
    visual = str(row.perfil_visual_id)
    label = VISUAL_PROFILE_LABELS[visual]
    items = [
        f"<strong>Sección {html.escape(str(row.clave_seccion))}</strong>",
        f"{html.escape(str(row.nombre_entidad).title())} · {html.escape(str(row.nombre_municipio))}",
        f"<span>{html.escape(label if visual.startswith('EI_') else visual + ' — ' + label)}</span>",
        f"2021 observado: {_format_percent(row.participacion_2021)}",
        f"2027 proyectado: {_format_percent(row.prediccion_central_2027)}",
        f"Cambio: {_format_pp(row.cambio_proyectado_2027_pp)}",
    ]
    if visual.startswith("EI_"):
        items.append(html.escape(str(row.motivo_evidencia_insuficiente)))
    if pd.notna(row.get("tasa_incidencia_total_100k")):
        items.append(
            f"Incidencia municipal 2025: {float(row.tasa_incidencia_total_100k):,.1f} por 100 mil"
        )
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


def build_geometry(
    section_table: pd.DataFrame, geometry: gpd.GeoDataFrame | None = None
) -> dict[str, int]:
    geometry = _read_geometry() if geometry is None else geometry.copy()
    source_crs = geometry.crs
    if source_crs is None:
        raise ValueError("La cartografía de visualización no declara CRS")
    geometry = geometry.merge(
        section_table[
            [
                "clave_seccion",
                "nombre_entidad",
                "nombre_municipio",
                "perfil_visual_id",
                "motivo_evidencia_insuficiente",
                "density_rank",
                "security_rank_start",
                "municipal_attacks_cumulative",
                "municipal_attacks_24m",
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
    geometry["density_rank"] = geometry["density_rank"].fillna(-1).astype("int32")
    geometry["security_rank_start"] = geometry["security_rank_start"].fillna(-1).astype("int32")
    geometry["municipal_attacks_cumulative"] = geometry["municipal_attacks_cumulative"].fillna(-1).astype("int32")
    geometry["municipal_attacks_24m"] = geometry["municipal_attacks_24m"].fillna(-1).astype("int32")
    geometry = geometry.rename(
        columns={
            "clave_seccion": "k",
            "perfil_visual_id": "p",
            "density_rank": "r",
            "security_rank_start": "s",
            "municipal_attacks_cumulative": "a",
            "municipal_attacks_24m": "b",
        }
    )[["k", "p", "r", "s", "a", "b", "tooltip", "geometry"]]

    # Simplificación en el CRS métrico de origen. Se conserva el polígono y su
    # identificador; las fuentes originales no se alteran.
    metric = geometry.to_crs(source_crs)
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
    geometry = _read_geometry()
    density = build_density_table(table, geometry)
    density.to_parquet(
        DATA_DIR / "section_housing_density.parquet", index=False, compression="zstd"
    )
    table = table.merge(
        density[
            [
                "section_id",
                "area_km2",
                "densidad_viviendas_km2",
                "density_data_status",
                "density_source_year",
                "density_rank",
            ]
        ],
        left_on="clave_seccion",
        right_on="section_id",
        how="left",
        validate="1:1",
    ).drop(columns="section_id")
    security_path = SECURITY_DIR / "section_security_2025.parquet"
    if not security_path.exists():
        raise FileNotFoundError(
            "Falta la tabla de seguridad; ejecuta scripts/run_security_municipal.py"
        )
    security = pd.read_parquet(security_path)
    if len(security) != 70_751 or not security["clave_seccion"].is_unique:
        raise ValueError("La tabla de seguridad no conserva el universo seccional")
    security_columns = [
        column
        for column in security.columns
        if column not in {"clave_entidad", "clave_municipio"}
    ]
    table = table.merge(
        security[security_columns], on="clave_seccion", how="left", validate="1:1"
    )
    veb_path = VEB_DIR / "section_veb_context.parquet"
    if not veb_path.exists():
        raise FileNotFoundError(
            "Falta Votar entre Balas; ejecuta scripts/run_votar_entre_balas.py"
        )
    veb = pd.read_parquet(veb_path)
    if len(veb) != 70_751 or not veb["clave_seccion"].is_unique:
        raise ValueError("La tabla Votar entre Balas no conserva el universo seccional")
    veb_columns = [
        column
        for column in veb.columns
        if column
        not in {
            "clave_entidad",
            "clave_municipio",
            "nombre_entidad",
            "nombre_municipio",
        }
    ]
    table = table.merge(veb[veb_columns], on="clave_seccion", how="left", validate="1:1")
    table.to_parquet(DATA_DIR / "dashboard_sections.parquet", index=False, compression="zstd")
    geometry_sizes = build_geometry(table, geometry)

    profile_counts = table["perfil_electoral_id"].value_counts().reindex(PROFILE_LABELS).to_dict()
    visual_counts = (
        table["perfil_visual_id"].value_counts().reindex(VISUAL_PROFILE_LABELS).to_dict()
    )
    manifest = {
        "manifest_version": 1,
        "dashboard_release_candidate": "unpublished_working_copy",
        **_git_state(),
        "handoff": "handoff/FINAL_2027_MUNICIPAL",
        "handoff_version": str(table["version_modelo"].iloc[0]),
        "geometry_source": "data/raw/public_ine/ine_secciones_2025_portal.zip",
        "geometry_version": str(table["version_geografica"].iloc[0]),
        "sections": len(table),
        "profile_counts": {key: int(value) for key, value in profile_counts.items()},
        "visual_profile_counts": {key: int(value) for key, value in visual_counts.items()},
        "geometry_files_bytes": geometry_sizes,
        "electoral_demography_sections": int(table["female_identified_2024"].notna().sum()),
        "eceg_sections": int(table["eceg_population_total"].notna().sum()),
        "density_source": "INEGI ECEG 2020 VIVPAR_HAB / INE snapshot 2024 area EPSG:6933",
        "density_valid_sections": int(table["density_rank"].notna().sum()),
        "density_area_crs": DENSITY_AREA_CRS,
        "density_status_counts": {
            str(key): int(value)
            for key, value in table["density_data_status"].value_counts().items()
        },
        "security_version": "radar27-security-municipal-2025.1",
        "security_indicator": "Tasa anual municipal de incidencia delictiva registrada por 100,000 habitantes",
        "security_valid_sections": int(table["security_rank_start"].notna().sum()),
        "security_missing_sections": int(table["security_rank_start"].isna().sum()),
        "veb_version": str(table["veb_dataset_version"].iloc[0]),
        "veb_cutoff_date": str(pd.Timestamp(table["veb_cutoff_date"].iloc[0]).date()),
        "veb_indicator": "Conteo de id_evento distintos con al menos un objetivo municipal",
        "veb_sections_crosswalk_available": int(
            table["inegi_municipality_keys"].notna().sum()
        ),
        "veb_sections_crosswalk_unavailable": int(
            table["inegi_municipality_keys"].isna().sum()
        ),
        "notes": [
            "No se recalcularon predicciones ni perfiles.",
            "La cartografía es el snapshot INE 2024-05-09, no geometría certificada para 2027.",
            "Las geometrías overview/detail fueron simplificadas solo para visualización.",
            "La densidad usa sólo coincidencias directas clase A; B–D no se interpolan.",
            "La incidencia es municipal y se asigna como contexto; no mide delitos dentro de la sección.",
            "Votar entre Balas cuenta eventos municipales y los asigna como contexto; no localiza ataques dentro de una sección.",
            "El pronóstico y los perfiles no incorporan Votar entre Balas; las variables quedan descriptivas y preparadas para evaluación futura.",
        ],
        "commands": [
            "PYTHONPATH=src .venv/bin/python scripts/run_security_municipal.py",
            "PYTHONPATH=src .venv/bin/python scripts/run_votar_entre_balas.py",
            "PYTHONPATH=src .venv/bin/python dashboard/prepare_data.py",
            ".venv/bin/pytest -q",
        ],
        "versions": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "geopandas": gpd.__version__,
            "pyarrow": pyarrow.__version__,
            "shapely": shapely.__version__,
        },
        "input_hashes": {
            "handoff_manifest": _sha256(HANDOFF / "MANIFEST.json"),
            "security_manifest": _sha256(SECURITY_DIR / "MANIFEST.json"),
            "veb_manifest": _sha256(VEB_DIR / "MANIFEST.json"),
        },
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
