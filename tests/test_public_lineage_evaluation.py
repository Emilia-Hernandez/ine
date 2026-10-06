from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_public_amge_source_is_frozen() -> None:
    with (ROOT / "configs/public_geography.yaml").open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    source = config["sources"]["amge_history"]
    workbook = ROOT / source["local_workbook"]
    assert workbook.is_file()
    assert workbook.stat().st_size == 376_914
    assert sha256_file(workbook) == source["workbook_sha256"]
    manifest = pd.read_csv(ROOT / "data/manifests/public_geography_manifest.csv")
    row = manifest[manifest["source_id"].eq("amge_history")].iloc[0]
    assert bool(row["local_exists"])
    assert row["sha256"] == source["workbook_sha256"]


def test_amge_parser_contracts() -> None:
    events = pd.read_parquet(ROOT / "artifacts/tables/amge_event_rows.parquet")
    edges = pd.read_parquet(ROOT / "artifacts/tables/amge_lineage_edges.parquet")
    affected = pd.read_parquet(ROOT / "artifacts/tables/amge_affected_sections.parquet")
    assert len(events) == 2_663
    assert int(events["lineage_eligible"].sum()) == 1_469
    assert len(edges) == 7_819
    assert len(affected) == 11_631
    assert events["event_id"].is_unique
    assert not edges.duplicated().any()
    assert set(edges["mapping_shape"]) <= {"one_to_many", "many_to_one"}
    assert edges["effective_year"].le(2022).all()
    assert edges["origin_section_key"].str.fullmatch(r"\d{2}:\d{4}").all()
    assert edges["destination_section_key"].str.fullmatch(r"\d{2}:\d{4}").all()


def test_confidence_classes_are_exhaustive_per_cutoff() -> None:
    classes = pd.read_parquet(ROOT / "artifacts/tables/section_confidence_by_election.parquet")
    expected_sections = {2015: 68_362, 2018: 68_408, 2021: 68_812, 2024: 70_751}
    assert set(classes["geography_confidence_class"]) == {"A", "B", "C", "D"}
    assert not classes.duplicated(["target_year", "section_key_observed"]).any()
    observed = classes.groupby("target_year")["section_key_observed"].nunique().to_dict()
    assert observed == expected_sections
    assert (classes["max_geography_event_year_allowed"] < classes["target_year"]).all()


def test_backtests_are_temporal_and_fallback_is_complete() -> None:
    predictions = pd.read_parquet(ROOT / "artifacts/tables/backtest_predictions.parquet")
    metrics = pd.read_csv(ROOT / "artifacts/tables/backtest_metrics.csv")
    assert len(metrics) == 12
    assert set(metrics["target_year"]) == {2015, 2018, 2021, 2024}
    assert set(metrics["scenario"]) == {
        "stable_only",
        "stable_plus_lineage",
        "hierarchical_fallback",
    }
    assert (predictions["feature_year"] < predictions["target_year"]).all()
    # Los escenarios restringidos conservan filas sin historia elegible para que
    # la falta de cobertura sea auditable; sólo las predicciones emitidas deben
    # pertenecer al intervalo de una proporción.
    emitted = predictions["prediction"].dropna()
    assert emitted.between(0, 1).all()
    fallback = metrics[metrics["scenario"].eq("hierarchical_fallback")]
    assert fallback["section_coverage"].eq(1).all()
    assert fallback["nominal_list_coverage"].eq(1).all()


def test_predeclared_2021_decision_gate_passes() -> None:
    metrics = pd.read_csv(ROOT / "artifacts/tables/backtest_metrics.csv")
    primary = metrics[metrics["target_year"].eq(2021)].set_index("scenario")
    stable = primary.loc["stable_only"]
    lineage = primary.loc["stable_plus_lineage"]
    assert lineage["section_coverage"] > stable["section_coverage"]
    assert lineage["identified_weighted_mae"] <= stable["identified_weighted_mae"]
    assert primary.loc["hierarchical_fallback", "section_coverage"] == 1
    fold_2024 = metrics[metrics["target_year"].eq(2024)]
    assert fold_2024["evidence_status"].eq("partial_amge_ends_2022").all()


def test_every_modeled_variable_has_audit_lineage() -> None:
    lineage = pd.read_csv(ROOT / "artifacts/tables/variable_lineage.csv")
    required = {
        "variable",
        "role",
        "description",
        "source_columns",
        "available_from",
        "transformation",
        "leakage_risk",
        "missing_policy",
        "implementation",
    }
    assert required <= set(lineage.columns)
    assert not lineage[list(required)].isna().any().any()
    assert lineage["variable"].is_unique
