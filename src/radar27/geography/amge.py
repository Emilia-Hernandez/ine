from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

SECTION_COLUMNS = {
    "origin_full_removed": 7,
    "origin_full_affected": 8,
    "origin_partial_affected": 9,
    "destination_integrated_section": 14,
    "destination_other_geography": 15,
    "destination_new": 16,
}
ORIGIN_COLUMNS = list(SECTION_COLUMNS)[:3]
DESTINATION_COLUMNS = list(SECTION_COLUMNS)[3:]
ELIGIBLE_CASES = {"DIVISION DE SECCIONES", "FUSION DE SECCIONES"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_text(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    return "".join(character for character in text if not unicodedata.combining(character)).strip().upper()


def expand_sections(value: Any) -> list[int]:
    """Expand hyphen ranges; commas and Spanish 'Y' denote discrete section codes."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return []
    if isinstance(value, (int, float)) and float(value).is_integer():
        return [int(value)]
    text = str(value).strip().replace("–", "-").replace("—", "-")
    if not text:
        return []
    parts = re.split(r"\s*(?:,|\b[Yy]\b)\s*", text)
    values: list[int] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        range_match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", part)
        if range_match:
            start, end = map(int, range_match.groups())
            if end < start or end - start > 500:
                raise ValueError(f"Rango seccional invalido o demasiado amplio: {value!r}")
            values.extend(range(start, end + 1))
        elif re.fullmatch(r"\d+(?:\.0)?", part):
            values.append(int(float(part)))
        else:
            raise ValueError(f"Expresion seccional no reconocida: {value!r}")
    return sorted(set(values))


def _year_from_value(value: Any, program: str, approval: str) -> int | None:
    candidates = [value, program, approval]
    for candidate in candidates:
        if isinstance(candidate, pd.Timestamp):
            return int(candidate.year)
        if isinstance(candidate, (int, float)) and not pd.isna(candidate):
            integer = int(candidate)
            if 2000 <= integer <= 2100:
                return integer
        match = re.search(r"20\d{2}", str(candidate))
        if match:
            return int(match.group())
    return None


def _key(entity_code: int, section: int) -> str:
    return f"{entity_code:02d}:{section:04d}"


def parse_amge_workbook(project_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    with (project_root / "configs/public_geography.yaml").open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    source = config["sources"]["amge_history"]
    workbook = project_root / source["local_workbook"]
    if sha256_file(workbook) != source["workbook_sha256"]:
        raise ValueError("El hash del libro AMGE no coincide con la configuracion versionada")

    raw = pd.read_excel(workbook, header=None, skiprows=14)
    raw = raw.rename(
        columns={
            1: "entity_code",
            2: "entity_name",
            3: "origin_federal_district",
            4: "origin_local_district",
            5: "origin_municipality_code",
            6: "origin_municipality_name",
            10: "destination_federal_district",
            11: "destination_local_district",
            12: "destination_municipality_code",
            13: "destination_municipality_name",
            17: "program",
            18: "case_label",
            19: "initiating_document",
            20: "approval_document",
            21: "effective_value",
            **{index: name for name, index in SECTION_COLUMNS.items()},
        }
    )
    keep_columns = [
        "entity_code",
        "entity_name",
        "origin_federal_district",
        "origin_local_district",
        "origin_municipality_code",
        "origin_municipality_name",
        *ORIGIN_COLUMNS,
        "destination_federal_district",
        "destination_local_district",
        "destination_municipality_code",
        "destination_municipality_name",
        *DESTINATION_COLUMNS,
        "program",
        "case_label",
        "initiating_document",
        "approval_document",
        "effective_value",
    ]
    raw = raw[keep_columns].copy()
    raw["source_excel_row"] = raw.index + 15
    event_context = [
        "entity_code",
        "entity_name",
        "program",
        "case_label",
        "initiating_document",
        "approval_document",
        "effective_value",
    ]
    raw[event_context] = raw[event_context].ffill()
    section_fields = ORIGIN_COLUMNS + DESTINATION_COLUMNS
    raw = raw[raw[section_fields].notna().any(axis=1)].copy()

    event_rows: list[dict[str, Any]] = []
    edge_rows: list[dict[str, Any]] = []
    affected_rows: list[dict[str, Any]] = []
    for item in raw.itertuples(index=False):
        values = item._asdict()
        entity_code = int(values["entity_code"])
        origin_by_status = {
            field: expand_sections(values[field]) for field in ORIGIN_COLUMNS
        }
        destination_by_status = {
            field: expand_sections(values[field]) for field in DESTINATION_COLUMNS
        }
        origins = sorted({section for sections in origin_by_status.values() for section in sections})
        destinations = sorted(
            {section for sections in destination_by_status.values() for section in sections}
        )
        case_normalized = normalize_text(values["case_label"])
        effective_year = _year_from_value(
            values["effective_value"], values["program"], values["approval_document"]
        )
        mapping_shape = "one_to_many" if len(origins) == 1 else "many_to_one" if len(destinations) == 1 else "many_to_many"
        lineage_eligible = (
            case_normalized in ELIGIBLE_CASES
            and bool(origins)
            and bool(destinations)
            and mapping_shape in {"one_to_many", "many_to_one"}
            and effective_year is not None
        )
        event_id = f"AMGE-{int(values['source_excel_row']):04d}"
        event = {
            "event_id": event_id,
            "source_excel_row": int(values["source_excel_row"]),
            "entity_id": f"{entity_code:02d}",
            "entity_name": values["entity_name"],
            "program": values["program"],
            "case_label": values["case_label"],
            "case_normalized": case_normalized,
            "effective_year": effective_year,
            "origin_sections_json": json.dumps(origins),
            "destination_sections_json": json.dumps(destinations),
            "origin_count": len(origins),
            "destination_count": len(destinations),
            "mapping_shape": mapping_shape,
            "lineage_eligible": lineage_eligible,
            "initiating_document": values["initiating_document"],
            "approval_document": values["approval_document"],
        }
        event_rows.append(event)
        for role, mapping in [("origin", origin_by_status), ("destination", destination_by_status)]:
            for status, sections in mapping.items():
                for section in sections:
                    affected_rows.append(
                        {
                            "event_id": event_id,
                            "effective_year": effective_year,
                            "section_key_observed": _key(entity_code, section),
                            "role": role,
                            "status_field": status,
                            "lineage_eligible": lineage_eligible,
                            "case_normalized": case_normalized,
                        }
                    )
        if lineage_eligible:
            for origin in origins:
                for destination in destinations:
                    edge_rows.append(
                        {
                            "event_id": event_id,
                            "effective_year": effective_year,
                            "origin_section_key": _key(entity_code, origin),
                            "destination_section_key": _key(entity_code, destination),
                            "case_normalized": case_normalized,
                            "mapping_shape": mapping_shape,
                            "source_excel_row": int(values["source_excel_row"]),
                        }
                    )

    events = pd.DataFrame(event_rows).sort_values(["effective_year", "source_excel_row"])
    edges = pd.DataFrame(edge_rows).drop_duplicates().sort_values(
        ["effective_year", "event_id", "origin_section_key", "destination_section_key"]
    )
    affected = pd.DataFrame(affected_rows).drop_duplicates().sort_values(
        ["effective_year", "event_id", "section_key_observed", "role"]
    )
    output = project_root / "artifacts/tables"
    output.mkdir(parents=True, exist_ok=True)
    events.to_parquet(output / "amge_event_rows.parquet", index=False)
    edges.to_parquet(output / "amge_lineage_edges.parquet", index=False)
    affected.to_parquet(output / "amge_affected_sections.parquet", index=False)
    return events, edges, affected


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, item: str) -> str:
        self.parent.setdefault(item, item)
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, left: str, right: str) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root == right_root:
            return
        smaller, larger = sorted([left_root, right_root])
        self.parent[larger] = smaller


def lineage_components(edges: pd.DataFrame, target_year: int) -> pd.DataFrame:
    available = edges[edges["effective_year"].lt(target_year)].copy()
    union_find = UnionFind()
    event_by_member: dict[str, set[str]] = defaultdict(set)
    for row in available.itertuples(index=False):
        union_find.union(row.origin_section_key, row.destination_section_key)
        event_by_member[row.origin_section_key].add(row.event_id)
        event_by_member[row.destination_section_key].add(row.event_id)
    groups: dict[str, list[str]] = defaultdict(list)
    for member in union_find.parent:
        groups[union_find.find(member)].append(member)
    records = []
    for members in groups.values():
        members = sorted(members)
        component_id = "L:" + members[0]
        event_ids = sorted({event for member in members for event in event_by_member[member]})
        for member in members:
            records.append(
                {
                    "target_year": target_year,
                    "amge_component_id": component_id,
                    "section_key_observed": member,
                    "component_members": len(members),
                    "event_ids": "|".join(event_ids),
                    "max_event_year": int(
                        available[
                            available["event_id"].isin(event_ids)
                        ]["effective_year"].max()
                    ),
                }
            )
    return pd.DataFrame(records)


def write_public_source_manifest(project_root: Path) -> pd.DataFrame:
    with (project_root / "configs/public_geography.yaml").open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    rows = []
    for source_id, source in config["sources"].items():
        local = source.get("local_workbook")
        path = project_root / local if local else None
        rows.append(
            {
                "source_id": source_id,
                "title": source["title"],
                "authority": source["authority"],
                "official_url": source.get("official_resolution_url", source.get("catalog_url", source.get("landing_url"))),
                "public_data_url": source.get("public_folder_url", source.get("workbook_url", source.get("catalog_url"))),
                "access": source["access"],
                "local_path": local or "",
                "local_exists": bool(path and path.is_file()),
                "bytes": path.stat().st_size if path and path.is_file() else None,
                "sha256": sha256_file(path) if path and path.is_file() else "",
                "use_in_this_phase": source.get("use_in_this_phase", "parsed_lineage_source"),
            }
        )
    manifest = pd.DataFrame(rows)
    destination = project_root / "data/manifests/public_geography_manifest.csv"
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(destination, index=False)
    return manifest


def keys_for_status(
    affected: pd.DataFrame, target_year: int, eligible: bool
) -> set[str]:
    rows = affected[
        affected["effective_year"].lt(target_year)
        & affected["lineage_eligible"].eq(eligible)
    ]
    return set(rows["section_key_observed"])


def iterable_to_json(values: Iterable[str]) -> str:
    return json.dumps(sorted(set(values)), ensure_ascii=False)
