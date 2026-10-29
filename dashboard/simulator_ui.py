"""Presentación y callbacks aislados del simulador de intervenciones."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode

import dash_leaflet as dl
import pandas as pd
from dash import Dash, Input, Output, State, ctx, dash_table, dcc, html, no_update
from dash_extensions.javascript import Namespace

from dashboard.data_layer import (
    ALL_PROFILES,
    PROFILE_LABELS,
    density_selection_count,
    normalize_density_percent,
    normalize_security_percent,
    normalize_veb_period,
    normalize_veb_threshold,
    security_target_count,
    veb_filter_enabled,
    veb_max,
)
from dashboard.map_geometry import geometry_spec
from dashboard.simulator import (
    INTERVENTIONS,
    PRIORITY_COLORS,
    PRIORITY_ORDER,
    coverage_count,
    crime_column,
    eligible_sections,
    priority_counts,
    security_context,
    simulate,
)

MAP_JS = Namespace("dashboardMap")
INTERVENTION_SHORT_LABELS = {
    1: "Secreto del voto",
    2: "Norma social",
    3: "SMS / WhatsApp",
    4: "Plan de voto",
    5: "Información de casilla",
    6: "Felicitación municipal",
}


def _fmt(value: Any, suffix: str = "%") -> str:
    if value is None or pd.isna(value):
        return "No disponible"
    return f"{float(value):.2f}{suffix}"


def _number(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _profile_options() -> list[dict[str, str]]:
    return [
        {
            "value": profile,
            "label": f"{profile.replace('EI_', 'EI-')} · {PROFILE_LABELS[profile]}",
        }
        for profile in ALL_PROFILES
    ]


def _priority_visual_spec(counts: dict[str, int]) -> dict[str, Any]:
    """Una sola fuente para segmentos, gradiente y marcas del deslizador."""
    total = sum(counts.values())
    widths = {
        priority: (100.0 * counts[priority] / total) if total else 0.0
        for priority in PRIORITY_ORDER
    }
    high_end = widths["Alta"]
    medium_end = high_end + widths["Media"]
    ranges = {
        "Alta": (0.0, high_end),
        "Media": (high_end, medium_end),
        "Baja": (medium_end, 100.0 if total else 0.0),
    }
    segments = [
        html.Span(
            f"{priority} · {counts[priority]:,}",
            className=f"sim-segment sim-segment-{priority.lower()}",
            style={
                "width": f"{widths[priority]:.6f}%",
                "backgroundColor": PRIORITY_COLORS[priority],
            },
            title=(
                f"Prioridad {priority.lower()}: {counts[priority]:,} secciones elegibles "
                f"({ranges[priority][0]:.2f}%–{ranges[priority][1]:.2f}%)"
            ),
        )
        for priority in PRIORITY_ORDER
        if counts[priority]
    ]
    marks: dict[float, str] = {0.0: "0%", 100.0: "100%"}
    for boundary in (high_end, medium_end):
        if 0.01 < boundary < 99.99:
            rounded = round(boundary, 2)
            marks[rounded] = f"{boundary:.2f}%"
    marks = dict(sorted(marks.items()))
    boundary_labels = []
    for position, label in marks.items():
        tone = "endpoint" if position in {0.0, 100.0} else "transition"
        edge = " start" if position == 0.0 else (" end" if position == 100.0 else "")
        boundary_labels.append(
            html.Span(
                label,
                className=f"sim-boundary-label sim-boundary-{tone}{edge}",
                style={"left": f"{position:.6f}%"},
            )
        )
    gradient = (
        "linear-gradient(90deg, "
        f"{PRIORITY_COLORS['Alta']} 0%, {PRIORITY_COLORS['Alta']} {high_end:.6f}%, "
        f"{PRIORITY_COLORS['Media']} {high_end:.6f}%, "
        f"{PRIORITY_COLORS['Media']} {medium_end:.6f}%, "
        f"{PRIORITY_COLORS['Baja']} {medium_end:.6f}%, "
        f"{PRIORITY_COLORS['Baja']} 100%)"
    )
    return {
        "segments": segments,
        "marks": marks,
        "slider_marks": {position: "" for position in marks},
        "boundary_labels": boundary_labels,
        "track_style": {"--priority-gradient": gradient},
        "ranges": ranges,
    }


def _selected_summary(simulation: dict[str, Any]) -> list[Any]:
    counts = simulation["selected_priority_counts"]
    items = [
        ("Seleccionadas", simulation["selected_count"], "total"),
        ("Alta", counts["Alta"], "high"),
        ("Media", counts["Media"], "medium"),
        ("Baja", counts["Baja"], "low"),
    ]
    return [
        html.Div(
            [html.Span(label), html.Strong(f"{value:,}")],
            className=f"sim-selected-stat sim-selected-stat-{tone}",
        )
        for label, value, tone in items
    ]


def _assignment_summary(simulation: dict[str, Any]) -> list[Any]:
    return [
        html.Div(
            [
                html.Span(
                    f"{item['id']}. {INTERVENTION_SHORT_LABELS[item['id']]}",
                    title=item["name"],
                ),
                html.Strong(f"{simulation['assignment_counts'][item['name']]:,}"),
            ],
            className="sim-assignment-item",
        )
        for item in INTERVENTIONS
    ]


def _legend_item(label: str, class_name: str) -> html.Div:
    return html.Div(
        [html.Span(className=f"sim-legend-swatch {class_name}"), html.Span(label)],
        className="sim-legend-item",
    )


def _map_legend() -> list[Any]:
    return [
        _legend_item("Prioridad alta", "sim-legend-high"),
        _legend_item("Prioridad media", "sim-legend-medium"),
        _legend_item("Prioridad baja", "sim-legend-low"),
        _legend_item("Sección no seleccionada", "sim-legend-empty"),
        _legend_item(
            "Seleccionada en municipio con registros de crímenes electorales",
            "sim-legend-crime",
        ),
    ]


def _result_card(label: str, component_id: str, note: str) -> html.Div:
    return html.Div(
        [
            html.Span(label, className="metric-label"),
            html.Strong("No disponible", id=component_id, className="metric-value"),
            html.Span(note, className="metric-note"),
        ],
        className="metric-card sim-result-card",
    )


def _scenario_result_card(
    label: str,
    scenario: str,
    note: str,
    *,
    central: bool = False,
) -> html.Div:
    central_class = " sim-scenario-card-central" if central else ""
    return html.Div(
        [
            html.Span(label, className="metric-label"),
            html.Div(
                [
                    html.Div(
                        [
                            html.Span("Incremento esperado"),
                            html.Strong(
                                "No disponible",
                                id=f"sim-{scenario}-increment",
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            html.Span("Participación resultante"),
                            html.Strong(
                                "No disponible",
                                id=f"sim-{scenario}-mean",
                            ),
                        ]
                    ),
                ],
                className="sim-scenario-values",
            ),
            html.Span(note, className="metric-note"),
        ],
        className=f"metric-card sim-scenario-card{central_class}",
    )


def _table(table_id: str) -> dash_table.DataTable:
    return dash_table.DataTable(
        id=table_id,
        columns=[
            {"name": ["", "Grupo"], "id": "grupo"},
            {"name": ["", "Secciones"], "id": "secciones_asignadas", "type": "numeric"},
            {"name": ["", "Base"], "id": "participacion_sin"},
            {"name": ["Pesimista", "Participación"], "id": "participacion_conservative"},
            {"name": ["Pesimista", "Incremento"], "id": "incremento_conservative_pp"},
            {"name": ["Normal", "Participación"], "id": "participacion_central"},
            {"name": ["Normal", "Incremento"], "id": "incremento_central_pp"},
            {"name": ["Optimista", "Participación"], "id": "participacion_optimistic"},
            {"name": ["Optimista", "Incremento"], "id": "incremento_optimistic_pp"},
            {"name": ["", "Sin proyección"], "id": "sin_proyeccion_valida", "type": "numeric"},
        ],
        data=[],
        merge_duplicate_headers=True,
        sort_action="native",
        page_action="none",
        style_table={"overflowX": "auto"},
        style_cell={
            "fontFamily": "Inter, system-ui, sans-serif",
            "fontSize": "11px",
            "padding": "9px",
            "textAlign": "left",
            "whiteSpace": "normal",
            "height": "auto",
        },
        style_header={"fontWeight": 700, "backgroundColor": "#f7f4f1"},
        style_data_conditional=[
            {
                "if": {"filter_query": '{grupo} = "Total"'},
                "fontWeight": 700,
                "backgroundColor": "#f7f0f2",
            }
        ],
    )


def layout(asset_prefix: str, mexico_bounds: list[list[float]]) -> html.Main:
    veb_maximum = veb_max("cumulative")
    return html.Main(
        [
            dcc.Store(id="sim-eligible-count", data=0),
            html.Section(
                [
                    html.Span("Planeación hipotética", className="eyebrow"),
                    html.H1("Simulador de intervenciones"),
                    html.P(
                        "Prioriza secciones, asigna una política reproducible y compara la proyección original con tres escenarios hipotéticos."
                    ),
                ],
                className="sim-hero",
            ),
            html.Section(
                [
                    html.Div(
                        [
                            html.H2("Configuración"),
                            html.Label("Perfiles incluidos", className="sim-label"),
                            dcc.Checklist(
                                id="sim-profile-filter",
                                options=_profile_options(),
                                value=ALL_PROFILES,
                                className="sim-profile-filter",
                            ),
                            dcc.Checklist(
                                id="sim-include-ei",
                                options=[
                                    {
                                        "label": "Incluir secciones con evidencia insuficiente",
                                        "value": "include",
                                    }
                                ],
                                value=["include"],
                                className="sim-check",
                            ),
                            html.Small(
                                "EI-A/B y EI-C/D conservan su etiqueta original; sólo se ordenan provisionalmente como prioridad media.",
                                className="sim-help",
                            ),
                            html.Label("Secciones con mayor densidad", className="sim-label"),
                            dcc.Slider(
                                id="sim-density-filter",
                                min=1,
                                max=100,
                                step=1,
                                value=100,
                                marks={1: "1%", 25: "25%", 50: "50%", 75: "75%", 100: "100%"},
                                updatemode="mouseup",
                                className="density-slider",
                            ),
                            html.Label("Secciones con menor incidencia municipal", className="sim-label"),
                            dcc.Slider(
                                id="sim-security-filter",
                                min=1,
                                max=100,
                                step=1,
                                value=100,
                                marks={1: "1%", 25: "25%", 50: "50%", 75: "75%", 100: "100%"},
                                updatemode="mouseup",
                                className="density-slider security-slider",
                            ),
                            html.Label("Periodo de crímenes electorales", className="sim-label"),
                            dcc.Dropdown(
                                id="sim-veb-period",
                                options=[
                                    {"label": "Acumulado histórico", "value": "cumulative"},
                                    {"label": "Últimos 24 meses", "value": "24m"},
                                ],
                                value="cumulative",
                                clearable=False,
                            ),
                            html.Label("Máximo de registros municipales (≤)", className="sim-label"),
                            dcc.Slider(
                                id="sim-veb-filter",
                                min=0,
                                max=veb_maximum,
                                step=1,
                                value=veb_maximum,
                                marks={0: "0", veb_maximum: str(veb_maximum)},
                                updatemode="mouseup",
                                className="density-slider security-slider",
                            ),
                            html.Small(
                                "Cero registros y ausencia de información municipal se mantienen diferenciados.",
                                className="sim-help",
                            ),
                        ],
                        className="panel sim-config-panel",
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Span("Cobertura", className="eyebrow"),
                                            html.H2("Orden estricto por prioridad"),
                                            html.P(
                                                "Primero alta, después media y finalmente baja. Dentro de cada nivel, el orden depende de la semilla."
                                            ),
                                        ]
                                    ),
                                    html.Strong("0 elegibles", id="sim-eligible-label", className="mode-badge"),
                                ],
                                className="sim-section-header",
                            ),
                            html.Div(id="sim-priority-segments", className="sim-segmented-bar"),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Div(
                                                [
                                                    html.Span(
                                                        "Cobertura seleccionada",
                                                        className="sim-coverage-caption",
                                                    ),
                                                    html.Strong(
                                                        "25.00%",
                                                        id="sim-coverage-display",
                                                        className="sim-coverage-display",
                                                    ),
                                                ],
                                                className="sim-coverage-readout",
                                            ),
                                            dcc.Slider(
                                                id="sim-coverage-percent",
                                                min=0,
                                                max=100,
                                                step=0.01,
                                                value=25,
                                                marks={0: "0%", 100: "100%"},
                                                updatemode="mouseup",
                                                className="sim-coverage-slider",
                                            ),
                                            html.Div(
                                                id="sim-coverage-boundaries",
                                                className="sim-coverage-boundaries",
                                            ),
                                        ],
                                        id="sim-coverage-track",
                                        className="sim-coverage-control",
                                    )
                                ],
                                className="sim-slider-section",
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Label("Número de secciones", className="sim-label"),
                                            dcc.Input(
                                                id="sim-coverage-count",
                                                type="number",
                                                min=0,
                                                max=0,
                                                step=1,
                                                value=0,
                                            ),
                                        ],
                                        className="sim-number-control",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Semilla aleatoria", className="sim-label"),
                                            dcc.Input(id="sim-seed", type="number", step=1, value=42),
                                        ],
                                        className="sim-number-control",
                                    ),
                                ],
                                className="sim-parameter-grid",
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Strong(
                                                "Resumen de cobertura",
                                                className="sim-summary-title",
                                            ),
                                            html.Div(
                                                id="sim-selected-summary",
                                                className="sim-selected-summary",
                                            ),
                                        ],
                                        className="sim-summary-block",
                                    ),
                                    html.Div(
                                        [
                                            html.Strong(
                                                "Asignación por política",
                                                className="sim-summary-title",
                                            ),
                                            html.Div(
                                                id="sim-assignment-summary",
                                                className="sim-assignment-summary",
                                            ),
                                        ],
                                        className="sim-summary-block",
                                    ),
                                ],
                                className="sim-summary-grid",
                            ),
                            html.P(id="sim-excluded-label", className="sim-help"),
                        ],
                        className="panel sim-coverage-panel",
                    ),
                ],
                className="sim-config-grid",
            ),
            html.Section(
                [
                    html.Div(
                        [
                            html.Span("Resultados de participación", className="eyebrow"),
                            html.H2("Comparación sobre las mismas secciones tratadas"),
                        ],
                        className="sim-results-heading",
                    ),
                    html.Div(
                        [
                            _result_card(
                                "Participación proyectada sin intervención",
                                "sim-base-mean",
                                "Referencia principal: media simple de las secciones tratadas válidas.",
                            ),
                            _result_card(
                                "Participación del universo filtrado",
                                "sim-reference",
                                "Referencia secundaria descriptiva; no es un grupo de control.",
                            ),
                        ],
                        className="sim-reference-grid",
                    ),
                    html.Div(
                        [
                            _scenario_result_card(
                                "Escenario pesimista",
                                "conservative",
                                "Supuesto de eficacia mínima.",
                            ),
                            _scenario_result_card(
                                "Escenario normal",
                                "central",
                                "Referencia central de eficacia.",
                                central=True,
                            ),
                            _scenario_result_card(
                                "Escenario optimista",
                                "optimistic",
                                "Supuesto de eficacia máxima.",
                            ),
                        ],
                        className="sim-scenario-result-grid",
                    ),
                    html.P(id="sim-projection-note", className="sim-help"),
                ],
                className="panel sim-results-panel",
            ),
            html.Section(
                [
                    html.Div(
                        html.Div(
                            [
                                html.Span("Mapa territorial", className="eyebrow"),
                                html.H2("Prioridad, selección y contexto municipal"),
                            ]
                        ),
                        className="sim-map-header",
                    ),
                    dl.Map(
                        [
                            dl.GeoJSON(
                                id="sim-section-geo",
                                url=f"{asset_prefix}/sections_overview.fgb",
                                format="flatgeobuf",
                                formatOptions={"rect": {
                                    "minX": -118.8,
                                    "minY": 14.2,
                                    "maxX": -86.4,
                                    "maxY": 33.4,
                                }},
                                style=MAP_JS("simulatorSectionStyle"),
                                filter=MAP_JS("simulatorFilter"),
                                onEachFeature=MAP_JS("simulatorOnEachFeature"),
                                hideout={},
                                hoverStyle={"weight": 1.6, "color": "#233E4D"},
                                zoomToBounds=False,
                            ),
                            dl.GeoJSON(
                                url=f"{asset_prefix}/state_boundaries.geojson",
                                interactive=False,
                                style={"color": "#4C4947", "weight": 1.1, "opacity": 0.65, "fillOpacity": 0},
                            ),
                            dl.ZoomControl(position="topright"),
                            dl.ScaleControl(position="bottomleft", imperial=False),
                        ],
                        id="sim-map",
                        center=[23.6, -102.5],
                        zoom=4,
                        bounds=mexico_bounds,
                        boundsOptions={"padding": [12, 12]},
                        minZoom=4,
                        maxZoom=16,
                        zoomControl=False,
                        preferCanvas=True,
                        trackViewport=True,
                        style={"width": "100%"},
                        className="mexico-map sim-map",
                    ),
                    html.Div(
                        _map_legend(),
                        id="sim-map-legend",
                        className="sim-map-legend",
                    ),
                    html.P(
                        "Vista nacional y detalle con polígonos seccionales.",
                        className="sim-help sim-map-detail-note",
                    ),
                ],
                className="panel sim-map-panel",
            ),
            html.Section(
                [
                    html.Div(
                        [
                            html.Div(
                                [html.H2("Resultados por intervención"), _table("sim-intervention-table")],
                                className="panel sim-table-panel",
                            ),
                            html.Div(
                                [html.H2("Resultados por prioridad"), _table("sim-priority-table")],
                                className="panel sim-table-panel",
                            ),
                        ],
                        className="sim-table-grid",
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.H2("Contexto de seguridad de las intervenciones"),
                                    html.Div(id="sim-security-context", className="sim-security-metrics"),
                                    html.P(
                                        "Los registros municipales aportan contexto para planeación operativa; no miden peligro individual en una sección.",
                                        className="sim-help",
                                    ),
                                ],
                                className="panel sim-security-panel",
                            ),
                            html.Div(
                                [
                                    html.H2("Descargas reproducibles"),
                                    html.A(
                                        "Descargar secciones (.csv)",
                                        id="sim-download-sections-button",
                                        href="/download/simulation-sections.csv",
                                        className="button export-button",
                                    ),
                                    html.A(
                                        "Descargar agregados (.csv)",
                                        id="sim-download-aggregate-button",
                                        href="/download/simulation-aggregate.csv",
                                        className="button",
                                    ),
                                ],
                                className="panel sim-download-panel",
                            ),
                        ],
                        className="sim-bottom-grid",
                    ),
                ],
                className="sim-detail-section",
            ),
            html.Section(
                [
                    html.Strong("Nota metodológica"),
                    html.P(
                        "Simulación hipotética, no estimación causal del modelo. Los efectos externos se aplican una sola vez, en puntos porcentuales a nivel sección, bajo el supuesto de alcance del 100% de la población objetivo. Las secciones no tratadas no son un grupo de control. Los perfiles y las proyecciones originales no se recalculan."
                    ),
                ],
                className="sim-method-note",
            ),
        ],
        id="simulator-app-content",
        className="sim-main",
    )


def _filter_args(
    profiles: list[str] | None,
    include_ei: list[str] | None,
    density: Any,
    security: Any,
    period: Any,
    threshold: Any,
) -> dict[str, Any]:
    normalized_period = normalize_veb_period(period)
    return {
        "active_profiles": profiles or [],
        "include_insufficient": "include" in (include_ei or []),
        "density_percent": normalize_density_percent(density),
        "security_percent": normalize_security_percent(security),
        "veb_period": normalized_period,
        "veb_threshold": normalize_veb_threshold(normalized_period, threshold),
    }


def _formatted_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        item = row.copy()
        item["participacion_sin"] = _fmt(item["participacion_sin"])
        for scenario in ("conservative", "central", "optimistic"):
            item[f"participacion_{scenario}"] = _fmt(
                item[f"participacion_{scenario}"]
            )
            item[f"incremento_{scenario}_pp"] = _fmt(
                item[f"incremento_{scenario}_pp"],
                " pp",
            )
        result.append(item)
    return result


def _export_frame(
    profiles: list[str] | None,
    include_ei: list[str] | None,
    density: Any,
    security: Any,
    period: Any,
    threshold: Any,
    requested_count: Any,
    seed: Any,
) -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any]]:
    args = _filter_args(profiles, include_ei, density, security, period, threshold)
    simulation = simulate(eligible_sections(**args), requested_count, seed=seed)
    export = _export_chunk(simulation["frame"], crime_column(period))
    export["parametros_filtros_json"] = _export_parameters(args, simulation, seed)
    return export, simulation, args


def _export_chunk(frame: pd.DataFrame, crime: str) -> pd.DataFrame:
    """Construye sólo las columnas contractuales de un lote del simulador."""
    export = pd.DataFrame(
        {
            "clave_seccion": frame["clave_seccion"],
            "clave_entidad": frame["clave_entidad"],
            "nombre_entidad": frame["nombre_entidad"],
            "clave_municipio": frame["clave_municipio"],
            "nombre_municipio": frame["nombre_municipio"],
            "perfil_original": frame["perfil_visual_id"],
            "prioridad_operativa": frame["prioridad_operativa"],
            "evidencia_insuficiente": frame["evidencia_insuficiente"],
            "seleccionada": frame["seleccionada"],
            "orden_seleccion": frame["orden_seleccion"],
            "intervencion": frame["intervencion"],
            "semilla": frame["semilla"],
            # Columnas históricas: siguen representando el escenario normal/central.
            "escenario_eficacia": frame["escenario_eficacia"],
            "efecto_aplicado_pp": frame["efecto_pp"],
            "participacion_sin_intervencion_pct": frame["participacion_base_pct"],
            "participacion_con_intervencion_pct": frame[
                "participacion_con_intervencion_pct"
            ],
            "variacion_proyectada_pp": frame["variacion_proyectada_pp"],
            "efecto_pesimista_pp": frame["efecto_conservative_pp"],
            "participacion_pesimista_pct": frame["participacion_conservative_pct"],
            "variacion_pesimista_pp": frame["variacion_conservative_pp"],
            "efecto_normal_pp": frame["efecto_central_pp"],
            "participacion_normal_pct": frame["participacion_central_pct"],
            "variacion_normal_pp": frame["variacion_central_pp"],
            "efecto_optimista_pp": frame["efecto_optimistic_pp"],
            "participacion_optimista_pct": frame["participacion_optimistic_pct"],
            "variacion_optimista_pp": frame["variacion_optimistic_pp"],
            "registros_crimenes_electorales_municipio": frame[crime],
            "informacion_municipal_faltante": frame[crime].isna(),
        }
    )
    return export


def _export_parameters(
    args: dict[str, Any], simulation: dict[str, Any], seed: Any
) -> str:
    frame = simulation["frame"]
    return json.dumps(
        {
            **args,
            "cobertura_secciones": simulation["selected_count"],
            "semilla": (
                int(simulation["frame"]["semilla"].iloc[0])
                if len(frame)
                else _number(seed)
            ),
            "escenario": "central",
            "escenarios_mostrados": ["pesimista", "normal", "optimista"],
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def simulation_csv_chunks(
    profiles: list[str] | None,
    include_ei: list[str] | None,
    density: Any,
    security: Any,
    period: Any,
    threshold: Any,
    requested_count: Any,
    seed: Any,
    *,
    chunk_size: int = 2_000,
) -> tuple[Any, int]:
    """Devuelve un CSV reproducible sin materializar una cadena nacional completa."""
    args = _filter_args(profiles, include_ei, density, security, period, threshold)
    simulation = simulate(eligible_sections(**args), requested_count, seed=seed)
    frame = simulation["frame"]
    crime = crime_column(period)
    parameters = _export_parameters(args, simulation, seed)

    def chunks() -> Any:
        yield "\ufeff"
        for start in range(0, len(frame), chunk_size):
            export = _export_chunk(frame.iloc[start : start + chunk_size], crime)
            export["parametros_filtros_json"] = parameters
            yield export.to_csv(index=False, header=start == 0)

    return chunks(), simulation["selected_count"]


def simulation_aggregate_csv(
    profiles: list[str] | None,
    include_ei: list[str] | None,
    density: Any,
    security: Any,
    period: Any,
    threshold: Any,
    requested_count: Any,
    seed: Any,
) -> str:
    """Genera el resumen pequeño por intervención y prioridad."""
    args = _filter_args(profiles, include_ei, density, security, period, threshold)
    simulation = simulate(eligible_sections(**args), requested_count, seed=seed)
    by_policy = pd.DataFrame(simulation["intervention_rows"]).assign(tipo="intervencion")
    by_priority = pd.DataFrame(simulation["priority_rows"]).assign(tipo="prioridad")
    aggregate = pd.concat([by_policy, by_priority], ignore_index=True)
    aggregate["parametros_filtros_json"] = _export_parameters(args, simulation, seed)
    return "\ufeff" + aggregate.to_csv(index=False)


def register_callbacks(app: Dash, asset_prefix: str) -> None:
    @app.callback(
        Output("sim-veb-filter", "max"),
        Output("sim-veb-filter", "marks"),
        Output("sim-veb-filter", "value"),
        Input("sim-veb-period", "value"),
        State("sim-veb-filter", "value"),
    )
    def update_veb(period: str, current: Any) -> tuple[int, dict[int, str], int]:
        maximum = veb_max(normalize_veb_period(period))
        value = normalize_veb_threshold(period, current)
        return maximum, {0: "0", maximum: str(maximum)}, value

    @app.callback(
        Output("sim-coverage-percent", "value"),
        Output("sim-coverage-count", "value"),
        Output("sim-coverage-count", "max"),
        Output("sim-eligible-count", "data"),
        Output("sim-priority-segments", "children"),
        Output("sim-coverage-percent", "marks"),
        Output("sim-coverage-boundaries", "children"),
        Output("sim-coverage-track", "style"),
        Output("sim-coverage-display", "children"),
        Output("sim-eligible-label", "children"),
        Output("sim-excluded-label", "children"),
        Input("sim-profile-filter", "value"),
        Input("sim-include-ei", "value"),
        Input("sim-density-filter", "value"),
        Input("sim-security-filter", "value"),
        Input("sim-veb-period", "value"),
        Input("sim-veb-filter", "value"),
        Input("sim-coverage-percent", "value"),
        Input("sim-coverage-count", "value"),
    )
    def sync_coverage(
        profiles: list[str] | None,
        include_ei: list[str] | None,
        density: Any,
        security: Any,
        period: Any,
        threshold: Any,
        percent: Any,
        requested_count: Any,
    ) -> tuple[Any, ...]:
        frame = eligible_sections(**_filter_args(profiles, include_ei, density, security, period, threshold))
        total = len(frame)
        if ctx.triggered_id == "sim-coverage-count":
            count = min(total, max(0, _number(requested_count)))
        else:
            count = coverage_count(total, percent)
        actual_percent = 100.0 * count / total if total else 0.0
        counts = priority_counts(frame)
        visual = _priority_visual_spec(counts)
        excluded = 70_751 - total
        return (
            actual_percent,
            count,
            total,
            total,
            visual["segments"],
            visual["slider_marks"],
            visual["boundary_labels"],
            visual["track_style"],
            f"{actual_percent:.2f}%",
            f"{total:,} elegibles",
            f"{excluded:,} secciones fuera del universo por perfiles, evidencia o filtros territoriales.",
        )

    @app.callback(
        Output("sim-selected-summary", "children"),
        Output("sim-assignment-summary", "children"),
        Output("sim-base-mean", "children"),
        Output("sim-conservative-increment", "children"),
        Output("sim-conservative-mean", "children"),
        Output("sim-central-increment", "children"),
        Output("sim-central-mean", "children"),
        Output("sim-optimistic-increment", "children"),
        Output("sim-optimistic-mean", "children"),
        Output("sim-reference", "children"),
        Output("sim-projection-note", "children"),
        Output("sim-intervention-table", "data"),
        Output("sim-priority-table", "data"),
        Output("sim-security-context", "children"),
        Output("sim-section-geo", "hideout"),
        Input("sim-profile-filter", "value"),
        Input("sim-include-ei", "value"),
        Input("sim-density-filter", "value"),
        Input("sim-security-filter", "value"),
        Input("sim-veb-period", "value"),
        Input("sim-veb-filter", "value"),
        Input("sim-coverage-count", "value"),
        Input("sim-seed", "value"),
    )
    def update_simulation(
        profiles: list[str] | None,
        include_ei: list[str] | None,
        density: Any,
        security: Any,
        period: Any,
        threshold: Any,
        requested_count: Any,
        seed: Any,
    ) -> tuple[Any, ...]:
        args = _filter_args(profiles, include_ei, density, security, period, threshold)
        frame = eligible_sections(**args)
        simulation = simulate(frame, requested_count, seed=seed)
        selected_summary = _selected_summary(simulation)
        assignment_summary = _assignment_summary(simulation)
        projection_note = (
            f"{simulation['valid_selected']:,} secciones tratadas entran en los cuatro promedios; "
            f"{simulation['invalid_selected']:,} quedaron fuera por falta de proyección válida. "
            "Los escenarios son supuestos alternativos de eficacia, no intervalos de confianza."
        )
        security = security_context(simulation, period)
        security_children = [
            html.Div([html.Strong(f"{security['positive']:,}"), html.Span("seleccionadas en municipios con registros")]),
            html.Div([html.Strong(f"{security['share']:.1%}"), html.Span("del total seleccionado")]),
            html.Div([html.Strong(f"{security['missing']:,}"), html.Span("sin información municipal")]),
        ]
        simulated = simulation["frame"]
        selected = simulated.loc[simulated["seleccionada"]]
        assignment_lookup = {
            str(row.clave_seccion): [
                int(row.intervencion_id),
                None if pd.isna(row.participacion_base_pct) else round(float(row.participacion_base_pct), 3),
            ]
            for row in selected.itertuples()
        }
        hideout = {
            "activeProfiles": args["active_profiles"],
            "includeEI": args["include_insufficient"],
            "densityEnabled": args["density_percent"] < 100,
            "densityLimit": density_selection_count(args["density_percent"]),
            "securityEnabled": args["security_percent"] < 100,
            "securityLimit": security_target_count(args["security_percent"]),
            "vebEnabled": veb_filter_enabled(args["veb_period"], args["veb_threshold"]),
            "vebPeriod": args["veb_period"],
            "vebThreshold": args["veb_threshold"],
            "assignmentLookup": assignment_lookup,
            "interventionNames": {str(item["id"]): item["name"] for item in INTERVENTIONS},
            "interventionEffects": {
                str(item["id"]): [
                    item["conservative"],
                    item["central"],
                    item["optimistic"],
                ]
                for item in INTERVENTIONS
            },
            "priorityColors": PRIORITY_COLORS,
        }
        scenario_results = simulation["scenario_results"]
        return (
            selected_summary,
            assignment_summary,
            _fmt(simulation["base_mean"]),
            _fmt(scenario_results["conservative"]["increment_mean"], " pp"),
            _fmt(scenario_results["conservative"]["with_mean"]),
            _fmt(scenario_results["central"]["increment_mean"], " pp"),
            _fmt(scenario_results["central"]["with_mean"]),
            _fmt(scenario_results["optimistic"]["increment_mean"], " pp"),
            _fmt(scenario_results["optimistic"]["with_mean"]),
            _fmt(simulation["reference_mean"]),
            projection_note,
            _formatted_rows(simulation["intervention_rows"]),
            _formatted_rows(simulation["priority_rows"]),
            security_children,
            hideout,
        )

    @app.callback(
        Output("sim-section-geo", "url"),
        Output("sim-section-geo", "format"),
        Output("sim-section-geo", "formatOptions"),
        Input("sim-map", "zoom"),
        Input("sim-map", "bounds"),
    )
    def update_map_source(
        zoom: Any,
        bounds: Any,
    ) -> tuple[Any, Any, Any]:
        return geometry_spec(asset_prefix, zoom, bounds)

    download_inputs = [
        Input("sim-profile-filter", "value"),
        Input("sim-include-ei", "value"),
        Input("sim-density-filter", "value"),
        Input("sim-security-filter", "value"),
        Input("sim-veb-period", "value"),
        Input("sim-veb-filter", "value"),
        Input("sim-coverage-count", "value"),
        Input("sim-seed", "value"),
    ]

    @app.callback(
        Output("sim-download-sections-button", "href"),
        Output("sim-download-aggregate-button", "href"),
        *download_inputs,
    )
    def update_download_urls(*values: Any) -> tuple[str, str]:
        profiles, include_ei, density, security, period, threshold, count, seed = values
        query = urlencode(
            {
                "profiles": ",".join(profiles or []),
                "include_ei": "1" if "include" in (include_ei or []) else "0",
                "density": density,
                "security": security,
                "period": period,
                "threshold": threshold,
                "count": count,
                "seed": seed,
            }
        )
        return (
            f"/download/simulation-sections.csv?{query}",
            f"/download/simulation-aggregate.csv?{query}",
        )
