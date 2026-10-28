from __future__ import annotations

import argparse
import json
from pathlib import Path

from radar27.publishing.dashboard_release import (
    publish_dashboard_release,
    rollback_dashboard_release,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Publicación explícita y atómica de RADAR 27")
    parser.add_argument("--version", required=True)
    parser.add_argument("--model-version", default="radar27-final-2027-municipal.1")
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.rollback:
        result = rollback_dashboard_release(root, args.version, args.approve)
    else:
        result = publish_dashboard_release(root, args.version, args.model_version, args.approve)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
