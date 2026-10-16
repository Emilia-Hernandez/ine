from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pytest

from dashboard.app import update_dashboard, update_geometry_source
from dashboard.data_layer import ALL_PROFILES, build_payload, load_sections
from dashboard.state import resolve_selection

ROOT = Path(__file__).resolve().parents[2]


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


def test_selected_section_without_electoral_demography_is_safe() -> None:
    frame = load_sections()
    section_id = str(frame.loc[frame["female_identified_2024"].isna(), "clave_seccion"].iloc[0])
    payload = build_payload(ALL_PROFILES, section_id, "internet")
    assert payload["mode"] == "section"
    assert all(item["share"] is None for item in payload["age"])
    rendered = update_dashboard(ALL_PROFILES, section_id, "internet")
    assert len(rendered) == 8


def test_selection_clears_when_profile_becomes_inactive() -> None:
    click = {"properties": {"k": "01:0001", "p": "P4"}}
    assert resolve_selection("section-geo", ALL_PROFILES, click, None) == "01:0001"
    assert resolve_selection("profile-filter", ["P1"], None, "01:0001") is None
    assert resolve_selection("clear-selection", ALL_PROFILES, None, "01:0001") is None


def test_geometry_sources_switch_without_touching_aggregates() -> None:
    overview, options = update_geometry_source(5, [[14.2, -118.8], [33.4, -86.4]])
    detail, detail_options = update_geometry_source(9, [[19.0, -100.0], [20.0, -99.0]])
    assert overview.endswith("sections_overview.fgb")
    assert detail.endswith("sections_detail.fgb")
    assert options["rect"]["minX"] <= -118.8
    assert detail_options["rect"]["maxX"] < -98.8


def test_callback_payload_renders_all_panels() -> None:
    rendered = update_dashboard(["P1"], None, "internet")
    assert len(rendered) == 8
    assert rendered[5] == "Vista agregada"
    assert "hidden" in rendered[6]


def test_geometry_and_manifest_are_complete() -> None:
    manifest = json.loads((ROOT / "dashboard" / "data" / "manifest.json").read_text())
    assert manifest["sections"] == 70_751
    assert manifest["geometry_version"].startswith("snapshot_INE_2024-05-09")
    for name in ("overview", "detail"):
        layer = gpd.read_file(ROOT / "dashboard" / "assets" / f"sections_{name}.fgb")
        assert len(layer) == 70_751
        assert layer["k"].is_unique
        assert layer.geometry.is_valid.all()
    states = gpd.read_file(ROOT / "dashboard" / "assets" / "state_boundaries.geojson")
    assert len(states) == 32
    assert states.geometry.is_valid.all()
