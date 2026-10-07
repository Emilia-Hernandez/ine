from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
METRICS_PATH = ROOT / "artifacts/tables/graph_embedding_metrics.csv"
REGISTRY_PATH = ROOT / "artifacts/tables/graph_embedding_registry.csv"
DECISION_PATH = ROOT / "artifacts/graph_embedding_decision.json"


def test_embedding_is_an_additional_label_free_signal() -> None:
    decision = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
    assert decision["embedding_role"] == "additional_features_for_hist_gradient_boosting"
    assert decision["embedding_is_standalone_predictor"] is False
    assert decision["embedding_uses_outcome_labels"] is False


def test_same_sample_is_used_for_reference_and_embedding_models() -> None:
    metrics = pd.read_csv(METRICS_PATH)
    assert set(metrics["target_year"]) == {2018, 2021, 2024}
    assert len(metrics) == 9
    assert not metrics["model_id"].str.contains("embedding_only").any()
    expected_models = {
        "hist_gradient_boosting_without_embedding",
        "hist_gradient_boosting_plus_graphsage_rook",
        "hist_gradient_boosting_plus_graphsage_augmented",
    }
    assert set(metrics["model_id"]) == expected_models
    for _, fold in metrics.groupby("target_year"):
        assert fold["evaluation_units"].nunique() == 1


def test_embedding_result_is_not_promoted() -> None:
    metrics = pd.read_csv(METRICS_PATH).set_index(["target_year", "model_id"])
    reference = "hist_gradient_boosting_without_embedding"
    rook = "hist_gradient_boosting_plus_graphsage_rook"
    assert metrics.loc[(2021, rook), "identified_weighted_mae"] > metrics.loc[
        (2021, reference), "identified_weighted_mae"
    ]
    assert metrics.loc[(2024, rook), "identified_weighted_mae"] < metrics.loc[
        (2024, reference), "identified_weighted_mae"
    ]
    decision = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
    assert decision["embedding_promoted"] is False
    assert decision["selected_model_for_next_iteration"] == reference


def test_encoder_registry_proves_temporal_and_label_free_contract() -> None:
    registry = pd.read_csv(REGISTRY_PATH, keep_default_na=False)
    encoded = registry[registry["embedding_dimensions"].eq(16)]
    assert len(encoded) == 6
    assert (~encoded["embedding_uses_target_labels"]).all()
    assert (pd.to_numeric(encoded["encoder_best_epoch"]) > 0).all()
    assert (pd.to_numeric(encoded["encoder_validation_loss"]) > 0).all()
    assert encoded["encoder_model_sha256"].str.fullmatch(r"[0-9a-f]{64}").all()
    for row in encoded.itertuples(index=False):
        assert max(map(int, row.training_target_years.split("|"))) < row.target_year


def test_embedding_artifacts_have_fixed_dimensions_and_keys() -> None:
    config = yaml.safe_load(
        (ROOT / "configs/graph_embedding_challenger.yaml").read_text(encoding="utf-8")
    )
    embedding_columns = [f"graph_embedding_{index:02d}" for index in range(16)]
    for target_year in config["evaluation_targets"]:
        for topology in config["topologies"]:
            path = (
                ROOT
                / config["outputs"]["embedding_directory"]
                / f"embeddings_fold_{target_year}_{topology}.parquet"
            )
            frame = pd.read_parquet(path)
            assert set(embedding_columns).issubset(frame.columns)
            assert frame[["graph_year", "section_key"]].duplicated().sum() == 0
            assert frame["graph_year"].max() == target_year
            assert np.isfinite(frame[embedding_columns].to_numpy()).all()
