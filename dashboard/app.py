"""Aplicación Dash del explorador de participación electoral 2027."""

from __future__ import annotations

import json
import logging
import math
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import dash_leaflet as dl
from dash import Dash, Input, Output, State, ctx, dcc, html, no_update
from dash_extensions.javascript import Namespace
from flask import Response, jsonify, stream_with_context

from dashboard.data_layer import (
    ALL_PROFILES,
    PROFILE_LABELS,
    SOCIO_METRICS,
    build_payload,
    density_selection_count,
    export_selection_csv_stream,
    load_sections,
    normalize_density_percent,
    normalize_security_percent,
    security_target_count,
)
from dashboard.figures import (
    ORANGE,
    SAND,
    TERRACOTTA,
    WINE,
    distribution_figure,
    empty_figure,
    socio_figure,
    timeline_figure,
)
from dashboard.state import resolve_selection

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "dashboard" / "assets"
RELEASE_POINTER = ROOT / "dashboard" / "data" / "current_release.json"
CURRENT_RELEASE = (
    json.loads(RELEASE_POINTER.read_text(encoding="utf-8"))
    if RELEASE_POINTER.exists()
    else {
        "dashboard_release_version": "working-copy",
        "model_version": "radar27-final-2027-municipal.1",
        "asset_prefix": "/assets",
    }
)
ASSET_PREFIX = str(CURRENT_RELEASE["asset_prefix"])
MEXICO_BOUNDS = [[14.2, -118.8], [33.4, -86.4]]
PROFILE_COLORS = {
    "P1": WINE,
    "P2": "#84213B",
    "P3": TERRACOTTA,
    "P4": ORANGE,
    "P5": SAND,
    "P6": "#EDE0C7",
    "EI_AB": "#F4C95D",
    "EI_CD": "#FBE9AF",
}

MAP_JS = Namespace("dashboardMap")

app = Dash(
    __name__,
    assets_folder=str(ASSETS),
    title="Participación electoral 2027 · INE",
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
    """Sonda ligera: no fuerza la carga del Parquet ni de las geometrías."""
    return jsonify(
        status="ok",
        release=CURRENT_RELEASE["dashboard_release_version"],
        model=CURRENT_RELEASE["model_version"],
    )


@server.get("/download/sections.csv")
def download_sections_csv() -> Response:
    from flask import request

    profiles = [value for value in request.args.get("profiles", "").split(",") if value]
    density = normalize_density_percent(request.args.get("density", 100))
    security = normalize_security_percent(request.args.get("security", 100))
    chunks, count = export_selection_csv_stream(profiles, density, security)
    logger.info(
        "csv_export_started rows=%s density=%s security=%s profiles=%s",
        count,
        density,
        security,
        profiles,
    )
    filename = f"radar27_secciones_seleccionadas_{count}.csv"

    def logged_chunks() -> Any:
        try:
            yield from chunks
        except GeneratorExit:
            logger.info("csv_export_cancelled rows=%s", count)
            raise
        except Exception:
            logger.exception("csv_export_failed rows=%s", count)
            raise
        else:
            logger.info("csv_export_completed rows=%s", count)

    return Response(
        stream_with_context(logged_chunks()),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _format_percent(value: Any) -> str:
    return "No disponible" if _missing(value) else f"{float(value):.1%}"


def _format_pp(value: Any) -> str:
    return "No disponible" if _missing(value) else f"{float(value):+.1f} pp"


def _format_bool(value: Any) -> str:
    if _missing(value):
        return "No disponible"
    return "Sí" if bool(value) else "No"


def _label(value: Any) -> str:
    if _missing(value) or str(value) in {"nan", "<NA>"}:
        return "No disponible"
    return str(value).replace("_", " ")


def _missing(value: Any) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def _profile_options() -> list[dict[str, Any]]:
    counts = load_sections()["perfil_visual_id"].value_counts().to_dict()
    options = []
    for profile in ALL_PROFILES:
        options.append(
            {
                "value": profile,
                "label": html.Span(
                    [
                        html.Span(
                            className="profile-dot",
                            style={"backgroundColor": PROFILE_COLORS[profile]},
                        ),
                        html.Span(
                            [
                                html.Strong("EI" if profile.startswith("EI_") else profile),
                                html.Span(
                                    f" — {PROFILE_LABELS[profile]}", className="profile-name"
                                ),
                            ],
                            className="profile-copy",
                        ),
                        html.Span(f"{counts.get(profile, 0):,}", className="profile-count"),
                    ],
                    className="profile-option",
                ),
            }
        )
    return options


def _metric_card(label: str, value: str, note: str | None = None, tone: str = "") -> html.Div:
    children: list[Any] = [
        html.Span(label, className="metric-label"),
        html.Strong(value, className="metric-value"),
    ]
    if note:
        children.append(html.Span(note, className="metric-note"))
    return html.Div(children, className=f"metric-card {tone}".strip())


def _coverage_row(label: str, coverage: dict[str, Any]) -> html.Div:
    rate = float(coverage.get("rate", 0))
    return html.Div(
        [
            html.Div(
                [
                    html.Span(label),
                    html.Span(f"{coverage.get('available', 0):,} / {coverage.get('total', 0):,}"),
                ],
                className="coverage-label",
            ),
            html.Div(html.Span(style={"width": f"{rate:.2%}"}), className="coverage-track"),
        ],
        className="coverage-row",
    )


def _profile_distribution(counts: dict[str, int], total: int) -> html.Div:
    rows = []
    for profile in ALL_PROFILES:
        count = int(counts.get(profile, 0))
        share = count / total if total else 0
        rows.append(
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(
                                className="mini-dot",
                                style={"backgroundColor": PROFILE_COLORS[profile]},
                            ),
                            html.Span(profile.replace("EI_", "EI-") if profile.startswith("EI_") else profile),
                            html.Span(f"{count:,}", className="mini-count"),
                        ],
                        className="mini-label",
                    ),
                    html.Div(
                        html.Span(
                            style={
                                "width": f"{share:.2%}",
                                "backgroundColor": PROFILE_COLORS[profile],
                            }
                        ),
                        className="mini-track",
                    ),
                ],
                className="mini-profile",
            )
        )
    return html.Div(rows, className="profile-distribution")


def _aggregate_panel(payload: dict[str, Any]) -> html.Div:
    if payload["empty"]:
        profiles_empty = payload["empty_reason"] == "profiles"
        return html.Div(
            [
                html.Div("∅", className="empty-symbol"),
                html.H3(
                    "No hay perfiles activos" if profiles_empty else "No hay secciones visibles"
                ),
                html.P(
                    "Selecciona al menos un perfil para recuperar el mapa y los agregados."
                    if profiles_empty
                    else "Aumenta el porcentaje de densidad para recuperar secciones."
                ),
            ],
            className="empty-panel",
        )
    return html.Div(
        [
            html.Div(
                [
                    html.Span("Vista agregada", className="eyebrow"),
                    html.H2("Resumen del conjunto activo"),
                    html.P(
                        "Los totales dependen de los filtros activos, no del zoom del mapa.",
                        className="muted",
                    ),
                ]
            ),
            html.Div(
                [
                    _metric_card(
                        "Secciones",
                        f"{payload['section_count']:,}",
                        f"{payload['universe_share']:.1%} del universo",
                    ),
                    _metric_card(
                        "2021 observado",
                        _format_percent(payload["observed_2021"]),
                        "Razón de sumas",
                    ),
                    _metric_card(
                        "2027 proyectado",
                        _format_percent(payload["projected_2027"]),
                        "Ponderado por lista nominal",
                        "accent",
                    ),
                    _metric_card(
                        "Cambio 2021→2027",
                        _format_pp(payload["change_2021_2027_pp"]),
                        "Referencia comparable del modelo",
                    ),
                ],
                className="metric-grid",
            ),
            html.H3("Distribución por perfil", className="section-heading"),
            _profile_distribution(payload["profile_counts"], payload["section_count"]),
            html.H3("Cobertura", className="section-heading"),
            _coverage_row("Proyección", payload["coverage"]["projection"]),
            _coverage_row("Edad y sexo electoral", payload["coverage"]["electoral_demography"]),
            _coverage_row("Demografía ECEG", payload["coverage"]["eceg"]),
            _coverage_row("Incidencia municipal", payload["coverage"]["security"]),
        ],
        className="context-panel-body",
    )


def _detail_row(label: str, value: str) -> html.Div:
    return html.Div([html.Span(label), html.Strong(value)], className="detail-row")


def _section_panel(payload: dict[str, Any]) -> html.Div:
    row = payload["section"]
    profile = str(row["perfil_visual_id"])
    return html.Div(
        [
            html.Div(
                [
                    html.Span("Sección seleccionada", className="eyebrow"),
                    html.H2(f"Sección {row['clave_seccion']}"),
                    html.P(
                        f"{str(row['nombre_entidad']).title()} · {row['nombre_municipio']}",
                        className="place-name",
                    ),
                    html.Div(
                        [
                            html.Span(
                                className="profile-dot",
                                style={"backgroundColor": PROFILE_COLORS[profile]},
                            ),
                            html.Strong(
                                f"EI — {PROFILE_LABELS[profile]}"
                                if profile.startswith("EI_")
                                else f"{profile} — {PROFILE_LABELS[profile]}"
                            ),
                        ],
                        className="selected-profile",
                    ),
                ]
            ),
            html.Div(
                [
                    _metric_card("2021 observado", _format_percent(row.get("participacion_2021"))),
                    _metric_card(
                        "2027 proyectado",
                        _format_percent(row.get("prediccion_central_2027")),
                        "Modelo A",
                        "accent",
                    ),
                    _metric_card(
                        "Cambio proyectado", _format_pp(row.get("cambio_proyectado_2027_pp"))
                    ),
                    _metric_card(
                        "Lista nominal 2024", f"{float(row.get('lista_nominal_2024', 0)):,.0f}"
                    ),
                ],
                className="metric-grid",
            ),
            html.H3("Información territorial", className="section-heading"),
            html.Div(
                [
                    _detail_row("Clase geográfica", _label(row.get("clase_confianza_geografica"))),
                    _detail_row("Historia electoral", _label(row.get("fuente_historia_electoral"))),
                    _detail_row(
                        "Caída material ≥1 pp",
                        _format_bool(row.get("senal_caida_material_proyectada")),
                    ),
                    _detail_row(
                        "Deterioro vs. municipio",
                        _format_bool(row.get("senal_deterioro_relativo_municipio")),
                    ),
                    _detail_row(
                        "Calidad municipal", _label(row.get("calidad_componente_municipal"))
                    ),
                    _detail_row("Fallback utilizado", _format_bool(row.get("uso_fallback"))),
                    _detail_row("Fuente 2027", _label(row.get("fuente_proyeccion_2027"))),
                    _detail_row(
                        "Incidencia municipal 2025",
                        "No disponible"
                        if _missing(row.get("tasa_incidencia_total_100k"))
                        else f"{float(row['tasa_incidencia_total_100k']):,.1f} por 100 mil",
                    ),
                    _detail_row(
                        "Nivel del indicador de seguridad", "Municipal asignado a la sección"
                    ),
                ],
                className="detail-list",
            ),
            html.Div(
                [
                    html.Strong("Evidencia insuficiente"),
                    html.Span(
                        row.get("motivo_evidencia_insuficiente")
                        if profile.startswith("EI_")
                        else "La evidencia insuficiente no implica que una sección carezca de importancia o prioridad. Indica que no disponemos de información suficiente o comparable para asignarle uno de los seis perfiles electorales."
                    ),
                    html.Span(
                        f"Años disponibles: {row.get('anios_historia_disponibles') or 'ninguno'}; "
                        f"faltantes: {row.get('anios_historia_faltantes') or 'ninguno'}."
                    )
                    if profile.startswith("EI_")
                    else None,
                ],
                className="note-box",
            )
            if profile.startswith("EI_")
            else None,
            html.Div(
                [
                    html.Strong("Lectura responsable"),
                    html.Span(
                        "La tipología describe trayectorias observadas y proyectadas; no identifica causas ni motivaciones individuales."
                    ),
                ],
                className="note-box",
            ),
        ],
        className="context-panel-body",
    )


def _chart_card(
    title: str,
    subtitle: str,
    graph_id: str,
    extra: Any = None,
    wide: bool = False,
    note: str | None = None,
) -> html.Section:
    header_children: list[Any] = [html.Div([html.H3(title), html.P(subtitle)])]
    if extra is not None:
        header_children.append(extra)
    graph_height = "350px" if wide else "240px"
    children: list[Any] = [
        html.Div(header_children, className="chart-header"),
        dcc.Graph(
            id=graph_id,
            config={"displayModeBar": False, "responsive": True},
            figure=empty_figure("Cargando…"),
            style={"height": graph_height},
        ),
    ]
    if note:
        children.append(html.P(note, className="chart-note"))
    return html.Section(
        children,
        className=f"chart-card {'chart-wide' if wide else ''}".strip(),
    )


app.layout = html.Div(
    [
        dcc.Store(id="selected-section", data=None),
        html.Header(
            [
                html.Div(
                    [
                        html.Span("RADAR 27", className="brand-mark"),
                        html.Div(
                            [
                                html.H1("Participación electoral 2027"),
                                html.P(
                                    "Explorador seccional de perfiles, territorio y contexto sociodemográfico"
                                ),
                            ]
                        ),
                    ],
                    className="brand-block",
                ),
                html.Div(
                    [
                        html.Span(
                            f"Proyección central · A_nacional_actual · {CURRENT_RELEASE['model_version']}"
                        ),
                        html.Span("Snapshot territorial 09·05·2024"),
                    ],
                    className="header-meta",
                ),
            ],
            className="app-header",
        ),
        html.Main(
            [
                html.Section(
                    [
                        html.Aside(
                            [
                                html.Div(
                                    [
                                        html.Span("Filtro", className="eyebrow"),
                                        html.H2("Perfiles electorales"),
                                        html.P(
                                            "Activa uno o varios perfiles para recalcular la vista agregada."
                                        ),
                                    ],
                                    className="filter-intro",
                                ),
                                dcc.Checklist(
                                    id="profile-filter",
                                    options=_profile_options(),
                                    value=ALL_PROFILES,
                                    className="profile-checklist",
                                    inputClassName="profile-checkbox",
                                    labelClassName="profile-label",
                                ),
                                html.Div(
                                    [
                                        html.Button(
                                            "Todos",
                                            id="select-all",
                                            n_clicks=0,
                                            className="button button-small",
                                        ),
                                        html.Button(
                                            "Limpiar",
                                            id="clear-profiles",
                                            n_clicks=0,
                                            className="button button-small button-quiet",
                                        ),
                                        html.Button(
                                            "Restaurar",
                                            id="restore-profiles",
                                            n_clicks=0,
                                            className="button button-small button-quiet",
                                        ),
                                    ],
                                    className="filter-actions",
                                ),
                                html.Div(
                                    [
                                        html.Strong("Clave de lectura"),
                                        html.P(
                                            "El color ordena la tipología acordada; no es una probabilidad continua de abstención."
                                        ),
                                    ],
                                    className="sidebar-note",
                                ),
                                html.Div(
                                    [
                                        html.Div(
                                            [
                                                html.Div(
                                                    [
                                                        html.Strong("Densidad de viviendas"),
                                                        html.Span(
                                                            "ⓘ",
                                                            title=(
                                                                "La densidad se calcula como viviendas "
                                                                "particulares habitadas por km². El porcentaje "
                                                                "identifica las secciones más densas del universo "
                                                                "nacional con información válida."
                                                            ),
                                                            className="density-help",
                                                        ),
                                                    ],
                                                    className="density-title",
                                                ),
                                                html.Span(
                                                    "Porcentaje de secciones más densas",
                                                    className="density-subtitle",
                                                ),
                                            ]
                                        ),
                                        html.Strong(
                                            "100%", id="density-value", className="density-value"
                                        ),
                                        dcc.Slider(
                                            id="density-filter",
                                            min=1,
                                            max=100,
                                            step=1,
                                            value=100,
                                            marks={
                                                10: "10%",
                                                25: "25%",
                                                50: "50%",
                                                66: "66%",
                                                100: "100%",
                                            },
                                            updatemode="drag",
                                            tooltip={"placement": "bottom"},
                                            className="density-slider",
                                        ),
                                        html.Div(
                                            [
                                                html.Button(
                                                    f"{value}%",
                                                    id=f"density-quick-{value}",
                                                    n_clicks=0,
                                                    className="button button-small button-quiet",
                                                )
                                                for value in (10, 25, 50, 66, 100)
                                            ],
                                            className="percent-shortcuts",
                                        ),
                                        html.P(
                                            "Mostrando el 100% de las secciones con mayor densidad de viviendas",
                                            id="density-description",
                                            className="density-description",
                                        ),
                                        html.Strong(
                                            "70,751 secciones visibles",
                                            id="density-visible",
                                            className="density-visible",
                                        ),
                                        html.Span(
                                            "Filtro desactivado; se incluyen secciones sin densidad válida.",
                                            id="density-threshold",
                                            className="density-threshold",
                                        ),
                                    ],
                                    className="density-control",
                                ),
                                html.Div(
                                    [
                                        html.Div(
                                            [
                                                html.Div(
                                                    [
                                                        html.Strong("Incidencia delictiva"),
                                                        html.Span(
                                                            "ⓘ",
                                                            title=(
                                                                "Tasa municipal anual de delitos registrados por "
                                                                "100,000 habitantes, asignada como contexto a las "
                                                                "secciones. No mide directamente la seguridad de "
                                                                "cada sección."
                                                            ),
                                                            className="density-help",
                                                        ),
                                                    ],
                                                    className="density-title",
                                                ),
                                                html.Span(
                                                    "Porcentaje de secciones con menor incidencia registrada",
                                                    className="density-subtitle",
                                                ),
                                            ]
                                        ),
                                        html.Strong(
                                            "100%", id="security-value", className="density-value"
                                        ),
                                        dcc.Slider(
                                            id="security-filter",
                                            min=1,
                                            max=100,
                                            step=1,
                                            value=100,
                                            marks={10: "10%", 25: "25%", 50: "50%", 66: "66%", 100: "100%"},
                                            updatemode="drag",
                                            tooltip={"placement": "bottom"},
                                            className="density-slider security-slider",
                                        ),
                                        html.Div(
                                            [
                                                html.Button(
                                                    f"{value}%",
                                                    id=f"security-quick-{value}",
                                                    n_clicks=0,
                                                    className="button button-small button-quiet",
                                                )
                                                for value in (10, 25, 50, 66, 100)
                                            ],
                                            className="percent-shortcuts",
                                        ),
                                        html.P(
                                            "Filtro desactivado: 100% del universo",
                                            id="security-description",
                                            className="density-description",
                                        ),
                                        html.Strong(
                                            "70,751 secciones visibles",
                                            id="security-visible",
                                            className="density-visible",
                                        ),
                                        html.Span(
                                            "Se incluyen secciones sin indicador municipal.",
                                            id="security-threshold",
                                            className="density-threshold",
                                        ),
                                    ],
                                    className="density-control",
                                ),
                                html.Div(
                                    [
                                        html.Strong("0 secciones seleccionadas", id="export-count"),
                                        html.A(
                                            "Descargar secciones seleccionadas (.csv)",
                                            id="download-selection",
                                            href=(
                                                "/download/sections.csv?"
                                                + urlencode(
                                                    {
                                                        "profiles": ",".join(ALL_PROFILES),
                                                        "density": 100,
                                                        "security": 100,
                                                    }
                                                )
                                            ),
                                            className="button export-button",
                                        ),
                                    ],
                                    className="export-control",
                                ),
                            ],
                            className="filter-panel panel",
                        ),
                        html.Section(
                            [
                                html.Div(
                                    [
                                        html.Div(
                                            [
                                                html.Span("Mapa seccional", className="eyebrow"),
                                                html.H2("México · 70,751 secciones"),
                                            ],
                                        ),
                                        html.Div(
                                            [
                                                html.Span(
                                                    "Vista agregada",
                                                    id="mode-badge",
                                                    className="mode-badge",
                                                ),
                                                html.Button(
                                                    "Limpiar selección",
                                                    id="clear-selection",
                                                    n_clicks=0,
                                                    className="button button-clear hidden",
                                                ),
                                            ],
                                            className="map-actions",
                                        ),
                                    ],
                                    className="map-header",
                                ),
                                dl.Map(
                                    [
                                        dl.GeoJSON(
                                            id="section-geo",
                                            url=f"{ASSET_PREFIX}/sections_overview.fgb",
                                            format="flatgeobuf",
                                            formatOptions={
                                                "rect": {
                                                    "minX": -118.8,
                                                    "minY": 14.2,
                                                    "maxX": -86.4,
                                                    "maxY": 33.4,
                                                }
                                            },
                                            style=MAP_JS("sectionStyle"),
                                            filter=MAP_JS("profileFilter"),
                                            hoverStyle={
                                                "weight": 1.6,
                                                "color": "#233E4D",
                                                "fillOpacity": 0.96,
                                            },
                                            hideout={
                                                "activeProfiles": ALL_PROFILES,
                                                "densityEnabled": False,
                                                "densityLimit": density_selection_count(100),
                                                "securityEnabled": False,
                                                "securityLimit": security_target_count(100),
                                                "selected": None,
                                                "colors": PROFILE_COLORS,
                                            },
                                            zoomToBounds=False,
                                        ),
                                        dl.GeoJSON(
                                            url=f"{ASSET_PREFIX}/state_boundaries.geojson",
                                            interactive=False,
                                            style={
                                                "color": "#4C4947",
                                                "weight": 1.1,
                                                "opacity": 0.65,
                                                "fillOpacity": 0,
                                            },
                                        ),
                                        dl.ZoomControl(position="topright"),
                                        dl.EasyButton(
                                            id="reset-map",
                                            icon="⌂",
                                            title="Volver a la vista nacional",
                                            position="topright",
                                        ),
                                        dl.ScaleControl(position="bottomleft", imperial=False),
                                    ],
                                    id="mexico-map",
                                    center=[23.6, -102.5],
                                    zoom=4,
                                    bounds=MEXICO_BOUNDS,
                                    boundsOptions={"padding": [12, 12]},
                                    minZoom=4,
                                    maxZoom=16,
                                    zoomControl=False,
                                    preferCanvas=True,
                                    trackViewport=True,
                                    attributionControl=True,
                                    style={"height": "100%", "width": "100%"},
                                    className="mexico-map",
                                ),
                                html.Div(
                                    [
                                        html.Span("Cartografía INE · snapshot 09/05/2024"),
                                        html.Span(
                                            "Referencia territorial; no certificada para 2027"
                                        ),
                                    ],
                                    className="map-footnote",
                                ),
                            ],
                            className="map-panel panel",
                        ),
                        html.Aside(html.Div(id="context-panel"), className="context-panel panel"),
                    ],
                    className="top-grid",
                ),
                html.Section(
                    [
                        _chart_card(
                            "Distribución por edad",
                            "Electorado identificado en los conteos censales INE 2024",
                            "age-chart",
                        ),
                        _chart_card(
                            "Distribución por sexo",
                            "Electorado identificado; no equivale a población residente",
                            "sex-chart",
                        ),
                        _chart_card(
                            "Contexto sociodemográfico",
                            "Población residente o vivienda según ECEG 2020",
                            "socio-chart",
                            dcc.Dropdown(
                                id="socio-metric",
                                options=[
                                    {"label": item["label"], "value": key}
                                    for key, item in SOCIO_METRICS.items()
                                ],
                                value="internet",
                                clearable=False,
                                searchable=False,
                                className="metric-select",
                            ),
                        ),
                        _chart_card(
                            "Trayectoria de participación",
                            "Observaciones directas por código seccional; 2027 enlaza con la intermedia 2021",
                            "timeline-chart",
                            wide=True,
                            note=(
                                "La serie observada y la proyección usan referencias comparables, "
                                "pero 2027 es una proyección de trabajo y no un resultado observado."
                            ),
                        ),
                    ],
                    className="charts-grid",
                ),
                html.Footer(
                    html.Span(id="data-caption"),
                    className="app-footer",
                ),
            ],
            className="app-main",
        ),
    ],
    className="app-shell",
)


@app.callback(
    Output("profile-filter", "value"),
    Output("density-filter", "value"),
    Output("security-filter", "value"),
    Input("select-all", "n_clicks"),
    Input("clear-profiles", "n_clicks"),
    Input("restore-profiles", "n_clicks"),
    *[Input(f"density-quick-{value}", "n_clicks") for value in (10, 25, 50, 66, 100)],
    *[Input(f"security-quick-{value}", "n_clicks") for value in (10, 25, 50, 66, 100)],
    prevent_initial_call=True,
)
def update_profile_buttons(*clicks: int) -> tuple[list[str] | Any, int | Any, int | Any]:
    del clicks
    trigger = str(ctx.triggered_id)
    if ctx.triggered_id == "clear-profiles":
        return [], no_update, no_update
    if ctx.triggered_id == "restore-profiles":
        return ALL_PROFILES, 100, 100
    if trigger.startswith("density-quick-"):
        return no_update, int(trigger.rsplit("-", 1)[1]), no_update
    if trigger.startswith("security-quick-"):
        return no_update, no_update, int(trigger.rsplit("-", 1)[1])
    return ALL_PROFILES, no_update, no_update


@app.callback(
    Output("selected-section", "data"),
    Output("section-geo", "hideout"),
    Input("profile-filter", "value"),
    Input("density-filter", "value"),
    Input("security-filter", "value"),
    Input("section-geo", "clickData"),
    Input("clear-selection", "n_clicks"),
    State("selected-section", "data"),
)
def update_selection(
    active_profiles: list[str] | None,
    density_percent: int | None,
    security_percent: int | None,
    click_data: dict[str, Any] | None,
    clear_clicks: int,
    current_selection: str | None,
) -> tuple[str | None, dict[str, Any]]:
    del clear_clicks
    active = active_profiles or []
    percent = normalize_density_percent(density_percent)
    safety_percent = normalize_security_percent(security_percent)
    selected = resolve_selection(
        ctx.triggered_id, active, click_data, current_selection, percent, safety_percent
    )
    return selected, {
        "activeProfiles": active,
        "densityEnabled": percent < 100,
        "densityLimit": density_selection_count(percent),
        "securityEnabled": safety_percent < 100,
        "securityLimit": security_target_count(safety_percent),
        "selected": selected,
        "colors": PROFILE_COLORS,
    }


@app.callback(
    Output("section-geo", "url"),
    Output("section-geo", "formatOptions"),
    Input("mexico-map", "zoom"),
    Input("mexico-map", "bounds"),
)
def update_geometry_source(zoom: float | None, bounds: Any) -> tuple[str, dict[str, Any]]:
    url = (
        f"{ASSET_PREFIX}/sections_detail.fgb"
        if (zoom or 4) >= 7
        else f"{ASSET_PREFIX}/sections_overview.fgb"
    )
    rect = {"minX": -118.8, "minY": 14.2, "maxX": -86.4, "maxY": 33.4}
    if isinstance(bounds, (list, tuple)) and len(bounds) == 2:
        try:
            south, west = bounds[0]
            north, east = bounds[1]
            lon_pad = max((east - west) * 0.08, 0.03)
            lat_pad = max((north - south) * 0.08, 0.03)
            rect = {
                "minX": max(-119.5, west - lon_pad),
                "minY": max(13.5, south - lat_pad),
                "maxX": min(-85.5, east + lon_pad),
                "maxY": min(34.0, north + lat_pad),
            }
        except (TypeError, ValueError):
            pass
    return url, {"rect": rect}


@app.callback(
    Output("mexico-map", "viewport"), Input("reset-map", "n_clicks"), prevent_initial_call=True
)
def reset_map_view(n_clicks: int) -> dict[str, Any] | Any:
    if not n_clicks:
        return no_update
    return {"bounds": MEXICO_BOUNDS, "transition": "fitBounds", "options": {"padding": [12, 12]}}


@app.callback(
    Output("context-panel", "children"),
    Output("age-chart", "figure"),
    Output("sex-chart", "figure"),
    Output("socio-chart", "figure"),
    Output("timeline-chart", "figure"),
    Output("mode-badge", "children"),
    Output("clear-selection", "className"),
    Output("data-caption", "children"),
    Output("density-value", "children"),
    Output("density-description", "children"),
    Output("density-visible", "children"),
    Output("density-threshold", "children"),
    Output("security-value", "children"),
    Output("security-description", "children"),
    Output("security-visible", "children"),
    Output("security-threshold", "children"),
    Output("export-count", "children"),
    Input("profile-filter", "value"),
    Input("selected-section", "data"),
    Input("socio-metric", "value"),
    Input("density-filter", "value"),
    Input("security-filter", "value"),
)
def update_dashboard(
    active_profiles: list[str] | None,
    selected_section: str | None,
    metric_id: str,
    density_percent: int | None = 100,
    security_percent: int | None = 100,
) -> tuple[Any, ...]:
    payload = build_payload(
        active_profiles or [], selected_section, metric_id, density_percent, security_percent
    )
    context = _section_panel(payload) if payload["mode"] == "section" else _aggregate_panel(payload)
    age = distribution_figure(payload["age"], WINE)
    sex = distribution_figure(payload["sex"], ORANGE)
    socio = socio_figure(payload["socio"])
    timeline = (
        timeline_figure(payload)
        if not payload["empty"]
        else empty_figure("No hay secciones en la selección")
    )
    mode = "Sección seleccionada" if payload["mode"] == "section" else "Vista agregada"
    clear_class = (
        "button button-clear" if payload["mode"] == "section" else "button button-clear hidden"
    )
    coverage = payload["socio"]["coverage"]
    caption = f"Indicador ECEG: {payload['socio']['period']} · cobertura {coverage['available']:,}/{coverage['total']:,} secciones del conjunto activo"
    density = payload["density"]
    percent = density["percent"]
    density_value = f"{percent}%"
    density_description = (
        f"Mostrando el {percent}% de las secciones con mayor densidad de viviendas"
    )
    density_visible = f"{density['visible_sections']:,} secciones visibles"
    if percent == 100:
        threshold = "Filtro desactivado; se incluyen secciones sin densidad válida."
    else:
        threshold = (
            f"Umbral mínimo: {density['threshold']:,.1f} viviendas/km² · "
            f"{density['national_selected']:,} de {density['valid_universe']:,} válidas"
        )
    security = payload["security"]
    security_value = f"{security['percent']}%"
    if security["percent"] == 100:
        security_description = "Filtro desactivado: 100% del universo"
        security_threshold_text = (
            f"Se incluyen {security['missing_sections']:,} secciones sin indicador municipal."
        )
    else:
        effective = security["effective_sections"] / security["valid_universe"]
        security_description = (
            f"Solicitud {security['percent']}% · efectivo {effective:.1%} por empates municipales"
        )
        security_threshold_text = (
            f"Umbral máximo: {security['threshold']:,.1f} delitos por 100 mil · "
            f"{security['effective_sections']:,} secciones con indicador"
        )
    security_visible = f"{security['visible_sections']:,} secciones visibles"
    export_count = f"{security['visible_sections']:,} secciones seleccionadas"
    return (
        context,
        age,
        sex,
        socio,
        timeline,
        mode,
        clear_class,
        caption,
        density_value,
        density_description,
        density_visible,
        threshold,
        security_value,
        security_description,
        security_visible,
        security_threshold_text,
        export_count,
    )


@app.callback(
    Output("download-selection", "href"),
    Input("profile-filter", "value"),
    Input("density-filter", "value"),
    Input("security-filter", "value"),
)
def update_download_href(
    active_profiles: list[str] | None,
    density_percent: int | None,
    security_percent: int | None,
) -> str:
    query = urlencode(
        {
            "profiles": ",".join(active_profiles or []),
            "density": normalize_density_percent(density_percent),
            "security": normalize_security_percent(security_percent),
        }
    )
    return f"/download/sections.csv?{query}"


if __name__ == "__main__":
    port = int(os.environ.get("DASHBOARD_PORT", "8050"))
    app.run(host="127.0.0.1", port=port, debug=False)
