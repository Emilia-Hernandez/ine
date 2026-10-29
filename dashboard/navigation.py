"""URLs de navegación entre los dos servicios independientes."""

from __future__ import annotations

import os


def _default_url(production: str, local: str) -> str:
    return production if os.environ.get("RENDER") else local


EXPLORER_URL = os.environ.get(
    "RADAR27_EXPLORER_URL",
    _default_url("https://radar27.onrender.com", "http://127.0.0.1:8050"),
)
SIMULATOR_URL = os.environ.get(
    "RADAR27_SIMULATOR_URL",
    _default_url("https://radar27-simulador.onrender.com", "http://127.0.0.1:8051"),
)
