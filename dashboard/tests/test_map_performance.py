from __future__ import annotations

import json

import geopandas as gpd

from dashboard.app import ASSET_PREFIX, ROOT, server as explorer_server
from dashboard.map_geometry import MAPS_BASE_URL, geometry_spec
from dashboard.simulator_app import server as simulator_server


def _find(component: object, target: str) -> dict[str, object] | None:
    if isinstance(component, dict):
        props = component.get("props", {})
        if props.get("id") == target:
            return props
        for value in component.values():
            found = _find(value, target)
            if found:
                return found
    elif isinstance(component, list):
        for value in component:
            found = _find(value, target)
            if found:
                return found
    return None


def test_active_release_contains_complete_polygon_layers() -> None:
    release = json.loads((ROOT / "dashboard/data/current_release.json").read_text())
    assert ASSET_PREFIX == release["asset_prefix"]
    assets = ROOT / "dashboard" / ASSET_PREFIX.lstrip("/")
    for name in ("sections_overview.fgb", "sections_detail.fgb"):
        path = assets / name
        assert path.is_file()
        frame = gpd.read_file(path, columns=["k"])
        assert len(frame) == 70_751
        assert frame["k"].is_unique
        assert set(frame.geometry.geom_type).issubset({"Polygon", "MultiPolygon"})


def test_polygon_assets_support_cached_range_requests_in_both_apps() -> None:
    assets = ROOT / "dashboard" / ASSET_PREFIX.lstrip("/")
    for app_server in (explorer_server, simulator_server):
        client = app_server.test_client()
        for name in ("sections_overview.fgb", "sections_detail.fgb"):
            path = assets / name
            response = client.get(f"{ASSET_PREFIX}/{name}", headers={"Range": "bytes=0-1023"})
            assert response.status_code == 206
            assert response.headers["Content-Range"] == f"bytes 0-1023/{path.stat().st_size}"
            assert int(response.headers["Content-Length"]) == 1024
            assert response.headers["Cache-Control"] == "public, max-age=31536000, immutable"


def test_geometry_uses_only_two_polygon_levels_and_quantized_bboxes() -> None:
    national = geometry_spec(4, None)
    assert national[0] == f"{MAPS_BASE_URL}/sections_overview.fgb"
    assert national[1] == "flatgeobuf"
    assert national[2]["rect"] == {
        "minX": -118.8,
        "minY": 14.2,
        "maxX": -86.4,
        "maxY": 33.4,
    }
    first = geometry_spec(7, [[19.01, -100.01], [19.99, -99.01]])
    nearby = geometry_spec(7, [[19.02, -100.02], [19.98, -99.02]])
    assert first == nearby
    assert first[0] == f"{MAPS_BASE_URL}/sections_detail.fgb"
    assert first[1] == "flatgeobuf"


def test_apps_have_independent_polygon_layouts() -> None:
    explorer = explorer_server.test_client().get("/_dash-layout").get_json()
    simulator = simulator_server.test_client().get("/_dash-layout").get_json()
    explorer_map = _find(explorer, "section-geo")
    simulator_map = _find(simulator, "sim-section-geo")
    assert explorer_map is not None
    assert simulator_map is not None
    assert explorer_map["url"] == f"{MAPS_BASE_URL}/sections_overview.fgb"
    assert simulator_map["url"] == f"{MAPS_BASE_URL}/sections_overview.fgb"
    assert _find(explorer, "sim-section-geo") is None
    assert _find(simulator, "section-geo") is None
    assert "pointToLayer" not in explorer_map
    assert "pointToLayer" not in simulator_map


def test_point_architecture_has_no_active_references() -> None:
    active_files = [
        ROOT / "dashboard/app.py",
        ROOT / "dashboard/simulator_app.py",
        ROOT / "dashboard/simulator_ui.py",
        ROOT / "dashboard/map_geometry.py",
        ROOT / "dashboard/prepare_data.py",
        ROOT / "dashboard/assets/map.js",
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in active_files)
    assert "sections_national_v1" not in source
    assert "sectionPointToLayer" not in source
    assert "simulatorPointToLayer" not in source
    assert "representative_point" not in source
