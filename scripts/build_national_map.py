from __future__ import annotations

import argparse
import json
from pathlib import Path

from dashboard.map_assets import build_national_map


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera el mapa nacional ligero de RADAR 27")
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("dashboard/assets/sections_overview.fgb"),
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=Path("dashboard/assets/sections_national_v1.geojson.gz"),
    )
    args = parser.parse_args()
    print(json.dumps(build_national_map(args.source, args.target), indent=2))


if __name__ == "__main__":
    main()
