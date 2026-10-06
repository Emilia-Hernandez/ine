from __future__ import annotations

import os
import time
from itertools import pairwise
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import yaml

from radar27.audit.raw_schema import EXPECTED_COLUMNS

YEARS = [2009, 2012, 2015, 2018, 2021, 2024]


def _sql_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def _csv_relation(paths: list[Path]) -> str:
    quoted = ", ".join(f"'{_sql_path(path)}'" for path in paths)
    columns = ", ".join(f"'{column}': 'VARCHAR'" for column in EXPECTED_COLUMNS)
    return (
        f"read_csv([{quoted}], header=true, auto_detect=false, delim=',', quote='\"', "
        f"escape='\"', columns={{{columns}}}, union_by_name=true, filename=true, "
        "strict_mode=true, null_padding=false)"
    )


def _replace_file(part_path: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(part_path, destination)


def _configured_years(project_root: Path) -> dict[int, dict[str, Any]]:
    with (project_root / "configs/harmonization.yaml").open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    return {int(year): values for year, values in config["years"].items()}


def _clean_select(year: int, settings: dict[str, Any]) -> str:
    family = settings["election_family"].replace("'", "''")
    source_date = settings["source_election_date"].replace("'", "''")
    election_date = settings["election_date"].replace("'", "''")
    return f"""
    SELECT
        cast(AELEC AS SMALLINT) AS election_year,
        '{family}'::VARCHAR AS election_family,
        DATE '{election_date}' AS election_date,
        FELECCION AS source_election_date,
        lpad(cast(cast(EDOCVE AS INTEGER) AS VARCHAR), 2, '0') AS entity_id,
        EDONOM AS entity_name,
        lpad(cast(cast(MPIOCVE AS INTEGER) AS VARCHAR), 3, '0') AS municipality_id,
        MPIONOM AS municipality_name,
        lpad(cast(cast(EDOCVE AS INTEGER) AS VARCHAR), 2, '0') || ':' ||
            lpad(cast(cast(MPIOCVE AS INTEGER) AS VARCHAR), 3, '0')
            AS municipality_key_observed,
        lpad(cast(cast(SECCION AS INTEGER) AS VARCHAR), 4, '0') AS section_number,
        lpad(cast(cast(EDOCVE AS INTEGER) AS VARCHAR), 2, '0') || ':' ||
            lpad(cast(cast(SECCION AS INTEGER) AS VARCHAR), 4, '0')
            AS section_key_observed,
        CASE WHEN nullif(trim(DEF), '') IS NULL THEN NULL
             ELSE lpad(cast(cast(DEF AS INTEGER) AS VARCHAR), 2, '0') END
            AS district_federal_id,
        CASE WHEN nullif(trim(DEL), '') IS NULL THEN NULL
             ELSE lpad(cast(cast(DEL AS INTEGER) AS VARCHAR), 2, '0') END
            AS district_local_id,
        TIPOSEC AS section_type_code,
        CASE TIPOSEC WHEN 'U' THEN 'urbana' WHEN 'M' THEN 'mixta' WHEN 'R' THEN 'rural' END
            AS section_type,
        cast(SEXO AS TINYINT) AS sex_code,
        CASE SEXO WHEN '0' THEN 'hombre' WHEN '1' THEN 'mujer' WHEN '2' THEN 'no_binario' END
            AS sex,
        cast(EDAD AS SMALLINT) AS age,
        cast(EDAD AS SMALLINT) > 100 AS age_review_flag,
        cast(LN AS INTEGER) AS nominal_list,
        cast(SV AS INTEGER) AS voted,
        cast(NV AS INTEGER) AS did_not_vote,
        cast(NS AS INTEGER) AS unspecified,
        cast(SV AS INTEGER) + cast(NV AS INTEGER) AS identified_records,
        cast(SV AS DOUBLE) / nullif(cast(SV AS DOUBLE) + cast(NV AS DOUBLE), 0)
            AS participation,
        cast(NV AS DOUBLE) / nullif(cast(SV AS DOUBLE) + cast(NV AS DOUBLE), 0)
            AS abstention,
        cast(NS AS DOUBLE) / nullif(cast(LN AS DOUBLE), 0) AS unspecified_share,
        (cast(SV AS DOUBLE) + cast(NV AS DOUBLE)) / nullif(cast(LN AS DOUBLE), 0)
            AS identified_coverage,
        cast(SV AS DOUBLE) / nullif(cast(LN AS DOUBLE), 0) AS voted_over_nominal_sensitivity,
        cast(AELEC AS VARCHAR) || ':' ||
            lpad(cast(cast(EDOCVE AS INTEGER) AS VARCHAR), 2, '0') || ':' ||
            lpad(cast(cast(SECCION AS INTEGER) AS VARCHAR), 4, '0') || ':' ||
            SEXO || ':' || lpad(cast(cast(EDAD AS INTEGER) AS VARCHAR), 3, '0') AS record_id,
        regexp_replace(filename, '^.*/', '') AS source_file
    FROM raw
    WHERE AELEC = '{year}' AND FELECCION = '{source_date}'
    """


def _validate_clean_year(
    connection: duckdb.DuckDBPyConnection,
    output_path: Path,
    year: int,
    expected_rows: int,
) -> dict[str, Any]:
    path = _sql_path(output_path)
    row = connection.execute(
        f"""SELECT
        count(*) AS rows,
        count(DISTINCT record_id) AS unique_record_ids,
        count(*) FILTER (WHERE election_year != {year}) AS wrong_year,
        count(*) FILTER (WHERE NOT regexp_full_match(entity_id, '[0-9]{{2}}')) AS bad_entity_id,
        count(*) FILTER (WHERE NOT regexp_full_match(municipality_id, '[0-9]{{3}}')) AS bad_municipality_id,
        count(*) FILTER (WHERE NOT regexp_full_match(section_number, '[0-9]{{4}}')) AS bad_section_id,
        count(*) FILTER (WHERE district_federal_id IS NOT NULL AND
            NOT regexp_full_match(district_federal_id, '[0-9]{{2}}')) AS bad_federal_district,
        count(*) FILTER (WHERE district_local_id IS NOT NULL AND
            NOT regexp_full_match(district_local_id, '[0-9]{{2}}')) AS bad_local_district,
        count(*) FILTER (WHERE nominal_list != voted + did_not_vote + unspecified)
            AS accounting_mismatches,
        count(*) FILTER (WHERE least(nominal_list, voted, did_not_vote, unspecified) < 0)
            AS negative_counts,
        count(*) FILTER (WHERE section_type IS NULL OR sex IS NULL) AS unmapped_categories,
        count(*) FILTER (WHERE age_review_flag) AS age_review_rows,
        count(*) FILTER (WHERE district_federal_id IS NULL) AS missing_federal_district_rows,
        count(*) FILTER (WHERE district_local_id IS NULL) AS missing_local_district_rows,
        count(*) FILTER (WHERE identified_records = 0) AS zero_identified_rows,
        count(*) FILTER (WHERE sex_code = 2) AS non_binary_rows,
        sum(nominal_list) AS sum_nominal_list,
        sum(voted) AS sum_voted,
        sum(did_not_vote) AS sum_did_not_vote,
        sum(unspecified) AS sum_unspecified
        FROM read_parquet('{path}')"""
    ).fetchone()
    names = [item[0] for item in connection.description]
    result = dict(zip(names, row))
    hard_failures = {
        "row_count": result["rows"] != expected_rows,
        "record_id_uniqueness": result["unique_record_ids"] != result["rows"],
        "wrong_year": result["wrong_year"] != 0,
        "bad_entity_id": result["bad_entity_id"] != 0,
        "bad_municipality_id": result["bad_municipality_id"] != 0,
        "bad_section_id": result["bad_section_id"] != 0,
        "bad_federal_district": result["bad_federal_district"] != 0,
        "bad_local_district": result["bad_local_district"] != 0,
        "accounting_mismatches": result["accounting_mismatches"] != 0,
        "negative_counts": result["negative_counts"] != 0,
        "unmapped_categories": result["unmapped_categories"] != 0,
    }
    failed = [name for name, value in hard_failures.items() if value]
    if failed:
        raise ValueError(f"Validacion fallida para {year}: {failed}; {result}")
    return result


def _write_provisional_aggregate(
    connection: duckdb.DuckDBPyConnection, project_root: Path
) -> tuple[pd.DataFrame, dict[str, int]]:
    source_glob = _sql_path(
        project_root / "data/interim/harmonized_demographic/*/ccpc_*_harmonized.parquet"
    )
    destination = project_root / "artifacts/tables/provisional_section_year_totals.parquet"
    part = destination.with_suffix(destination.suffix + ".part")
    if part.exists():
        part.unlink()
    part.parent.mkdir(parents=True, exist_ok=True)
    connection.execute(
        f"""COPY (
        WITH grouped AS (
          SELECT election_year, election_family, election_date, entity_id,
            any_value(entity_name) AS entity_name,
            any_value(municipality_id) AS municipality_id,
            any_value(municipality_name) AS municipality_name,
            any_value(municipality_key_observed) AS municipality_key_observed,
            section_number, section_key_observed,
            any_value(district_federal_id) AS district_federal_id,
            any_value(district_local_id) AS district_local_id,
            any_value(section_type_code) AS section_type_code,
            any_value(section_type) AS section_type,
            count(DISTINCT coalesce(municipality_id, '<NULL>')) AS municipality_variants,
            count(DISTINCT coalesce(district_federal_id, '<NULL>')) AS federal_district_variants,
            count(DISTINCT coalesce(district_local_id, '<NULL>')) AS local_district_variants,
            count(DISTINCT coalesce(section_type_code, '<NULL>')) AS section_type_variants,
            count(*) AS demographic_rows,
            sum(nominal_list) AS nominal_list,
            sum(voted) AS voted,
            sum(did_not_vote) AS did_not_vote,
            sum(unspecified) AS unspecified
          FROM read_parquet('{source_glob}')
          GROUP BY election_year, election_family, election_date, entity_id,
            section_number, section_key_observed
        )
        SELECT *, voted + did_not_vote AS identified_records,
          voted::DOUBLE / nullif(voted + did_not_vote, 0) AS participation,
          did_not_vote::DOUBLE / nullif(voted + did_not_vote, 0) AS abstention,
          unspecified::DOUBLE / nullif(nominal_list, 0) AS unspecified_share,
          (voted + did_not_vote)::DOUBLE / nullif(nominal_list, 0) AS identified_coverage,
          (municipality_variants > 1 OR federal_district_variants > 1 OR
           local_district_variants > 1 OR section_type_variants > 1)
            AS territorial_metadata_conflict,
          'observed_code_not_longitudinal_crosswalk'::VARCHAR AS geography_status
        FROM grouped
        ORDER BY election_year, entity_id, section_number
        ) TO '{_sql_path(part)}' (FORMAT PARQUET, COMPRESSION ZSTD)"""
    )
    _replace_file(part, destination)
    aggregate_path = _sql_path(destination)
    reconciliation = connection.execute(
        f"""SELECT election_year, count(*) AS sections,
        sum(demographic_rows) AS demographic_rows,
        sum(nominal_list) AS sum_nominal_list,
        sum(voted) AS sum_voted,
        sum(did_not_vote) AS sum_did_not_vote,
        sum(unspecified) AS sum_unspecified,
        count(*) FILTER (WHERE territorial_metadata_conflict) AS metadata_conflict_sections
        FROM read_parquet('{aggregate_path}') GROUP BY election_year ORDER BY election_year"""
    ).df()
    totals = connection.execute(
        f"""SELECT sum(demographic_rows), sum(nominal_list), sum(voted),
        sum(did_not_vote), sum(unspecified)
        FROM read_parquet('{aggregate_path}')"""
    ).fetchone()
    return reconciliation, {
        "rows": int(totals[0]),
        "nominal_list": int(totals[1]),
        "voted": int(totals[2]),
        "did_not_vote": int(totals[3]),
        "unspecified": int(totals[4]),
    }


def _write_transitions(project_root: Path) -> pd.DataFrame:
    frame = pd.read_parquet(project_root / "artifacts/tables/raw_section_frame_inventory.parquet")
    frame["section_key_observed"] = (
        frame["EDOCVE"].astype(str).str.zfill(2)
        + ":"
        + frame["SECCION"].astype(str).str.zfill(4)
    )
    rows: list[dict[str, int | str]] = []
    for previous, current in pairwise(YEARS):
        left = frame[frame["year"].eq(previous)].set_index("section_key_observed")
        right = frame[frame["year"].eq(current)].set_index("section_key_observed")
        shared_keys = left.index.intersection(right.index)
        shared = left.loc[shared_keys].join(
            right.loc[shared_keys], how="inner", lsuffix="_previous", rsuffix="_current"
        )
        row: dict[str, int | str] = {
            "previous_year": previous,
            "current_year": current,
            "previous_sections": len(left),
            "current_sections": len(right),
            "shared_observed_codes": len(shared_keys),
            "only_previous": len(left.index.difference(right.index)),
            "only_current": len(right.index.difference(left.index)),
            "interpretation": "nominal_overlap_not_geometric_equivalence",
        }
        for field, output in [
            ("MPIOCVE", "changed_municipality"),
            ("DEF", "changed_federal_district"),
            ("DEL", "changed_local_district"),
            ("TIPOSEC", "changed_section_type"),
        ]:
            row[output] = int(
                (
                    shared[f"{field}_previous"].fillna("<NULL>").astype(str)
                    != shared[f"{field}_current"].fillna("<NULL>").astype(str)
                ).sum()
            )
        rows.append(row)
    result = pd.DataFrame(rows)
    result.to_csv(project_root / "artifacts/tables/section_code_transition_summary.csv", index=False)
    return result


def harmonize_all(
    project_root: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Clean all configured years, validate contracts, and write provisional aggregates."""
    settings = _configured_years(project_root)
    raw_summary = pd.read_json(project_root / "artifacts/tables/raw_year_summary.json").set_index(
        "year"
    )
    connection = duckdb.connect(database=":memory:")
    connection.execute("SET threads TO 4")
    connection.execute("SET memory_limit='2GB'")
    connection.execute("SET preserve_insertion_order=false")
    summary_rows: list[dict[str, Any]] = []
    exclusion_rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    try:
        for year in YEARS:
            paths = sorted((project_root / "data/interim/extracted" / str(year)).rglob("*.csv"))
            if len(paths) != 32:
                raise ValueError(f"Se esperaban 32 CSV para {year}; encontrados: {len(paths)}")
            connection.execute(f"CREATE OR REPLACE TEMP VIEW raw AS SELECT * FROM {_csv_relation(paths)}")
            raw_count, date_count = connection.execute(
                f"""SELECT count(*), count(*) FILTER (
                WHERE AELEC = '{year}' AND FELECCION = '{settings[year]['source_election_date']}')
                FROM raw"""
            ).fetchone()
            if raw_count != date_count:
                raise ValueError(f"Año o fecha fuente inesperados en {year}: {raw_count-date_count}")
            destination = (
                project_root
                / "data/interim/harmonized_demographic"
                / str(year)
                / f"ccpc_{year}_harmonized.parquet"
            )
            part = destination.with_suffix(destination.suffix + ".part")
            part.parent.mkdir(parents=True, exist_ok=True)
            if part.exists():
                part.unlink()
            select = _clean_select(year, settings[year])
            connection.execute(
                f"COPY ({select}) TO '{_sql_path(part)}' "
                "(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 200000)"
            )
            _replace_file(part, destination)
            validated = _validate_clean_year(connection, destination, year, int(raw_count))
            expected = raw_summary.loc[year]
            if any(
                [
                    validated["sum_nominal_list"] != int(expected["sum_ln"]),
                    validated["sum_voted"] != int(expected["sum_sv"]),
                    validated["sum_did_not_vote"] != int(expected["sum_nv"]),
                    validated["sum_unspecified"] != int(expected["sum_ns"]),
                ]
            ):
                raise ValueError(f"Los totales limpios no concilian con la auditoria cruda en {year}")
            summary_rows.append(
                {
                    "year": year,
                    "election_family": settings[year]["election_family"],
                    "election_date": settings[year]["election_date"],
                    "source_election_date": settings[year]["source_election_date"],
                    "raw_rows": int(raw_count),
                    "clean_rows": int(validated["rows"]),
                    "excluded_rows": 0,
                    **{key: int(value) for key, value in validated.items() if key not in {"rows"}},
                    "output_path": destination.relative_to(project_root).as_posix(),
                }
            )
            for reason, action, field in [
                ("all_source_rows", "retained", "rows"),
                ("age_over_100_review", "flagged_retained", "age_review_rows"),
                ("missing_federal_district", "flagged_retained", "missing_federal_district_rows"),
                ("missing_local_district", "flagged_retained", "missing_local_district_rows"),
                ("zero_identified_denominator", "flagged_retained", "zero_identified_rows"),
                ("non_binary_source_category", "retained", "non_binary_rows"),
            ]:
                exclusion_rows.append(
                    {
                        "year": year,
                        "reason": reason,
                        "action": action,
                        "row_count": int(validated[field]),
                        "excluded_rows": 0,
                    }
                )
        summary = pd.DataFrame(summary_rows)
        output_dir = project_root / "artifacts/tables"
        output_dir.mkdir(parents=True, exist_ok=True)
        summary.to_csv(output_dir / "harmonization_year_summary.csv", index=False)
        exclusions = pd.DataFrame(exclusion_rows)
        exclusions.to_csv(output_dir / "cleaning_exclusion_log.csv", index=False)
        reconciliation, aggregate_totals = _write_provisional_aggregate(connection, project_root)
        expected_totals = {
            "rows": int(summary["clean_rows"].sum()),
            "nominal_list": int(summary["sum_nominal_list"].sum()),
            "voted": int(summary["sum_voted"].sum()),
            "did_not_vote": int(summary["sum_did_not_vote"].sum()),
            "unspecified": int(summary["sum_unspecified"].sum()),
        }
        if aggregate_totals != expected_totals:
            raise ValueError(
                f"El agregado provisional no concilia: {aggregate_totals} != {expected_totals}"
            )
        reconciliation.to_csv(output_dir / "aggregation_reconciliation.csv", index=False)
        transitions = _write_transitions(project_root)
        summary["elapsed_total_seconds"] = round(time.perf_counter() - started, 3)
        summary.to_csv(output_dir / "harmonization_year_summary.csv", index=False)
        return summary, exclusions, reconciliation, transitions
    finally:
        connection.close()
