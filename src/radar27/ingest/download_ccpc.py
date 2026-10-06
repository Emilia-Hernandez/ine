from __future__ import annotations

import csv
import hashlib
import os
import shutil
import stat
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

import requests
import yaml

MANIFEST_FIELDS = [
    "source_id",
    "year",
    "kind",
    "requested_url",
    "redirect_chain",
    "final_url",
    "retrieved_at_utc",
    "http_status",
    "content_type",
    "content_length_header",
    "last_modified",
    "etag",
    "local_path",
    "bytes",
    "sha256",
    "validation_status",
    "notebook",
    "cell_id",
]


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_sources(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def _looks_like_html(prefix: bytes, content_type: str) -> bool:
    sample = prefix.lstrip().lower()
    return "text/html" in content_type.lower() or sample.startswith((b"<!doctype html", b"<html"))


def _validate_zip_path(member: zipfile.ZipInfo) -> None:
    normalized = member.filename.replace("\\", "/")
    member_path = PurePosixPath(normalized)
    if member_path.is_absolute() or ".." in member_path.parts:
        raise ValueError(f"Miembro ZIP inseguro: {member.filename!r}")
    mode = member.external_attr >> 16
    if stat.S_ISLNK(mode):
        raise ValueError(f"Enlace simbólico no permitido en ZIP: {member.filename!r}")


def validate_zip(path: Path) -> list[dict[str, Any]]:
    if not zipfile.is_zipfile(path):
        raise ValueError(f"No es ZIP válido: {path}")
    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as archive:
        for member in archive.infolist():
            _validate_zip_path(member)
            rows.append(
                {
                    "member_name": member.filename,
                    "is_dir": member.is_dir(),
                    "compressed_bytes": member.compress_size,
                    "uncompressed_bytes": member.file_size,
                    "crc32": f"{member.CRC:08x}",
                    "compression": member.compress_type,
                }
            )
        bad_member = archive.testzip()
        if bad_member is not None:
            raise ValueError(f"CRC inválido en {path.name}: {bad_member}")
    return rows


def safe_extract_zip(path: Path, destination: Path) -> int:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    extracted = 0
    with zipfile.ZipFile(path) as archive:
        for member in archive.infolist():
            _validate_zip_path(member)
            target = (destination / member.filename).resolve()
            if target != root and root not in target.parents:
                raise ValueError(f"Extracción fuera del destino: {member.filename!r}")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
            extracted += 1
    return extracted


def download_source(
    *,
    source_id: str,
    year: int | None,
    kind: str,
    url: str,
    destination: Path,
    notebook: str,
    cell_id: str,
    retries: int = 3,
    timeout: tuple[int, int] = (30, 180),
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for attempt in range(retries):
        temp_path = destination.with_name(f".{destination.name}.{uuid4().hex}.part")
        try:
            with requests.get(
                url,
                stream=True,
                allow_redirects=True,
                timeout=timeout,
                headers={"User-Agent": "RADAR27/0.1 (auditoria academica; datos abiertos INE)"},
            ) as response:
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "")
                digest = hashlib.sha256()
                size = 0
                prefix = b""
                with temp_path.open("xb") as output:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        if len(prefix) < 512:
                            prefix += chunk[: 512 - len(prefix)]
                        output.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
                    output.flush()
                    os.fsync(output.fileno())
                if size == 0:
                    raise ValueError("Respuesta vacía")
                if _looks_like_html(prefix, content_type):
                    raise ValueError("La respuesta parece HTML, no el archivo solicitado")
                downloaded_hash = digest.hexdigest()
                if destination.exists():
                    existing_hash = sha256_file(destination)
                    if existing_hash != downloaded_hash:
                        raise FileExistsError(
                            f"Instantánea existente distinta: {destination}; "
                            f"existente={existing_hash}, nueva={downloaded_hash}"
                        )
                    temp_path.unlink()
                else:
                    temp_path.replace(destination)
                members: list[dict[str, Any]] = []
                validation_status = "downloaded_sha256_verified"
                if kind == "zip":
                    members = validate_zip(destination)
                    validation_status = "zip_signature_crc_paths_verified"
                elif kind == "pdf" and not prefix.startswith(b"%PDF"):
                    raise ValueError("La fuente declarada PDF no tiene firma PDF")
                redirect_chain = " | ".join(
                    f"{item.status_code}:{item.url}" for item in response.history
                )
                row = {
                    "source_id": source_id,
                    "year": year if year is not None else "",
                    "kind": kind,
                    "requested_url": url,
                    "redirect_chain": redirect_chain,
                    "final_url": response.url,
                    "retrieved_at_utc": datetime.now(UTC).isoformat(),
                    "http_status": response.status_code,
                    "content_type": content_type,
                    "content_length_header": response.headers.get("Content-Length", ""),
                    "last_modified": response.headers.get("Last-Modified", ""),
                    "etag": response.headers.get("ETag", ""),
                    "local_path": destination.as_posix(),
                    "bytes": destination.stat().st_size,
                    "sha256": sha256_file(destination),
                    "validation_status": validation_status,
                    "notebook": notebook,
                    "cell_id": cell_id,
                }
                return row, members
        except Exception as exc:  # noqa: BLE001 - el reintento registra cualquier fallo de transferencia/validación
            last_error = exc
            if temp_path.exists():
                temp_path.unlink()
            if attempt + 1 < retries:
                time.sleep(2**attempt)
    assert last_error is not None
    raise last_error


def write_csv_atomic(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{uuid4().hex}.part")
    with temp_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        stream.flush()
        os.fsync(stream.fileno())
    temp_path.replace(path)


def download_configured_sources(
    project_root: Path,
    *,
    notebook: str = "notebooks/00_setup_sources_download.ipynb",
    cell_id: str = "download-official-sources",
    extract: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    config = load_sources(project_root / "configs/sources.yaml")
    manifest_rows: list[dict[str, Any]] = []
    member_rows: list[dict[str, Any]] = []

    manual = config["manual"]
    manual_row, _ = download_source(
        source_id=manual["id"],
        year=None,
        kind=manual["kind"],
        url=manual["url"],
        destination=project_root / "data/raw/reference" / manual["filename"],
        notebook=notebook,
        cell_id=cell_id,
    )
    manual_row["local_path"] = Path(manual_row["local_path"]).relative_to(project_root).as_posix()
    manifest_rows.append(manual_row)

    for year_text, source in sorted(config["elections"].items(), key=lambda item: int(item[0])):
        year = int(year_text)
        destination = project_root / "data/raw/ccpc" / str(year) / source["filename"]
        row, members = download_source(
            source_id=f"ccpc_federal_{year}",
            year=year,
            kind=source["kind"],
            url=source["url"],
            destination=destination,
            notebook=notebook,
            cell_id=cell_id,
        )
        row["local_path"] = Path(row["local_path"]).relative_to(project_root).as_posix()
        manifest_rows.append(row)
        for member in members:
            member_rows.append(
                {
                    "source_id": row["source_id"],
                    "year": year,
                    "archive_path": destination.relative_to(project_root).as_posix(),
                    **member,
                }
            )
        if extract:
            safe_extract_zip(destination, project_root / "data/interim/extracted" / str(year))

    write_csv_atomic(
        project_root / "data/manifests/source_manifest.csv",
        manifest_rows,
        MANIFEST_FIELDS,
    )
    member_fields = [
        "source_id",
        "year",
        "archive_path",
        "member_name",
        "is_dir",
        "compressed_bytes",
        "uncompressed_bytes",
        "crc32",
        "compression",
    ]
    write_csv_atomic(
        project_root / "data/manifests/zip_member_inventory.csv",
        member_rows,
        member_fields,
    )
    return manifest_rows, member_rows
