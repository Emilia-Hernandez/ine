from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy import sparse

from radar27.modeling.spatial_feature_challenger import _neighbor_statistics

ROOT = Path(__file__).resolve().parents[1]
METRICS_PATH = ROOT / "artifacts/tables/spatial_feature_metrics.csv"
REGISTRY_PATH = ROOT / "artifacts/tables/spatial_feature_registry.csv"
DECISION_PATH = ROOT / "artifacts/spatial_feature_decision.json"


def test_neighbor_statistics_are_explicit_and_directionally_correct() -> None:
    adjacency = sparse.csr_matrix(
        (
            np.ones(4),
            (np.asarray([0, 1, 1, 2]), np.asarray([1, 0, 2, 1])),
        ),
        shape=(3, 3),
    )
    values = np.asarray([1.0, 3.0, 5.0])
    result = _neighbor_statistics(adjacency, values, "signal", 10.0)
    assert np.allclose(result["neighbor_signal_mean"], [3.0, 3.0, 3.0])
    assert np.allclose(result["signal_minus_neighbor_mean"], [-2.0, 0.0, 2.0])
    assert result["signal_neighbor_zscore"].tolist() == [-10.0, 0.0, 10.0]


def test_spatial_feature_artifacts_have_frozen_dimensions() -> None:
    config = yaml.safe_load(
        (ROOT / "configs/spatial_feature_challenger.yaml").read_text(encoding="utf-8")
    )
    for year in [2015, *config["evaluation_targets"]]:
        for topology in config["topologies"]:
            frame = pd.read_parquet(
                ROOT
                / config["outputs"]["feature_directory"]
                / f"spatial_features_{year}_{topology}.parquet"
            )
            assert frame.shape[1] == 36
            assert frame["section_key"].is_unique
            zscores = [column for column in frame if column.endswith("_neighbor_zscore")]
            assert len(zscores) == 5
            finite = frame[zscores].to_numpy(dtype=float)
            assert np.nanmax(np.abs(finite)) <= 10.0


def test_spatial_models_use_identical_evaluation_samples() -> None:
    metrics = pd.read_csv(METRICS_PATH)
    assert len(metrics) == 15
    assert set(metrics["target_year"]) == {2018, 2021, 2024}
    for _, fold in metrics.groupby("target_year"):
        assert fold["evaluation_units"].nunique() == 1


def test_neighbor_core_improves_every_out_of_time_fold() -> None:
    metrics = pd.read_csv(METRICS_PATH).set_index(["target_year", "model_id"])
    reference = "hist_gradient_boosting_without_spatial_explicit"
    candidate = "hist_gradient_boosting_plus_spatial_explicit_neighbor_core_rook"
    for year in [2018, 2021, 2024]:
        assert metrics.loc[(year, candidate), "identified_weighted_mae"] < metrics.loc[
            (year, reference), "identified_weighted_mae"
        ]
        assert metrics.loc[(year, candidate), "spatial_feature_count"] == 24


def test_spatial_decision_promotes_only_the_compact_neighbor_core() -> None:
    decision = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
    assert decision["spatial_features_promoted"] is True
    assert decision["spatial_feature_set"] == "neighbor_core"
    assert decision["spatial_feature_count"] == 24
    assert decision["selected_model_for_next_iteration"].endswith("neighbor_core_rook")


def test_spatial_registry_excludes_target_outcomes() -> None:
    registry = pd.read_csv(REGISTRY_PATH, keep_default_na=False)
    candidates = registry[registry["spatial_features"].eq(24)]
    assert len(candidates) == 6
    assert candidates["uses_target_outcome_features"].astype(str).str.lower().eq("false").all()
    for row in candidates.itertuples(index=False):
        assert max(map(int, row.training_target_years.split("|"))) < row.target_year
