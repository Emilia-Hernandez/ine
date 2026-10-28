from __future__ import annotations

import json
from pathlib import Path

from radar27.security.municipal import build_security_artifacts

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    result = build_security_artifacts(root / "configs/security_municipal.yaml")
    print(json.dumps(result, ensure_ascii=False, indent=2))
