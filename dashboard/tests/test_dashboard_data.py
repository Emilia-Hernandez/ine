from __future__ import annotations

import io
import json
import math
import os
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest

from dashboard.app import (
    ASSET_PREFIX,
    CURRENT_RELEASE,
    _veb_attack_card,
    app,
    update_dashboard,
    update_geometry_source,
    veb_range,
)
from dashboard.data_layer import (
    ALL_PROFILES,
    VEB_COLUMNS,
    build_payload,
    density_selection_count,
    density_valid_count,
    export_selection_csv,
    load_sections,
    security_effective_count,
    security_target_count,
    security_valid_count,
    select_frame,
    veb_max,
)
from dashboard.prepare_data import _rank_density
from dashboard.state import resolve_selection

ROOT = Path(__file__).resolve().parents[2]
WORKING_COPY = os.environ.get("RADAR27_DASHBOARD_WORKING_COPY") == "1"


def test_prepared_layer_preserves_canonical_universe() -> None:
    frame = load_sections()
    assert len(frame) == 70_751
    assert frame.index.is_unique
    assert frame["perfil_electoral_id"].value_counts().to_dict() == {
        "P6": 20_932,
        "P3": 20_698,
        "P5": 9_955,
        "EI": 9_362,
        "P4": 7_028,
        "P1": 2_718,
        "P2": 58,
    }
    assert frame["perfil_visual_id"].value_counts().to_dict()["EI_AB"] == 3_706
    assert frame["perfil_visual_id"].value_counts().to_dict()["EI_CD"] == 5_656
    assert frame.loc[frame["perfil_visual_id"].str.startswith("EI_"), "perfil_electoral_id"].eq("EI").all()


def test_national_aggregates_match_canonical_reference() -> None:
    payload = build_payload(ALL_PROFILES, None)
    assert payload["section_count"] == 70_751
    assert payload["projected_2027"] == pytest.approx(0.5566234244, abs=1e-10)
    assert payload["model_reference_2021"] == pytest.approx(0.517738, abs=5e-7)
    assert payload["change_2021_2027_pp"] == pytest.approx(3.8885, abs=2e-3)


def test_profile_filter_recalculates_and_empty_state_is_safe() -> None:
    p1 = build_payload(["P1"], None)
    assert p1["section_count"] == 2_718
    assert p1["profile_counts"]["P1"] == 2_718
    assert sum(p1["profile_counts"].values()) == 2_718
    empty = build_payload([], None)
    assert empty["empty"] is True
    assert empty["section_count"] == 0
    assert empty["projected_2027"] is None


def test_selected_section_has_exclusive_history_and_demography() -> None:
    payload = build_payload(ALL_PROFILES, "01:0001", "internet")
    assert payload["mode"] == "section"
    assert payload["section_count"] == 1
    assert payload["section"]["nombre_entidad"] == "AGUASCALIENTES"
    assert payload["section"]["perfil_electoral_id"] == "P4"
    assert any(item["year"] == 2021 and item["value"] is not None for item in payload["history"])
    assert payload["age"][0]["count"] == 547
    assert payload["socio"]["coverage"]["available"] == 1
    assert "municipal_attacks_12m" in payload["section"]


def test_selected_section_without_electoral_demography_is_safe() -> None:
    frame = load_sections()
    section_id = str(frame.loc[frame["female_identified_2024"].isna(), "clave_seccion"].iloc[0])
    payload = build_payload(ALL_PROFILES, section_id, "internet")
    assert payload["mode"] == "section"
    assert all(item["share"] is None for item in payload["age"])
    rendered = update_dashboard(ALL_PROFILES, section_id, "internet")
    assert len(rendered) == 21


def test_selection_clears_when_profile_becomes_inactive() -> None:
    rank = int(load_sections().loc["01:0001", "density_rank"])
    click = {"properties": {"k": "01:0001", "p": "P4", "r": rank}}
    assert resolve_selection("section-geo", ALL_PROFILES, click, None) == "01:0001"
    assert resolve_selection("profile-filter", ["P1"], None, "01:0001") is None
    assert resolve_selection("clear-selection", ALL_PROFILES, None, "01:0001") is None
    assert resolve_selection("density-filter", ALL_PROFILES, None, "01:0001", 0) is None


def test_geometry_sources_switch_without_touching_aggregates() -> None:
    national, national_format, national_options = update_geometry_source(
        5, [[14.2, -118.8], [33.4, -86.4]]
    )
    overview, overview_format, options = update_geometry_source(
        6, [[19.0, -100.0], [20.0, -99.0]]
    )
    detail, detail_format, detail_options = update_geometry_source(
        9, [[19.0, -100.0], [20.0, -99.0]]
    )
    assert national.endswith("sections_overview.fgb")
    assert national_format == "flatgeobuf"
    assert set(national_options["rect"]) == {"minX", "minY", "maxX", "maxY"}
    assert overview.endswith("sections_overview.fgb")
    assert overview_format == "flatgeobuf"
    assert detail.endswith("sections_detail.fgb")
    assert detail_format == "flatgeobuf"
    assert set(options["rect"]) == {"minX", "minY", "maxX", "maxY"}
    assert detail_options["rect"]["maxX"] <= -98.75


def test_callback_payload_renders_all_panels() -> None:
    rendered = update_dashboard(["P1"], None, "internet")
    assert len(rendered) == 21
    assert rendered[5] == "Vista agregada"
    assert "hidden" in rendered[6]
    assert rendered[8] == "100%"


def test_geometry_and_manifest_are_complete() -> None:
    manifest_path = ROOT / CURRENT_RELEASE["manifest_file"]
    manifest = json.loads(manifest_path.read_text())
    asset_root = ROOT / "dashboard" / ASSET_PREFIX.lstrip("/")
    data_path = ROOT / CURRENT_RELEASE["data_file"]
    assert manifest["sections"] == 70_751
    assert manifest["geometry_version"].startswith("snapshot_INE_2024-05-09")
    for name in ("overview", "detail"):
        layer = gpd.read_file(asset_root / f"sections_{name}.fgb")
        assert len(layer) == 70_751
        assert layer["k"].is_unique
        assert {"k", "p", "r", "s", "a", "b"}.issubset(layer.columns)
        sample = layer.set_index("k").loc["01:0001"]
        source = pd.read_parquet(
            data_path,
            columns=["clave_seccion", "municipal_attacks_cumulative", "municipal_attacks_24m"],
        ).set_index("clave_seccion").loc["01:0001"]
        assert sample["a"] == int(source["municipal_attacks_cumulative"])
        assert sample["b"] == int(source["municipal_attacks_24m"])
        assert layer.geometry.is_valid.all()
    states = gpd.read_file(asset_root / "state_boundaries.geojson")
    assert len(states) == 32
    assert states.geometry.is_valid.all()


def test_density_canonical_table_integrity_and_coverage() -> None:
    density_path = (ROOT / CURRENT_RELEASE["manifest_file"]).parent / "section_housing_density.parquet"
    density = pd.read_parquet(density_path)
    assert list(density.columns) == [
        "section_id",
        "entidad",
        "seccion",
        "viviendas_habitadas_2020",
        "area_km2",
        "densidad_viviendas_km2",
        "density_data_status",
        "density_source_year",
        "density_rank",
    ]
    assert len(density) == 70_751
    assert density["section_id"].is_unique
    assert (density["section_id"] == density["entidad"] + ":" + density["seccion"]).all()
    assert density["area_km2"].gt(0).all()
    valid = density[density["density_data_status"].eq("valid")]
    assert len(valid) == 58_530
    assert valid["viviendas_habitadas_2020"].ge(0).all()
    assert valid["densidad_viviendas_km2"].ge(0).all()
    assert np.isfinite(valid["densidad_viviendas_km2"]).all()
    assert valid["density_rank"].astype(int).sort_values().tolist() == list(
        range(1, len(valid) + 1)
    )
    assert density.loc[~density.index.isin(valid.index), "densidad_viviendas_km2"].isna().all()


@pytest.mark.parametrize("percent", [90, 66, 10])
def test_density_filter_keeps_expected_top_n(percent: int) -> None:
    payload = build_payload(ALL_PROFILES, None, density_percent=percent)
    expected = math.ceil(density_valid_count() * percent / 100)
    assert density_selection_count(percent) == expected
    assert payload["section_count"] == expected
    assert payload["density"]["national_selected"] == expected


def test_density_filter_boundaries_nesting_and_profile_independence() -> None:
    full = build_payload(ALL_PROFILES, None, density_percent=100)
    minimum = build_payload(ALL_PROFILES, None, density_percent=1)
    assert full["section_count"] == 70_751
    assert minimum["section_count"] == math.ceil(density_valid_count() / 100)

    frame = load_sections()
    subsets = {}
    for percent in (10, 25, 50, 90):
        limit = density_selection_count(percent)
        subsets[percent] = set(frame.index[frame["density_rank"].notna() & frame["density_rank"].le(limit)])
    assert subsets[10] < subsets[25] < subsets[50] < subsets[90]
    assert build_payload(["P6"], None, density_percent=66)["density"]["national_selected"] == (
        build_payload(ALL_PROFILES, None, density_percent=66)["density"]["national_selected"]
    )


def test_density_ranking_is_deterministic_for_ties() -> None:
    toy = pd.DataFrame(
        {
            "section_id": ["02:0002", "01:0002", "01:0001", "03:0001"],
            "densidad_viviendas_km2": [10.0, 20.0, 20.0, np.nan],
            "density_data_status": ["valid", "valid", "valid", "eceg_not_available"],
        }
    )
    ranked = _rank_density(toy).set_index("section_id")
    assert ranked.loc["01:0001", "density_rank"] == 1
    assert ranked.loc["01:0002", "density_rank"] == 2
    assert ranked.loc["02:0002", "density_rank"] == 3
    assert pd.isna(ranked.loc["03:0001", "density_rank"])


def test_density_slider_is_present_with_requested_contract() -> None:
    layout = app.layout
    slider = next(
        component
        for component in _walk_components(layout)
        if getattr(component, "id", None) == "density-filter"
    )
    assert (slider.min, slider.max, slider.step, slider.value) == (1, 100, 1, 100)
    assert set(slider.marks) == {10, 25, 50, 66, 100}


@pytest.mark.parametrize("percent", [10, 25, 50, 66])
def test_security_filter_keeps_low_rates_and_complete_ties(percent: int) -> None:
    payload = build_payload(ALL_PROFILES, None, security_percent=percent)
    frame = load_sections()
    selected = frame.loc[
        frame["security_rank_start"].notna()
        & frame["security_rank_start"].le(security_target_count(percent))
    ]
    assert payload["section_count"] == len(selected) == security_effective_count(percent)
    assert len(selected) >= security_target_count(percent)
    assert selected["tasa_incidencia_total_100k"].max() == pytest.approx(
        payload["security"]["threshold"]
    )
    threshold = payload["security"]["threshold"]
    assert frame.loc[frame["tasa_incidencia_total_100k"].eq(threshold)].index.isin(selected.index).all()


def test_security_filter_is_neutral_at_100_and_excludes_missing_when_restrictive() -> None:
    full = build_payload(ALL_PROFILES, None, security_percent=100)
    restricted = build_payload(ALL_PROFILES, None, security_percent=66)
    assert full["section_count"] == 70_751
    assert full["security"]["missing_sections"] == 70_751 - security_valid_count() == 301
    selected = load_sections().loc[
        load_sections()["security_rank_start"].notna()
        & load_sections()["security_rank_start"].le(security_target_count(66))
    ]
    assert selected["tasa_incidencia_total_100k"].notna().all()
    assert restricted["section_count"] == len(selected)


def test_combined_filters_and_export_share_exact_ids() -> None:
    profiles = ["P1", "P3", "EI_AB"]
    payload = build_payload(profiles, None, density_percent=25, security_percent=50)
    content, count = export_selection_csv(profiles, 25, 50)
    exported = pd.read_csv(io.StringIO(content.lstrip("\ufeff")), dtype={"clave_seccion": "string"})
    assert count == payload["section_count"] == len(exported)
    assert exported["clave_seccion"].is_unique
    assert {"did_not_vote_2009", "unspecified_2009", "did_not_vote_2024", "unspecified_2024"}.issubset(
        exported.columns
    )
    assert set(exported["clave_seccion"]) == set(
        load_sections().loc[
            load_sections()["perfil_visual_id"].isin(profiles)
            & load_sections()["density_rank"].notna()
            & load_sections()["density_rank"].le(density_selection_count(25))
            & load_sections()["security_rank_start"].notna()
            & load_sections()["security_rank_start"].le(security_target_count(50)),
            "clave_seccion",
        ]
    )
    assert exported["metadatos_filtros_json"].nunique() == 1


@pytest.mark.skipif(not WORKING_COPY, reason="Requiere la copia local con Votar entre Balas")
def test_veb_export_uses_same_count_threshold_as_map() -> None:
    content, count = export_selection_csv(["P1"], 100, 100, "cumulative", 3)
    exported = pd.read_csv(io.StringIO(content.lstrip("\ufeff")))
    expected = select_frame(["P1"], veb_period="cumulative", veb_threshold=3)
    assert count == len(exported) == len(expected)
    assert set(exported["clave_seccion"]) == set(expected.index)
    metadata = json.loads(exported["metadatos_filtros_json"].iloc[0])
    assert metadata["veb_periodo"] == "cumulative"
    assert metadata["veb_ataques_municipales_maximo"] == 3


def test_security_slider_and_download_are_present() -> None:
    components = list(_walk_components(app.layout))
    security = next(item for item in components if getattr(item, "id", None) == "security-filter")
    assert (security.min, security.max, security.step, security.value) == (1, 100, 1, 100)
    assert set(security.marks) == {10, 25, 50, 66, 100}
    assert any(getattr(item, "id", None) == "download-selection" for item in components)
    veb = next(item for item in components if getattr(item, "id", None) == "veb-period")
    assert veb.value == "cumulative"
    assert {item["value"] for item in veb.options} == {
        "cumulative",
        "24m",
    }
    attacks = next(item for item in components if getattr(item, "id", None) == "veb-filter")
    assert (attacks.min, attacks.max, attacks.step, attacks.value) == (
        0, veb_max("cumulative"), 1, veb_max("cumulative")
    )
    filter_panel = next(item for item in components if getattr(item, "className", None) == "filter-panel panel")
    children = list(filter_panel.children)
    security_index = next(i for i, item in enumerate(children) if "security-filter" in [getattr(c, "id", None) for c in _walk_components(item)])
    veb_index = next(i for i, item in enumerate(children) if "veb-filter" in [getattr(c, "id", None) for c in _walk_components(item)])
    assert veb_index == security_index + 1


def test_veb_summary_distinguishes_zero_from_unavailable() -> None:
    zero = _veb_attack_card(
        {
            "veb_data_status": "zero_registered_attacks_in_monitored_source",
            "municipal_attacks_cumulative": 0,
            "nombre_municipio": "Municipio de prueba",
            "nombre_entidad": "Entidad de prueba",
        },
        "cumulative",
    )
    unavailable = _veb_attack_card(
        {
            "veb_data_status": pd.NA,
            "municipal_attacks_cumulative": pd.NA,
            "nombre_municipio": "Municipio sin cruce",
            "nombre_entidad": "Entidad de prueba",
        },
        "cumulative",
    )
    zero_text = " ".join(
        str(getattr(item, "children", "")) for item in _walk_components(zero)
    )
    unavailable_text = " ".join(
        str(getattr(item, "children", "")) for item in _walk_components(unavailable)
    )
    assert "0 eventos" in zero_text
    assert "Sin dato" in unavailable_text


@pytest.mark.parametrize("period,threshold", [
    ("cumulative", 0), ("cumulative", 3), ("24m", 0)
])
@pytest.mark.skipif(not WORKING_COPY, reason="Requiere la copia local con Votar entre Balas")
def test_veb_threshold_selects_exact_municipal_counts(period: str, threshold: int) -> None:
    frame = load_sections()
    selected = select_frame(ALL_PROFILES, veb_period=period, veb_threshold=threshold)
    expected = frame[frame[VEB_COLUMNS[period]].notna() & frame[VEB_COLUMNS[period]].le(threshold)]
    assert set(selected.index) == set(expected.index)
    assert selected[VEB_COLUMNS[period]].max() <= threshold
    assert selected[VEB_COLUMNS[period]].isna().sum() == 0


@pytest.mark.skipif(not WORKING_COPY, reason="Requiere la copia local con Votar entre Balas")
def test_veb_maxima_are_observed_and_maximum_preserves_missing() -> None:
    frame = load_sections()
    for period in ("cumulative", "24m"):
        maximum = veb_max(period)
        assert maximum == int(frame[VEB_COLUMNS[period]].max())
        selected = select_frame(ALL_PROFILES, veb_period=period, veb_threshold=maximum)
        assert len(selected) == len(frame) == 70_751
        assert selected[VEB_COLUMNS[period]].isna().sum() == 136


@pytest.mark.skipif(not WORKING_COPY, reason="Requiere la copia local con Votar entre Balas")
def test_veb_period_change_clamps_only_when_needed() -> None:
    cumulative = veb_max("cumulative")
    recent = veb_max("24m")
    assert veb_range("24m", cumulative)[0] == recent
    assert veb_range("24m", cumulative)[2] == recent
    assert veb_range("cumulative", 3)[2] == 3
    assert veb_range("cumulative", 3, restore=True)[2] == cumulative


def _walk_components(component: object):
    yield component
    children = getattr(component, "children", None)
    if children is None:
        return
    if not isinstance(children, (list, tuple)):
        children = [children]
    for child in children:
        if hasattr(child, "children") or getattr(child, "id", None) is not None:
            yield from _walk_components(child)
