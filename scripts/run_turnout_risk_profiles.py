from __future__ import annotations

import json
from pathlib import Path

from radar27.modeling.turnout_risk_profiles import run_turnout_risk_profiles

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    result = run_turnout_risk_profiles(root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
