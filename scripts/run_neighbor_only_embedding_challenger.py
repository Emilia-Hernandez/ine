from __future__ import annotations

import json
from pathlib import Path

from radar27.modeling.graph_embedding_challenger import run_graph_embedding_challenger


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    _, metrics, _, decision = run_graph_embedding_challenger(
        project_root,
        "configs/neighbor_only_embedding_challenger.yaml",
    )
    print(
        json.dumps(
            {
                "metrics": metrics.to_dict(orient="records"),
                "decision": decision,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
