from __future__ import annotations

from dashboard.app import _chart_card
from dashboard.data_layer import ALL_PROFILES, build_payload
from dashboard.figures import timeline_figure


def test_chart_cards_reserve_explicit_graph_heights() -> None:
    standard = _chart_card("Edad", "Detalle", "age-test")
    timeline = _chart_card(
        "Trayectoria",
        "Detalle",
        "timeline-test",
        wide=True,
        note="Nota metodológica",
    )

    assert standard.children[1].style["height"] == "240px"
    assert timeline.children[1].style["height"] == "350px"
    assert "chart-wide" in timeline.className
    assert timeline.children[2].className == "chart-note"


def test_timeline_uses_responsive_size_and_lower_legend() -> None:
    figure = timeline_figure(build_payload(ALL_PROFILES, None))

    assert figure.layout.autosize is True
    assert figure.layout.height is None
    assert figure.layout.showlegend is True
    assert figure.layout.legend.orientation == "h"
    assert figure.layout.legend.y < 0
    assert figure.layout.margin.b >= 80
