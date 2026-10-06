from __future__ import annotations

import csv
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

EXPECTED_COLUMNS = [
    "AELEC",
    "FELECCION",
    "EDOCVE",
    "EDONOM",
    "MPIOCVE",
    "MPIONOM",
    "SECCION",
    "TIPOSEC",
    "DEF",
    "DEL",
    "SEXO",
    "EDAD",
    "LN",
    "SV",
    "NV",
    "NS",
]
NUMERIC_COLUMNS = [
    "AELEC",
    "EDOCVE",
    "MPIOCVE",
    "SECCION",
    "DEF",
    "DEL",
    "SEXO",
    "EDAD",
    "LN",
    "SV",
    "NV",
    "NS",
]
KEY_COLUMNS = ["AELEC", "EDOCVE", "SECCION", "SEXO", "EDAD"]


def sha256_file(path: Path, chunk_size: int = 4 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def detect_text_format(path: Path) -> dict[str, str | bool]:
    with path.open("rb") as stream:
        sample = stream.read(64 * 1024)
    has_utf8_bom = sample.startswith(b"\xef\xbb\xbf")
    first_line = sample.splitlines()[0].decode("utf-8-sig")
    delimiter_counts = {candidate: first_line.count(candidate) for candidate in [",", ";", "\t", "|"]}
    delimiter = max(delimiter_counts, key=delimiter_counts.get)
    if b"\r\n" in sample:
        line_ending = "CRLF"
    elif b"\n" in sample:
        line_ending = "LF"
    else:
        line_ending = "undetected"
    return {
        "encoding": "utf-8-sig" if has_utf8_bom else "utf-8",
        "has_utf8_bom": has_utf8_bom,
        "separator": delimiter,
        "line_ending": line_ending,
        "header": first_line,
    }


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


def _number(column: str) -> str:
    return f'try_cast("{column}" AS BIGINT)'


def audit_year(
    connection: duckdb.DuckDBPyConnection,
    year: int,
    paths: list[Path],
    project_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]], pd.DataFrame]:
    relation = _csv_relation(paths)
    view = f"year_{year}"
    connection.execute(f"CREATE OR REPLACE TEMP TABLE {view} AS SELECT * FROM {relation}")
    columns = [row[0] for row in connection.execute(f"DESCRIBE {view}").fetchall()]
    data_columns = [column for column in columns if column != "filename"]

    per_file_selects = ["filename", "count(*) AS rows"]
    for column in data_columns:
        per_file_selects.extend(
            [
                (
                    f'count(*) FILTER (WHERE "{column}" IS NULL OR trim("{column}") = \'\') '
                    f'AS "missing__{column}"'
                ),
                (
                    f'count(*) FILTER (WHERE "{column}" IS NOT NULL AND trim("{column}") = \'\') '
                    f'AS "blank__{column}"'
                ),
                f'approx_count_distinct("{column}") AS "unique__{column}"',
            ]
        )
    for column in [name for name in NUMERIC_COLUMNS if name in data_columns]:
        values = _number(column)
        per_file_selects.extend(
            [
                f'min({values}) AS "min__{column}"',
                f'max({values}) AS "max__{column}"',
                (
                    f'count(*) FILTER (WHERE "{column}" IS NOT NULL '
                    f'AND trim("{column}") != \'\' AND {values} IS NULL) '
                    f'AS "invalid__{column}"'
                ),
            ]
        )
    file_stats = connection.execute(
        f"SELECT {', '.join(per_file_selects)} FROM {view} GROUP BY filename ORDER BY filename"
    ).df()

    key_expression = ", ".join(f'"{column}"' for column in KEY_COLUMNS)
    key_duplicate_files = connection.execute(
        f"""WITH duplicated AS (
        SELECT filename, {key_expression}, count(*) AS n
        FROM {view}
        GROUP BY filename, {key_expression}
        HAVING count(*) > 1
        )
        SELECT filename, count(*) AS duplicate_key_groups,
        coalesce(sum(n - 1), 0) AS duplicate_key_extra_rows
        FROM duplicated GROUP BY filename"""
    ).df()
    full_expression = ", ".join(f'"{column}"' for column in data_columns)
    exact_duplicate_files = connection.execute(
        f"""WITH duplicated AS (
        SELECT filename, {full_expression}, count(*) AS n
        FROM {view}
        GROUP BY filename, {full_expression}
        HAVING count(*) > 1
        )
        SELECT filename, count(*) AS exact_duplicate_groups,
        coalesce(sum(n - 1), 0) AS exact_duplicate_extra_rows
        FROM duplicated GROUP BY filename"""
    ).df()
    file_stats = file_stats.merge(key_duplicate_files, on="filename", how="left").merge(
        exact_duplicate_files, on="filename", how="left"
    )
    duplicate_columns = [
        "duplicate_key_groups",
        "duplicate_key_extra_rows",
        "exact_duplicate_groups",
        "exact_duplicate_extra_rows",
    ]
    file_stats[duplicate_columns] = file_stats[duplicate_columns].fillna(0).astype("int64")
    total_rows = int(file_stats["rows"].sum())

    file_rows: list[dict[str, Any]] = []
    for row in file_stats.itertuples(index=False):
        path = Path(row.filename)
        text_format = detect_text_format(path)
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            sample_rows = []
            for _, sample_row in zip(range(3), reader):
                sample_rows.append(sample_row)
        row_values = row._asdict()
        null_counts = {column: int(row_values[f"missing__{column}"]) for column in data_columns}
        blank_counts = {column: int(row_values[f"blank__{column}"]) for column in data_columns}
        unique_counts = {column: int(row_values[f"unique__{column}"]) for column in data_columns}
        numeric_ranges = {
            column: {
                "min": row_values[f"min__{column}"],
                "max": row_values[f"max__{column}"],
                "invalid_non_null": int(row_values[f"invalid__{column}"]),
            }
            for column in NUMERIC_COLUMNS
            if column in data_columns
        }
        file_rows.append(
            {
                "year": year,
                "path": path.relative_to(project_root).as_posix(),
                "extension": path.suffix.lower(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                **text_format,
                "rows": int(row.rows),
                "column_count": len(data_columns),
                "columns_json": json.dumps(data_columns, ensure_ascii=False),
                "inferred_types_json": json.dumps(
                    {column: "VARCHAR (lectura conservadora)" for column in data_columns},
                    ensure_ascii=False,
                ),
                "null_counts_json": json.dumps(null_counts, ensure_ascii=False, sort_keys=True),
                "blank_counts_json": json.dumps(blank_counts, ensure_ascii=False, sort_keys=True),
                "unique_counts_json": json.dumps(unique_counts, ensure_ascii=False, sort_keys=True),
                "numeric_ranges_json": json.dumps(numeric_ranges, ensure_ascii=False, sort_keys=True),
                "null_pct_max": max(null_counts.values(), default=0) / max(int(row.rows), 1),
                "duplicate_key_groups": int(row.duplicate_key_groups),
                "duplicate_key_extra_rows": int(row.duplicate_key_extra_rows),
                "exact_duplicate_groups": int(row.exact_duplicate_groups),
                "exact_duplicate_extra_rows": int(row.exact_duplicate_extra_rows),
                "sample_json": json.dumps(sample_rows, ensure_ascii=False),
            }
        )

    null_counts_year = {
        column: int(file_stats[f"missing__{column}"].sum()) for column in data_columns
    }
    numeric_audit = {
        column: {
            "min": file_stats[f"min__{column}"].min(),
            "max": file_stats[f"max__{column}"].max(),
            "invalid_non_null": int(file_stats[f"invalid__{column}"].sum()),
        }
        for column in NUMERIC_COLUMNS
        if column in data_columns
    }
    duplicate_groups = int(file_stats["duplicate_key_groups"].sum())
    duplicate_extra_rows = int(file_stats["duplicate_key_extra_rows"].sum())
    exact_duplicate_groups = int(file_stats["exact_duplicate_groups"].sum())
    exact_duplicate_extra_rows = int(file_stats["exact_duplicate_extra_rows"].sum())

    accounting = connection.execute(
        f"""SELECT
        count(*) FILTER (WHERE {_number('LN')} != {_number('SV')} + {_number('NV')} + {_number('NS')}),
        max(abs({_number('LN')} - ({_number('SV')} + {_number('NV')} + {_number('NS')}))),
        sum({_number('LN')}), sum({_number('SV')}), sum({_number('NV')}), sum({_number('NS')})
        FROM {view}"""
    ).fetchone()
    denominator_counts = connection.execute(
        f"""SELECT
        count(*) FILTER (WHERE {_number('LN')} = 0),
        count(*) FILTER (WHERE {_number('SV')} + {_number('NV')} = 0)
        FROM {view}"""
    ).fetchone()

    section_counts = connection.execute(
        f"SELECT count(DISTINCT EDOCVE || ':' || SECCION) FROM {view}"
    ).fetchone()[0]
    municipality_counts = connection.execute(
        f"SELECT count(DISTINCT EDOCVE || ':' || MPIOCVE) FROM {view}"
    ).fetchone()[0]
    section_frame = connection.execute(
        f"""SELECT {year} AS year, EDOCVE, SECCION, MPIOCVE, DEF, DEL, TIPOSEC,
        count(*) AS demographic_rows,
        sum({_number('LN')}) AS nominal_list
        FROM {view}
        GROUP BY EDOCVE, SECCION, MPIOCVE, DEF, DEL, TIPOSEC
        ORDER BY EDOCVE, SECCION"""
    ).df()
    category_rows: list[dict[str, Any]] = []
    for column in ["SEXO", "EDAD", "TIPOSEC", "EDOCVE"]:
        categories = connection.execute(
            f'SELECT "{column}" AS value, count(*) AS rows, '
            f"sum({_number('LN')}) AS nominal_list FROM {view} "
            f'GROUP BY "{column}" ORDER BY "{column}"'
        ).fetchall()
        for value, rows, nominal_list in categories:
            category_rows.append(
                {
                    "year": year,
                    "column": column,
                    "value": value,
                    "rows": int(rows),
                    "nominal_list": int(nominal_list) if nominal_list is not None else None,
                }
            )

    summary = {
        "year": year,
        "files": len(paths),
        "rows": total_rows,
        "columns": data_columns,
        "schema_matches_expected": data_columns == EXPECTED_COLUMNS,
        "null_counts": null_counts_year,
        "numeric_audit": numeric_audit,
        "key_columns": KEY_COLUMNS,
        "duplicate_key_groups": int(duplicate_groups),
        "duplicate_key_extra_rows": int(duplicate_extra_rows),
        "exact_duplicate_groups": int(exact_duplicate_groups),
        "exact_duplicate_extra_rows": int(exact_duplicate_extra_rows),
        "sections": int(section_counts),
        "municipalities": int(municipality_counts),
        "accounting_mismatch_rows": int(accounting[0]),
        "accounting_max_abs_difference": int(accounting[1] or 0),
        "ln_zero_rows": int(denominator_counts[0]),
        "identified_zero_rows": int(denominator_counts[1]),
        "sum_ln": int(accounting[2] or 0),
        "sum_sv": int(accounting[3] or 0),
        "sum_nv": int(accounting[4] or 0),
        "sum_ns": int(accounting[5] or 0),
    }
    connection.execute(f"DROP TABLE {view}")
    return file_rows, summary, category_rows, section_frame


def audit_all(project_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    extracted = project_root / "data/interim/extracted"
    connection = duckdb.connect(database=":memory:")
    connection.execute("SET threads TO 4")
    connection.execute("SET memory_limit='2GB'")
    connection.execute("SET preserve_insertion_order=false")
    file_rows: list[dict[str, Any]] = []
    year_summaries: list[dict[str, Any]] = []
    category_rows: list[dict[str, Any]] = []
    section_frames: list[pd.DataFrame] = []
    started = time.perf_counter()
    for year in [2009, 2012, 2015, 2018, 2021, 2024]:
        paths = sorted((extracted / str(year)).rglob("*.csv"))
        if len(paths) != 32:
            raise ValueError(f"Se esperaban 32 CSV estatales en {year}; encontrados: {len(paths)}")
        rows, summary, categories, sections = audit_year(connection, year, paths, project_root)
        file_rows.extend(rows)
        year_summaries.append(summary)
        category_rows.extend(categories)
        section_frames.append(sections)
    connection.close()
    inventory = pd.DataFrame(file_rows)
    summaries = pd.DataFrame(year_summaries)
    categories = pd.DataFrame(category_rows)
    sections = pd.concat(section_frames, ignore_index=True)
    summaries["elapsed_total_seconds"] = round(time.perf_counter() - started, 3)
    output_dir = project_root / "artifacts/tables"
    output_dir.mkdir(parents=True, exist_ok=True)
    inventory.to_parquet(output_dir / "raw_file_inventory.parquet", index=False)
    summaries.to_json(
        output_dir / "raw_year_summary.json", orient="records", force_ascii=False, indent=2
    )
    categories.to_csv(output_dir / "category_inventory.csv", index=False)
    sections.to_parquet(output_dir / "raw_section_frame_inventory.parquet", index=False)
    return inventory, summaries, categories, sections
