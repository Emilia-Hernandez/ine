from __future__ import annotations

import argparse
import json
from pathlib import Path

from radar27.geography.section_graph import build_section_graph, download_section_archive


def main() -> None:
    parser = argparse.ArgumentParser(description="Construye el grafo seccional espacial para GNN")
    parser.add_argument(
        "--download",
        action="store_true",
        help="Descarga primero el ZIP oficial y valida tamano y SHA-256",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Vuelve a descargar aun si existe una copia valida",
    )
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    if args.download or args.force_download:
        download_section_archive(project_root, force=args.force_download)
    metadata = build_section_graph(project_root)
    print(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
