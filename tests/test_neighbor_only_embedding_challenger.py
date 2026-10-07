from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import yaml

from radar27.modeling.graph_embedding_challenger import (
    NeighborOnlyDenoisingAutoencoder,
    _normalized_adjacency,
)

ROOT = Path(__file__).resolve().parents[1]
METRICS_PATH = ROOT / "artifacts/tables/neighbor_only_embedding_metrics.csv"
REGISTRY_PATH = ROOT / "artifacts/tables/neighbor_only_embedding_registry.csv"
DECISION_PATH = ROOT / "artifacts/neighbor_only_embedding_decision.json"


def test_neighbor_only_encoder_has_no_path_from_node_to_itself() -> None:
    edge_index = np.asarray([[0, 1, 1, 2], [1, 0, 2, 1]], dtype=np.int64)
    adjacency = _normalized_adjacency(edge_index, nodes=4)
    model = NeighborOnlyDenoisingAutoencoder(2, 4, 3, 0.0, 0.0).eval()
    values = torch.tensor([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0]])
    original = model.encode(values, adjacency)
    changed = values.clone()
    changed[0] = torch.tensor([100.0, 200.0])
    modified = model.encode(changed, adjacency)
    assert torch.equal(original[0], modified[0])
    assert not torch.equal(original[1], modified[1])
    assert torch.equal(original[3], torch.zeros(3))


def test_neighbor_only_challenger_is_additional_and_label_free() -> None:
    decision = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
    assert decision["embedding_is_standalone_predictor"] is False
    assert decision["embedding_uses_outcome_labels"] is False
    assert decision["encoder_uses_own_node_features"] is False


def test_neighbor_only_models_use_the_same_evaluation_sample() -> None:
    metrics = pd.read_csv(METRICS_PATH)
    assert len(metrics) == 9
    assert set(metrics["target_year"]) == {2018, 2021, 2024}
    assert not metrics["model_id"].str.contains("embedding_only$").any()
    for _, fold in metrics.groupby("target_year"):
        assert fold["evaluation_units"].nunique() == 1


def test_neighbor_only_registry_is_temporally_valid() -> None:
    registry = pd.read_csv(REGISTRY_PATH, keep_default_na=False)
    encoded = registry[registry["embedding_dimensions"].eq(16)]
    assert len(encoded) == 6
    assert encoded["embedding_uses_target_labels"].astype(str).str.lower().eq("false").all()
    assert (
        encoded["encoder_uses_own_node_features"].astype(str).str.lower().eq("false").all()
    )
    assert encoded["encoder_model_sha256"].str.fullmatch(r"[0-9a-f]{64}").all()
    for row in encoded.itertuples(index=False):
        assert max(map(int, row.training_target_years.split("|"))) < row.target_year


def test_neighbor_only_result_respects_the_frozen_gate() -> None:
    metrics = pd.read_csv(METRICS_PATH).set_index(["target_year", "model_id"])
    reference = "hist_gradient_boosting_without_embedding"
    rook = "hist_gradient_boosting_plus_neighbor_only_embedding_rook"
    assert metrics.loc[(2021, rook), "identified_weighted_mae"] > metrics.loc[
        (2021, reference), "identified_weighted_mae"
    ]
    assert metrics.loc[(2024, rook), "identified_weighted_mae"] < metrics.loc[
        (2024, reference), "identified_weighted_mae"
    ]
    decision = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
    assert decision["embedding_promoted"] is False
    assert decision["selected_model_for_next_iteration"] == reference


def test_neighbor_only_embedding_artifacts_are_finite() -> None:
    config = yaml.safe_load(
        (ROOT / "configs/neighbor_only_embedding_challenger.yaml").read_text(
            encoding="utf-8"
        )
    )
    columns = [f"graph_embedding_{index:02d}" for index in range(16)]
    for target_year in config["evaluation_targets"]:
        for topology in config["topologies"]:
            path = (
                ROOT
                / config["outputs"]["embedding_directory"]
                / f"embeddings_fold_{target_year}_{topology}.parquet"
            )
            frame = pd.read_parquet(path)
            assert np.isfinite(frame[columns].to_numpy()).all()
            assert frame[["graph_year", "section_key"]].duplicated().sum() == 0
