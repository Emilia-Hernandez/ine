"""Selección compartida de nivel cartográfico para los dos mapas."""

from __future__ import annotations

import math
from typing import Any

NATIONAL_MAP_URL = "/map/sections-national-v1.geojson"
NATIONAL_MAX_ZOOM = 5
DETAIL_MIN_ZOOM = 7
MEXICO_RECT = {"minX": -118.8, "minY": 14.2, "maxX": -86.4, "maxY": 33.4}


def _bounded_rect(bounds: Any, grid: float) -> dict[str, float]:
    if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
        return MEXICO_RECT.copy()
    try:
        south, west = (float(value) for value in bounds[0])
        north, east = (float(value) for value in bounds[1])
    except (TypeError, ValueError):
        return MEXICO_RECT.copy()
    if not all(math.isfinite(value) for value in (south, west, north, east)):
        return MEXICO_RECT.copy()
    lon_pad = max((east - west) * 0.08, 0.03)
    lat_pad = max((north - south) * 0.08, 0.03)
    return {
        "minX": max(-119.5, math.floor((west - lon_pad) / grid) * grid),
        "minY": max(13.5, math.floor((south - lat_pad) / grid) * grid),
        "maxX": min(-85.5, math.ceil((east + lon_pad) / grid) * grid),
        "maxY": min(34.0, math.ceil((north + lat_pad) / grid) * grid),
    }


def geometry_spec(
    asset_prefix: str,
    zoom: Any,
    bounds: Any,
    national_url: str = NATIONAL_MAP_URL,
) -> tuple[str, str, dict[str, Any]]:
    """Devuelve URL, formato y bbox cuantizado para el nivel visible."""
    try:
        level = float(zoom)
    except (TypeError, ValueError):
        level = 4.0
    if level <= NATIONAL_MAX_ZOOM:
        return national_url, "geojson", {}
    detail = level >= DETAIL_MIN_ZOOM
    filename = "sections_detail.fgb" if detail else "sections_overview.fgb"
    grid = 0.25 if detail else 1.0
    return (
        f"{asset_prefix}/{filename}",
        "flatgeobuf",
        {"rect": _bounded_rect(bounds, grid)},
    )
