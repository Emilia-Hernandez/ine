from pathlib import Path

from radar27.modeling.final_2027 import run_final_2027


if __name__ == "__main__":
    run_final_2027(Path(__file__).resolve().parents[1])
