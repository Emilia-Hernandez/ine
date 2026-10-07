from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy import sparse

ROOT = Path(__file__).resolve().parents[1]
GRAPH = ROOT / "artifacts/graphs"


def test_spatial_graph_source_and_temporal_cut_are_frozen() -> None:
    with (ROOT / "configs/spatial_graph.yaml").open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    manifest = pd.read_csv(ROOT / "data/manifests/spatial_graph_source_manifest.csv")
    assert len(manifest) == 1
    assert manifest.loc[0, "authority"] == "Instituto Nacional Electoral"
    assert manifest.loc[0, "sha256"] == config["source"]["archive_sha256"]
    assert manifest.loc[0, "bytes"] == config["source"]["archive_bytes"]
    assert pd.Timestamp(config["source"]["geometry_created_on"]) < pd.Timestamp("2024-06-02")


def test_spatial_graph_nodes_cover_the_complete_2024_model_universe() -> None:
    nodes = pd.read_parquet(GRAPH / "section_graph_2024_nodes.parquet")
    observed = pd.read_parquet(
        ROOT / "artifacts/tables/provisional_section_year_totals.parquet",
        filters=[("election_year", "=", 2024)],
        columns=["section_key_observed"],
    )
    assert len(nodes) == 70_751
    assert nodes["section_key"].is_unique
    assert nodes["node_id"].tolist() == list(range(len(nodes)))
    assert set(nodes["section_key"]) == set(observed["section_key_observed"])
    assert nodes[["centroid_lon", "centroid_lat", "area_m2"]].notna().all().all()
    assert nodes["area_m2"].gt(0).all()


def test_spatial_edges_are_unique_typed_and_do_not_conflate_point_contacts() -> None:
    edges = pd.read_parquet(GRAPH / "section_graph_2024_edges.parquet")
    contacts = pd.read_parquet(GRAPH / "section_graph_2024_contacts.parquet")
    assert len(edges) == 201_288
    assert not edges.duplicated(["source_node_id", "target_node_id"]).any()
    assert edges["source_node_id"].lt(edges["target_node_id"]).all()
    assert set(edges["edge_type"]) == {
        "rook_shared_boundary",
        "island_nearest_same_entity",
    }
    rook = edges[edges["edge_type"].eq("rook_shared_boundary")]
    synthetic = edges[edges["is_synthetic"]]
    assert rook["shared_boundary_m"].ge(1.0).all()
    assert (~rook["same_entity"]).sum() == 4_045
    assert len(synthetic) == 2
    assert synthetic["gap_distance_m"].gt(0).all()
    point_contacts = contacts[contacts["contact_dimension"].eq("point")]
    assert len(point_contacts) == 14_417
    assert not point_contacts["passes_rook_threshold"].any()


def test_sparse_exports_are_symmetric_loop_free_and_aligned() -> None:
    nodes = pd.read_parquet(GRAPH / "section_graph_2024_nodes.parquet")
    edges = pd.read_parquet(GRAPH / "section_graph_2024_edges.parquet")
    adjacency = sparse.load_npz(GRAPH / "section_graph_2024_adjacency.npz")
    edge_index = np.load(GRAPH / "section_graph_2024_edge_index.npz")
    assert adjacency.shape == (len(nodes), len(nodes))
    assert adjacency.nnz == 2 * len(edges)
    assert (adjacency != adjacency.T).nnz == 0
    assert not adjacency.diagonal().any()
    assert np.asarray(adjacency.sum(axis=1)).ravel().min() >= 1
    assert edge_index["edge_index"].shape == (2, adjacency.nnz)
    assert edge_index["num_nodes"].item() == len(nodes)
    assert np.array_equal(edge_index["section_keys"], nodes["section_key"].to_numpy())


def test_graph_metadata_closes_quality_contract() -> None:
    metadata = json.loads((GRAPH / "section_graph_2024_metadata.json").read_text())
    assert metadata["model_universe"]["coverage"] == 1.0
    assert metadata["quality"]["all_source_geometries_valid"] is True
    assert metadata["quality"]["duplicate_section_keys"] == 0
    assert metadata["quality"]["symmetric_adjacency"] is True
    assert metadata["quality"]["self_loops"] == 0
    assert metadata["quality"]["isolated_nodes_after_fallback"] == 0
    assert metadata["quality"]["connected_components"] == 5
