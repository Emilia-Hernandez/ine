"""Figuras Plotly del dashboard."""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go

WINE = "#5B1731"
TERRACOTTA = "#B85C43"
ORANGE = "#DF9462"
SAND = "#D9B98C"
BLUE = "#2D5B74"
GRID = "#E7E3DF"
TEXT = "#2B2928"


def _base_layout(
    figure: go.Figure, *, margin: dict[str, int] | None = None
) -> go.Figure:
    figure.update_layout(
        autosize=True,
        margin=margin or {"l": 42, "r": 24, "t": 28, "b": 42},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, system-ui, sans-serif", "color": TEXT, "size": 12},
        hoverlabel={"bgcolor": "#FFFFFF", "bordercolor": GRID, "font": {"color": TEXT}},
        showlegend=False,
    )
    figure.update_xaxes(showgrid=False, zeroline=False, linecolor=GRID, automargin=True)
    figure.update_yaxes(showgrid=True, gridcolor=GRID, zeroline=False, automargin=True)
    return figure


def empty_figure(message: str) -> go.Figure:
    figure = go.Figure()
    figure.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"color": "#746F6B", "size": 13},
        align="center",
    )
    figure.update_xaxes(visible=False)
    figure.update_yaxes(visible=False)
    return _base_layout(figure)


def distribution_figure(data: list[dict[str, Any]], color: str) -> go.Figure:
    available = [item for item in data if item.get("share") is not None]
    if not available:
        return empty_figure("Información no disponible para la selección")
    labels = [item["label"] for item in available]
    shares = [item["share"] for item in available]
    counts = [item["count"] for item in available]
    turnout = [item.get("turnout") for item in available]
    hover = []
    for count, rate in zip(counts, turnout, strict=True):
        rate_text = f"{rate:.1%}" if rate is not None else "No disponible"
        hover.append(f"Registros identificados: {count:,.0f}<br>Participación 2024: {rate_text}")
    figure = go.Figure(
        go.Bar(
            x=labels,
            y=shares,
            marker={"color": color, "cornerradius": 5},
            text=[f"{value:.1%}" for value in shares],
            textposition="outside",
            customdata=hover,
            hovertemplate="<b>%{x}</b><br>Distribución: %{y:.1%}<br>%{customdata}<extra></extra>",
            cliponaxis=False,
        )
    )
    figure.update_yaxes(tickformat=".0%", range=[0, max(shares) * 1.22], title=None)
    return _base_layout(figure)


def timeline_figure(payload: dict[str, Any]) -> go.Figure:
    history = [item for item in payload["history"] if item["value"] is not None]
    if not history:
        return empty_figure("No hay observaciones electorales para la selección")
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=[item["year"] for item in history],
            y=[item["value"] for item in history],
            mode="lines+markers",
            line={"color": WINE, "width": 2.5},
            marker={
                "color": [WINE if item["family"] == "intermedia" else SAND for item in history],
                "size": 10,
                "symbol": [
                    "circle" if item["family"] == "intermedia" else "square" for item in history
                ],
                "line": {"color": "#FFFFFF", "width": 1.5},
            },
            customdata=[[item["sections"], item["family"]] for item in history],
            hovertemplate=(
                "<b>%{x} observado</b><br>Participación: %{y:.1%}<br>"
                "Secciones con datos: %{customdata[0]:,}<br>Tipo: %{customdata[1]}<extra></extra>"
            ),
            name="Observado",
        )
    )
    projected = payload.get("projected_2027")
    model_reference = payload.get("model_reference_2021")
    if projected is not None and model_reference is not None:
        figure.add_trace(
            go.Scatter(
                x=[2021, 2027],
                y=[model_reference, projected],
                mode="lines+markers",
                line={"color": BLUE, "width": 2.5, "dash": "dot"},
                marker={
                    "color": [BLUE, BLUE],
                    "size": [7, 12],
                    "symbol": ["circle-open", "diamond"],
                },
                customdata=[["Referencia comparable del modelo"], ["Proyección de trabajo"]],
                hovertemplate="<b>%{x}</b><br>Participación: %{y:.1%}<br>%{customdata[0]}<extra></extra>",
                name="Proyección 2027",
            )
        )
        figure.add_annotation(
            x=2027,
            y=projected,
            text="Proyección de trabajo",
            showarrow=False,
            xanchor="right",
            yshift=20,
            font={"color": BLUE, "size": 11},
        )
    figure.update_yaxes(tickformat=".0%", rangemode="tozero", title=None)
    figure.update_xaxes(tickmode="array", tickvals=[2009, 2012, 2015, 2018, 2021, 2024, 2027])
    figure = _base_layout(figure, margin={"l": 52, "r": 28, "t": 34, "b": 84})
    figure.update_layout(
        showlegend=True,
        legend={
            "orientation": "h",
            "x": 0,
            "xanchor": "left",
            "y": -0.22,
            "yanchor": "top",
        },
    )
    return figure


def socio_figure(data: dict[str, Any]) -> go.Figure:
    value = data.get("value")
    if value is None:
        return empty_figure("Información no disponible para la selección")
    is_percent = data.get("format") == "percent"
    display = f"{value:.1%}" if is_percent else f"{value:.1f} años"
    xmax = 1 if is_percent else max(15, value * 1.25)
    figure = go.Figure(
        go.Bar(
            x=[value],
            y=[data["label"]],
            orientation="h",
            marker={"color": TERRACOTTA, "cornerradius": 6},
            text=[display],
            textposition="outside",
            hovertemplate=f"<b>{data['label']}</b><br>{display}<extra></extra>",
            cliponaxis=False,
        )
    )
    figure.update_xaxes(range=[0, xmax], tickformat=".0%" if is_percent else ".0f")
    figure.update_yaxes(showgrid=False)
    return _base_layout(figure, margin={"l": 42, "r": 62, "t": 28, "b": 42})
