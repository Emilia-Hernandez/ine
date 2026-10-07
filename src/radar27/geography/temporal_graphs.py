from __future__ import annotations

import json
import shutil
import warnings
import zipfile
from datetime import date
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
import shapely
import yaml
from scipy import sparse
from scipy.sparse.csgraph import connected_components

from radar27.geography.section_graph import (
    _build_contact_table,
    _nearest_edges_for_islands,
    sha256_file,
)


def load_temporal_graph_config(project_root: Path) -> dict[str, Any]:
    with (project_root / "configs/temporal_graphs.yaml").open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def _validate_archive(path: Path, source: dict[str, Any]) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Falta la cartografia temporal: {path}")
    if path.stat().st_size != int(source["archive_bytes"]):
        raise ValueError(f"Tamano inesperado para {path}")
    actual_hash = sha256_file(path)
    if actual_hash != source["archive_sha256"]:
        raise ValueError(f"SHA-256 inesperado para {path}: {actual_hash}")
    member_root = source["archive_member"].removesuffix(".shp")
    required = {
        source["archive_member"],
        member_root + ".shx",
        member_root + ".dbf",
        member_root + ".prj",
        source["metadata_member"],
    }
    with zipfile.ZipFile(path) as archive:
        missing = required.difference(archive.namelist())
        if missing:
            raise ValueError(f"Faltan miembros del Shapefile: {sorted(missing)}")
        metadata = ElementTree.fromstring(archive.read(source["metadata_member"]))
        creation_value = metadata.findtext(".//CreaDate")
        if creation_value != source["geometry_created_on"].replace("-", ""):
            raise ValueError("La fecha CreaDate del XML no coincide con la configuracion")
        with archive.open(member_root + ".dbf") as dbf_stream:
            header = dbf_stream.read(4)
        dbf_date = date(1900 + header[1], header[2], header[3]).isoformat()
        if dbf_date != source["dbf_last_update"]:
            raise ValueError("La fecha del encabezado DBF no coincide con la configuracion")


def download_temporal_archives(project_root: Path, force: bool = False) -> list[Path]:
    config = load_temporal_graph_config(project_root)
    destinations = []
    for source in config["snapshots"].values():
        destination = project_root / source["local_archive"]
        if destination.is_file() and not force:
            _validate_archive(destination, source)
            destinations.append(destination)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".part")
        with requests.get(source["download_url"], stream=True, timeout=(30, 300)) as response:
            response.raise_for_status()
            with temporary.open("wb") as output:
                shutil.copyfileobj(response.raw, output, length=1024 * 1024)
        try:
            _validate_archive(temporary, source)
            temporary.replace(destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        destinations.append(destination)
    return destinations


def _column(frame: pd.DataFrame, aliases: list[str]) -> pd.Series:
    columns = {column.upper(): column for column in frame.columns}
    for alias in aliases:
        if alias.upper() in columns:
            return frame[columns[alias.upper()]]
    return pd.Series(pd.NA, index=frame.index, dtype="Int64")


def _load_snapshot(
    project_root: Path, source: dict[str, Any]
) -> tuple[gpd.GeoDataFrame, dict[str, int]]:
    archive = project_root / source["local_archive"]
    _validate_archive(archive, source)
    virtual_path = f"/vsizip/{archive.resolve()}/{source['archive_member']}"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        geometry_check = gpd.read_file(virtual_path, columns=[], on_invalid="warn")
        raw = gpd.read_file(virtual_path, on_invalid="fix")
    ring_repairs = int(geometry_check.geometry.isna().sum())
    if ring_repairs != int(source["expected_wkb_ring_repairs"]):
        raise ValueError("Cambio inesperado en el numero de anillos no cerrados")
    if len(raw) != int(source["expected_feature_count"]):
        raise ValueError("El numero de geometrias no coincide con la fuente congelada")
    if raw.crs is None or not raw.crs.is_projected:
        raise ValueError("La capa temporal no tiene un CRS proyectado")
    if raw.geometry.isna().any() or raw.geometry.is_empty.any():
        raise ValueError("La lectura reparada contiene geometrias nulas o vacias")
    invalid = ~raw.geometry.is_valid
    make_valid_repairs = int(invalid.sum())
    if make_valid_repairs != int(source["expected_make_valid_repairs"]):
        raise ValueError("Cambio inesperado en el numero de geometrias invalidas")
    if make_valid_repairs:
        raw.loc[invalid, "geometry"] = shapely.make_valid(raw.loc[invalid, "geometry"].array)
    if not raw.geometry.is_valid.all():
        raise ValueError("Persisten geometrias invalidas despues de la reparacion explicita")

    normalized = gpd.GeoDataFrame(
        {
            "ENTIDAD": _column(raw, ["ENTIDAD"]).astype("Int64"),
            "MUNICIPIO": _column(raw, ["MUNICIPIO"]).astype("Int64"),
            "DISTRITO_F": _column(raw, ["DISTRITO_F", "DISTRITO"]).astype("Int64"),
            "DISTRITO_L": _column(raw, ["DISTRITO_L"]).astype("Int64"),
            "SECCION": _column(raw, ["SECCION"]).astype("Int64"),
            "TIPO": _column(raw, ["TIPO"]).astype("Int64"),
            "LN": _column(raw, ["LN", "LISTAN", "LISTA"]).astype("Int64"),
            "PAD": _column(raw, ["PAD", "PADRON"]).astype("Int64"),
        },
        geometry=raw.geometry,
        crs=raw.crs,
    )
    if normalized[["ENTIDAD", "SECCION"]].isna().any().any():
        raise ValueError("La fuente no contiene llaves entidad/seccion completas")
    normalized["section_key"] = normalized["ENTIDAD"].map(
        lambda value: f"{int(value):02d}"
    ) + ":" + normalized["SECCION"].map(lambda value: f"{int(value):04d}")
    if normalized["section_key"].duplicated().any():
        raise ValueError("La fuente temporal contiene llaves duplicadas")
    return normalized.sort_values("section_key").reset_index(drop=True), {
        "wkb_ring_repairs": ring_repairs,
        "make_valid_repairs": make_valid_repairs,
    }


def _model_universe(
    project_root: Path,
    config: dict[str, Any],
    year: int,
    source_sections: gpd.GeoDataFrame,
) -> tuple[gpd.GeoDataFrame, pd.DataFrame, pd.DataFrame, float]:
    universe_config = config["model_universe"]
    observed = pd.read_parquet(
        project_root / universe_config["table"],
        filters=[(universe_config["year_column"], "=", year)],
        columns=[universe_config["key_column"]],
    )
    observed_keys = pd.Index(observed[universe_config["key_column"]].astype(str).unique())
    source_keys = pd.Index(source_sections["section_key"])
    covered_keys = observed_keys.intersection(source_keys)
    selected = source_sections[source_sections["section_key"].isin(covered_keys)].copy()
    selected = selected.sort_values("section_key").reset_index(drop=True)
    selected["node_id"] = np.arange(len(selected), dtype=np.int64)
    missing = pd.DataFrame({"section_key": observed_keys.difference(source_keys)})
    missing["exclusion_reason"] = "observed_section_without_contemporary_geometry"
    extra = source_sections[~source_sections["section_key"].isin(observed_keys)][
        ["section_key"]
    ].copy()
    extra["exclusion_reason"] = "geometry_not_observed_in_target_election"
    coverage = len(covered_keys) / len(observed_keys)
    return selected, missing, extra, float(coverage)


def _assemble_edges(
    sections: gpd.GeoDataFrame, contacts: pd.DataFrame, snapped: np.ndarray
) -> pd.DataFrame:
    rook = contacts[contacts["passes_rook_threshold"]].copy()
    rook["edge_type"] = "rook_shared_boundary"
    rook["gap_distance_m"] = 0.0
    rook["is_synthetic"] = False
    columns = [
        "source_node_id",
        "target_node_id",
        "source_section_key",
        "target_section_key",
        "edge_type",
        "shared_boundary_m",
        "gap_distance_m",
        "is_synthetic",
    ]
    rook = rook[columns]
    nearest = _nearest_edges_for_islands(sections, snapped, rook)
    edges = pd.concat([rook, nearest[columns]], ignore_index=True)
    edges = edges.drop_duplicates(["source_node_id", "target_node_id"], keep="first")
    entities = sections["ENTIDAD"].to_numpy()
    municipalities = sections["MUNICIPIO"].to_numpy()
    source_ids = edges["source_node_id"].to_numpy(dtype=np.int64)
    target_ids = edges["target_node_id"].to_numpy(dtype=np.int64)
    edges["same_entity"] = entities[source_ids] == entities[target_ids]
    edges["same_municipality"] = edges["same_entity"] & (
        municipalities[source_ids] == municipalities[target_ids]
    )
    return edges.sort_values(["source_node_id", "target_node_id"]).reset_index(drop=True)


def _export_snapshot(
    project_root: Path,
    config: dict[str, Any],
    year: int,
    source: dict[str, Any],
    sections: gpd.GeoDataFrame,
    missing: pd.DataFrame,
    extra: pd.DataFrame,
    coverage: float,
    repairs: dict[str, int],
) -> dict[str, Any]:
    topology = config["geometry_policy"]
    contacts, snapped = _build_contact_table(
        sections,
        float(topology["precision_grid_m"]),
        float(topology["minimum_shared_boundary_m"]),
    )
    edges = _assemble_edges(sections, contacts, snapped)
    source_ids = edges["source_node_id"].to_numpy(dtype=np.int64)
    target_ids = edges["target_node_id"].to_numpy(dtype=np.int64)
    rows = np.concatenate([source_ids, target_ids])
    columns = np.concatenate([target_ids, source_ids])
    adjacency = sparse.csr_matrix(
        (np.ones(len(rows), dtype=np.float32), (rows, columns)),
        shape=(len(sections), len(sections)),
    )
    adjacency.sum_duplicates()
    adjacency.data[:] = 1.0
    component_count, component_ids = connected_components(adjacency, directed=False)
    degree = np.asarray(adjacency.sum(axis=1)).ravel().astype(np.int32)
    centroids = gpd.GeoSeries(shapely.centroid(snapped), crs=sections.crs).to_crs(4326)
    nodes = pd.DataFrame(
        {
            "node_id": sections["node_id"].astype(np.int64),
            "section_key": sections["section_key"],
            "entity_id": sections["ENTIDAD"].map(lambda value: f"{int(value):02d}"),
            "municipality_code": sections["MUNICIPIO"],
            "federal_district": sections["DISTRITO_F"],
            "local_district": sections["DISTRITO_L"],
            "section_code": sections["SECCION"],
            "section_type": sections["TIPO"],
            "source_nominal_list": sections["LN"],
            "source_electoral_roll": sections["PAD"],
            "centroid_lon": centroids.x.astype(float),
            "centroid_lat": centroids.y.astype(float),
            "area_m2": shapely.area(snapped).astype(float),
            "degree": degree,
            "component_id": component_ids.astype(np.int32),
        }
    )
    output = project_root / config["outputs"]["directory"] / str(year)
    output.mkdir(parents=True, exist_ok=True)
    nodes.to_parquet(output / "nodes.parquet", index=False)
    contacts.to_parquet(output / "contacts.parquet", index=False)
    edges.to_parquet(output / "edges.parquet", index=False)
    pd.concat([missing, extra], ignore_index=True).to_csv(output / "exclusions.csv", index=False)
    sparse.save_npz(output / "adjacency.npz", adjacency, compressed=True)
    np.savez_compressed(
        output / "edge_index.npz",
        edge_index=np.vstack([rows, columns]),
        edge_weight=np.ones(len(rows), dtype=np.float32),
        section_keys=nodes["section_key"].to_numpy(dtype=str),
        num_nodes=np.array([len(nodes)], dtype=np.int64),
    )
    metadata = {
        "target_year": year,
        "election_date": source["election_date"],
        "geometry_created_on": source["geometry_created_on"],
        "dbf_last_update": source["dbf_last_update"],
        "archive_sha256": source["archive_sha256"],
        "source_feature_count": int(source["expected_feature_count"]),
        "observed_sections": len(sections) + len(missing),
        "covered_nodes": len(sections),
        "key_coverage": coverage,
        "observed_sections_without_geometry": len(missing),
        "source_geometries_not_observed": len(extra),
        "repairs": repairs,
        "topology": topology,
        "quality": {
            "undirected_edges": len(edges),
            "rook_edges": int(edges["edge_type"].eq("rook_shared_boundary").sum()),
            "synthetic_edges": int(edges["is_synthetic"].sum()),
            "point_contacts_excluded": int(contacts["contact_dimension"].eq("point").sum()),
            "connected_components": int(component_count),
            "isolated_nodes_after_fallback": int((degree == 0).sum()),
            "symmetric": bool((adjacency != adjacency.T).nnz == 0),
            "self_loops": int(adjacency.diagonal().sum()),
            "minimum_degree": int(degree.min()),
            "median_degree": float(np.median(degree)),
            "maximum_degree": int(degree.max()),
        },
    }
    with (output / "metadata.json").open("w", encoding="utf-8") as stream:
        json.dump(metadata, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    return metadata


def build_temporal_graphs(project_root: Path) -> dict[int, dict[str, Any]]:
    config = load_temporal_graph_config(project_root)
    manifest_rows = []
    results = {}
    for year_value, source in config["snapshots"].items():
        year = int(year_value)
        if date.fromisoformat(source["dbf_last_update"]) > date.fromisoformat(
            source["election_date"]
        ):
            raise ValueError(f"La cartografia {year} es posterior a la eleccion")
        sections, repairs = _load_snapshot(project_root, source)
        selected, missing, extra, coverage = _model_universe(
            project_root, config, year, sections
        )
        if coverage < float(source["minimum_key_coverage"]):
            raise ValueError(f"Cobertura cartografica insuficiente para {year}: {coverage:.3%}")
        results[year] = _export_snapshot(
            project_root,
            config,
            year,
            source,
            selected,
            missing,
            extra,
            coverage,
            repairs,
        )
        archive = project_root / source["local_archive"]
        manifest_rows.append(
            {
                "target_year": year,
                "election_date": source["election_date"],
                "authority": source["authority"],
                "title": source["title"],
                "landing_url": source.get("landing_url", ""),
                "download_url": source["download_url"],
                "local_archive": source["local_archive"],
                "bytes": archive.stat().st_size,
                "sha256": sha256_file(archive),
                "geometry_created_on": source["geometry_created_on"],
                "dbf_last_update": source["dbf_last_update"],
                "covered_nodes": results[year]["covered_nodes"],
                "key_coverage": results[year]["key_coverage"],
            }
        )
    manifest = pd.DataFrame(manifest_rows).sort_values("target_year")
    manifest_path = project_root / config["outputs"]["source_manifest"]
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(manifest_path, index=False)
    return results
