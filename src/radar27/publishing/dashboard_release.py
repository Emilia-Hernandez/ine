"""Empaqueta una versión completa y cambia el puntero vigente atómicamente."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

DATA_FILES = ["dashboard_sections.parquet", "section_housing_density.parquet", "manifest.json"]
ASSET_FILES = ["sections_overview.fgb", "sections_detail.fgb", "state_boundaries.geojson"]


def _validate_source(data_dir: Path, assets_dir: Path, expected_model: str) -> dict[str, Any]:
    for name in DATA_FILES:
        if not (data_dir / name).exists():
            raise FileNotFoundError(data_dir / name)
    for name in ASSET_FILES:
        if not (assets_dir / name).exists():
            raise FileNotFoundError(assets_dir / name)
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    frame = pd.read_parquet(
        data_dir / "dashboard_sections.parquet",
        columns=["clave_seccion", "version_modelo", "perfil_electoral_id", "perfil_visual_id"],
    )
    if len(frame) != 70_751 or not frame["clave_seccion"].is_unique:
        raise ValueError("La versión candidata no conserva el universo de 70,751 secciones")
    model_versions = frame["version_modelo"].dropna().astype(str).unique().tolist()
    if model_versions != [expected_model] or manifest.get("handoff_version") != expected_model:
        raise ValueError("La versión candidata mezcla o no corresponde al modelo aprobado")
    if int(frame["perfil_visual_id"].isna().sum()) or int(frame["perfil_electoral_id"].isna().sum()):
        raise ValueError("La versión candidata contiene perfiles incompletos")
    return manifest


def _write_pointer(pointer: Path, payload: dict[str, Any]) -> None:
    pointer.parent.mkdir(parents=True, exist_ok=True)
    temporary = pointer.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, pointer)


def publish_dashboard_release(
    root: Path,
    version: str,
    expected_model: str,
    approved: bool,
) -> dict[str, Any]:
    if not approved:
        raise PermissionError("La publicación requiere --approve explícito")
    data_dir = root / "dashboard/data"
    assets_dir = root / "dashboard/assets"
    manifest = _validate_source(data_dir, assets_dir, expected_model)
    data_releases = data_dir / "releases"
    asset_releases = assets_dir / "releases"
    final_data = data_releases / version
    final_assets = asset_releases / version
    if final_data.exists() or final_assets.exists():
        raise FileExistsError(f"La versión {version} ya existe; no se sobrescribe")
    data_releases.mkdir(parents=True, exist_ok=True)
    asset_releases.mkdir(parents=True, exist_ok=True)
    staged_data = Path(tempfile.mkdtemp(prefix=f".{version}-", dir=data_releases))
    staged_assets = Path(tempfile.mkdtemp(prefix=f".{version}-", dir=asset_releases))
    try:
        for name in DATA_FILES:
            shutil.copy2(data_dir / name, staged_data / name)
        for name in ASSET_FILES:
            shutil.copy2(assets_dir / name, staged_assets / name)
        staged_manifest_path = staged_data / "manifest.json"
        staged_manifest = json.loads(staged_manifest_path.read_text(encoding="utf-8"))
        staged_manifest.pop("dashboard_release_candidate", None)
        staged_manifest["dashboard_release_version"] = version
        staged_manifest_path.write_text(
            json.dumps(staged_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        _validate_source(staged_data, staged_assets, expected_model)
        os.replace(staged_data, final_data)
        os.replace(staged_assets, final_assets)
    except Exception:
        shutil.rmtree(staged_data, ignore_errors=True)
        shutil.rmtree(staged_assets, ignore_errors=True)
        if final_data.exists() and not final_assets.exists():
            shutil.rmtree(final_data, ignore_errors=True)
        raise
    pointer = {
        "dashboard_release_version": version,
        "model_version": expected_model,
        "model_id": "A_nacional_actual",
        "published_date": str(datetime.now(UTC).date()),
        "data_file": f"dashboard/data/releases/{version}/dashboard_sections.parquet",
        "manifest_file": f"dashboard/data/releases/{version}/manifest.json",
        "asset_prefix": f"/assets/releases/{version}",
        "security_version": manifest.get("security_version"),
        "requires_dashboard_restart": True,
    }
    _write_pointer(data_dir / "current_release.json", pointer)
    return pointer


def rollback_dashboard_release(root: Path, version: str, approved: bool) -> dict[str, Any]:
    if not approved:
        raise PermissionError("El rollback requiere --approve explícito")
    data_dir = root / "dashboard/data/releases" / version
    assets_dir = root / "dashboard/assets/releases" / version
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    expected_model = str(manifest["handoff_version"])
    _validate_source(data_dir, assets_dir, expected_model)
    pointer = {
        "dashboard_release_version": version,
        "model_version": expected_model,
        "model_id": "A_nacional_actual",
        "published_date": str(datetime.now(UTC).date()),
        "data_file": f"dashboard/data/releases/{version}/dashboard_sections.parquet",
        "manifest_file": f"dashboard/data/releases/{version}/manifest.json",
        "asset_prefix": f"/assets/releases/{version}",
        "security_version": manifest.get("security_version"),
        "requires_dashboard_restart": True,
        "rollback": True,
    }
    _write_pointer(root / "dashboard/data/current_release.json", pointer)
    return pointer
