.PHONY: setup fetch-data audit clean-data geography evaluate features-models uncertainty calibration-adaptation forecast-2027 feature-ablation tabular-challengers dense-neural notebooks test

setup:
	uv sync --locked
	uv run python -m ipykernel install --user --name radar27 --display-name "Python (RADAR 27)"

fetch-data:
	uv run python scripts/run_notebooks.py --only setup_sources_download

audit:
	uv run python scripts/run_notebooks.py --only raw_schema_audit

clean-data:
	uv run python scripts/run_notebooks.py --only clean_ids_harmonization

geography:
	uv run python scripts/run_notebooks.py --only public_geography_lineage

evaluate:
	uv run python scripts/run_notebooks.py --only panel_backtest_evaluation

features-models:
	uv run python scripts/run_notebooks.py --only feature_model_evaluation

uncertainty:
	uv run python scripts/run_notebooks.py --only uncertainty_spatial_validation

calibration-adaptation:
	uv run python scripts/run_notebooks.py --only calibration_adaptation

forecast-2027:
	uv run python scripts/run_notebooks.py --only forecast_2027_experimental

feature-ablation:
	uv run python scripts/run_notebooks.py --only feature_ablation

tabular-challengers:
	uv run python scripts/run_notebooks.py --only tabular_challengers

dense-neural:
	uv run python scripts/run_notebooks.py --only dense_neural_challenger

notebooks:
	uv run python scripts/run_notebooks.py

test:
	uv run pytest -q
