from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from radar27.modeling.electoral_context import (
    _competition_metrics,
    build_concurrency_table,
    build_entity_cycle_table,
    consolidate_candidate_votes,
    load_entity_turnout_source,
)
from radar27.modeling.feature_models import _load_yaml

ROOT = Path(__file__).resolve().parents[1]


def test_coalition_votes_are_consolidated_only_where_active() -> None:
    raw = pd.DataFrame(
        {
            "ID_ESTADO": [1, 1],
            "ID_DISTRITO": [1, 2],
            "SECCION": [10, 20],
            "A": [30, 30],
            "B": [20, 20],
            "C": [50, 50],
            "A_B": [5, 0],
        }
    )
    source = {
        "district_column": "ID_DISTRITO",
        "vote_columns": ["A", "B", "C", "A_B"],
        "alliances": [{"name": "ab", "members": ["A", "B"], "joint_columns": ["A_B"]}],
    }
    consolidated, options = consolidate_candidate_votes(raw, source)
    assert set(options) == {"A", "B", "C", "alliance__ab"}
    first = consolidated.set_index("section_key_observed").loc["01:0010"]
    second = consolidated.set_index("section_key_observed").loc["01:0020"]
    assert first["alliance__ab"] == 55
    assert first["A"] == first["B"] == 0
    assert second["A"] == 30
    assert second["B"] == 20
    assert second["alliance__ab"] == 0
    assert consolidated[options].sum(axis=1).tolist() == [105, 100]


def test_competition_metrics_use_aggregated_lineage_votes() -> None:
    members = pd.DataFrame(
        {
            "evaluation_unit_id": ["C:x", "C:x"],
            "section_key_observed": ["01:0001", "01:0002"],
        }
    )
    votes = pd.DataFrame(
        {
            "section_key_observed": ["01:0001", "01:0002"],
            "a": [60, 20],
            "b": [40, 80],
        }
    )
    result = _competition_metrics(members, votes, ["a", "b"]).iloc[0]
    assert result["prior_competition_valid_votes"] == 200
    assert np.isclose(result["prior_winner_vote_share"], 0.6)
    assert np.isclose(result["prior_competition_margin"], 0.2)
    assert np.isclose(result["prior_competition_hhi"], 0.52)
    assert np.isclose(result["prior_effective_number_options"], 1 / 0.52)
    assert result["prior_competition_coverage"] == 1


def test_concurrency_schedule_is_prior_known_and_covers_all_entities() -> None:
    config = _load_yaml(ROOT / "configs/electoral_context.yaml")
    schedule = build_concurrency_table(config)
    assert not schedule.duplicated(["target_year", "entity_id"]).any()
    assert schedule.groupby("target_year").size().eq(32).all()
    assert pd.to_datetime(schedule["concurrency_known_date"]).lt(
        pd.to_datetime(schedule["target_election_date"])
    ).all()
    by_year = schedule.groupby("target_year").agg(
        local=("local_election_concurrent", "sum"),
        executive=("local_executive_on_ballot", "sum"),
        congress=("local_congress_on_ballot", "sum"),
        municipal=("municipal_on_ballot", "sum"),
    )
    assert by_year.loc[2015].tolist() == [16, 9, 16, 16]
    assert by_year.loc[2018].tolist() == [30, 9, 27, 26]
    assert by_year.loc[2021].tolist() == [32, 15, 30, 30]
    assert by_year.loc[2024].tolist() == [32, 9, 31, 30]
    assert by_year.loc[2027].tolist() == [32, 17, 31, 30]


def test_entity_turnout_excludes_overseas_vote_and_is_ratio_of_totals() -> None:
    config = _load_yaml(ROOT / "configs/electoral_context.yaml")
    turnout = load_entity_turnout_source(ROOT, 2018, config)
    assert len(turnout) == 32
    assert not turnout["entity_id"].duplicated().any()
    aguascalientes = turnout.set_index("entity_id").loc["01"]
    assert aguascalientes["total_votes"] == 560_269
    assert aguascalientes["nominal_list"] == 943_448
    assert np.isclose(
        aguascalientes["turnout"],
        aguascalientes["total_votes"] / aguascalientes["nominal_list"],
    )


def test_entity_same_family_cycle_is_strictly_prior_and_complete() -> None:
    config = _load_yaml(ROOT / "configs/electoral_context.yaml")
    cycle = build_entity_cycle_table(ROOT, config)
    assert not cycle.duplicated(["target_year", "entity_id"]).any()
    assert cycle.groupby("target_year").size().eq(32).all()
    assert (cycle["entity_cycle_previous_source_year"] < cycle["entity_cycle_recent_source_year"]).all()
    assert (cycle["entity_cycle_recent_source_year"] < cycle["target_year"]).all()
    expected = {
        2015: (2003, 2009),
        2018: (2006, 2012),
        2021: (2009, 2015),
        2024: (2012, 2018),
        2027: (2015, 2021),
    }
    observed = cycle.groupby("target_year").agg(
        previous=("entity_cycle_previous_source_year", "first"),
        recent=("entity_cycle_recent_source_year", "first"),
    )
    assert {
        int(year): (int(row.previous), int(row.recent))
        for year, row in observed.iterrows()
    } == expected
    reconstructed = (
        cycle["entity_same_family_turnout_change"]
        - cycle["national_same_family_turnout_change"]
    )
    assert np.allclose(reconstructed, cycle["entity_same_family_change_minus_national"])


def test_enriched_mart_has_prior_competition_and_target_known_concurrency() -> None:
    path = ROOT / "artifacts/tables/feature_ablation_mart.parquet"
    if not path.exists():
        return
    mart = pd.read_parquet(path)
    required = {
        "prior_competition_margin",
        "prior_effective_number_options",
        "prior_competition_coverage",
        "local_election_concurrent",
        "local_executive_on_ballot",
        "local_congress_on_ballot",
        "municipal_on_ballot",
        "competition_source_year",
        "entity_same_family_turnout_change",
        "entity_same_family_change_minus_national",
        "entity_cycle_source_max_year",
    }
    assert required <= set(mart)
    assert (mart["competition_source_year"] < mart["target_year"]).all()
    assert (mart["entity_cycle_source_max_year"] < mart["target_year"]).all()
    assert mart["prior_competition_coverage"].between(0, 1).all()
