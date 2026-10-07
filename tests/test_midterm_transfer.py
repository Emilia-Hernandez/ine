from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from radar27.modeling.midterm_transfer import derive_cycle_features

ROOT = Path(__file__).resolve().parents[1]


def test_cycle_features_use_prior_family_transitions_with_correct_direction() -> None:
    history = pd.DataFrame(
        {
            "evaluation_unit_id": ["S:1"] * 4,
            "election_year": [2009, 2012, 2015, 2018],
            "voted": [40, 60, 50, 70],
            "did_not_vote": [60, 40, 50, 30],
            "nominal_list": [100] * 4,
        }
    )
    for column in [
        "unspecified",
        "female_nominal_list",
        "female_voted",
        "female_did_not_vote",
        "male_nominal_list",
        "male_voted",
        "male_did_not_vote",
        "age_18_29_nominal_list",
        "age_18_29_voted",
        "age_18_29_did_not_vote",
        "age_30_44_nominal_list",
        "age_30_44_voted",
        "age_30_44_did_not_vote",
        "age_45_64_nominal_list",
        "age_45_64_voted",
        "age_45_64_did_not_vote",
        "age_65_plus_nominal_list",
        "age_65_plus_voted",
        "age_65_plus_did_not_vote",
    ]:
        history[column] = 0
    family = {2009: "midterm", 2012: "presidential", 2015: "midterm", 2018: "presidential"}
    result = derive_cycle_features(history, 2021, family).iloc[0]
    assert np.isclose(result["latest_completed_presidential_to_midterm_change"], -0.10)
    assert np.isclose(result["latest_completed_midterm_to_presidential_change"], 0.20)
    assert np.isclose(result["latest_midterm_minus_latest_presidential"], -0.20)
    assert result["cycle_source_max_year"] == 2018


def test_midterm_transfer_artifacts_share_the_same_2021_sample() -> None:
    metrics = pd.read_csv(ROOT / "artifacts/tables/midterm_transfer_metrics.csv")
    assert set(metrics["variant"]) == {
        "shared_all_elections",
        "midterm_only",
        "midterm_transfer_two_head",
    }
    assert set(metrics["target_year"]) == {2021}
    assert metrics["evaluation_units"].nunique() == 1
    assert metrics["entities_compared"].eq(32).all()


def test_cycle_mart_is_strictly_prior_and_contains_both_families() -> None:
    mart = pd.read_parquet(ROOT / "artifacts/tables/midterm_cycle_mart.parquet")
    assert (mart["cycle_source_max_year"] < mart["target_year"]).all()
    assert {
        "latest_midterm_participation",
        "latest_presidential_participation",
        "latest_completed_presidential_to_midterm_change",
        "entity_latest_midterm_minus_latest_presidential_mean",
    } <= set(mart.columns)


def test_transfer_registry_separates_shared_and_midterm_heads() -> None:
    registry = pd.read_csv(
        ROOT / "artifacts/tables/midterm_transfer_registry.csv", keep_default_na=False
    )
    transfer = registry[registry["variant"].eq("midterm_transfer_two_head")]
    assert set(transfer["head"]) == {"shared", "midterm_specialist"}
    shared = transfer[transfer["head"].eq("shared")].iloc[0]
    specialist = transfer[transfer["head"].eq("midterm_specialist")].iloc[0]
    assert shared["training_target_years"] == "2015|2018"
    assert shared["training_families"] == "midterm|presidential"
    assert specialist["training_target_years"] == "2015"
    assert specialist["training_families"] == "midterm"
    assert transfer["uses_target_or_future_outcomes"].astype(str).str.lower().eq("false").all()


def test_experiment_cannot_auto_promote_from_one_midterm_fold() -> None:
    decision = json.loads(
        (ROOT / "artifacts/midterm_transfer_decision.json").read_text(encoding="utf-8")
    )
    assert decision["evaluation_target"] == 2021
    assert decision["automatic_promotion"] is False
    assert decision["presidential_role"] == "auxiliary_shared_head_only"
