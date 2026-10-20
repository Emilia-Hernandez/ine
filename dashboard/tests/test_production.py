from __future__ import annotations

from dashboard.app import CURRENT_RELEASE, server


def test_healthz_reports_frozen_release() -> None:
    response = server.test_client().get("/healthz")
    assert response.status_code == 200
    assert response.json == {
        "status": "ok",
        "release": "radar27-dashboard-security.5",
        "model": "radar27-final-2027-municipal.1",
    }
    assert CURRENT_RELEASE["model_id"] == "A_nacional_actual"


def test_download_endpoint_streams_full_contract() -> None:
    response = server.test_client().get(
        "/download/sections.csv",
        query_string={"profiles": "P1", "density": 100, "security": 100},
        buffered=False,
    )
    try:
        first_chunk = next(iter(response.response)).decode("utf-8-sig")
        header = first_chunk.splitlines()[0].split(",")
        assert response.status_code == 200
        assert response.headers["Content-Disposition"].startswith("attachment;")
        assert "Content-Length" not in response.headers
        assert len(header) == 164
        assert header[-1] == "metadatos_filtros_json"
        assert "did_not_vote_2009" in header
        assert "unspecified_2024" in header
    finally:
        response.close()
