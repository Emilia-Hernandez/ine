from __future__ import annotations

import argparse
import json
from pathlib import Path

from radar27.geography.temporal_graphs import (
    build_temporal_graphs,
    download_temporal_archives,
)
from radar27.modeling.gnn_dataset import build_gnn_dataset


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Construye snapshots temporales y tensores auditables para una GNN"
    )
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--force-download", action="store_true")
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    if args.download or args.force_download:
        download_temporal_archives(project_root, force=args.force_download)
    graph_metadata = build_temporal_graphs(project_root)
    dataset_metadata = build_gnn_dataset(project_root)
    print(
        json.dumps(
            {"temporal_graphs": graph_metadata, "gnn_dataset": dataset_metadata},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
