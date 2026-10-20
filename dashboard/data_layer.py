"""Consultas y agregaciones del dashboard, separadas de la interfaz Dash."""

from __future__ import annotations

import gc
import json
import math
import threading
from collections.abc import Iterator
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
RELEASE_POINTER = ROOT / "dashboard" / "data" / "current_release.json"


def _data_path() -> Path:
    if RELEASE_POINTER.exists():
        release = json.loads(RELEASE_POINTER.read_text(encoding="utf-8"))
        return ROOT / str(release["data_file"])
    return ROOT / "dashboard" / "data" / "dashboard_sections.parquet"


DATA_PATH = _data_path()
YEARS = [2009, 2012, 2015, 2018, 2021, 2024]
ALL_PROFILES = ["P1", "P2", "P3", "P4", "P5", "P6", "EI_AB", "EI_CD"]
_EXPORT_LOCK = threading.Lock()

# La interfaz necesita sólo estas columnas. Las 163 columnas del contrato de
# exportación se leen por lotes únicamente cuando se solicita un CSV.
RUNTIME_COLUMNS = [
    "clave_seccion",
    "clave_entidad",
    "nombre_entidad",
    "clave_municipio",
    "nombre_municipio",
    "lista_nominal_2024",
    "participacion_2021",
    "baseline_persistencia_2027",
    "prediccion_central_2027",
    "cambio_proyectado_2027_pp",
    "senal_caida_material_proyectada",
    "senal_deterioro_relativo_municipio",
    "perfil_electoral_id",
    "clase_confianza_geografica",
    "fuente_historia_electoral",
    "fuente_proyeccion_2027",
    "calidad_componente_municipal",
    "uso_fallback",
    "version_modelo",
    "anios_historia_disponibles",
    "anios_historia_faltantes",
    "motivo_evidencia_insuficiente",
    "perfil_visual_id",
    "densidad_viviendas_km2",
    "density_rank",
    "tasa_incidencia_total_100k",
    "security_rank_start",
    *[column for year in YEARS for column in (f"voted_{year}", f"denom_{year}")],
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
    "eceg_population_total",
    "eceg_population_female",
    "eceg_population_60_plus",
    "eceg_population_15_plus",
    "eceg_population_12_plus",
    "eceg_population_3_plus",
    "eceg_population_15_plus_illiterate",
    "eceg_economically_active_population",
    "eceg_population_with_disability",
    "eceg_population_3_plus_indigenous_language",
    "eceg_inhabited_private_dwellings",
    "eceg_dwellings_with_internet",
    "eceg_average_schooling",
]

PROFILE_LABELS = {
    "P1": "Deterioro persistente",
    "P2": "Deterioro proyectado",
    "P3": "Rezago persistente",
    "P4": "Recuperación",
    "P5": "Favorable y estable",
    "P6": "Variable o no diferenciada",
    "EI_AB": "Historia incompleta (A/B)",
    "EI_CD": "Comparabilidad no validada (C/D)",
}

AGE_GROUPS = [
    ("18–29", "age_18_29_identified_2024", "age_18_29_turnout_2024"),
    ("30–44", "age_30_44_identified_2024", "age_30_44_turnout_2024"),
    ("45–64", "age_45_64_identified_2024", "age_45_64_turnout_2024"),
    ("65+", "age_65_plus_identified_2024", "age_65_plus_turnout_2024"),
]
SEX_GROUPS = [
    ("Mujeres", "female_identified_2024", "female_turnout_2024"),
    ("Hombres", "male_identified_2024", "male_turnout_2024"),
]

SOCIO_METRICS = {
    "female_population": {
        "label": "Población femenina",
        "numerator": "eceg_population_female",
        "denominator": "eceg_population_total",
        "format": "percent",
        "period": "ECEG 2020 · población residente",
    },
    "older_population": {
        "label": "Población de 60 años y más",
        "numerator": "eceg_population_60_plus",
        "denominator": "eceg_population_total",
        "format": "percent",
        "period": "ECEG 2020 · población residente",
    },
    "illiteracy": {
        "label": "Analfabetismo (15+)",
        "numerator": "eceg_population_15_plus_illiterate",
        "denominator": "eceg_population_15_plus",
        "format": "percent",
        "period": "ECEG 2020 · población de 15+",
    },
    "economic_activity": {
        "label": "Población económicamente activa",
        "numerator": "eceg_economically_active_population",
        "denominator": "eceg_population_12_plus",
        "format": "percent",
        "period": "ECEG 2020 · población de 12+",
    },
    "disability": {
        "label": "Población con discapacidad",
        "numerator": "eceg_population_with_disability",
        "denominator": "eceg_population_total",
        "format": "percent",
        "period": "ECEG 2020 · población residente",
    },
    "indigenous_language": {
        "label": "Habla lengua indígena",
        "numerator": "eceg_population_3_plus_indigenous_language",
        "denominator": "eceg_population_3_plus",
        "format": "percent",
        "period": "ECEG 2020 · población de 3+",
    },
    "internet": {
        "label": "Viviendas con internet",
        "numerator": "eceg_dwellings_with_internet",
        "denominator": "eceg_inhabited_private_dwellings",
        "format": "percent",
        "period": "ECEG 2020 · viviendas particulares habitadas",
    },
    "schooling": {
        "label": "Escolaridad promedio",
        "numerator": "eceg_average_schooling",
        "denominator": "eceg_population_15_plus",
        "format": "years",
        "period": "ECEG 2020 · promedio ponderado, población de 15+",
    },
}


@lru_cache(maxsize=1)
def load_sections() -> pd.DataFrame:
    frame = pd.read_parquet(DATA_PATH, columns=RUNTIME_COLUMNS, dtype_backend="pyarrow")
    frame = frame.set_index("clave_seccion", drop=False)
    if len(frame) != 70_751 or not frame.index.is_unique:
        raise ValueError("La capa del dashboard no conserva el universo seccional esperado")
    return frame


def _ratio(numerator: pd.Series, denominator: pd.Series) -> float | None:
    valid = numerator.notna() & denominator.notna() & denominator.gt(0)
    if not valid.any():
        return None
    denominator_sum = float(denominator[valid].sum())
    if denominator_sum <= 0:
        return None
    return float(numerator[valid].sum() / denominator_sum)


def _weighted_average(values: pd.Series, weights: pd.Series) -> float | None:
    valid = values.notna() & weights.notna() & weights.gt(0)
    if not valid.any():
        return None
    return float(np.average(values[valid], weights=weights[valid]))


def _coverage(frame: pd.DataFrame, column: str) -> dict[str, float | int]:
    available = int(frame[column].notna().sum())
    total = len(frame)
    return {"available": available, "total": total, "rate": available / total if total else 0.0}


def normalize_density_percent(value: Any) -> int:
    try:
        return min(100, max(1, round(float(value))))
    except (TypeError, ValueError):
        return 100


def density_valid_count() -> int:
    return int(load_sections()["density_rank"].notna().sum())


def density_selection_count(density_percent: Any) -> int:
    percent = normalize_density_percent(density_percent)
    return math.ceil(density_valid_count() * percent / 100)


def density_threshold(density_percent: Any) -> float | None:
    percent = normalize_density_percent(density_percent)
    limit = density_selection_count(percent)
    if percent == 100 or limit == 0:
        return None
    rows = load_sections().loc[load_sections()["density_rank"].eq(limit)]
    if rows.empty:
        return None
    return float(rows.iloc[0]["densidad_viviendas_km2"])


def _density_mask(frame: pd.DataFrame, density_percent: Any) -> pd.Series:
    percent = normalize_density_percent(density_percent)
    if percent == 100:
        return pd.Series(True, index=frame.index)
    limit = density_selection_count(percent)
    return frame["density_rank"].notna() & frame["density_rank"].le(limit)


def normalize_security_percent(value: Any) -> int:
    try:
        return min(100, max(1, round(float(value))))
    except (TypeError, ValueError):
        return 100


def security_valid_count() -> int:
    return int(load_sections()["security_rank_start"].notna().sum())


def security_target_count(security_percent: Any) -> int:
    percent = normalize_security_percent(security_percent)
    return math.ceil(security_valid_count() * percent / 100)


def _security_mask(frame: pd.DataFrame, security_percent: Any) -> pd.Series:
    percent = normalize_security_percent(security_percent)
    if percent == 100:
        return pd.Series(True, index=frame.index)
    target = security_target_count(percent)
    return frame["security_rank_start"].notna() & frame["security_rank_start"].le(target)


def security_threshold(security_percent: Any) -> float | None:
    percent = normalize_security_percent(security_percent)
    if percent == 100:
        return None
    frame = load_sections()
    selected = frame[_security_mask(frame, percent)]
    if selected.empty:
        return None
    return float(selected["tasa_incidencia_total_100k"].max())


def security_effective_count(security_percent: Any) -> int:
    percent = normalize_security_percent(security_percent)
    if percent == 100:
        return security_valid_count()
    return int(_security_mask(load_sections(), percent).sum())


def select_frame(
    active_profiles: list[str],
    selected_id: str | None = None,
    density_percent: Any = 100,
    security_percent: Any = 100,
) -> pd.DataFrame:
    frame = load_sections()
    active = [profile for profile in active_profiles if profile in ALL_PROFILES]
    if selected_id:
        if selected_id not in frame.index:
            return frame.iloc[0:0]
        row = frame.loc[[selected_id]]
        if (
            str(row.iloc[0]["perfil_visual_id"]) not in active
            or not bool(_density_mask(row, density_percent).iloc[0])
            or not bool(_security_mask(row, security_percent).iloc[0])
        ):
            return frame.iloc[0:0]
        return row
    if (
        len(active) == len(ALL_PROFILES)
        and set(active) == set(ALL_PROFILES)
        and normalize_density_percent(density_percent) == 100
        and normalize_security_percent(security_percent) == 100
    ):
        return frame
    return frame.loc[
        frame["perfil_visual_id"].isin(active)
        & _density_mask(frame, density_percent)
        & _security_mask(frame, security_percent)
    ]


def historical_series(frame: pd.DataFrame) -> list[dict[str, Any]]:
    result = []
    for year in YEARS:
        voted = frame[f"voted_{year}"]
        denominator = frame[f"denom_{year}"]
        value = _ratio(voted, denominator)
        valid = voted.notna() & denominator.notna() & denominator.gt(0)
        result.append(
            {
                "year": year,
                "value": value,
                "sections": int(valid.sum()),
                "denominator": float(denominator[valid].sum()) if valid.any() else 0.0,
                "family": "intermedia" if year in (2009, 2015, 2021) else "presidencial",
            }
        )
    return result


def group_distribution(
    frame: pd.DataFrame, groups: list[tuple[str, str, str]]
) -> list[dict[str, Any]]:
    counts = []
    for label, count_col, turnout_col in groups:
        raw_count = frame[count_col].sum(min_count=1) if len(frame) else np.nan
        count = None if pd.isna(raw_count) else float(raw_count)
        # Los perfiles de participación almacenan la tasa y el denominador
        # identificado; la tasa agregada se pondera por ese denominador.
        turnout = _weighted_average(frame[turnout_col], frame[count_col]) if len(frame) else None
        counts.append({"label": label, "count": count, "turnout": turnout})
    total = sum(item["count"] or 0 for item in counts)
    for item in counts:
        item["share"] = item["count"] / total if total and item["count"] is not None else None
    return counts


def sociodemographic_value(frame: pd.DataFrame, metric_id: str) -> dict[str, Any]:
    metric = SOCIO_METRICS.get(metric_id, SOCIO_METRICS["internet"])
    numerator = metric["numerator"]
    denominator = metric["denominator"]
    if metric["format"] == "years":
        value = _weighted_average(frame[numerator], frame[denominator]) if len(frame) else None
    else:
        value = _ratio(frame[numerator], frame[denominator]) if len(frame) else None
    return {
        "id": metric_id,
        "label": metric["label"],
        "value": value,
        "format": metric["format"],
        "period": metric["period"],
        "coverage": _coverage(frame, numerator)
        if len(frame)
        else {"available": 0, "total": 0, "rate": 0},
    }


def build_payload(
    active_profiles: list[str],
    selected_id: str | None,
    metric_id: str = "internet",
    density_percent: Any = 100,
    security_percent: Any = 100,
) -> dict[str, Any]:
    percent = normalize_density_percent(density_percent)
    safety_percent = normalize_security_percent(security_percent)
    frame = select_frame(active_profiles, selected_id, percent, safety_percent)
    visible_sections = (
        len(frame)
        if selected_id is None
        else len(select_frame(active_profiles, None, percent, safety_percent))
    )
    universe = len(load_sections())
    selected = frame.iloc[0] if selected_id and len(frame) == 1 else None
    history = historical_series(frame) if len(frame) else []
    projected = _weighted_average(frame["prediccion_central_2027"], frame["lista_nominal_2024"])
    model_reference = _weighted_average(
        frame["baseline_persistencia_2027"], frame["lista_nominal_2024"]
    )
    observed_2021 = next((item["value"] for item in history if item["year"] == 2021), None)
    change = _weighted_average(frame["cambio_proyectado_2027_pp"], frame["lista_nominal_2024"])
    counts = (
        frame["perfil_visual_id"].value_counts().reindex(ALL_PROFILES, fill_value=0).to_dict()
        if len(frame)
        else {profile: 0 for profile in ALL_PROFILES}
    )
    return {
        "mode": "section" if selected is not None else "aggregate",
        "empty": len(frame) == 0,
        "empty_reason": (
            "profiles"
            if not active_profiles
            else "filters"
        ),
        "section": selected.to_dict() if selected is not None else None,
        "section_count": len(frame),
        "universe_share": len(frame) / universe,
        "density": {
            "percent": percent,
            "valid_universe": density_valid_count(),
            "national_selected": density_selection_count(percent),
            "visible_sections": visible_sections,
            "threshold": density_threshold(percent),
            "coverage_rate": density_valid_count() / universe,
        },
        "security": {
            "percent": safety_percent,
            "valid_universe": security_valid_count(),
            "target_sections": security_target_count(safety_percent),
            "effective_sections": security_effective_count(safety_percent),
            "visible_sections": visible_sections,
            "threshold": security_threshold(safety_percent),
            "coverage_rate": security_valid_count() / universe,
            "missing_sections": universe - security_valid_count(),
        },
        "profile_counts": {key: int(value) for key, value in counts.items()},
        "history": history,
        "projected_2027": projected,
        "observed_2021": observed_2021,
        "model_reference_2021": model_reference,
        "change_2021_2027_pp": change,
        "age": group_distribution(frame, AGE_GROUPS) if len(frame) else [],
        "sex": group_distribution(frame, SEX_GROUPS) if len(frame) else [],
        "socio": sociodemographic_value(frame, metric_id),
        "coverage": {
            "projection": _coverage(frame, "prediccion_central_2027")
            if len(frame)
            else {"available": 0, "total": 0, "rate": 0},
            "electoral_demography": _coverage(frame, "female_identified_2024")
            if len(frame)
            else {"available": 0, "total": 0, "rate": 0},
            "eceg": _coverage(frame, "eceg_population_total")
            if len(frame)
            else {"available": 0, "total": 0, "rate": 0},
            "security": _coverage(frame, "tasa_incidencia_total_100k")
            if len(frame)
            else {"available": 0, "total": 0, "rate": 0},
        },
    }


def export_selection_csv(
    active_profiles: list[str], density_percent: Any = 100, security_percent: Any = 100
) -> tuple[str, int]:
    """Compatibilidad para consumidores internos; la ruta web usa streaming."""
    chunks, count = export_selection_csv_stream(
        active_profiles, density_percent, security_percent
    )
    return "".join(chunks), count


def _export_metadata(
    active_profiles: list[str], density_percent: Any, security_percent: Any, row_count: int
) -> str:
    density = normalize_density_percent(density_percent)
    security = normalize_security_percent(security_percent)
    metadata = {
        "perfiles_visuales": [profile for profile in active_profiles if profile in ALL_PROFILES],
        "densidad_superior_porcentaje": density,
        "incidencia_inferior_porcentaje_solicitado": security,
        "incidencia_inferior_porcentaje_efectivo": (
            security_effective_count(security) / security_valid_count()
            if security < 100 and security_valid_count()
            else 1.0
        ),
        "universo_nacional": len(load_sections()),
        "filas_exportadas": row_count,
        "modelo_vigente": str(load_sections()["version_modelo"].iloc[0]),
        "generado_utc": datetime.now(UTC).isoformat(),
    }
    return json.dumps(metadata, ensure_ascii=False, sort_keys=True)


def export_selection_csv_stream(
    active_profiles: list[str],
    density_percent: Any = 100,
    security_percent: Any = 100,
    *,
    batch_size: int = 512,
) -> tuple[Iterator[str], int]:
    """Entrega el contrato CSV completo por lotes, sin materializarlo en RAM."""
    density = normalize_density_percent(density_percent)
    security = normalize_security_percent(security_percent)
    active = [profile for profile in active_profiles if profile in ALL_PROFILES]
    row_count = len(select_frame(active, None, density, security))
    metadata = _export_metadata(active, density, security, row_count)
    density_limit = density_selection_count(density)
    security_limit = security_target_count(security)

    def generate() -> Iterator[str]:
        # Dos CSV de 171 MB en paralelo reducen demasiado el margen de una
        # instancia de 512 MB. Se atienden en serie; los callbacks siguen
        # disponibles en el segundo hilo de Gunicorn.
        with _EXPORT_LOCK:
            first = True
            parquet = pq.ParquetFile(DATA_PATH)
            try:
                for batch in parquet.iter_batches(batch_size=batch_size):
                    chunk = batch.to_pandas()
                    mask = chunk["perfil_visual_id"].isin(active)
                    if density < 100:
                        mask &= chunk["density_rank"].notna() & chunk["density_rank"].le(
                            density_limit
                        )
                    if security < 100:
                        mask &= chunk["security_rank_start"].notna() & chunk[
                            "security_rank_start"
                        ].le(security_limit)
                    selected = chunk.loc[mask]
                    if selected.empty:
                        del selected, chunk, batch
                        gc.collect()
                        pa.default_memory_pool().release_unused()
                        continue
                    selected = selected.copy()
                    selected["metadatos_filtros_json"] = metadata
                    csv_chunk = selected.to_csv(
                        index=False, header=first, lineterminator="\n"
                    )
                    if first:
                        csv_chunk = "\ufeff" + csv_chunk
                        first = False
                    del selected, chunk, batch
                    gc.collect()
                    pa.default_memory_pool().release_unused()
                    yield csv_chunk
                if first:
                    columns = list(parquet.schema.names) + ["metadatos_filtros_json"]
                    yield "\ufeff" + ",".join(columns) + "\n"
            finally:
                del parquet
                gc.collect()
                pa.default_memory_pool().release_unused()

    return generate(), row_count
