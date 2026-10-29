"""Construcción reproducible de la representación nacional ligera."""

from __future__ import annotations

import gzip
import json
import os
from pathlib import Path
from typing import Any

import geopandas as gpd

NATIONAL_COLUMNS = ["k", "p", "r", "s", "a", "b", "geometry"]


def build_national_map(source: Path, target: Path) -> dict[str, Any]:
    """Convierte polígonos seccionales en puntos interiores y GeoJSON gzip."""
    frame = gpd.read_file(source)[NATIONAL_COLUMNS]
    if len(frame) != 70_751 or not frame["k"].is_unique:
        raise ValueError("La cartografía nacional no conserva las 70,751 claves únicas")
    metric = frame.to_crs(6933)
    metric.geometry = metric.geometry.representative_point()
    points = metric.to_crs(4326)
    if not points.geometry.is_valid.all() or points.geometry.is_empty.any():
        raise ValueError("La representación nacional contiene puntos inválidos")
    payload = points.to_json(
        drop_id=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    compressed = gzip.compress(payload, compresslevel=9, mtime=0)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(compressed)
    os.replace(temporary, target)
    decoded = json.loads(gzip.decompress(compressed))
    return {
        "features": len(decoded["features"]),
        "uncompressed_bytes": len(payload),
        "compressed_bytes": len(compressed),
    }
