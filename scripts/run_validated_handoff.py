from pathlib import Path

from radar27.modeling.validated_handoff import run_validated_handoff

if __name__ == "__main__":
    run_validated_handoff(Path(__file__).resolve().parents[1])

