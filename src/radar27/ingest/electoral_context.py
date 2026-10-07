from __future__ import annotations

from pathlib import Path

from radar27.ingest.download_ccpc import download_source
from radar27.modeling.feature_models import _load_yaml


def download_electoral_context_sources(project_root: Path) -> list[dict[str, object]]:
    """Download and validate the frozen SICEE archives used for electoral context."""
    config = _load_yaml(project_root / "configs/electoral_context.yaml")
    rows: list[dict[str, object]] = []
    sources: dict[str, tuple[int, dict[str, object]]] = {}
    for group in ["turnout_sources", "competition_sources"]:
        for source_year, source in config[group].items():
            sources.setdefault(str(source["archive_path"]), (int(source_year), source))
    for source_year, source in sorted(sources.values()):
        destination = project_root / str(source["archive_path"])
        row, _ = download_source(
            source_id=f"sicee_federal_{source_year}_{source['ballot']}",
            year=int(source_year),
            kind="zip",
            url=str(source["url"]),
            destination=destination,
            notebook="scripts/download_electoral_context.py",
            cell_id="download-electoral-context-sources",
        )
        if row["sha256"] != str(source["sha256"]):
            raise ValueError(
                f"SHA-256 inesperado para {destination.name}: {row['sha256']}"
            )
        row["local_path"] = destination.relative_to(project_root).as_posix()
        rows.append(row)
    return rows
