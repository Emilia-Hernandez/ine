from __future__ import annotations

from dashboard.app import CURRENT_RELEASE, server
from dashboard.simulator_app import server as simulator_server


def test_healthz_reports_frozen_release() -> None:
    response = server.test_client().get("/healthz")
    assert response.status_code == 200
    assert response.json == {
        "status": "ok",
        "release": "radar27-dashboard-intervention-simulator.1",
        "model": "radar27-final-2027-municipal.1",
    }
    assert CURRENT_RELEASE["model_id"] == "A_nacional_actual"

    simulator_response = simulator_server.test_client().get("/healthz")
    assert simulator_response.status_code == 200
    assert simulator_response.json == {
        "status": "ok",
        "application": "simulator",
        "release": "radar27-dashboard-intervention-simulator.1",
        "model": "radar27-final-2027-municipal.1",
    }


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
        assert len(header) == 180
        assert header[-1] == "metadatos_filtros_json"
        assert "did_not_vote_2009" in header
        assert "unspecified_2024" in header
    finally:
        response.close()


def test_simulator_download_endpoints_are_streamed_and_reproducible() -> None:
    query = {
        "profiles": "P1,P2,P3,P4,P5,P6,EI_AB,EI_CD",
        "include_ei": "1",
        "density": 100,
        "security": 100,
        "period": "cumulative",
        "threshold": 63,
        "count": 3,
        "seed": 42,
    }
    client = simulator_server.test_client()
    response = client.get(
        "/download/simulation-sections.csv", query_string=query, buffered=False
    )
    try:
        iterator = iter(response.response)
        bom = next(iterator).decode("utf-8")
        first_chunk = next(iterator).decode("utf-8")
        assert response.status_code == 200
        assert bom == "\ufeff"
        assert "Content-Length" not in response.headers
        assert "parametros_filtros_json" in first_chunk.splitlines()[0]
        assert '""semilla"": 42' in first_chunk
    finally:
        response.close()

    aggregate = client.get(
        "/download/simulation-aggregate.csv", query_string=query
    )
    assert aggregate.status_code == 200
    assert aggregate.data.startswith("\ufeff".encode("utf-8"))
    assert b"intervencion" in aggregate.data
    assert b"prioridad" in aggregate.data
