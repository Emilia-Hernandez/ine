from __future__ import annotations

import hashlib
import json
import shutil
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_config(project_root: Path) -> dict[str, Any]:
    with (project_root / "configs/spatial_graph.yaml").open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def download_section_archive(project_root: Path, force: bool = False) -> Path:
    """Download atomically and accept only the exact archive frozen in configuration."""
    config = load_config(project_root)
    source = config["source"]
    destination = project_root / source["local_archive"]
    if destination.is_file() and not force:
        _validate_archive(destination, source)
        return destination

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
    return destination


def _validate_archive(path: Path, source: dict[str, Any]) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Falta la cartografia seccional: {path}")
    if path.stat().st_size != int(source["archive_bytes"]):
        raise ValueError(f"Tamano inesperado para {path}")
    actual_hash = sha256_file(path)
    if actual_hash != source["archive_sha256"]:
        raise ValueError(f"SHA-256 inesperado para {path}: {actual_hash}")
    shape_member = source["archive_member"]
    member_root = shape_member.removesuffix(".shp")
    required = {
        shape_member,
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
        expected_creation = source["geometry_created_on"].replace("-", "")
        if creation_value != expected_creation:
            raise ValueError("La fecha de creacion del XML no coincide con la configuracion")
        with archive.open(member_root + ".dbf") as dbf_stream:
            dbf_header = dbf_stream.read(4)
        dbf_date = date(1900 + dbf_header[1], dbf_header[2], dbf_header[3]).isoformat()
        if dbf_date != source["dbf_last_update"]:
            raise ValueError("La fecha de actualizacion del DBF no coincide con la configuracion")


def _section_key(entity: pd.Series, section: pd.Series) -> pd.Series:
    return entity.astype(int).map(lambda value: f"{value:02d}") + ":" + section.astype(
        int
    ).map(lambda value: f"{value:04d}")


def _load_source_geometries(project_root: Path, config: dict[str, Any]) -> gpd.GeoDataFrame:
    source = config["source"]
    archive = project_root / source["local_archive"]
    _validate_archive(archive, source)
    virtual_path = f"/vsizip/{archive.resolve()}/{source['archive_member']}"
    sections = gpd.read_file(
        virtual_path,
        columns=[
            "ID",
            "ENTIDAD",
            "DISTRITO_F",
            "DISTRITO_L",
            "MUNICIPIO",
            "SECCION",
            "TIPO",
            "LN",
            "PAD",
        ],
    )
    if len(sections) != int(source["expected_feature_count"]):
        raise ValueError("El numero de geometrias no coincide con la fuente congelada")
    if sections.crs is None or not sections.crs.is_projected:
        raise ValueError("La capa debe tener un CRS proyectado para medir fronteras en metros")
    if sections.crs.name != source["expected_crs_name"]:
        raise ValueError(f"CRS inesperado: {sections.crs.name}")
    if any(axis.unit_name != source["coordinate_unit"] for axis in sections.crs.axis_info):
        raise ValueError("Las unidades del CRS no coinciden con la configuracion")
    if sections.geometry.isna().any() or sections.geometry.is_empty.any():
        raise ValueError("La fuente contiene geometrias vacias o nulas")
    if not sections.geometry.is_valid.all():
        raise ValueError("La fuente contiene geometrias invalidas; no se reparan silenciosamente")

    sections["section_key"] = _section_key(sections["ENTIDAD"], sections["SECCION"])
    if sections["section_key"].duplicated().any():
        raise ValueError("La llave entidad:seccion no es unica en la cartografia")
    return sections.sort_values("section_key").reset_index(drop=True)


def _restrict_to_model_universe(
    project_root: Path, config: dict[str, Any], sections: gpd.GeoDataFrame
) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    universe = config["model_universe"]
    table = project_root / universe["table"]
    frame = pd.read_parquet(
        table,
        filters=[(universe["year_column"], "=", int(universe["year"]))],
        columns=[universe["key_column"]],
    )
    keys = pd.Index(frame[universe["key_column"]].astype(str).unique())
    if len(keys) != int(universe["expected_nodes"]):
        raise ValueError("El universo de modelado no tiene el numero esperado de secciones")
    source_keys = pd.Index(sections["section_key"])
    missing = keys.difference(source_keys)
    if len(missing):
        raise ValueError(f"Hay {len(missing)} secciones del modelo sin geometria oficial")

    selected = sections[sections["section_key"].isin(keys)].copy()
    selected = selected.sort_values("section_key").reset_index(drop=True)
    selected["node_id"] = np.arange(len(selected), dtype=np.int64)
    excluded = sections[~sections["section_key"].isin(keys)][
        ["section_key", "ENTIDAD", "MUNICIPIO", "SECCION"]
    ].copy()
    excluded["exclusion_reason"] = "not_observed_in_ccpc_2024"
    return selected, excluded


def _build_contact_table(
    sections: gpd.GeoDataFrame, precision_grid_m: float, minimum_shared_boundary_m: float
) -> tuple[pd.DataFrame, np.ndarray]:
    snapped = shapely.set_precision(sections.geometry.array, grid_size=precision_grid_m)
    if not bool(np.all(shapely.is_valid(snapped))) or bool(np.any(shapely.is_empty(snapped))):
        raise ValueError("La normalizacion de precision produjo geometrias invalidas o vacias")

    tree = shapely.STRtree(snapped)
    pair_index = tree.query(snapped, predicate="touches")
    unique = pair_index[0] < pair_index[1]
    left = pair_index[0, unique]
    right = pair_index[1, unique]
    boundaries = shapely.boundary(snapped)
    shared = shapely.length(
        shapely.intersection(boundaries.take(left), boundaries.take(right))
    )
    selected = shared >= minimum_shared_boundary_m
    contacts = pd.DataFrame(
        {
            "source_node_id": left.astype(np.int64),
            "target_node_id": right.astype(np.int64),
            "source_section_key": sections["section_key"].to_numpy()[left],
            "target_section_key": sections["section_key"].to_numpy()[right],
            "shared_boundary_m": shared.astype(float),
            "contact_dimension": np.where(shared > 0, "line", "point"),
            "passes_rook_threshold": selected,
        }
    )
    return contacts.sort_values(["source_node_id", "target_node_id"]), snapped


def _nearest_edges_for_islands(
    sections: gpd.GeoDataFrame, snapped: np.ndarray, rook_edges: pd.DataFrame
) -> pd.DataFrame:
    degree = np.bincount(
        np.concatenate(
            [
                rook_edges["source_node_id"].to_numpy(dtype=np.int64),
                rook_edges["target_node_id"].to_numpy(dtype=np.int64),
            ]
        ),
        minlength=len(sections),
    )
    island_ids = np.flatnonzero(degree == 0)
    records: list[dict[str, Any]] = []
    entities = sections["ENTIDAD"].to_numpy()
    keys = sections["section_key"].to_numpy()
    for entity in sorted(set(entities[island_ids])):
        entity_ids = np.flatnonzero(entities == entity)
        entity_islands = island_ids[entities[island_ids] == entity]
        tree = shapely.STRtree(snapped.take(entity_ids))
        nearest, distances = tree.query_nearest(
            snapped.take(entity_islands),
            all_matches=False,
            return_distance=True,
            exclusive=True,
        )
        for query_position, target_position, distance in zip(
            nearest[0], nearest[1], distances, strict=True
        ):
            left = int(entity_islands[query_position])
            right = int(entity_ids[target_position])
            source, target = sorted([left, right])
            records.append(
                {
                    "source_node_id": source,
                    "target_node_id": target,
                    "source_section_key": keys[source],
                    "target_section_key": keys[target],
                    "edge_type": "island_nearest_same_entity",
                    "shared_boundary_m": 0.0,
                    "gap_distance_m": float(distance),
                    "is_synthetic": True,
                }
            )
    if not records:
        return pd.DataFrame(columns=list(rook_edges.columns))
    return pd.DataFrame(records).drop_duplicates(["source_node_id", "target_node_id"])


def _export_graph(
    project_root: Path,
    config: dict[str, Any],
    sections: gpd.GeoDataFrame,
    excluded: pd.DataFrame,
    contacts: pd.DataFrame,
    snapped: np.ndarray,
) -> dict[str, Any]:
    output_config = config["outputs"]
    output = project_root / output_config["directory"]
    output.mkdir(parents=True, exist_ok=True)

    topology = config["topology"]
    rook = contacts[contacts["passes_rook_threshold"]].copy()
    rook["edge_type"] = "rook_shared_boundary"
    rook["gap_distance_m"] = 0.0
    rook["is_synthetic"] = False
    edge_columns = [
        "source_node_id",
        "target_node_id",
        "source_section_key",
        "target_section_key",
        "edge_type",
        "shared_boundary_m",
        "gap_distance_m",
        "is_synthetic",
    ]
    rook = rook[edge_columns]
    nearest = _nearest_edges_for_islands(sections, snapped, rook)
    edges = pd.concat([rook, nearest[edge_columns]], ignore_index=True)
    edges = edges.drop_duplicates(["source_node_id", "target_node_id"], keep="first")
    edges = edges.sort_values(["source_node_id", "target_node_id"]).reset_index(drop=True)
    entities = sections["ENTIDAD"].to_numpy()
    municipalities = sections["MUNICIPIO"].to_numpy()
    edge_source_ids = edges["source_node_id"].to_numpy(dtype=np.int64)
    edge_target_ids = edges["target_node_id"].to_numpy(dtype=np.int64)
    edges["same_entity"] = entities[edge_source_ids] == entities[edge_target_ids]
    edges["same_municipality"] = edges["same_entity"] & (
        municipalities[edge_source_ids] == municipalities[edge_target_ids]
    )

    source_ids = edges["source_node_id"].to_numpy(dtype=np.int64)
    target_ids = edges["target_node_id"].to_numpy(dtype=np.int64)
    rows = np.concatenate([source_ids, target_ids])
    columns = np.concatenate([target_ids, source_ids])
    values = np.ones(len(rows), dtype=np.float32)
    adjacency = sparse.csr_matrix((values, (rows, columns)), shape=(len(sections), len(sections)))
    adjacency.sum_duplicates()
    adjacency.data[:] = 1.0
    component_count, component_labels = connected_components(adjacency, directed=False)
    degree = np.asarray(adjacency.sum(axis=1)).ravel().astype(np.int32)

    centroids = gpd.GeoSeries(shapely.centroid(snapped), crs=sections.crs)
    centroids_wgs84 = centroids.to_crs(4326)
    nodes = pd.DataFrame(
        {
            "node_id": sections["node_id"].astype(np.int64),
            "section_key": sections["section_key"],
            "entity_id": sections["ENTIDAD"].astype(int).map(lambda value: f"{value:02d}"),
            "municipality_code": sections["MUNICIPIO"].astype(np.int64),
            "federal_district": sections["DISTRITO_F"].astype(int),
            "local_district": sections["DISTRITO_L"].astype(int),
            "section_code": sections["SECCION"].astype(np.int64),
            "section_type": sections["TIPO"].astype(int),
            "source_nominal_list": sections["LN"].astype(np.int64),
            "source_electoral_roll": sections["PAD"].astype(np.int64),
            "area_m2": shapely.area(snapped).astype(float),
            "centroid_x_m": centroids.x.astype(float),
            "centroid_y_m": centroids.y.astype(float),
            "centroid_lon": centroids_wgs84.x.astype(float),
            "centroid_lat": centroids_wgs84.y.astype(float),
            "degree": degree,
            "component_id": component_labels.astype(np.int32),
            "has_synthetic_edge": False,
        }
    )
    synthetic_nodes = set(nearest.get("source_node_id", [])) | set(
        nearest.get("target_node_id", [])
    )
    nodes["has_synthetic_edge"] = nodes["node_id"].isin(synthetic_nodes)

    nodes.to_parquet(output / output_config["nodes"], index=False)
    contacts.to_parquet(output / output_config["contacts"], index=False)
    edges.to_parquet(output / output_config["edges"], index=False)
    excluded.to_csv(output / output_config["excluded_source_nodes"], index=False)
    sparse.save_npz(output / output_config["adjacency"], adjacency, compressed=True)
    np.savez_compressed(
        output / output_config["edge_index"],
        edge_index=np.vstack([rows, columns]),
        edge_weight=values,
        section_keys=nodes["section_key"].to_numpy(dtype=str),
        num_nodes=np.array([len(nodes)], dtype=np.int64),
    )

    source = config["source"]
    archive = project_root / source["local_archive"]
    manifest = pd.DataFrame(
        [
            {
                "source_id": config["snapshot_id"],
                "authority": source["authority"],
                "title": source["title"],
                "landing_url": source["landing_url"],
                "download_url": source["download_url"],
                "local_archive": source["local_archive"],
                "bytes": archive.stat().st_size,
                "sha256": sha256_file(archive),
                "geometry_created_on": source["geometry_created_on"],
                "dbf_last_update": source["dbf_last_update"],
                "target_election_date": config["target_election_date"],
                "role": "authoritative_section_geometry_and_adjacency",
            }
        ]
    )
    manifest_path = project_root / output_config["source_manifest"]
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(manifest_path, index=False)

    edge_type_counts = edges["edge_type"].value_counts().sort_index().to_dict()
    metadata: dict[str, Any] = {
        "snapshot_id": config["snapshot_id"],
        "source": {
            "authority": source["authority"],
            "landing_url": source["landing_url"],
            "download_url": source["download_url"],
            "archive_sha256": source["archive_sha256"],
            "archive_bytes": int(source["archive_bytes"]),
            "geometry_created_on": source["geometry_created_on"],
            "target_election_date": config["target_election_date"],
            "feature_count": int(source["expected_feature_count"]),
        },
        "model_universe": {
            "year": int(config["model_universe"]["year"]),
            "node_count": len(nodes),
            "source_features_excluded": len(excluded),
            "coverage": 1.0,
        },
        "topology": {
            "definition": topology["definition"],
            "precision_grid_m": float(topology["precision_grid_m"]),
            "minimum_shared_boundary_m": float(topology["minimum_shared_boundary_m"]),
            "point_contacts_are_neighbors": bool(topology["point_contacts_are_neighbors"]),
            "island_policy": topology["island_policy"],
            "self_loops_in_export": bool(topology["self_loops_in_export"]),
        },
        "quality": {
            "all_source_geometries_valid": True,
            "duplicate_section_keys": 0,
            "point_only_contacts_excluded": int(
                contacts["contact_dimension"].eq("point").sum()
            ),
            "line_contacts_below_threshold_excluded": int(
                (
                    contacts["contact_dimension"].eq("line")
                    & ~contacts["passes_rook_threshold"]
                ).sum()
            ),
            "isolated_nodes_after_fallback": int((degree == 0).sum()),
            "symmetric_adjacency": bool((adjacency != adjacency.T).nnz == 0),
            "self_loops": int(adjacency.diagonal().sum()),
            "connected_components": int(component_count),
            "minimum_degree": int(degree.min()),
            "median_degree": float(np.median(degree)),
            "maximum_degree": int(degree.max()),
        },
        "edges": {
            "undirected_count": len(edges),
            "directed_count": int(adjacency.nnz),
            "by_type": {key: int(value) for key, value in edge_type_counts.items()},
            "cross_entity_count": int((~edges["same_entity"]).sum()),
            "cross_municipality_count": int((~edges["same_municipality"]).sum()),
        },
        "files": {
            key: str((output / value).relative_to(project_root))
            for key, value in output_config.items()
            if key not in {"directory", "source_manifest"}
        }
        | {"source_manifest": output_config["source_manifest"]},
    }
    with (output / output_config["metadata"]).open("w", encoding="utf-8") as stream:
        json.dump(metadata, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    return metadata


def build_section_graph(project_root: Path) -> dict[str, Any]:
    config = load_config(project_root)
    if date.fromisoformat(config["source"]["geometry_created_on"]) > date.fromisoformat(
        config["target_election_date"]
    ):
        raise ValueError("La geometria es posterior a la eleccion objetivo")
    sections = _load_source_geometries(project_root, config)
    sections, excluded = _restrict_to_model_universe(project_root, config, sections)
    topology = config["topology"]
    contacts, snapped = _build_contact_table(
        sections,
        precision_grid_m=float(topology["precision_grid_m"]),
        minimum_shared_boundary_m=float(topology["minimum_shared_boundary_m"]),
    )
    return _export_graph(project_root, config, sections, excluded, contacts, snapped)
