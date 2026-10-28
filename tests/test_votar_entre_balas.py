from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
VEB = ROOT / "artifacts/security/radar27-votar-entre-balas-2026-10-24.1"


def _read(name: str) -> pd.DataFrame:
    return pd.read_parquet(VEB / name)


def test_source_integrity_unit_and_cutoff_are_explicit() -> None:
    manifest = json.loads((VEB / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["dataset_version"] == "radar27-votar-entre-balas-2026-10-24.1"
    assert manifest["cutoff_date"] == "2026-10-24"
    assert manifest["latest_event_date"] == "2026-09-29"
    assert manifest["unit_of_source_rows"] == "victim_or_installation"
    assert manifest["unit_of_indicator"] == "distinct_id_evento"
    hashes = {item["role"]: item["sha256"] for item in manifest["sources"]}
    assert hashes["download_bundle"] == (
        "c30a1348b0e5da61d509eb44c276b2a2a69e8e782b2289cc38b68e4bde1cf32d"
    )
    assert manifest["source_audit"]["blank_trailing_rows_excluded"] == 286
    assert manifest["source_audit"]["rows_missing_event_id"] == 1


def test_events_are_unique_and_never_exceed_cutoff() -> None:
    events = _read("events.parquet")
    assert len(events) == 2_604
    assert events["id_evento"].notna().all()
    assert events["id_evento"].is_unique
    assert events["event_date"].max() <= pd.Timestamp("2026-10-24")
    assert events["victim_or_installation_rows"].sum() == 3_081
    assert events["municipal_target"].sum() == 2_052


def test_municipal_aggregates_count_events_not_victim_rows() -> None:
    events = _read("events.parquet")
    features = _read("municipal_features_asof.parquet")
    current = features[features["cutoff_label"].eq("forecast_2027")]
    matched = events[events["ine_municipality_key"].notna()]
    expected_main = matched.loc[matched["municipal_target"], "id_evento"].nunique()
    expected_all = matched["id_evento"].nunique()
    assert current["municipal_attacks_cumulative"].sum() == expected_main == 2_051
    assert current["territorial_attacks_all_levels_cumulative"].sum() == expected_all == 2_603
    assert expected_all < matched["victim_or_installation_rows"].sum()


def test_windows_are_reproducible_and_2026_is_incomplete() -> None:
    events = _read("events.parquet")
    features = _read("municipal_features_asof.parquet")
    annual = _read("municipal_attacks_annual.parquet")
    current = features[features["cutoff_label"].eq("forecast_2027")]
    matched_municipal = events[
        events["municipal_target"] & events["ine_municipality_key"].notna()
    ]
    for months, column in ((12, "municipal_attacks_12m"), (24, "municipal_attacks_24m")):
        start = pd.Timestamp("2026-10-24") - pd.DateOffset(months=months)
        expected = matched_municipal.loc[
            matched_municipal["event_date"].gt(start)
            & matched_municipal["event_date"].le(pd.Timestamp("2026-10-24")),
            "id_evento",
        ].nunique()
        assert current[column].sum() == expected
    year_2026 = annual[annual["year"].eq(2026)]
    assert not year_2026["year_complete_at_cutoff"].any()
    assert year_2026["period_end"].eq(pd.Timestamp("2026-10-24")).all()


def test_official_crosswalk_handles_inegi_and_ine_key_difference() -> None:
    events = _read("events.parquet")
    los_cabos = events[events["inegi_municipality_key"].eq("03:008")]
    assert not los_cabos.empty
    assert los_cabos["ine_municipality_key"].eq("03:004").all()
    recent = events[events["inegi_municipality_key"].isin(["02:006", "02:007", "12:082", "12:083"])]
    assert recent["ine_municipality_key"].notna().all()
    unmatched = pd.read_csv(VEB / "unmatched_records.csv", dtype="string")
    assert set(unmatched["source_row"]) == {"2271", "2400"}


def test_section_join_is_many_to_one_without_event_multiplication() -> None:
    sections = _read("section_veb_context.parquet")
    features = _read("municipal_features_asof.parquet")
    current = features[features["cutoff_label"].eq("forecast_2027")]
    assert len(sections) == 70_751
    assert sections["clave_seccion"].is_unique
    valid = sections[sections["veb_data_status"].ne("municipality_crosswalk_unavailable")]
    assert valid.groupby("clave_municipio")["municipal_attacks_cumulative"].nunique().max() == 1
    section_once = sections.drop_duplicates("clave_municipio")
    assert section_once["municipal_attacks_cumulative"].sum() == current[
        "municipal_attacks_cumulative"
    ].sum()


def test_zero_is_distinct_from_unavailable_crosswalk() -> None:
    features = _read("municipal_features_asof.parquet")
    current = features[features["cutoff_label"].eq("forecast_2027")]
    zero = current[current["veb_data_status"].eq("zero_registered_attacks_in_monitored_source")]
    unavailable = current[current["veb_data_status"].eq("municipality_crosswalk_unavailable")]
    assert len(unavailable) == 8
    assert zero["municipal_attacks_cumulative"].eq(0).all()
    assert unavailable["inegi_municipality_keys"].isna().all()
    assert unavailable["municipal_attacks_cumulative"].isna().all()
    assert unavailable["territorial_attacks_all_levels_cumulative"].isna().all()


def test_historical_features_are_temporally_bounded_but_not_claimed_as_asof() -> None:
    events = _read("events.parquet")
    features = _read("municipal_features_asof.parquet")
    for label, cutoff in {
        "election_2018": "2018-04-30",
        "election_2021": "2021-04-30",
        "election_2024": "2024-04-30",
    }.items():
        rows = features[features["cutoff_label"].eq(label)]
        expected = events.loc[
            events["municipal_target"]
            & events["ine_municipality_key"].notna()
            & events["event_date"].le(pd.Timestamp(cutoff)),
            "id_evento",
        ].nunique()
        assert rows["municipal_attacks_cumulative"].sum() == expected
        assert rows["historical_availability_status"].eq(
            "current_snapshot_reconstructed_by_event_date_not_historical_asof"
        ).all()
