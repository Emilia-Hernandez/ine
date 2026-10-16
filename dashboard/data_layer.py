"""Consultas y agregaciones del dashboard, separadas de la interfaz Dash."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "dashboard" / "data" / "dashboard_sections.parquet"
YEARS = [2009, 2012, 2015, 2018, 2021, 2024]
ALL_PROFILES = ["P1", "P2", "P3", "P4", "P5", "P6", "EI"]

PROFILE_LABELS = {
    "P1": "Deterioro persistente",
    "P2": "Deterioro proyectado",
    "P3": "Rezago persistente",
    "P4": "Recuperación",
    "P5": "Favorable y estable",
    "P6": "Variable o no diferenciada",
    "EI": "Evidencia insuficiente",
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
    frame = pd.read_parquet(DATA_PATH)
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


def select_frame(active_profiles: list[str], selected_id: str | None = None) -> pd.DataFrame:
    frame = load_sections()
    active = [profile for profile in active_profiles if profile in ALL_PROFILES]
    if selected_id:
        if selected_id not in frame.index:
            return frame.iloc[0:0]
        row = frame.loc[[selected_id]]
        if str(row.iloc[0]["perfil_electoral_id"]) not in active:
            return frame.iloc[0:0]
        return row
    return frame[frame["perfil_electoral_id"].isin(active)]


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
    active_profiles: list[str], selected_id: str | None, metric_id: str = "internet"
) -> dict[str, Any]:
    frame = select_frame(active_profiles, selected_id)
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
        frame["perfil_electoral_id"].value_counts().reindex(ALL_PROFILES, fill_value=0).to_dict()
        if len(frame)
        else {profile: 0 for profile in ALL_PROFILES}
    )
    return {
        "mode": "section" if selected is not None else "aggregate",
        "empty": len(frame) == 0,
        "section": selected.to_dict() if selected is not None else None,
        "section_count": len(frame),
        "universe_share": len(frame) / universe,
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
        },
    }
