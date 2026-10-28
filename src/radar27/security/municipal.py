"""Procesa incidencia municipal SESNSP y población municipal CONAPO.

La unidad de observación de seguridad permanece municipal. La tabla seccional
resultante es solamente un crosswalk contextual y nunca se presenta como una
estimación de delitos ocurridos dentro de cada sección.
"""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import zipfile
from collections import defaultdict
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[3]
MONTHS = [
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
]
VIOLENT_TYPES = {
    "Abuso sexual",
    "Acoso sexual",
    "Feminicidio",
    "Hostigamiento sexual",
    "Rapto",
    "Secuestro",
    "Trata de personas",
    "Tráfico de menores",
    "Violación equiparada",
    "Violación simple",
    "Violencia de género en todas sus modalidades distinta a la violencia familiar",
    "Violencia familiar",
}
VIOLENT_SUBTYPES = {"Homicidio doloso", "Lesiones dolosas"}
XML_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_state() -> dict[str, Any]:
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


def _municipality_key(value: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(value, errors="coerce").astype("Int64")
    code = numeric.astype("string").str.zfill(5)
    return code.str[:2] + ":" + code.str[2:]


def _shared_strings(book: zipfile.ZipFile) -> list[str]:
    root = ET.fromstring(book.read("xl/sharedStrings.xml"))
    return ["".join(node.text or "" for node in item.iter(XML_NS + "t")) for item in root]


def _xlsx_rows(blob: bytes) -> Iterator[list[Any]]:
    """Lee la hoja CONAPO aunque su dimensión OOXML declare erróneamente A1."""
    with zipfile.ZipFile(io.BytesIO(blob)) as book:
        strings = _shared_strings(book)
        with book.open("xl/worksheets/sheet1.xml") as sheet:
            for _, row in ET.iterparse(sheet, events=("end",)):
                if row.tag != XML_NS + "row":
                    continue
                values: list[Any] = []
                for cell in row.findall(XML_NS + "c"):
                    ref = str(cell.get("r", "A1"))
                    letters = "".join(char for char in ref if char.isalpha())
                    column = 0
                    for char in letters:
                        column = column * 26 + ord(char.upper()) - 64
                    while len(values) < column:
                        values.append(None)
                    node = cell.find(XML_NS + "v")
                    raw = None if node is None else node.text
                    if raw is not None and cell.get("t") == "s":
                        value: Any = strings[int(raw)]
                    elif raw is None:
                        value = None
                    else:
                        value = float(raw) if "." in raw else int(raw)
                    values[column - 1] = value
                yield values
                row.clear()


def read_conapo_population(source: Path, years: set[int] | None = None) -> pd.DataFrame:
    """Extrae población total municipal a mitad de año del libro nacional."""
    years = years or set(range(2015, 2026))
    with zipfile.ZipFile(source) as archive:
        member = next(name for name in archive.namelist() if name.endswith("2_Gran_Gedad_00_RM.xlsx"))
        rows = _xlsx_rows(archive.read(member))
        header = [str(value) for value in next(rows)]
        index = {name: header.index(name) for name in ["CLAVE", "CLAVE_ENT", "NOM_ENT", "NOM_MUN", "SEXO", "AÑO", "POB_TOTAL"]}
        records = []
        for row in rows:
            if len(row) <= max(index.values()) or row[index["AÑO"]] not in years:
                continue
            records.append({name: row[position] for name, position in index.items()})
    frame = pd.DataFrame.from_records(records)
    frame["anio"] = pd.to_numeric(frame.pop("AÑO"), errors="raise").astype("int16")
    frame["clave_municipio"] = _municipality_key(frame.pop("CLAVE"))
    frame["clave_entidad"] = pd.to_numeric(frame.pop("CLAVE_ENT"), errors="raise").astype("int16").astype("string").str.zfill(2)
    frame["poblacion_sexo"] = pd.to_numeric(frame.pop("POB_TOTAL"), errors="raise")
    frame = frame.rename(columns={"NOM_ENT": "nombre_entidad_conapo", "NOM_MUN": "nombre_municipio_conapo", "SEXO": "sexo"})
    if frame.duplicated(["clave_municipio", "anio", "sexo"]).any():
        raise ValueError("CONAPO contiene municipio/año/sexo duplicado")
    counts = frame.groupby(["clave_municipio", "anio"])["sexo"].nunique()
    if not counts.eq(2).all():
        raise ValueError("CONAPO no contiene exactamente dos sexos por municipio/año")
    result = frame.groupby(["clave_municipio", "clave_entidad", "anio"], as_index=False).agg(
        nombre_entidad_conapo=("nombre_entidad_conapo", "first"),
        nombre_municipio_conapo=("nombre_municipio_conapo", "first"),
        poblacion_mitad_anio=("poblacion_sexo", "sum"),
    )
    if result["poblacion_mitad_anio"].le(0).any():
        raise ValueError("CONAPO contiene denominadores municipales no positivos")
    return result


def read_sesnsp_monthly(source: Path, chunk_size: int = 200_000) -> pd.DataFrame:
    """Suma exclusivamente filas de modalidad; no suma agregados intermedios."""
    dimensions = [
        "Año",
        "Clave_Ent",
        "Entidad",
        "Cve. Municipio",
        "Municipio",
        "Bien jurídico afectado",
        "Tipo de delito",
        "Subtipo de delito",
        "Modalidad",
    ]
    totals: defaultdict[tuple[str, int, int], list[float]] = defaultdict(lambda: [0.0, 0.0])
    names: dict[tuple[str, int], tuple[str, str, str]] = {}
    seen_hashes: set[int] = set()
    with zipfile.ZipFile(source) as archive:
        member = next(name for name in archive.namelist() if name.lower().endswith(".csv"))
        with archive.open(member) as raw:
            stream = io.TextIOWrapper(raw, encoding="cp1252", newline="")
            for chunk in pd.read_csv(stream, chunksize=chunk_size, low_memory=False):
                chunk.columns = [str(column).strip() for column in chunk.columns]
                missing = set(dimensions + MONTHS) - set(chunk.columns)
                if missing:
                    raise ValueError(f"SESNSP carece de columnas requeridas: {sorted(missing)}")
                hashes = pd.util.hash_pandas_object(chunk[dimensions], index=False).astype("uint64")
                hash_set = {int(value) for value in hashes}
                if len(hash_set) != len(hashes) or seen_hashes.intersection(hash_set):
                    raise ValueError("SESNSP contiene filas de modalidad duplicadas")
                seen_hashes.update(hash_set)
                chunk["clave_municipio"] = _municipality_key(chunk["Cve. Municipio"])
                if chunk["clave_municipio"].isna().any():
                    raise ValueError("SESNSP contiene claves municipales inválidas")
                values = chunk[MONTHS].apply(pd.to_numeric, errors="coerce").fillna(0.0)
                if values.lt(0).any().any():
                    raise ValueError("SESNSP contiene conteos mensuales negativos")
                violent = chunk["Tipo de delito"].isin(VIOLENT_TYPES) | chunk["Subtipo de delito"].isin(VIOLENT_SUBTYPES)
                years = pd.to_numeric(chunk["Año"], errors="raise").astype(int)
                for month_index, month in enumerate(MONTHS, start=1):
                    work = pd.DataFrame(
                        {
                            "clave_municipio": chunk["clave_municipio"],
                            "anio": years,
                            "total": values[month].to_numpy(),
                            "violenta": values[month].where(violent, 0.0).to_numpy(),
                        }
                    )
                    grouped = work.groupby(["clave_municipio", "anio"], sort=False)[["total", "violenta"]].sum()
                    for (key, year), row in grouped.iterrows():
                        aggregate = totals[(str(key), int(year), month_index)]
                        aggregate[0] += float(row["total"])
                        aggregate[1] += float(row["violenta"])
                for row in chunk[["clave_municipio", "Año", "Clave_Ent", "Entidad", "Municipio"]].drop_duplicates().itertuples(index=False):
                    key = (str(row.clave_municipio), int(row.Año))
                    value = (str(row.Clave_Ent).zfill(2), str(row.Entidad), str(row.Municipio))
                    if key in names and names[key] != value:
                        raise ValueError(f"Metadatos municipales SESNSP inconsistentes para {key}")
                    names[key] = value
    records = []
    for (key, year, month), (total, violent) in totals.items():
        entity, entity_name, municipality_name = names[(key, year)]
        records.append(
            {
                "clave_entidad": entity,
                "clave_municipio": key,
                "nombre_entidad_sesnsp": entity_name,
                "nombre_municipio_sesnsp": municipality_name,
                "anio": year,
                "mes": month,
                "delitos_registrados_total": round(total),
                "delitos_registrados_violentos": round(violent),
            }
        )
    result = pd.DataFrame.from_records(records).sort_values(["clave_municipio", "anio", "mes"])
    if result.duplicated(["clave_municipio", "anio", "mes"]).any():
        raise ValueError("La agregación SESNSP no es única por municipio/año/mes")
    return result.reset_index(drop=True)


def build_municipal_table(monthly: pd.DataFrame, population: pd.DataFrame) -> pd.DataFrame:
    annual = monthly.groupby(["clave_entidad", "clave_municipio", "nombre_entidad_sesnsp", "nombre_municipio_sesnsp", "anio"], as_index=False).agg(
        delitos_registrados=("delitos_registrados_total", "sum"),
        delitos_violentos_registrados=("delitos_registrados_violentos", "sum"),
        meses_disponibles=("mes", "nunique"),
    )
    result = annual.merge(population, on=["clave_entidad", "clave_municipio", "anio"], how="left", validate="1:1")
    result["indicador_disponible"] = result["poblacion_mitad_anio"].gt(0) & result["meses_disponibles"].eq(12)
    result["tasa_incidencia_total_100k"] = np.where(
        result["indicador_disponible"], result["delitos_registrados"] / result["poblacion_mitad_anio"] * 100_000, np.nan
    )
    result["tasa_incidencia_violenta_100k"] = np.where(
        result["indicador_disponible"], result["delitos_violentos_registrados"] / result["poblacion_mitad_anio"] * 100_000, np.nan
    )
    result["fuente_incidencia"] = "SESNSP, fuero común, delitos municipales"
    result["fuente_poblacion"] = "CONAPO, población municipal a mitad de año"
    result["version_metodologica"] = "SESNSP CNSP/38/15 (2015-2025)"
    result["corte_fuente_sesnsp"] = "2026-09"
    result["publicacion_conapo"] = "2024-05-09"
    return result.sort_values(["anio", "clave_municipio"]).reset_index(drop=True)


def build_section_security(municipal: pd.DataFrame, sections: pd.DataFrame, year: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    crosswalk = sections[["clave_seccion", "clave_entidad", "clave_municipio", "nombre_entidad", "nombre_municipio"]].copy()
    if crosswalk["clave_seccion"].duplicated().any():
        raise ValueError("El universo seccional contiene claves duplicadas")
    current = municipal[municipal["anio"].eq(year)].copy()
    result = crosswalk.merge(current, on=["clave_entidad", "clave_municipio"], how="left", validate="m:1")
    result["security_data_status"] = np.where(
        result["indicador_disponible"].eq(True),
        "valid",
        "municipal_indicator_unavailable",
    )
    valid = result["security_data_status"].eq("valid")
    counts = result.loc[valid].groupby("tasa_incidencia_total_100k").size().sort_index()
    starts = counts.cumsum().shift(fill_value=0).add(1).astype(int)
    ends = counts.cumsum().astype(int)
    result["security_rank_start"] = pd.Series(pd.NA, index=result.index, dtype="Int64")
    result["security_rank_end"] = pd.Series(pd.NA, index=result.index, dtype="Int64")
    result.loc[valid, "security_rank_start"] = result.loc[valid, "tasa_incidencia_total_100k"].map(starts).astype("Int64")
    result.loc[valid, "security_rank_end"] = result.loc[valid, "tasa_incidencia_total_100k"].map(ends).astype("Int64")
    denominator = int(valid.sum())
    result["security_percentile_low"] = np.where(valid, result["security_rank_end"] / denominator, np.nan)
    result["security_context_level"] = "municipal_asignado_a_seccion"
    result["security_indicator_year"] = year
    keep = [
        "clave_seccion", "clave_entidad", "clave_municipio", "anio", "delitos_registrados",
        "delitos_violentos_registrados", "poblacion_mitad_anio", "tasa_incidencia_total_100k",
        "tasa_incidencia_violenta_100k", "indicador_disponible", "security_data_status",
        "security_rank_start", "security_rank_end", "security_percentile_low",
        "security_context_level", "security_indicator_year", "fuente_incidencia", "fuente_poblacion",
        "version_metodologica", "corte_fuente_sesnsp", "publicacion_conapo",
    ]
    return result[keep].sort_values("clave_seccion").reset_index(drop=True), crosswalk.sort_values("clave_seccion").reset_index(drop=True)


def build_security_artifacts(config_path: Path) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    sesnsp = ROOT / config["sources"]["sesnsp"]
    conapo = ROOT / config["sources"]["conapo"]
    handoff = ROOT / "handoff/FINAL_2027_MUNICIPAL/SECCIONES_ELECTORALES_2027.csv"
    output = ROOT / config["output_directory"]
    output.mkdir(parents=True, exist_ok=True)
    monthly = read_sesnsp_monthly(sesnsp)
    population = read_conapo_population(conapo, set(range(2015, 2026)))
    municipal = build_municipal_table(monthly, population)
    sections = pd.read_csv(handoff, dtype={"clave_entidad": "string", "clave_municipio": "string", "clave_seccion": "string"}, low_memory=False)
    section_security, crosswalk = build_section_security(municipal, sections, int(config["dashboard_year"]))
    monthly.to_parquet(output / "municipal_security_monthly_2015_2025.parquet", index=False, compression="zstd")
    municipal.to_parquet(output / "municipal_security_annual_2015_2025.parquet", index=False, compression="zstd")
    section_security.to_parquet(output / "section_security_2025.parquet", index=False, compression="zstd")
    crosswalk.to_parquet(output / "section_municipality_crosswalk.parquet", index=False, compression="zstd")
    valid = section_security["security_data_status"].eq("valid")
    manifest = {
        "manifest_version": 1,
        "security_version": config["security_version"],
        "generation_date": str(datetime.now(UTC).date()),
        **_git_state(),
        "dashboard_year": int(config["dashboard_year"]),
        "methodology": "SESNSP 2015-2025; suma de filas hoja modalidad sin agregados intermedios",
        "population_denominator": "CONAPO población municipal a mitad de año",
        "temporal_validation_caveat": "El corte SESNSP 2026-09 contiene revisiones retrospectivas; no es un archivo as-of histórico.",
        "violent_definition": {"tipo_de_delito": sorted(VIOLENT_TYPES), "subtipo_de_delito": sorted(VIOLENT_SUBTYPES)},
        "coverage": {
            "sections_total": len(section_security),
            "sections_valid_2025": int(valid.sum()),
            "sections_missing_2025": int((~valid).sum()),
            "municipalities_sesnsp_2025": int(municipal.loc[municipal["anio"].eq(2025), "clave_municipio"].nunique()),
            "municipalities_matched_sections_2025": int(section_security.loc[valid, "clave_municipio"].nunique()),
        },
        "sources": [
            {"path": config["sources"]["sesnsp"], "sha256": _sha256(sesnsp), "official_url": config["official_urls"]["sesnsp"]},
            {"path": config["sources"]["conapo"], "sha256": _sha256(conapo), "official_url": config["official_urls"]["conapo"]},
        ],
        "outputs": [],
        "commands": [
            "PYTHONPATH=src .venv/bin/python scripts/run_security_municipal.py"
        ],
        "versions": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "PyYAML": yaml.__version__,
        },
    }
    for name in ["municipal_security_monthly_2015_2025.parquet", "municipal_security_annual_2015_2025.parquet", "section_security_2025.parquet", "section_municipality_crosswalk.parquet"]:
        path = output / name
        first_column = pd.read_parquet(path).columns[0]
        rows = len(pd.read_parquet(path, columns=[first_column]))
        manifest["outputs"].append({"path": str(path.relative_to(ROOT)), "rows": int(rows), "sha256": _sha256(path)})
    (output / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest
