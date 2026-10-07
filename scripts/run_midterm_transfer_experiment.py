from __future__ import annotations

import json
from pathlib import Path

from radar27.modeling.midterm_transfer import run_midterm_transfer_experiment


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    _, metrics, _, decision = run_midterm_transfer_experiment(project_root)
    print(
        json.dumps(
            {"metrics": metrics.to_dict(orient="records"), "decision": decision},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
