"""Aplicación Dash independiente del Simulador de intervenciones."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from dash import Dash, html
from flask import Response, jsonify, request, stream_with_context

from dashboard.navigation import EXPLORER_URL
from dashboard.simulator_ui import layout as simulator_layout
from dashboard.simulator_ui import register_callbacks
from dashboard.simulator_ui import simulation_aggregate_csv, simulation_csv_chunks

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "dashboard" / "assets"
RELEASE_POINTER = ROOT / "dashboard" / "data" / "current_release.json"
WORKING_COPY = os.environ.get("RADAR27_DASHBOARD_WORKING_COPY") == "1"
CURRENT_RELEASE = (
    json.loads(RELEASE_POINTER.read_text(encoding="utf-8"))
    if RELEASE_POINTER.exists() and not WORKING_COPY
    else {
        "dashboard_release_version": "working-copy-votar-entre-balas",
        "model_version": "radar27-final-2027-municipal.1",
        "asset_prefix": "/assets",
    }
)
ASSET_PREFIX = str(CURRENT_RELEASE["asset_prefix"])
MEXICO_BOUNDS = [[14.2, -118.8], [33.4, -86.4]]

app = Dash(
    __name__,
    assets_folder=str(ASSETS),
    title="Simulador de intervenciones · RADAR 27",
    update_title="Actualizando…",
)
server = app.server
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@server.get("/healthz")
def healthz() -> Any:
    """Sonda ligera que no fuerza el cálculo de una simulación."""
    return jsonify(
        status="ok",
        application="simulator",
        release=CURRENT_RELEASE["dashboard_release_version"],
        model=CURRENT_RELEASE["model_version"],
    )


@server.after_request
def cache_versioned_map_assets(response: Any) -> Any:
    if request.path.startswith("/assets/releases/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


def _download_args() -> tuple[Any, ...]:
    profiles = [value for value in request.args.get("profiles", "").split(",") if value]
    include_ei = ["include"] if request.args.get("include_ei", "1") == "1" else []
    return (
        profiles,
        include_ei,
        request.args.get("density", 100),
        request.args.get("security", 100),
        request.args.get("period", "cumulative"),
        request.args.get("threshold"),
        request.args.get("count", 0),
        request.args.get("seed", 42),
    )


@server.get("/download/simulation-sections.csv")
def download_simulation_sections() -> Response:
    chunks, selected_count = simulation_csv_chunks(*_download_args())
    logger.info("simulation_csv_started selected=%s", selected_count)
    return Response(
        stream_with_context(chunks),
        mimetype="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="radar27_simulacion_{selected_count}.csv"'
            ),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@server.get("/download/simulation-aggregate.csv")
def download_simulation_aggregate() -> Response:
    payload = simulation_aggregate_csv(*_download_args())
    return Response(
        payload,
        mimetype="text/csv",
        headers={
            "Content-Disposition": (
                'attachment; filename="radar27_simulacion_agregados.csv"'
            ),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


app.layout = html.Div(
    [
        html.Header(
            [
                html.Div(
                    [
                        html.Span("RADAR 27", className="brand-mark"),
                        html.Div(
                            [
                                html.H1("Simulador de intervenciones"),
                                html.P("Planeación reproducible sobre secciones electorales"),
                            ]
                        ),
                    ],
                    className="brand-block",
                ),
                html.Div(
                    [
                        html.Span(f"Proyección central · {CURRENT_RELEASE['model_version']}"),
                        html.A(
                            "Volver al explorador territorial",
                            href=EXPLORER_URL,
                            className="dashboard-link",
                        ),
                    ],
                    className="header-meta",
                ),
            ],
            className="app-header",
        ),
        simulator_layout(ASSET_PREFIX, MEXICO_BOUNDS),
    ],
    className="app-shell",
)

register_callbacks(app)


if __name__ == "__main__":
    port = int(os.environ.get("SIMULATOR_PORT", "8051"))
    app.run(host="127.0.0.1", port=port, debug=False)


__all__ = ["app", "server"]
