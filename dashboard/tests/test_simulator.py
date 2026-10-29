from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dashboard.app import app as explorer_app
from dashboard.data_layer import ALL_PROFILES, load_sections
from dashboard.map_geometry import MAPS_BASE_URL
from dashboard.simulator import (
    INTERVENTIONS,
    coverage_count,
    eligible_sections,
    simulate,
    stable_score,
)
from dashboard.simulator_ui import (
    PARTICIPATION_COLORS,
    _export_frame,
    _map_scale_legend,
    _priority_visual_spec,
    _shared_participation_range,
)
from dashboard.simulator_app import app as simulator_app

ROOT = Path(__file__).resolve().parents[2]


def _toy_frame(size_per_profile: int = 12) -> pd.DataFrame:
    profiles = ["P1", "P2", "P3", "P6", "P4", "P5", "EI_AB", "EI_CD"]
    rows = []
    sequence = 0
    for profile in profiles:
        for _ in range(size_per_profile):
            sequence += 1
            rows.append(
                {
                    "clave_seccion": f"{sequence // 9999 + 1:02d}:{sequence:04d}",
                    "perfil_visual_id": profile,
                    "prediccion_central_2027": 0.45 + (sequence % 20) / 100,
                    "municipal_attacks_cumulative": sequence % 4,
                    "municipal_attacks_24m": sequence % 2,
                }
            )
    return pd.DataFrame(rows)


def _selected(result: dict) -> set[str]:
    return set(result["frame"].loc[result["frame"]["seleccionada"], "clave_seccion"])


def test_stable_score_is_namespaced_and_repeatable() -> None:
    assert stable_score(42, "01:0001", "selection") == stable_score(
        42, "01:0001", "selection"
    )
    assert stable_score(42, "01:0001", "selection") != stable_score(
        42, "01:0001", "assignment"
    )


def test_zero_and_full_coverage_obey_boundaries() -> None:
    frame = _toy_frame()
    zero = simulate(frame, 0)
    full = simulate(frame, len(frame))
    assert zero["selected_count"] == 0
    assert zero["frame"]["intervencion"].isna().all()
    assert full["selected_count"] == len(frame)
    assert full["frame"]["intervencion"].notna().all()


def test_priority_is_exhausted_before_next_level() -> None:
    frame = _toy_frame(10)
    high_count = 20
    medium_count = 40
    partial_high = simulate(frame, high_count - 1)
    assert partial_high["selected_priority_counts"] == {
        "Alta": high_count - 1,
        "Media": 0,
        "Baja": 0,
    }
    partial_medium = simulate(frame, high_count + medium_count - 1)
    assert partial_medium["selected_priority_counts"] == {
        "Alta": high_count,
        "Media": medium_count - 1,
        "Baja": 0,
    }


def test_selection_is_nested_reproducible_and_row_order_independent() -> None:
    frame = _toy_frame(30)
    first = simulate(frame, 50, seed=90210)
    larger = simulate(frame, 90, seed=90210)
    shuffled = simulate(frame.sample(frac=1, random_state=7), 50, seed=90210)
    assert _selected(first) < _selected(larger)
    assert _selected(first) == _selected(shuffled)
    assignments_first = first["frame"].set_index("clave_seccion")["intervencion"].dropna()
    assignments_larger = larger["frame"].set_index("clave_seccion")["intervencion"]
    assert assignments_first.to_dict() == assignments_larger.loc[assignments_first.index].to_dict()


def test_all_scenarios_share_one_selection_and_assignment() -> None:
    frame = _toy_frame(20)
    result = simulate(frame, 70, seed=31)
    selected = result["frame"].loc[result["frame"]["seleccionada"]]

    assert len(result["selected_keys"]) == len(selected) == 70
    assert selected["intervencion"].notna().all()
    assert set(result["scenario_results"]) == {
        "conservative",
        "central",
        "optimistic",
    }
    increments = [
        result["scenario_results"][scenario]["increment_mean"]
        for scenario in ("conservative", "central", "optimistic")
    ]
    assert increments == sorted(increments)
    assert result["with_mean"] == result["scenario_results"]["central"]["with_mean"]
    assert result["increment_mean"] == result["scenario_results"]["central"][
        "increment_mean"
    ]
    pd.testing.assert_series_equal(
        result["frame"]["participacion_con_intervencion_pct"],
        result["frame"]["participacion_central_pct"],
        check_names=False,
    )


def test_missing_projection_is_excluded_symmetrically_and_cap_is_100() -> None:
    frame = _toy_frame(2)
    frame["prediccion_central_2027"] = 0.999
    frame.loc[0, "prediccion_central_2027"] = np.nan
    result = simulate(frame, len(frame), seed=42)
    selected = result["frame"]
    assert result["invalid_selected"] == 1
    assert result["valid_selected"] == len(frame) - 1
    for scenario in ("conservative", "central", "optimistic"):
        column = f"participacion_{scenario}_pct"
        assert selected[column].dropna().le(100).all()
        assert pd.isna(selected.loc[0, column])


def test_total_row_is_direct_calculation_not_mean_of_policy_means() -> None:
    frame = _toy_frame(18)
    result = simulate(frame, 83, seed=42, scenario="central")
    total = result["intervention_rows"][-1]
    treated = result["frame"].loc[result["frame"]["seleccionada"]]
    valid = treated.loc[treated["participacion_base_pct"].notna()]
    assert total["participacion_sin"] == pytest.approx(valid["participacion_base_pct"].mean())
    for scenario in ("conservative", "central", "optimistic"):
        expected = valid[f"participacion_{scenario}_pct"].mean()
        assert total[f"participacion_{scenario}"] == pytest.approx(expected)
        assert total[f"incremento_{scenario}_pp"] == pytest.approx(
            expected - valid["participacion_base_pct"].mean()
        )


def test_assignments_are_approximately_uniform() -> None:
    frame = _toy_frame(100)
    result = simulate(frame, len(frame), seed=42)
    counts = list(result["assignment_counts"].values())
    assert sum(counts) == len(frame)
    assert max(counts) - min(counts) < len(frame) * 0.08
    assert set(result["assignment_counts"]) == {item["name"] for item in INTERVENTIONS}


def test_intervention_effects_match_requested_three_scenarios() -> None:
    assert [
        (item["conservative"], item["central"], item["optimistic"])
        for item in INTERVENTIONS
    ] == [
        (0.5, 1.0, 2.0),
        (0.2, 0.6, 1.0),
        (0.5, 1.0, 1.5),
        (0.3, 0.75, 1.2),
        (0.2, 0.6, 1.0),
        (0.0, 0.5, 1.0),
    ]


def test_normal_scenario_preserves_previous_real_universe_result() -> None:
    frame = eligible_sections(ALL_PROFILES, include_insufficient=True)
    result = simulate(frame, coverage_count(len(frame), 25), seed=42)
    normal = result["scenario_results"]["central"]
    assert result["base_mean"] == pytest.approx(54.68972360068719, abs=1e-12)
    assert normal["with_mean"] == pytest.approx(55.42969622746825, abs=1e-12)
    assert normal["increment_mean"] == pytest.approx(
        0.7399726267810607,
        abs=1e-12,
    )


def test_coverage_count_uses_integer_as_source_of_truth() -> None:
    assert coverage_count(10_000, 0) == 0
    assert coverage_count(10_000, 5) == 500
    assert coverage_count(10_000, 25) == 2_500
    assert coverage_count(10_000, 75) == 7_500
    assert coverage_count(10_000, 100) == 10_000
    assert coverage_count(3, 50) == 2


def test_priority_bar_and_slider_share_exact_dynamic_boundaries() -> None:
    counts = {"Alta": 2_776, "Media": 50_992, "Baja": 16_983}
    visual = _priority_visual_spec(counts)
    high_end = 100 * counts["Alta"] / sum(counts.values())
    medium_end = 100 * (counts["Alta"] + counts["Media"]) / sum(counts.values())

    assert visual["ranges"]["Alta"] == pytest.approx((0, high_end))
    assert visual["ranges"]["Media"] == pytest.approx((high_end, medium_end))
    assert visual["ranges"]["Baja"] == pytest.approx((medium_end, 100))
    assert set(visual["marks"]) == {0.0, round(high_end, 2), round(medium_end, 2), 100.0}

    widths = [float(segment.style["width"].removesuffix("%")) for segment in visual["segments"]]
    assert widths == pytest.approx(
        [100 * counts[priority] / sum(counts.values()) for priority in ("Alta", "Media", "Baja")],
        abs=1e-6,
    )
    gradient = visual["track_style"]["--priority-gradient"]
    assert f"{high_end:.6f}%" in gradient
    assert f"{medium_end:.6f}%" in gradient


def test_priority_visual_boundaries_change_with_filtered_universe() -> None:
    first = _priority_visual_spec({"Alta": 20, "Media": 30, "Baja": 50})
    second = _priority_visual_spec({"Alta": 10, "Media": 80, "Baja": 10})
    assert first["ranges"] != second["ranges"]
    assert first["ranges"]["Alta"][1] == pytest.approx(20)
    assert second["ranges"]["Alta"][1] == pytest.approx(10)
    assert second["ranges"]["Media"][1] == pytest.approx(90)


def test_simulator_map_styles_only_selected_sections() -> None:
    source = (ROOT / "dashboard" / "assets" / "map.js").read_text(encoding="utf-8")
    assert 'if (!(hideout.assignmentLookup || {})[String(props.k || "")]) return false;' in source
    assert "const fillOpacity = selected ? 0.88 : 0;" in source
    assert 'const crimeContext = selected && Number.isFinite(crimeCount) && crimeCount > 0;' in source
    assert "weight: crimeContext ? 0.45 : (selected ? 0.55 : 0)" in source
    assert "opacity: crimeContext ? 0.78 : (selected ? 0.72 : 0)" in source
    assert "hideout.mapView" not in source
    assert 'conservative: "Pesimista", central: "Normal", optimistic: "Optimista"' in source
    assert "simulatorParticipationColor" in source


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js no disponible")
def test_simulator_map_colors_use_real_percentages_and_preserve_missing_values() -> None:
    script = """
        const fs = require("fs");
        const vm = require("vm");
        global.window = {};
        vm.runInThisContext(fs.readFileSync(process.argv[1], "utf8"));
        const map = window.dashboardMap;
        const colors = JSON.parse(process.argv[2]);
        const feature = {properties: {k: "01:0001", p: "P1", a: 2, b: 0}};
        const hideout = {
            assignmentLookup: {"01:0001": [1, 50]},
            interventionEffects: {"1": [0.5, 1, 2]},
            interventionNames: {"1": "Carta sobre el secreto del voto"},
            participationColors: colors,
            participationRanges: {conservative: [40, 60], central: [40, 60], optimistic: [40, 60]},
            activeProfiles: ["P1"],
            includeEI: true,
            vebPeriod: "cumulative",
            mapScenario: "base"
        };
        map.simulatorApplyScenario("central");
        const base = map.simulatorSectionStyle(feature, {hideout});
        const central = map.simulatorSectionStyle(feature, {
            hideout: {...hideout, mapScenario: "central"}
        });
        map.simulatorApplyScenario("conservative");
        const conservative = map.simulatorSectionStyle(feature, {
            hideout: {...hideout, mapScenario: "central"}
        });
        map.simulatorApplyScenario("optimistic");
        const optimistic = map.simulatorSectionStyle(feature, {
            hideout: {...hideout, mapScenario: "central"}
        });
        const invalid = map.simulatorSectionStyle(feature, {
            hideout: {...hideout, assignmentLookup: {"01:0001": [1, null]}}
        });
        const untreated = map.simulatorFilter(
            {properties: {k: "01:0002", p: "P1"}},
            {hideout}
        );
        let tooltip = "";
        map.simulatorApplyScenario("central");
        map.simulatorOnEachFeature(
            feature, {bindTooltip: value => {tooltip = value;}}, {hideout}
        );
        let optimisticTooltip = "";
        map.simulatorApplyScenario("optimistic");
        map.simulatorOnEachFeature(
            feature, {bindTooltip: value => {optimisticTooltip = value;}},
            {hideout}
        );
        let cappedTooltip = "";
        map.simulatorApplyScenario("central");
        map.simulatorOnEachFeature(
            feature,
            {bindTooltip: value => {cappedTooltip = value;}},
            {hideout: {...hideout, assignmentLookup: {"01:0001": [1, 99.9]}}}
        );
        const liveBase = {_map: {}, setStyle: function(style) {this.style = style;},
            bindTooltip: function(value) {this.tooltip = value;}};
        const liveRight = {_map: {}, setStyle: function(style) {this.style = style;},
            bindTooltip: function(value) {this.tooltip = value;}};
        map.simulatorOnEachFeature(feature, liveBase, {hideout});
        map.simulatorOnEachFeature(feature, liveRight, {hideout: {...hideout, mapScenario: "central"}});
        map.simulatorApplyScenario("optimistic");
        console.log(JSON.stringify({
            stops: [40, 45, 50, 55, 60].map(v => map.simulatorParticipationColor(v, colors, [40, 60])),
            between: map.simulatorParticipationColor(47.5, colors, [40, 60]),
            adjacent: [45.1, 45.2].map(v => map.simulatorParticipationColor(v, colors, [40, 60])),
            equalLimits: map.simulatorParticipationColor(50, colors, [50, 50]),
            noLimits: map.simulatorParticipationColor(50, colors, null),
            base: base.fillColor,
            central: central.fillColor,
            conservative: conservative.fillColor,
            optimistic: optimistic.fillColor,
            invalid: invalid.fillColor,
            selected: map.simulatorFilter(feature, {hideout}),
            untreated: untreated,
            crimeOutline: base.dashArray,
            tooltip: tooltip,
            optimisticTooltip: optimisticTooltip,
            cappedTooltip: cappedTooltip,
            liveBase: liveBase.style.fillColor,
            liveRight: liveRight.style.fillColor,
            liveTooltip: liveRight.tooltip
        }));
    """
    result = subprocess.run(
        ["node", "-e", script, str(ROOT / "dashboard/assets/map.js"), json.dumps(PARTICIPATION_COLORS)],
        check=True,
        capture_output=True,
        text=True,
    )
    actual = json.loads(result.stdout)
    assert actual["stops"] == list(PARTICIPATION_COLORS)
    assert actual["between"] == "rgb(238.5, 164, 110)"
    assert actual["adjacent"][0] != actual["adjacent"][1]
    assert actual["equalLimits"] == PARTICIPATION_COLORS[2]
    assert actual["noLimits"] == "#9CA3AF"
    assert actual["base"] == PARTICIPATION_COLORS[2]
    assert actual["central"] != actual["base"]
    assert len({actual["conservative"], actual["central"], actual["optimistic"]}) == 3
    assert actual["invalid"] == "#9CA3AF"
    assert actual["selected"] is True
    assert actual["untreated"] is False
    assert actual["crimeOutline"] == "4 3"
    assert "Sección 01:0001" in actual["tooltip"]
    assert "Perfil: P1" in actual["tooltip"]
    assert "Intervención: Carta sobre el secreto del voto" in actual["tooltip"]
    assert "Sin intervención: 50.00%" in actual["tooltip"]
    assert "Normal: +1.00 pp → 51.00%" in actual["tooltip"]
    assert "Optimista: +2.00 pp → 52.00%" in actual["optimisticTooltip"]
    assert "Normal:" not in actual["optimisticTooltip"]
    assert "Registros municipales: 2" in actual["tooltip"]
    assert "Normal: +0.10 pp → 100.00%" in actual["cappedTooltip"]
    assert actual["liveBase"] == actual["base"]
    assert actual["liveRight"] == actual["optimistic"]
    assert "Optimista: +2.00 pp → 52.00%" in actual["liveTooltip"]


def test_simulator_css_covers_requested_responsive_breakpoints() -> None:
    source = (ROOT / "dashboard" / "assets" / "style.css").read_text(encoding="utf-8")
    assert "@media (max-width: 1180px)" in source
    assert "@media (max-width: 1020px)" in source
    assert "@media (max-width: 720px)" in source
    assert "@media (max-width: 430px)" in source
    assert ".sim-main > *" in source and "min-width: 0" in source
    assert ".sim-table-grid, .sim-bottom-grid" in source
    assert ".dashboard-link" in source
    assert ".sim-comparison-grid" in source
    assert "overflow-x: hidden" not in source


def test_real_universe_evidence_toggle_and_original_projection_are_preserved() -> None:
    included = eligible_sections(ALL_PROFILES, include_insufficient=True)
    excluded = eligible_sections(ALL_PROFILES, include_insufficient=False)
    original = load_sections()
    assert len(included) == len(original) == 70_751
    assert len(included) - len(excluded) == int(
        original["perfil_visual_id"].str.startswith("EI_").sum()
    )
    result = simulate(included.head(50), 25)
    merged = result["frame"].set_index("clave_seccion")
    expected = original.loc[merged.index, "prediccion_central_2027"].astype(float) * 100
    pd.testing.assert_series_equal(
        merged["participacion_base_pct"], expected, check_names=False, check_dtype=False
    )


def test_layouts_are_independent_and_simulator_has_all_controls() -> None:
    explorer_ids = {
        getattr(component, "id", None) for component in _walk(explorer_app.layout)
    }
    simulator_ids = {
        getattr(component, "id", None) for component in _walk(simulator_app.layout)
    }
    assert "app-tabs" not in explorer_ids | simulator_ids
    assert "sim-map-base" not in explorer_ids
    assert "sim-map-central" not in explorer_ids
    assert "sim-map" not in simulator_ids
    assert "profile-filter" not in simulator_ids
    assert {
        "sim-profile-filter",
        "sim-density-filter",
        "sim-security-filter",
        "sim-coverage-percent",
        "sim-coverage-count",
        "sim-seed",
        "sim-map-base",
        "sim-map-central",
        "sim-section-geo-base",
        "sim-section-geo-central",
        "sim-map-legend",
        "sim-map-scenario",
        "sim-map-scenario-title",
        "sim-map-data",
        "sim-map-scenario-applied",
        "sim-download-sections-button",
        "sim-conservative-increment",
        "sim-conservative-mean",
        "sim-central-increment",
        "sim-central-mean",
        "sim-optimistic-increment",
        "sim-optimistic-mean",
    }.issubset(simulator_ids)
    assert "sim-scenario" not in simulator_ids
    assert "sim-map-view" not in simulator_ids

    assert len(explorer_app.callback_map) == 7
    assert len(simulator_app.callback_map) == 8
    assert all("sim-" not in callback_id for callback_id in explorer_app.callback_map)
    explorer_only_ids = ("context-panel", "age-chart", "timeline-chart", "section-geo")
    assert all(
        not any(
            component_id in callback_id.replace("sim-section-geo-base", "").replace("sim-section-geo-central", "")
            for component_id in explorer_only_ids
        )
        for callback_id in simulator_app.callback_map
    )
    layout_json = json.dumps(
        simulator_app.server.test_client().get("/_dash-layout").get_json(),
        ensure_ascii=False,
    )
    assert "Rojo — Prioridad alta" in layout_json
    assert "Amarillo — Prioridad media" in layout_json
    assert "Verde — Prioridad baja" in layout_json
    assert "EI-A/B: Evidencia insuficiente por historia incompleta" in layout_json
    assert "EI-C/D: Evidencia insuficiente por comparabilidad territorial no validada" in layout_json
    assert "https://radar27.onrender.com" in layout_json
    assert "escala compartida ajustada a las secciones tratadas" in layout_json
    assert "Sin secciones tratadas." in layout_json
    selector = next(component for component in _walk(simulator_app.layout) if getattr(component, "id", None) == "sim-map-scenario")
    assert selector.value == "central"
    assert selector.options == [
        {"label": "Pesimista", "value": "conservative"},
        {"label": "Normal", "value": "central"},
        {"label": "Optimista", "value": "optimistic"},
    ]


def test_shared_scale_uses_only_valid_treated_values_for_each_scenario() -> None:
    selected = pd.DataFrame(
        {
            "participacion_base_pct": [45.1, 52.2, np.nan],
            "participacion_central_pct": [46.1, 54.2, np.nan],
            "participacion_conservative_pct": [45.6, 52.4, np.nan],
            "participacion_optimistic_pct": [47.1, 56.2, np.nan],
        }
    )
    assert _shared_participation_range(selected) == (45.1, 54.2)
    assert _shared_participation_range(selected, "conservative") == (45.1, 52.4)
    assert _shared_participation_range(selected, "optimistic") == (45.1, 56.2)
    selected.loc[0, "participacion_optimistic_pct"] = np.nan
    assert _shared_participation_range(selected, "optimistic") == (52.2, 56.2)
    assert _shared_participation_range(selected.iloc[:0]) is None
    assert _shared_participation_range(selected.iloc[2:]) is None
    legend = _map_scale_legend((45.1, 54.2), 3)
    assert all(
        f"{color} {index * 25}%" in legend[0].style["background"]
        for index, color in enumerate(PARTICIPATION_COLORS)
    )
    assert legend[1].children[0].children == "45.10%"
    assert legend[1].children[-1].children == "54.20%"
    assert _map_scale_legend(None, 0)[0].children == "Sin secciones tratadas."
    assert "no tienen proyección válida" in _map_scale_legend(None, 3)[0].children
    assert _map_scale_legend((50.0, 50.0), 3)[0].style["background"] == PARTICIPATION_COLORS[2]


def test_comparison_maps_share_selection_and_dynamic_percent_scale() -> None:
    simulation_entry = next(
        entry
        for key, entry in simulator_app.callback_map.items()
        if "sim-map-data.data" in key
    )
    visual_entry = next(
        entry for key, entry in simulator_app.callback_map.items()
        if "sim-map-scale.children" in key
    )
    simulate_callback = simulation_entry["callback"].__wrapped__
    visual_callback = visual_entry["callback"].__wrapped__
    assert {item["id"] for item in visual_entry["inputs"]} == {"sim-map-scenario", "sim-map-data"}
    output = simulate_callback(ALL_PROFILES, ["include"], 100, 100, "cumulative", 63, 25, 42)
    base, central, map_data = output[-3:]
    legend, title = visual_callback("central", map_data)
    assert len(base["assignmentLookup"]) == 25
    assert base["assignmentLookup"] == central["assignmentLookup"]
    assert base["mapScenario"] == "base"
    assert central["mapScenario"] == "central"
    assert title == "Con intervención · escenario normal"
    assert base["participationColors"] == central["participationColors"] == PARTICIPATION_COLORS
    assert base["participationRanges"] == central["participationRanges"]
    assert base["interventionEffects"] == central["interventionEffects"]
    simulated = simulate(eligible_sections(ALL_PROFILES, include_insufficient=True), 25, seed=42)
    treated = simulated["frame"].loc[simulated["frame"]["seleccionada"]]
    values = pd.concat([treated["participacion_base_pct"], treated["participacion_central_pct"]])
    assert base["participationRanges"]["central"] == (float(values.min()), float(values.max()))
    key = next(iter(base["assignmentLookup"]))
    expected_base = float(treated.loc[treated["clave_seccion"].eq(key), "participacion_base_pct"].iloc[0])
    assert base["assignmentLookup"][key][1] == expected_base
    assert legend[1].children[0].children == f"{values.min():.2f}%"
    assert legend[1].children[-1].children == f"{values.max():.2f}%"
    assert output[2] != "No disponible"
    assert output[5] != "No disponible"

    for scenario, label in (("conservative", "pesimista"), ("optimistic", "optimista")):
        other_legend, other_title = visual_callback(scenario, map_data)
        values = pd.concat([treated["participacion_base_pct"], treated[f"participacion_{scenario}_pct"]])
        assert base["participationRanges"][scenario] == central["participationRanges"][scenario]
        assert base["participationRanges"][scenario] == (float(values.min()), float(values.max()))
        assert other_legend[1].children[-1].children == f"{values.max():.2f}%"
        assert other_title == f"Con intervención · escenario {label}"

    assert all(item["id"] != "sim-map-scenario" for item in simulation_entry["inputs"])

    empty_output = simulate_callback(ALL_PROFILES, ["include"], 100, 100, "cumulative", 63, 0, 42)
    assert empty_output[-3]["participationRanges"]["optimistic"] is None
    assert empty_output[-2]["participationRanges"]["optimistic"] is None
    assert visual_callback("optimistic", empty_output[-1])[0][0].children == "Sin secciones tratadas."
    no_projection = visual_callback("conservative", {
        "participationRanges": {"conservative": None},
        "selectedCount": 1,
    })
    assert "no tienen proyección válida" in no_projection[0][0].children

    larger_output = simulate_callback(ALL_PROFILES, ["include"], 100, 100, "cumulative", 63, 1000, 42)
    larger_range = larger_output[-3]["participationRanges"]["central"]
    assert larger_range == larger_output[-2]["participationRanges"]["central"]
    assert larger_range != base["participationRanges"]["central"]
    assert visual_callback("central", larger_output[-1])[0][1].children[0].children == (
        f"{larger_range[0]:.2f}%"
    )


def test_comparison_maps_switch_polygon_detail_from_the_same_cdn() -> None:
    callback = next(
        entry["callback"].__wrapped__
        for key, entry in simulator_app.callback_map.items()
        if "sim-section-geo-base.url" in key
    )
    base_url, base_format, base_options, central_url, central_format, central_options = callback(
        4, None, 9, [[19, -100], [20, -99]]
    )
    assert base_url == f"{MAPS_BASE_URL}/sections_overview.fgb"
    assert central_url == f"{MAPS_BASE_URL}/sections_detail.fgb"
    assert base_format == central_format == "flatgeobuf"
    assert set(base_options["rect"]) == set(central_options["rect"])


def test_section_export_contains_all_scenarios_and_keeps_central_aliases() -> None:
    export, simulation, _ = _export_frame(
        ALL_PROFILES,
        ["include"],
        100,
        100,
        "cumulative",
        63,
        25,
        42,
    )
    required = {
        "efecto_pesimista_pp",
        "participacion_pesimista_pct",
        "variacion_pesimista_pp",
        "efecto_normal_pp",
        "participacion_normal_pct",
        "variacion_normal_pp",
        "efecto_optimista_pp",
        "participacion_optimista_pct",
        "variacion_optimista_pp",
    }
    assert required.issubset(export.columns)
    pd.testing.assert_series_equal(
        export["efecto_aplicado_pp"],
        export["efecto_normal_pp"],
        check_names=False,
    )
    pd.testing.assert_series_equal(
        export["participacion_con_intervencion_pct"],
        export["participacion_normal_pct"],
        check_names=False,
    )
    assert simulation["scenario_results"]["central"]["with_mean"] == pytest.approx(
        export.loc[export["seleccionada"], "participacion_normal_pct"].mean()
    )


def _walk(component: object):
    yield component
    children = getattr(component, "children", None)
    if children is None:
        return
    if not isinstance(children, (list, tuple)):
        children = [children]
    for child in children:
        if hasattr(child, "children") or getattr(child, "id", None) is not None:
            yield from _walk(child)
