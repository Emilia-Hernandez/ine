from __future__ import annotations

import gzip
import hashlib
import json

from dashboard.app import ASSET_PREFIX, NATIONAL_MAP_PATH, NATIONAL_MAP_URL, ROOT, server
from dashboard.map_geometry import NATIONAL_MAP_URL as DEFAULT_NATIONAL_MAP_URL
from dashboard.map_geometry import geometry_spec


def test_national_map_is_compact_complete_and_versioned() -> None:
    assert NATIONAL_MAP_PATH.exists()
    assert NATIONAL_MAP_PATH.stat().st_size < 2_000_000
    payload = json.loads(gzip.decompress(NATIONAL_MAP_PATH.read_bytes()))
    features = payload["features"]
    assert len(features) == 70_751
    assert len({feature["properties"]["k"] for feature in features}) == 70_751
    assert {feature["geometry"]["type"] for feature in features} == {"Point"}
    assert set(features[0]["properties"]) == {"k", "p", "r", "s", "a", "b"}


def test_national_map_response_is_compressed_and_immutable() -> None:
    response = server.test_client().get(NATIONAL_MAP_URL)
    assert response.status_code == 200
    assert response.headers["Content-Encoding"] == "gzip"
    assert response.headers["Cache-Control"] == "public, max-age=31536000, immutable"
    assert int(response.headers["Content-Length"]) == NATIONAL_MAP_PATH.stat().st_size
    assert len(json.loads(gzip.decompress(response.data))["features"]) == 70_751


def test_active_release_paths_and_partial_content() -> None:
    release = json.loads((ROOT / "dashboard/data/current_release.json").read_text())
    assert ASSET_PREFIX == release["asset_prefix"]
    assert NATIONAL_MAP_URL.endswith(
        hashlib.sha256(NATIONAL_MAP_PATH.read_bytes()).hexdigest()[:12] + ".geojson"
    )
    assets = ROOT / "dashboard" / ASSET_PREFIX.lstrip("/")
    client = server.test_client()
    for name in ("sections_overview.fgb", "sections_detail.fgb"):
        path = assets / name
        assert path.is_file()
        response = client.get(f"{ASSET_PREFIX}/{name}", headers={"Range": "bytes=0-1023"})
        assert response.status_code == 206
        assert response.headers["Content-Range"] == f"bytes 0-1023/{path.stat().st_size}"
        assert int(response.headers["Content-Length"]) == 1024
        assert response.headers["Cache-Control"] == "public, max-age=31536000, immutable"


def test_geometry_levels_and_quantized_bboxes() -> None:
    assert geometry_spec("/assets/release", 4, None) == (
        DEFAULT_NATIONAL_MAP_URL,
        "geojson",
        {},
    )
    first = geometry_spec("/assets/release", 7, [[19.01, -100.01], [19.99, -99.01]])
    nearby = geometry_spec("/assets/release", 7, [[19.02, -100.02], [19.98, -99.02]])
    assert first == nearby
    assert first[0].endswith("sections_detail.fgb")
    assert first[1] == "flatgeobuf"


def test_simulator_map_is_deferred_until_tab_activation() -> None:
    layout = server.test_client().get("/_dash-layout").get_json()

    def find(component: object, target: str) -> dict[str, object] | None:
        if isinstance(component, dict):
            props = component.get("props", {})
            if props.get("id") == target:
                return props
            for value in component.values():
                found = find(value, target)
                if found:
                    return found
        elif isinstance(component, list):
            for value in component:
                found = find(value, target)
                if found:
                    return found
        return None

    explorer = find(layout, "section-geo")
    simulator = find(layout, "sim-section-geo")
    assert explorer is not None and explorer["url"] == NATIONAL_MAP_URL
    assert simulator is not None and simulator.get("url") is None
