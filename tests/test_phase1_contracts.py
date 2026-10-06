from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import nbformat
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_source_manifest_and_zip_integrity() -> None:
    manifest = pd.read_csv(ROOT / "data/manifests/source_manifest.csv", dtype={"year": "string"})
    assert len(manifest) == 7
    zip_rows = manifest[manifest["kind"].eq("zip")]
    assert set(zip_rows["year"].dropna().astype(int)) == {2009, 2012, 2015, 2018, 2021, 2024}
    assert manifest["http_status"].eq(200).all()
    assert (manifest["requested_url"] == manifest["final_url"]).all()
    for row in manifest.itertuples(index=False):
        path = ROOT / row.local_path
        assert path.is_file()
        assert path.stat().st_size == row.bytes
        assert sha256_file(path) == row.sha256
        if row.kind == "zip":
            assert zipfile.is_zipfile(path)
            with zipfile.ZipFile(path) as archive:
                assert archive.testzip() is None


def test_zip_member_inventory_contract() -> None:
    members = pd.read_csv(ROOT / "data/manifests/zip_member_inventory.csv")
    assert len(members) == 204
    counts = members.groupby("year").size()
    assert counts.eq(34).all()
    assert not members["member_name"].str.replace("\\", "/").str.split("/").apply(
        lambda parts: ".." in parts
    ).any()


def test_raw_audit_contracts() -> None:
    inventory = pd.read_parquet(ROOT / "artifacts/tables/raw_file_inventory.parquet")
    summary = pd.read_json(ROOT / "artifacts/tables/raw_year_summary.json")
    assert len(inventory) == 192
    assert inventory.groupby("year").size().eq(32).all()
    assert int(inventory["rows"].sum()) == 54_872_712
    assert summary["schema_matches_expected"].all()
    assert summary["accounting_mismatch_rows"].eq(0).all()
    assert summary["duplicate_key_extra_rows"].eq(0).all()
    assert summary["exact_duplicate_extra_rows"].eq(0).all()


def test_categories_distinguish_non_binary_availability() -> None:
    categories = pd.read_csv(
        ROOT / "artifacts/tables/category_inventory.csv", dtype={"value": "string"}
    )
    non_binary = categories[categories["column"].eq("SEXO") & categories["value"].eq("2")]
    assert non_binary["year"].tolist() == [2024]
    assert int(non_binary["rows"].iloc[0]) == 105
    assert int(non_binary["nominal_list"].iloc[0]) == 105


def test_indicator_denominators_and_accounting() -> None:
    summary = pd.read_json(ROOT / "artifacts/tables/raw_year_summary.json")
    identified = summary["sum_sv"] + summary["sum_nv"]
    assert (summary["sum_ln"] == identified + summary["sum_ns"]).all()
    participation = summary["sum_sv"] / identified
    abstention = summary["sum_nv"] / identified
    assert ((participation + abstention) - 1).abs().max() < 1e-12
    assert summary["identified_zero_rows"].gt(0).all()


def test_notebooks_have_stable_unique_cell_ids() -> None:
    for name in [
        "00_setup_sources_download.ipynb",
        "01_raw_schema_audit.ipynb",
        "02_clean_ids_harmonization.ipynb",
        "03_geography_graph.ipynb",
        "04_panel_build_audit.ipynb",
        "05_feature_model_evaluation.ipynb",
    ]:
        notebook = nbformat.read(ROOT / "notebooks" / name, as_version=4)
        cell_ids = [cell["id"] for cell in notebook.cells]
        assert len(cell_ids) == len(set(cell_ids))
        assert notebook.cells[0]["cell_type"] == "markdown"
        assert not any(cell.get("outputs") for cell in notebook.cells if cell["cell_type"] == "code")


def test_equivalence_matrix_marks_external_dashboard_fields() -> None:
    matrix = pd.read_csv(ROOT / "artifacts/tables/field_equivalence_matrix.csv")
    absent = matrix[matrix["campo_conceptual"].isin(["referente indígena", "referente afromexicano"])]
    year_columns = ["2009", "2012", "2015", "2018", "2021", "2024"]
    assert absent[year_columns].eq("NO PRESENTE EN CSV").all().all()


def test_run_manifests_do_not_claim_failed_runs_succeeded() -> None:
    for path in (ROOT / "artifacts/runs").glob("*/run_manifest.json"):
        run = json.loads(path.read_text(encoding="utf-8"))
        if run["status"] == "success":
            assert all(item["status"] == "success" for item in run["notebooks"])
