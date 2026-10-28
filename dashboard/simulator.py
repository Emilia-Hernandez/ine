"""Lógica pura del simulador de intervenciones.

Este módulo no modifica predicciones ni perfiles. Toma el universo ya preparado
por el dashboard, establece un orden pseudoaleatorio reproducible y aplica los
efectos hipotéticos expresados en puntos porcentuales.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any

import numpy as np
import pandas as pd

from dashboard.data_layer import ALL_PROFILES, VEB_COLUMNS, select_frame

PRIORITY_ORDER = ("Alta", "Media", "Baja")
PRIORITY_BY_PROFILE = {
    "P1": "Alta",
    "P2": "Alta",
    "P3": "Media",
    "P6": "Media",
    "P4": "Baja",
    "P5": "Baja",
    "EI_AB": "Media",
    "EI_CD": "Media",
}
PRIORITY_COLORS = {"Alta": "#B42318", "Media": "#E7B416", "Baja": "#2E7D57"}

INTERVENTIONS: tuple[dict[str, Any], ...] = (
    {
        "id": 1,
        "name": "Carta sobre el secreto del voto",
        "conservative": 0.5,
        "central": 1.0,
        "optimistic": 2.0,
    },
    {
        "id": 2,
        "name": "Carta con norma social",
        "conservative": 0.2,
        "central": 0.6,
        "optimistic": 1.0,
    },
    {
        "id": 3,
        "name": "Recordatorio por SMS o WhatsApp",
        "conservative": 0.5,
        "central": 1.0,
        "optimistic": 1.5,
    },
    {
        "id": 4,
        "name": "Plan de voto",
        "conservative": 0.3,
        "central": 0.75,
        "optimistic": 1.2,
    },
    {
        "id": 5,
        "name": "Información personalizada sobre la casilla",
        "conservative": 0.2,
        "central": 0.6,
        "optimistic": 1.0,
    },
    {
        "id": 6,
        "name": "Carta felicitando al municipio",
        "conservative": 0.0,
        "central": 0.5,
        "optimistic": 1.0,
    },
)
SCENARIO_ORDER = ("conservative", "central", "optimistic")
SCENARIOS = set(SCENARIO_ORDER)
SIMULATOR_COLUMNS = [
    "clave_seccion",
    "clave_entidad",
    "nombre_entidad",
    "clave_municipio",
    "nombre_municipio",
    "perfil_visual_id",
    "prediccion_central_2027",
    "municipal_attacks_cumulative",
    "municipal_attacks_24m",
]


def stable_score(seed: int, section_key: str, namespace: str) -> int:
    """Devuelve un entero estable entre procesos y ajeno al orden de filas."""
    payload = f"radar27|{namespace}|{int(seed)}|{section_key}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big", signed=False)


def priority_for_profile(profile: Any) -> str | None:
    return PRIORITY_BY_PROFILE.get(str(profile))


def intervention_for(seed: int, section_key: str) -> dict[str, Any]:
    index = stable_score(seed, section_key, "assignment-v1") % len(INTERVENTIONS)
    return INTERVENTIONS[index]


def eligible_sections(
    active_profiles: list[str] | None = None,
    *,
    include_insufficient: bool = True,
    density_percent: Any = 100,
    security_percent: Any = 100,
    veb_period: Any = "cumulative",
    veb_threshold: Any = None,
) -> pd.DataFrame:
    """Reutiliza exactamente las máscaras territoriales del explorador."""
    requested = ALL_PROFILES if active_profiles is None else active_profiles
    active = [profile for profile in requested if profile in ALL_PROFILES]
    if not include_insufficient:
        active = [profile for profile in active if not profile.startswith("EI_")]
    frame = select_frame(
        active,
        None,
        density_percent,
        security_percent,
        veb_period,
        veb_threshold,
    ).loc[:, SIMULATOR_COLUMNS].copy()
    frame["prioridad_operativa"] = frame["perfil_visual_id"].map(PRIORITY_BY_PROFILE)
    return frame.loc[frame["prioridad_operativa"].notna()]


def priority_counts(frame: pd.DataFrame) -> dict[str, int]:
    counts = frame.get("prioridad_operativa", pd.Series(dtype="string")).value_counts()
    return {priority: int(counts.get(priority, 0)) for priority in PRIORITY_ORDER}


def _projection_percent(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce").astype("float64")
    finite = numeric[np.isfinite(numeric)]
    if len(finite) and float(finite.abs().max()) <= 1.5:
        numeric = numeric * 100.0
    return numeric.where(numeric.between(0, 100, inclusive="both"))


def _ordered_keys(frame: pd.DataFrame, seed: int) -> list[str]:
    pieces: list[pd.DataFrame] = []
    for priority in PRIORITY_ORDER:
        namespace = f"selection-{priority.lower()}-v1"
        piece = frame.loc[
            frame["prioridad_operativa"].eq(priority), ["clave_seccion"]
        ].reset_index(drop=True)
        piece["_score"] = piece["clave_seccion"].map(
            lambda key, namespace=namespace: stable_score(seed, str(key), namespace)
        )
        piece = piece.sort_values(["_score", "clave_seccion"], kind="mergesort")
        pieces.append(piece)
    if not pieces:
        return []
    return pd.concat(pieces, ignore_index=True)["clave_seccion"].astype(str).tolist()


def _mean(values: pd.Series) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce")
    return None if not numeric.notna().any() else float(numeric.mean())


def _summary_row(
    frame: pd.DataFrame,
    label: str,
    legacy_scenario: str = "central",
) -> dict[str, Any]:
    treated = frame.loc[frame["seleccionada"]]
    valid = treated.loc[treated["participacion_base_pct"].notna()]
    base = _mean(valid["participacion_base_pct"])
    row: dict[str, Any] = {
        "grupo": label,
        "secciones_asignadas": len(treated),
        "participacion_sin": base,
        "sin_proyeccion_valida": int(treated["participacion_base_pct"].isna().sum()),
    }
    for scenario in SCENARIO_ORDER:
        after = _mean(valid[f"participacion_{scenario}_pct"])
        row[f"participacion_{scenario}"] = after
        row[f"incremento_{scenario}_pp"] = (
            None if base is None or after is None else after - base
        )
    row["participacion_con"] = row[f"participacion_{legacy_scenario}"]
    row["incremento_pp"] = row[f"incremento_{legacy_scenario}_pp"]
    return row


def simulate(
    frame: pd.DataFrame,
    selected_count: Any,
    *,
    seed: Any = 42,
    scenario: str = "central",
) -> dict[str, Any]:
    """Selecciona, asigna y simula sin alterar el ``frame`` de entrada."""
    scenario = scenario if scenario in SCENARIOS else "central"
    try:
        normalized_seed = int(seed)
    except (TypeError, ValueError, OverflowError):
        normalized_seed = 42
    try:
        count = round(float(selected_count))
    except (TypeError, ValueError, OverflowError):
        count = 0
    count = min(len(frame), max(0, count))

    result = frame.copy()
    if "prioridad_operativa" not in result:
        result["prioridad_operativa"] = result["perfil_visual_id"].map(PRIORITY_BY_PROFILE)
    if not result["clave_seccion"].is_unique:
        raise ValueError("La llave seccional debe ser inequívoca para simular")

    ordered = _ordered_keys(result, normalized_seed)
    selected_keys = ordered[:count]
    selection_rank = {key: rank for rank, key in enumerate(selected_keys, start=1)}
    result["orden_seleccion"] = result["clave_seccion"].map(selection_rank).astype("Int64")
    result["seleccionada"] = result["orden_seleccion"].notna()
    result["evidencia_insuficiente"] = result["perfil_visual_id"].astype(str).str.startswith("EI_")

    assignments = {
        key: intervention_for(normalized_seed, key) for key in selected_keys
    }
    result["intervencion_id"] = result["clave_seccion"].map(
        {key: item["id"] for key, item in assignments.items()}
    ).astype("Int64")
    result["intervencion"] = result["clave_seccion"].map(
        {key: item["name"] for key, item in assignments.items()}
    )
    result["participacion_base_pct"] = _projection_percent(result["prediccion_central_2027"])
    treated_valid = result["seleccionada"] & result["participacion_base_pct"].notna()
    for scenario_name in SCENARIO_ORDER:
        effect_column = f"efecto_{scenario_name}_pp"
        participation_column = f"participacion_{scenario_name}_pct"
        variation_column = f"variacion_{scenario_name}_pp"
        result[effect_column] = result["clave_seccion"].map(
            {key: item[scenario_name] for key, item in assignments.items()}
        ).fillna(0.0).astype(float)
        result[participation_column] = result["participacion_base_pct"]
        result.loc[treated_valid, participation_column] = np.minimum(
            100.0,
            result.loc[treated_valid, "participacion_base_pct"]
            + result.loc[treated_valid, effect_column],
        )
        result[variation_column] = (
            result[participation_column] - result["participacion_base_pct"]
        )

    # Alias compatibles: conservan el escenario solicitado por consumidores previos.
    result["efecto_pp"] = result[f"efecto_{scenario}_pp"]
    result["participacion_con_intervencion_pct"] = result[
        f"participacion_{scenario}_pct"
    ]
    result["variacion_proyectada_pp"] = result[f"variacion_{scenario}_pp"]
    result["semilla"] = normalized_seed
    result["escenario_eficacia"] = scenario

    selected = result.loc[result["seleccionada"]]
    valid = selected.loc[selected["participacion_base_pct"].notna()]
    base = _mean(valid["participacion_base_pct"])
    scenario_results: dict[str, dict[str, float | None]] = {}
    for scenario_name in SCENARIO_ORDER:
        after = _mean(valid[f"participacion_{scenario_name}_pct"])
        scenario_results[scenario_name] = {
            "with_mean": after,
            "increment_mean": None if base is None or after is None else after - base,
        }
    after = scenario_results[scenario]["with_mean"]
    period_rows: list[dict[str, Any]] = []
    for intervention in INTERVENTIONS:
        subset = result.loc[result["intervencion_id"].eq(intervention["id"])]
        period_rows.append(_summary_row(subset, intervention["name"], scenario))
    period_rows.append(_summary_row(result, "Total", scenario))

    priority_rows = [
        _summary_row(
            result.loc[result["prioridad_operativa"].eq(priority)],
            priority,
            scenario,
        )
        for priority in PRIORITY_ORDER
    ]
    priority_rows.append(_summary_row(result, "Total", scenario))

    return {
        "frame": result,
        "selected_keys": selected_keys,
        "eligible_count": len(result),
        "selected_count": len(selected),
        "coverage_percent": (100.0 * len(selected) / len(result)) if len(result) else 0.0,
        "priority_counts": priority_counts(result),
        "selected_priority_counts": priority_counts(selected),
        "base_mean": base,
        "with_mean": after,
        "increment_mean": None if base is None or after is None else after - base,
        "scenario_results": scenario_results,
        "reference_mean": _mean(result["participacion_base_pct"]),
        "valid_selected": len(valid),
        "invalid_selected": int(selected["participacion_base_pct"].isna().sum()),
        "intervention_rows": period_rows,
        "priority_rows": priority_rows,
        "assignment_counts": {
            item["name"]: int(selected["intervencion_id"].eq(item["id"]).sum())
            for item in INTERVENTIONS
        },
    }


def crime_column(period: Any) -> str:
    return VEB_COLUMNS.get(str(period), VEB_COLUMNS["cumulative"])


def security_context(simulation: dict[str, Any], period: Any) -> dict[str, Any]:
    selected = simulation["frame"].loc[simulation["frame"]["seleccionada"]]
    values = pd.to_numeric(selected[crime_column(period)], errors="coerce")
    positive = int(values.gt(0).sum())
    total = len(selected)
    return {
        "positive": positive,
        "share": positive / total if total else 0.0,
        "missing": int(values.isna().sum()),
        "total": total,
    }


def coverage_count(total: int, percent: Any) -> int:
    try:
        value = min(100.0, max(0.0, float(percent)))
    except (TypeError, ValueError, OverflowError):
        value = 0.0
    return min(total, max(0, math.floor(total * value / 100.0 + 0.5)))
