from pathlib import Path

from radar27.modeling.section_trend_2027 import ExperimentPaths, run_experiment

ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    metrics, counts = run_experiment(
        ExperimentPaths(
            totals=ROOT / "artifacts/tables/provisional_section_year_totals.parquet",
            confidence=ROOT / "artifacts/tables/section_confidence_by_election.parquet",
            backtest_a=ROOT / "handoff/FINAL_2027/PREDICCIONES_BACKTEST_PAREADAS.parquet",
            master_2027=ROOT / "handoff/FINAL_2027_MUNICIPAL/SECCIONES_ELECTORALES_2027.csv",
            output_dir=ROOT / "experiments/section_trend_2027",
        )
    )
    print(metrics.to_string(index=False))
    print(counts)
