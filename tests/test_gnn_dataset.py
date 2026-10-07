from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPORAL_ROOT = PROJECT_ROOT / "artifacts/graphs/temporal"
GNN_ROOT = PROJECT_ROOT / "artifacts/gnn_dataset"

EXPECTED_GRAPH_NODES = {2015: 68_362, 2018: 68_361, 2021: 67_633, 2024: 70_751}
EXPECTED_GNN_NODES = {2015: 60_983, 2018: 60_430, 2021: 59_963, 2024: 58_534}
EXPECTED_REPAIRS = {
    2015: {"wkb_ring_repairs": 3, "make_valid_repairs": 0},
    2018: {"wkb_ring_repairs": 10, "make_valid_repairs": 1},
    2021: {"wkb_ring_repairs": 10, "make_valid_repairs": 1},
    2024: {"wkb_ring_repairs": 0, "make_valid_repairs": 0},
}


def test_temporal_source_manifest_is_complete() -> None:
    manifest = pd.read_csv(
        PROJECT_ROOT / "data/manifests/temporal_graph_source_manifest.csv"
    )
    assert manifest["target_year"].tolist() == [2015, 2018, 2021, 2024]
    assert manifest["sha256"].str.fullmatch(r"[0-9a-f]{64}").all()
    assert (manifest["bytes"] > 0).all()
    assert pd.to_datetime(manifest["geometry_created_on"]).notna().all()
    assert pd.to_datetime(manifest["dbf_last_update"]).notna().all()


def test_temporal_graphs_are_undirected_and_auditable() -> None:
    for year, expected_nodes in EXPECTED_GRAPH_NODES.items():
        with (TEMPORAL_ROOT / str(year) / "metadata.json").open(
            encoding="utf-8"
        ) as stream:
            metadata = json.load(stream)
        adjacency = sparse.load_npz(TEMPORAL_ROOT / str(year) / "adjacency.npz")
        assert adjacency.shape == (expected_nodes, expected_nodes)
        assert (adjacency != adjacency.T).nnz == 0
        assert adjacency.diagonal().sum() == 0
        assert np.asarray(adjacency.sum(axis=1)).min() >= 1
        assert metadata["quality"]["symmetric"] is True
        assert metadata["quality"]["self_loops"] == 0
        assert metadata["quality"]["isolated_nodes_after_fallback"] == 0
        assert metadata["repairs"] == EXPECTED_REPAIRS[year]
        assert metadata["geometry_created_on"] < metadata["election_date"]


def test_gnn_bundles_have_frozen_shapes_and_no_temporal_leakage() -> None:
    with (GNN_ROOT / "gnn_dataset_metadata.json").open(encoding="utf-8") as stream:
        metadata = json.load(stream)
    assert len(metadata["numeric_features"]) == 22

    for year, expected_nodes in EXPECTED_GNN_NODES.items():
        bundle = np.load(GNN_ROOT / f"graph_{year}.npz")
        nodes = pd.read_parquet(GNN_ROOT / f"nodes_{year}.parquet")
        assert len(nodes) == expected_nodes
        assert bundle["x_numeric"].shape == (expected_nodes, 22)
        assert bundle["x_numeric_missing"].shape == (expected_nodes, 22)
        assert bundle["x_categorical"].shape == (expected_nodes, 38)
        assert np.array_equal(bundle["section_keys"], nodes["section_key"].to_numpy())
        assert np.array_equal(bundle["labeled_mask"], nodes["labeled_mask"].to_numpy())
        assert not np.any(bundle["fit_mask"] & bundle["validation_mask"])
        assert np.all(bundle["fit_mask"] | ~bundle["labeled_mask"] | bundle["validation_mask"])
        assert nodes["max_electoral_feature_year"].max() < year
        assert nodes["context_source_max_year"].max() < year

        edge_index = bundle["edge_index_augmented"]
        pairs = set(map(tuple, edge_index.T.tolist()))
        assert all((target, source) in pairs for source, target in pairs)
        assert all(source != target for source, target in pairs)


def test_fold_preprocessing_uses_only_prior_fit_nodes() -> None:
    preprocessing = np.load(GNN_ROOT / "gnn_fold_preprocessing.npz")
    expected = {2018: [2015], 2021: [2015, 2018], 2024: [2015, 2018, 2021]}
    for year, train_years in expected.items():
        prefix = f"fold_{year}"
        assert preprocessing[f"{prefix}_train_years"].tolist() == train_years
        assert np.isfinite(preprocessing[f"{prefix}_median"]).all()
        assert np.isfinite(preprocessing[f"{prefix}_mean"]).all()
        assert (preprocessing[f"{prefix}_scale"] > 0).all()
