from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
YEARS = {2009, 2012, 2015, 2018, 2021, 2024}


def test_all_rows_are_retained_and_ids_are_unique() -> None:
    summary = pd.read_csv(ROOT / "artifacts/tables/harmonization_year_summary.csv")
    assert set(summary["year"]) == YEARS
    assert int(summary["raw_rows"].sum()) == 54_872_712
    assert int(summary["clean_rows"].sum()) == 54_872_712
    assert int(summary["excluded_rows"].sum()) == 0
    assert summary["clean_rows"].eq(summary["unique_record_ids"]).all()
    assert summary["accounting_mismatches"].eq(0).all()
    assert summary["negative_counts"].eq(0).all()
    assert summary["unmapped_categories"].eq(0).all()


def test_clean_parquet_types_dates_ids_and_ratios() -> None:
    parquet_glob = (
        ROOT / "data/interim/harmonized_demographic/*/ccpc_*_harmonized.parquet"
    ).as_posix()
    connection = duckdb.connect(database=":memory:")
    try:
        row = connection.execute(
            f"""SELECT
            count(*),
            count(*) FILTER (WHERE NOT regexp_full_match(entity_id, '[0-9]{{2}}')),
            count(*) FILTER (WHERE NOT regexp_full_match(municipality_id, '[0-9]{{3}}')),
            count(*) FILTER (WHERE NOT regexp_full_match(section_number, '[0-9]{{4}}')),
            count(*) FILTER (WHERE nominal_list != voted + did_not_vote + unspecified),
            count(*) FILTER (WHERE identified_records > 0 AND
                abs(participation + abstention - 1.0) > 1e-12),
            count(*) FILTER (WHERE identified_records = 0 AND
                (participation IS NOT NULL OR abstention IS NOT NULL)),
            count(DISTINCT record_id)
            FROM read_parquet('{parquet_glob}')"""
        ).fetchone()
    finally:
        connection.close()
    assert row == (54_872_712, 0, 0, 0, 0, 0, 0, 54_872_712)


def test_exact_election_date_contract() -> None:
    with (ROOT / "configs/harmonization.yaml").open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    expected = {
        2009: ("5/7/2009", "2009-07-05", "midterm"),
        2012: ("1/7/2012", "2012-07-01", "presidential"),
        2015: ("7/6/2015", "2015-06-07", "midterm"),
        2018: ("1/7/2018", "2018-07-01", "presidential"),
        2021: ("6/6/2021", "2021-06-06", "midterm"),
        2024: ("06/02/2024", "2024-06-02", "presidential"),
    }
    observed = {
        int(year): (
            values["source_election_date"],
            values["election_date"],
            values["election_family"],
        )
        for year, values in config["years"].items()
    }
    assert observed == expected


def test_provisional_aggregate_reconciles_without_claiming_crosswalk() -> None:
    aggregate = ROOT / "artifacts/tables/provisional_section_year_totals.parquet"
    connection = duckdb.connect(database=":memory:")
    try:
        status = connection.execute(
            f"""SELECT count(*), count(DISTINCT election_year),
            count(*) FILTER (WHERE geography_status !=
                'observed_code_not_longitudinal_crosswalk'),
            sum(demographic_rows), sum(nominal_list), sum(voted),
            sum(did_not_vote), sum(unspecified)
            FROM read_parquet('{aggregate.as_posix()}')"""
        ).fetchone()
    finally:
        connection.close()
    raw = pd.read_json(ROOT / "artifacts/tables/raw_year_summary.json")
    assert status[0] == 406_866
    assert status[1] == 6
    assert status[2] == 0
    assert status[3] == 54_872_712
    assert status[4] == int(raw["sum_ln"].sum())
    assert status[5] == int(raw["sum_sv"].sum())
    assert status[6] == int(raw["sum_nv"].sum())
    assert status[7] == int(raw["sum_ns"].sum())


def test_exclusion_log_and_geography_gate() -> None:
    exclusions = pd.read_csv(ROOT / "artifacts/tables/cleaning_exclusion_log.csv")
    assert exclusions["excluded_rows"].eq(0).all()
    assert not exclusions["action"].eq("excluded").any()
    with (ROOT / "configs/geography_sources.yaml").open(encoding="utf-8") as stream:
        geography = yaml.safe_load(stream)
    assert geography["status"] == (
        "spatial_adjacency_available_historical_crosswalk_request_required"
    )
    assert geography["crosswalk_downloaded"] is False
    assert geography["geometry_downloaded"] is True
