"""Reglas puras del estado interactivo."""

from __future__ import annotations

from typing import Any

import pandas as pd

from dashboard.data_layer import (
    VEB_COLUMNS,
    density_selection_count,
    load_sections,
    normalize_density_percent,
    normalize_security_percent,
    normalize_veb_period,
    normalize_veb_threshold,
    security_target_count,
    veb_filter_enabled,
)


def resolve_selection(
    trigger: str | None,
    active_profiles: list[str],
    click_data: dict[str, Any] | None,
    current_selection: str | None,
    density_percent: int = 100,
    security_percent: int = 100,
    veb_period: str = "cumulative",
    veb_threshold: int | None = None,
) -> str | None:
    """Resuelve la sección activa sin alterar el estado geográfico del mapa."""
    selected = current_selection
    period = normalize_veb_period(veb_period)
    attack_limit = normalize_veb_threshold(period, veb_threshold)
    if trigger == "clear-selection":
        selected = None
    elif trigger == "section-geo" and click_data:
        properties = click_data.get("properties", {})
        candidate = properties.get("k")
        density_enabled = normalize_density_percent(density_percent) < 100
        rank = properties.get("r", -1)
        density_allowed = not density_enabled or (
            isinstance(rank, (int, float)) and rank > 0 and rank <= density_selection_count(density_percent)
        )
        security_enabled = normalize_security_percent(security_percent) < 100
        security_rank = properties.get("s", -1)
        security_allowed = not security_enabled or (
            isinstance(security_rank, (int, float))
            and security_rank > 0
            and security_rank <= security_target_count(security_percent)
        )
        attack_count = properties.get("a" if period == "cumulative" else "b", -1)
        veb_allowed = not veb_filter_enabled(period, attack_limit) or (
            isinstance(attack_count, (int, float))
            and attack_count >= 0
            and attack_count <= attack_limit
        )
        if (
            candidate
            and properties.get("p") in active_profiles
            and density_allowed
            and security_allowed
            and veb_allowed
        ):
            selected = str(candidate)
    if selected:
        frame = load_sections()
        if selected not in frame.index:
            return None
        row = frame.loc[selected]
        density_allowed = normalize_density_percent(density_percent) == 100 or (
            pd.notna(row["density_rank"])
            and int(row["density_rank"]) <= density_selection_count(density_percent)
        )
        security_allowed = normalize_security_percent(security_percent) == 100 or (
            pd.notna(row["security_rank_start"])
            and int(row["security_rank_start"]) <= security_target_count(security_percent)
        )
        attack_count = row[VEB_COLUMNS[period]]
        veb_allowed = not veb_filter_enabled(period, attack_limit) or (
            pd.notna(attack_count) and int(attack_count) <= attack_limit
        )
        if (
            str(row["perfil_visual_id"]) not in active_profiles
            or not density_allowed
            or not security_allowed
            or not veb_allowed
        ):
            selected = None
    return selected
