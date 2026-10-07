from __future__ import annotations

import argparse
from pathlib import Path

from radar27.ingest.electoral_context import download_electoral_context_sources


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Descarga y valida las bases SICEE para contexto electoral."
    )
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    rows = download_electoral_context_sources(args.project_root.resolve())
    for row in rows:
        print(f"{row['source_id']}: {row['bytes']} bytes {row['sha256']}")


if __name__ == "__main__":
    main()
