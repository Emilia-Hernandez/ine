"""Reglas puras del estado interactivo."""

from __future__ import annotations

from typing import Any

from dashboard.data_layer import load_sections


def resolve_selection(
    trigger: str | None,
    active_profiles: list[str],
    click_data: dict[str, Any] | None,
    current_selection: str | None,
) -> str | None:
    """Resuelve la sección activa sin alterar el estado geográfico del mapa."""
    selected = current_selection
    if trigger == "clear-selection":
        selected = None
    elif trigger == "section-geo" and click_data:
        properties = click_data.get("properties", {})
        candidate = properties.get("k")
        if candidate and properties.get("p") in active_profiles:
            selected = str(candidate)
    if selected:
        frame = load_sections()
        if (
            selected not in frame.index
            or str(frame.loc[selected, "perfil_electoral_id"]) not in active_profiles
        ):
            selected = None
    return selected
