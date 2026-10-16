from pathlib import Path

from radar27.modeling.final_2027_municipal import run_final_2027_municipal


if __name__ == "__main__":
    run_final_2027_municipal(Path(__file__).resolve().parents[1])
