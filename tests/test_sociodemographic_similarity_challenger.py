from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from radar27.modeling.sociodemographic_similarity_challenger import (
    _mutual_knn_graph,
)

ROOT = Path(__file__).resolve().parents[1]


def test_mutual_knn_graph_is_symmetric_without_isolates() -> None:
    values = np.asarray([[0.0], [0.1], [0.2], [10.0]], dtype=np.float32)
    adjacency, distances, fallback = _mutual_knn_graph(values, k=1)
    assert (adjacency != adjacency.T).nnz == 0
    assert adjacency.diagonal().sum() == 0
    assert np.asarray(adjacency.sum(axis=1)).ravel().min() >= 1
    assert (distances != distances.T).nnz == 0
    assert fallback


def test_similarity_topology_uses_only_lagged_composition() -> None:
    config = pd.read_csv(
        ROOT / "artifacts/tables/sociodemographic_similarity_graph_registry.csv"
    )
    features = set(config["similarity_features"].iloc[0].split("|"))
    assert features == {
        "female_nominal_share_lag1",
        "age_18_29_nominal_share_lag1",
        "age_30_44_nominal_share_lag1",
        "age_45_64_nominal_share_lag1",
        "age_65_plus_nominal_share_lag1",
    }
    assert config["minimum_degree"].ge(1).all()
    assert config["cross_entity_edge_share"].between(0, 1).all()


def test_reference_reproduces_current_entity_cycle_model() -> None:
    metrics = pd.read_csv(
        ROOT / "artifacts/tables/sociodemographic_similarity_metrics.csv"
    )
    reference = metrics[metrics["candidate_kind"].eq("reference")].set_index(
        "target_year"
    )
    adaptation = pd.read_csv(
        ROOT / "artifacts/tables/entity_cycle_adaptation_metrics.csv"
    )
    adaptation = adaptation[adaptation["entity_cycle_shrinkage"].eq(-0.5)].set_index(
        "target_year"
    )
    assert np.allclose(
        reference.loc[[2018, 2021, 2024], "identified_weighted_mae"],
        adaptation.loc[[2018, 2021, 2024], "identified_weighted_mae"],
        atol=1e-6,
    )


def test_embedding_is_label_free_and_decision_obeys_gate() -> None:
    registry = pd.read_csv(
        ROOT / "artifacts/tables/sociodemographic_similarity_registry.csv"
    )
    candidates = registry[~registry["candidate_kind"].eq("reference")]
    assert candidates["encoder_uses_target_labels"].eq(False).all()
    assert candidates["encoder_uses_own_node_features"].eq(False).all()
    assert set(candidates["encoder_dimensions"]) == {16}
    decision = json.loads(
        (ROOT / "artifacts/sociodemographic_similarity_decision.json").read_text(
            encoding="utf-8"
        )
    )
    assert decision["topology_uses_outcome"] is False
    assert decision["feature_group_held_constant"] == "competition_concurrency"
    assert decision["entity_cycle_shrinkage_held_constant"] == -0.5
    if decision["candidate_promoted"]:
        assert decision["best_candidate_gate"]["passes"] is True
        assert all(
            row["passes"] for row in decision["best_candidate_gate"]["robustness"]
        )
