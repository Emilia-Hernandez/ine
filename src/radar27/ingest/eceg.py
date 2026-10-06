from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import duckdb
import pandas as pd
import yaml


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sql_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def _config(project_root: Path) -> dict[str, Any]:
    with (project_root / "configs/inegi_eceg.yaml").open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def _validate_archive(path: Path, expected_bytes: int, expected_sha256: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(
            f"Falta {path}. Descargue el ZIP desde la URL oficial declarada en "
            "configs/inegi_eceg.yaml."
        )
    if path.stat().st_size != expected_bytes:
        raise ValueError(f"Tamaño ECEG inesperado: {path.stat().st_size} != {expected_bytes}")
    observed = _sha256(path)
    if observed != expected_sha256:
        raise ValueError(f"SHA-256 ECEG inesperado: {observed} != {expected_sha256}")
    if not zipfile.is_zipfile(path):
        raise ValueError("El archivo ECEG no es un ZIP válido")
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("El ZIP ECEG no supera la verificación CRC")
        for item in archive.infolist():
            parts = PurePosixPath(item.filename.replace("\\", "/")).parts
            if item.filename.startswith(("/", "\\")) or ".." in parts:
                raise ValueError(f"Ruta insegura en ZIP ECEG: {item.filename}")


def _extract_required(project_root: Path, archive_path: Path, config: dict[str, Any]) -> dict[str, Path]:
    source = config["source"]
    destination = project_root / "data/interim/inegi/eceg_2020"
    destination.mkdir(parents=True, exist_ok=True)
    members = {
        "section": source["section_member"],
        "dictionary": source["dictionary_member"],
        "metadata": source["metadata_member"],
    }
    output: dict[str, Path] = {}
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        missing = set(members.values()) - names
        if missing:
            raise ValueError(f"Miembros ECEG faltantes: {sorted(missing)}")
        for label, member in members.items():
            archive.extract(member, destination)
            output[label] = destination / member
    return output


def prepare_eceg(project_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Validate the frozen public ECEG package and create selected section covariates."""
    config = _config(project_root)
    source = config["source"]
    archive_path = project_root / source["local_zip"]
    _validate_archive(archive_path, int(source["bytes"]), source["sha256"])
    members = _extract_required(project_root, archive_path, config)

    manifest = pd.DataFrame(
        [
            {
                **{key: value for key, value in source.items() if key not in {"section_member", "dictionary_member", "metadata_member"}},
                "local_exists": True,
                "observed_bytes": archive_path.stat().st_size,
                "observed_sha256": _sha256(archive_path),
                "validation_status": "zip_signature_crc_paths_hash_verified",
            }
        ]
    )
    manifest_path = project_root / "data/manifests/eceg_source_manifest.csv"
    manifest.to_csv(manifest_path, index=False)

    descriptor = pd.read_csv(members["dictionary"], encoding="cp1252")
    descriptor.columns = [
        "topic",
        "indicator",
        "definition",
        "mnemonic",
        "unit",
        "source",
        "temporality",
        "observation_unit",
        "reference_population",
    ]
    selected = config["selected_variables"]
    selected_names = list(selected)
    dictionary = descriptor[descriptor["mnemonic"].isin(selected_names)].copy()
    dictionary["output_variable"] = dictionary["mnemonic"].map(
        {name: values["output"] for name, values in selected.items()}
    )
    dictionary["selection_role"] = dictionary["mnemonic"].map(
        {name: values["role"] for name, values in selected.items()}
    )
    if set(dictionary["mnemonic"]) != set(selected_names):
        missing = set(selected_names) - set(dictionary["mnemonic"])
        raise ValueError(f"Variables seleccionadas ausentes del diccionario ECEG: {sorted(missing)}")
    dictionary.to_csv(project_root / "artifacts/tables/eceg_selected_variable_dictionary.csv", index=False)

    aliases = ",\n".join(
        f'cast("{name}" AS DOUBLE) AS {values["output"]}' for name, values in selected.items()
    )
    connection = duckdb.connect(database=":memory:")
    try:
        frame = connection.execute(
            f"""
            SELECT
              lpad(cast(ENTIDAD AS VARCHAR), 2, '0') AS entity_id,
              lpad(cast(SECCION AS VARCHAR), 4, '0') AS section_number,
              lpad(cast(ENTIDAD AS VARCHAR), 2, '0') || ':' ||
                lpad(cast(SECCION AS VARCHAR), 4, '0') AS section_key_observed,
              lpad(cast(MUNICIPIO AS VARCHAR), 3, '0') AS municipality_id_inegi,
              cast(TIPO AS TINYINT) AS eceg_section_type_code,
              {aliases}
            FROM read_csv_auto('{_sql_path(members['section'])}', header=true)
            ORDER BY entity_id, section_number
            """
        ).df()
    finally:
        connection.close()
    if frame["section_key_observed"].duplicated().any():
        raise ValueError("ECEG contiene claves de sección duplicadas")
    if len(frame) != 68_806:
        raise ValueError(f"Número de secciones ECEG inesperado: {len(frame)}")
    frame.to_parquet(project_root / "artifacts/tables/eceg_2020_section_features.parquet", index=False)
    return manifest, dictionary, frame
