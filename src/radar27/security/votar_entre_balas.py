"""Pipeline municipal de violencia político-criminal de Votar entre Balas.

La fuente publicada tiene una fila por víctima o instalación y un identificador
de evento repetible. Los conteos de este módulo usan eventos distintos y nunca
se suman a través de las secciones que comparten municipio.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[3]
REQUIRED_COLUMNS = {
    "id",
    "id_evento",
    "id_victima",
    "tipo_vic",
    "nom_vic",
    "nivel_gob",
    "tipo_evento",
    "fecha",
    "estado",
    "municipio",
    "cve_edoINEGI",
    "cve_munINEGI",
}
EVENT_TYPES = {
    "Amenaza",
    "Atentado",
    "Ataque armado",
    "Desaparición",
    "Secuestro",
    "Asesinato",
}
GOVERNMENT_LEVELS = {"Federal", "Estatal", "Municipal"}


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


def _normalise_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]+", " ", text.upper()).strip()


def _entity_key(value: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(value, errors="coerce").astype("Int64")
    return numeric.astype("string").str.zfill(2)


def _municipality_component(value: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(value, errors="coerce").astype("Int64")
    return numeric.astype("string").str.zfill(3)


def read_victim_records(path: Path, cutoff: pd.Timestamp) -> tuple[pd.DataFrame, dict[str, int]]:
    raw = pd.read_csv(path, dtype="string", low_memory=False)
    missing = REQUIRED_COLUMNS - set(raw.columns)
    if missing:
        raise ValueError(f"Votar entre Balas carece de columnas requeridas: {sorted(missing)}")
    substantive = [column for column in raw.columns if column != "Unnamed: 0"]
    blank_rows = raw[substantive].isna().all(axis=1)
    frame = raw.loc[~blank_rows].copy()
    frame = frame.rename(columns={"Unnamed: 0": "source_row"})
    frame["event_date"] = pd.to_datetime(frame["fecha"], errors="coerce")
    if frame["event_date"].isna().any():
        raise ValueError("Votar entre Balas contiene fechas de acontecimiento inválidas")
    after_cutoff = frame["event_date"].gt(cutoff)
    retained = frame.loc[~after_cutoff].copy()
    retained["source_entity_key"] = _entity_key(retained["cve_edoINEGI"])
    retained["source_municipality_component"] = _municipality_component(retained["cve_munINEGI"])
    retained["inegi_municipality_key"] = (
        retained["source_entity_key"] + ":" + retained["source_municipality_component"]
    )
    if not retained["tipo_evento"].isin(EVENT_TYPES).all():
        values = sorted(
            retained.loc[~retained["tipo_evento"].isin(EVENT_TYPES), "tipo_evento"].unique()
        )
        raise ValueError(f"Categorías de evento no documentadas: {values}")
    if not retained["nivel_gob"].isin(GOVERNMENT_LEVELS).all():
        values = sorted(
            retained.loc[~retained["nivel_gob"].isin(GOVERNMENT_LEVELS), "nivel_gob"].unique()
        )
        raise ValueError(f"Niveles de gobierno no documentados: {values}")
    audit = {
        "raw_rows": len(raw),
        "blank_trailing_rows_excluded": int(blank_rows.sum()),
        "substantive_rows": len(frame),
        "rows_after_cutoff_excluded": int(after_cutoff.sum()),
        "retained_victim_or_installation_rows": len(retained),
        "rows_missing_event_id": int(retained["id_evento"].isna().sum()),
        "rows_missing_inegi_municipality_key": int(retained["inegi_municipality_key"].isna().sum()),
    }
    return retained, audit


def read_section_municipalities(path: Path) -> pd.DataFrame:
    columns = [
        "clave_seccion",
        "clave_entidad",
        "clave_municipio",
        "nombre_entidad",
        "nombre_municipio",
    ]
    frame = pd.read_csv(
        path,
        usecols=columns,
        dtype={
            "clave_seccion": "string",
            "clave_entidad": "string",
            "clave_municipio": "string",
        },
        low_memory=False,
    )
    if frame["clave_seccion"].duplicated().any():
        raise ValueError("El universo del dashboard contiene secciones duplicadas")
    return frame


def build_municipality_crosswalk(
    catalog_path: Path, sections: pd.DataFrame, victims: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Construye INEGI->INE sin coincidencias aproximadas.

    La ruta principal usa el catálogo comparativo oficial ECEG 2020. Para
    municipios posteriores al catálogo sólo se acepta un nombre normalizado
    exacto, único dentro de la entidad, entre la fuente y el handoff vigente.
    """
    catalog = pd.read_excel(catalog_path, sheet_name=0, header=2, dtype="string")
    needed = {"CVE_ENT", "CVE_MUN", "NOMGEO", "ENTIDAD", "MUNICIPIO", "NOMBRE"}
    if not needed.issubset(catalog.columns):
        raise ValueError("El catálogo INEGI-INE no contiene el esquema esperado")
    official = catalog[catalog["CVE_ENT"].notna() & catalog["CVE_MUN"].notna()].copy()
    official["inegi_municipality_key"] = (
        _entity_key(official["CVE_ENT"]) + ":" + _municipality_component(official["CVE_MUN"])
    )
    official["ine_municipality_key"] = (
        _entity_key(official["ENTIDAD"]) + ":" + _municipality_component(official["MUNICIPIO"])
    )
    official["crosswalk_method"] = "official_eceg_2020_inegi_ine"
    official = official[
        [
            "inegi_municipality_key",
            "ine_municipality_key",
            "NOMGEO",
            "NOMBRE",
            "crosswalk_method",
        ]
    ].rename(columns={"NOMGEO": "inegi_name", "NOMBRE": "ine_name"})
    official = official[official["ine_municipality_key"].notna()].copy()
    if official["inegi_municipality_key"].duplicated().any():
        raise ValueError("El catálogo oficial no es único por clave INEGI")

    municipalities = sections[
        ["clave_entidad", "clave_municipio", "nombre_entidad", "nombre_municipio"]
    ].drop_duplicates("clave_municipio")
    if municipalities["clave_municipio"].duplicated().any():
        raise ValueError("El handoff no es único por clave municipal INE")
    mapped = official.merge(
        municipalities,
        left_on="ine_municipality_key",
        right_on="clave_municipio",
        how="inner",
        validate="m:1",
    )
    mapped = mapped[
        [
            "inegi_municipality_key",
            "ine_municipality_key",
            "inegi_name",
            "nombre_municipio",
            "crosswalk_method",
        ]
    ].rename(columns={"nombre_municipio": "dashboard_municipality_name"})

    source_municipalities = (
        victims[["source_entity_key", "inegi_municipality_key", "municipio"]]
        .dropna(subset=["inegi_municipality_key"])
        .drop_duplicates()
    )
    existing_inegi = set(mapped["inegi_municipality_key"])
    additions: list[dict[str, str]] = []
    for row in source_municipalities.itertuples(index=False):
        if row.inegi_municipality_key in existing_inegi:
            continue
        candidates = municipalities[
            municipalities["clave_entidad"].eq(row.source_entity_key)
            & municipalities["nombre_municipio"]
            .map(_normalise_name)
            .eq(_normalise_name(row.municipio))
        ]
        if len(candidates) != 1:
            continue
        candidate = candidates.iloc[0]
        additions.append(
            {
                "inegi_municipality_key": str(row.inegi_municipality_key),
                "ine_municipality_key": str(candidate["clave_municipio"]),
                "inegi_name": str(row.municipio),
                "dashboard_municipality_name": str(candidate["nombre_municipio"]),
                "crosswalk_method": "exact_current_name_unique_not_fuzzy",
            }
        )
        existing_inegi.add(str(row.inegi_municipality_key))
    if additions:
        mapped = pd.concat([mapped, pd.DataFrame(additions)], ignore_index=True)
    if mapped["inegi_municipality_key"].duplicated().any():
        raise ValueError("El crosswalk resultante no es único por clave INEGI")
    source_audit = source_municipalities.merge(
        mapped, on="inegi_municipality_key", how="left", validate="m:1"
    )
    source_audit["match_status"] = np.where(
        source_audit["ine_municipality_key"].notna(), "matched", "unmatched"
    )
    return mapped.sort_values("inegi_municipality_key").reset_index(drop=True), source_audit


def build_events(victims: pd.DataFrame, crosswalk: pd.DataFrame) -> pd.DataFrame:
    work = victims.merge(crosswalk, on="inegi_municipality_key", how="left", validate="m:1")
    keyed = work[work["id_evento"].notna()].copy()
    for column in ("event_date", "inegi_municipality_key"):
        inconsistent = keyed.groupby("id_evento")[column].nunique(dropna=False).gt(1)
        if inconsistent.any():
            raise ValueError(
                f"Eventos con {column} inconsistente: {inconsistent[inconsistent].index[:10].tolist()}"
            )

    def join_values(series: pd.Series) -> str:
        return " | ".join(sorted({str(value) for value in series.dropna()}))

    events = keyed.groupby("id_evento", as_index=False, dropna=False).agg(
        event_date=("event_date", "first"),
        source_id=("id", "first"),
        inegi_municipality_key=("inegi_municipality_key", "first"),
        ine_municipality_key=("ine_municipality_key", "first"),
        source_state=("estado", "first"),
        source_municipality=("municipio", "first"),
        attack_types=("tipo_evento", join_values),
        government_levels=("nivel_gob", join_values),
        victim_or_installation_rows=("source_row", "size"),
        distinct_victim_ids=("id_victima", "nunique"),
        municipal_target=("nivel_gob", lambda values: bool(values.eq("Municipal").any())),
    )
    events["geography_status"] = np.where(
        events["ine_municipality_key"].notna(), "matched", "unmatched"
    )
    if events["id_evento"].duplicated().any():
        raise ValueError("La tabla de eventos no conserva unicidad de id_evento")
    return events.sort_values(["event_date", "id_evento"]).reset_index(drop=True)


def _count_window(
    events: pd.DataFrame,
    cutoff: pd.Timestamp,
    months: int | None,
    municipal_only: bool,
) -> pd.Series:
    mask = events["event_date"].le(cutoff) & events["ine_municipality_key"].notna()
    if months is not None:
        mask &= events["event_date"].gt(cutoff - pd.DateOffset(months=months))
    if municipal_only:
        mask &= events["municipal_target"]
    selected = events.loc[mask]
    return selected.groupby("ine_municipality_key")["id_evento"].nunique()


def build_features_asof(
    events: pd.DataFrame,
    crosswalk: pd.DataFrame,
    sections: pd.DataFrame,
    cutoffs: list[tuple[str, pd.Timestamp]],
) -> pd.DataFrame:
    municipalities = sections[
        ["clave_entidad", "clave_municipio", "nombre_entidad", "nombre_municipio"]
    ].drop_duplicates("clave_municipio")
    bridge = crosswalk.groupby("ine_municipality_key", as_index=False).agg(
        inegi_municipality_keys=(
            "inegi_municipality_key",
            lambda values: " | ".join(sorted(set(values))),
        ),
        crosswalk_method=(
            "crosswalk_method",
            lambda values: " | ".join(sorted(set(values))),
        ),
    )
    base = municipalities.merge(
        bridge,
        left_on="clave_municipio",
        right_on="ine_municipality_key",
        how="left",
        validate="1:1",
    )
    rows = []
    for label, cutoff in cutoffs:
        current = base.copy()
        indicator_columns: list[str] = []
        for prefix, municipal_only in (
            ("municipal_attacks", True),
            ("territorial_attacks_all_levels", False),
        ):
            for suffix, months in (("cumulative", None), ("12m", 12), ("24m", 24)):
                column = f"{prefix}_{suffix}"
                counts = _count_window(events, cutoff, months, municipal_only)
                current[column] = (
                    current["clave_municipio"].map(counts).fillna(0).astype("Int64")
                )
                indicator_columns.append(column)
        current["cutoff_label"] = label
        current["cutoff_date"] = cutoff
        current["historical_availability_status"] = (
            "current_snapshot_reconstructed_by_event_date_not_historical_asof"
        )
        current["veb_data_status"] = np.where(
            current["inegi_municipality_keys"].isna(),
            "municipality_crosswalk_unavailable",
            np.where(
                current["municipal_attacks_cumulative"].gt(0),
                "positive_registered_attacks",
                "zero_registered_attacks_in_monitored_source",
            ),
        )
        current.loc[
            current["veb_data_status"].eq("municipality_crosswalk_unavailable"),
            indicator_columns,
        ] = pd.NA
        rows.append(current)
    result = pd.concat(rows, ignore_index=True)
    if result.duplicated(["cutoff_label", "clave_municipio"]).any():
        raise ValueError("Las features as-of no son únicas por corte y municipio")
    return result


def build_annual(
    events: pd.DataFrame, crosswalk: pd.DataFrame, sections: pd.DataFrame, cutoff: pd.Timestamp
) -> pd.DataFrame:
    municipalities = sections[
        ["clave_entidad", "clave_municipio", "nombre_entidad", "nombre_municipio"]
    ].drop_duplicates("clave_municipio")
    bridge = crosswalk.groupby("ine_municipality_key", as_index=False).agg(
        inegi_municipality_keys=(
            "inegi_municipality_key",
            lambda values: " | ".join(sorted(set(values))),
        ),
        crosswalk_method=(
            "crosswalk_method",
            lambda values: " | ".join(sorted(set(values))),
        ),
    )
    base = municipalities.merge(
        bridge,
        left_on="clave_municipio",
        right_on="ine_municipality_key",
        how="left",
        validate="1:1",
    )
    min_year = int(events["event_date"].dt.year.min())
    pieces = []
    for year in range(min_year, cutoff.year + 1):
        current = base.copy()
        applicable = events[
            events["event_date"].dt.year.eq(year)
            & events["event_date"].le(cutoff)
            & events["ine_municipality_key"].notna()
        ]
        municipal = (
            applicable[applicable["municipal_target"]]
            .groupby("ine_municipality_key")["id_evento"]
            .nunique()
        )
        all_levels = applicable.groupby("ine_municipality_key")["id_evento"].nunique()
        current["year"] = year
        current["municipal_attacks"] = (
            current["clave_municipio"].map(municipal).fillna(0).astype("Int64")
        )
        current["territorial_attacks_all_levels"] = (
            current["clave_municipio"].map(all_levels).fillna(0).astype("Int64")
        )
        current["year_complete_at_cutoff"] = year < cutoff.year
        current["period_end"] = min(cutoff, pd.Timestamp(year=year, month=12, day=31))
        current.loc[
            current["inegi_municipality_keys"].isna(),
            ["municipal_attacks", "territorial_attacks_all_levels"],
        ] = pd.NA
        pieces.append(current)
    result = pd.concat(pieces, ignore_index=True)
    if result.duplicated(["year", "clave_municipio"]).any():
        raise ValueError("La tabla anual no es única por municipio y año")
    return result


def build_section_context(
    features: pd.DataFrame,
    annual: pd.DataFrame,
    sections: pd.DataFrame,
    current_label: str,
    dataset_version: str,
    cutoff: pd.Timestamp,
) -> pd.DataFrame:
    current = features[features["cutoff_label"].eq(current_label)].copy()
    current = current[
        [
            "clave_municipio",
            "inegi_municipality_keys",
            "crosswalk_method",
            "veb_data_status",
            "municipal_attacks_cumulative",
            "municipal_attacks_12m",
            "municipal_attacks_24m",
            "territorial_attacks_all_levels_cumulative",
            "territorial_attacks_all_levels_12m",
            "territorial_attacks_all_levels_24m",
        ]
    ]
    for year in (2025, 2026):
        yearly = annual[annual["year"].eq(year)][
            ["clave_municipio", "municipal_attacks", "territorial_attacks_all_levels"]
        ].rename(
            columns={
                "municipal_attacks": f"municipal_attacks_{year}",
                "territorial_attacks_all_levels": f"territorial_attacks_all_levels_{year}",
            }
        )
        current = current.merge(yearly, on="clave_municipio", how="left", validate="1:1")
    context = sections[
        ["clave_seccion", "clave_entidad", "clave_municipio", "nombre_entidad", "nombre_municipio"]
    ].merge(current, on="clave_municipio", how="left", validate="m:1")
    context["veb_cutoff_date"] = cutoff
    context["veb_dataset_version"] = dataset_version
    context["veb_geography_level"] = "municipal_context_assigned_to_section"
    if len(context) != len(sections) or context["clave_seccion"].duplicated().any():
        raise ValueError("La asignación VEB no conserva exactamente una fila por sección")
    return context


def build_votar_entre_balas_artifacts(
    config_path: Path, cutoff_override: str | None = None
) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    cutoff = pd.Timestamp(cutoff_override or config["cutoff_date"])
    sources = {
        key: ROOT / value
        for key, value in config["sources"].items()
        if key not in {"official_page", "download_url"}
    }
    for key in (
        "zip",
        "csv",
        "dictionary",
        "methodology",
        "ine_inegi_crosswalk",
        "section_universe",
    ):
        if not sources[key].exists():
            raise FileNotFoundError(f"Falta la fuente {key}: {sources[key]}")
    output = ROOT / config["output_directory"]
    output.mkdir(parents=True, exist_ok=True)

    victims, source_audit = read_victim_records(sources["csv"], cutoff)
    sections = read_section_municipalities(sources["section_universe"])
    crosswalk, source_crosswalk_audit = build_municipality_crosswalk(
        sources["ine_inegi_crosswalk"], sections, victims
    )
    events = build_events(victims, crosswalk)
    cutoffs = [
        (str(item["label"]), pd.Timestamp(item["date"]))
        for item in config["historical_cutoffs"]
        if pd.Timestamp(item["date"]) <= cutoff
    ]
    current_label = next(label for label, date in cutoffs if date == cutoff)
    features = build_features_asof(events, crosswalk, sections, cutoffs)
    annual = build_annual(events, crosswalk, sections, cutoff)
    section_context = build_section_context(
        features, annual, sections, current_label, config["dataset_version"], cutoff
    )
    victims_with_crosswalk = victims.merge(
        crosswalk, on="inegi_municipality_key", how="left", validate="m:1"
    )
    unmatched = victims_with_crosswalk[
        victims_with_crosswalk["id_evento"].isna()
        | victims_with_crosswalk["ine_municipality_key"].isna()
    ].copy()

    paths = {
        "clean_victim_records.parquet": victims_with_crosswalk,
        "events.parquet": events,
        "municipality_crosswalk.parquet": crosswalk,
        "municipal_features_asof.parquet": features,
        "municipal_attacks_annual.parquet": annual,
        "section_veb_context.parquet": section_context,
    }
    for name, frame in paths.items():
        frame.to_parquet(output / name, index=False, compression="zstd")
    unmatched.to_csv(output / "unmatched_records.csv", index=False)
    source_crosswalk_audit.to_csv(output / "source_municipality_crosswalk_audit.csv", index=False)

    matched_events = events[events["geography_status"].eq("matched")]
    current_features = features[features["cutoff_label"].eq(current_label)]
    source_key_status = source_crosswalk_audit.groupby("inegi_municipality_key")[
        "ine_municipality_key"
    ].size()
    matched_source_keys = source_crosswalk_audit.loc[
        source_crosswalk_audit["ine_municipality_key"].notna(), "inegi_municipality_key"
    ].nunique()
    manifest: dict[str, Any] = {
        "manifest_version": 1,
        "dataset_version": config["dataset_version"],
        "generation_date": str(datetime.now(UTC).date()),
        "cutoff_date": str(cutoff.date()),
        "latest_event_date": str(events["event_date"].max().date()),
        **_git_state(),
        "unit_of_source_rows": "victim_or_installation",
        "unit_of_indicator": "distinct_id_evento",
        "main_indicator_definition": "Eventos distintos con al menos una fila nivel_gob=Municipal, agregados por municipio de ocurrencia.",
        "alternative_indicator_definition": "Todos los eventos distintos ocurridos en el territorio municipal, sin filtrar nivel_gob.",
        "source_audit": source_audit,
        "coverage": {
            "events_with_id": len(events),
            "events_municipal_target": int(events["municipal_target"].sum()),
            "events_matched_to_dashboard_municipality": len(matched_events),
            "events_unmatched_to_dashboard_municipality": int(
                (events["geography_status"] == "unmatched").sum()
            ),
            "source_municipalities": int(victims["inegi_municipality_key"].nunique()),
            "source_municipalities_matched": int(matched_source_keys),
            "source_municipalities_unmatched": int(
                len(source_key_status) - matched_source_keys
            ),
            "dashboard_municipalities": int(sections["clave_municipio"].nunique()),
            "dashboard_municipalities_with_crosswalk": int(
                current_features["inegi_municipality_keys"].notna().sum()
            ),
            "dashboard_municipalities_crosswalk_unavailable": int(
                current_features["inegi_municipality_keys"].isna().sum()
            ),
            "sections_total": len(section_context),
            "sections_crosswalk_available": int(
                section_context["inegi_municipality_keys"].notna().sum()
            ),
            "sections_crosswalk_unavailable": int(
                section_context["inegi_municipality_keys"].isna().sum()
            ),
        },
        "temporal_caveat": "Los cortes históricos se reconstruyen por fecha del acontecimiento con el snapshot descargado en 2026; no prueban disponibilidad histórica de publicación y no son backtests estrictamente as-of.",
        "sources": [
            {
                "role": "download_bundle",
                "path": str(sources["zip"].relative_to(ROOT)),
                "url": config["sources"]["download_url"],
                "downloaded_at_utc": config["downloaded_at_utc"],
                "sha256": _sha256(sources["zip"]),
            },
            *[
                {
                    "role": key,
                    "path": str(sources[key].relative_to(ROOT)),
                    "sha256": _sha256(sources[key]),
                }
                for key in (
                    "csv",
                    "dictionary",
                    "methodology",
                    "ine_inegi_crosswalk",
                    "section_universe",
                )
            ],
        ],
        "outputs": [],
        "commands": [
            "PYTHONPATH=src .venv/bin/python scripts/run_votar_entre_balas.py",
            "RADAR27_DASHBOARD_WORKING_COPY=1 .venv/bin/python -m dashboard.app",
        ],
        "versions": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "PyYAML": yaml.__version__,
        },
    }
    for name in [*paths, "unmatched_records.csv", "source_municipality_crosswalk_audit.csv"]:
        path = output / name
        manifest["outputs"].append(
            {
                "path": str(path.relative_to(ROOT)),
                "rows": len(paths[name]) if name in paths else len(pd.read_csv(path)),
                "sha256": _sha256(path),
            }
        )
    manifest_path = output / "MANIFEST.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    tracked_manifest = ROOT / config["source_manifest"]
    tracked_manifest.parent.mkdir(parents=True, exist_ok=True)
    tracked_manifest.write_text(
        json.dumps(
            {
                "dataset_version": config["dataset_version"],
                "cutoff_date": str(cutoff.date()),
                "latest_event_date": manifest["latest_event_date"],
                "downloaded_at_utc": config["downloaded_at_utc"],
                "official_page": config["sources"]["official_page"],
                "download_url": config["sources"]["download_url"],
                "files": manifest["sources"],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest
