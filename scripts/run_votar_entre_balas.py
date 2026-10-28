from __future__ import annotations

import argparse
import json
from pathlib import Path

from radar27.security.votar_entre_balas import build_votar_entre_balas_artifacts

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Procesa Votar entre Balas con un corte temporal configurable."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "configs/votar_entre_balas.yaml",
    )
    parser.add_argument(
        "--cutoff-date",
        help="Sustituye cutoff_date del YAML (AAAA-MM-DD) sin modificar el archivo.",
    )
    args = parser.parse_args()
    result = build_votar_entre_balas_artifacts(args.config, cutoff_override=args.cutoff_date)
    print(json.dumps(result, ensure_ascii=False, indent=2))
