.PHONY: setup fetch-data audit clean-data geography evaluate features-models notebooks test

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

notebooks:
	uv run python scripts/run_notebooks.py

test:
	uv run pytest -q
