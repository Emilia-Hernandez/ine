# Notebooks RADAR 27

## Orden de la base de datos

1. `00_setup_sources_download.ipynb`: entorno, alcance, procedencia documental, descarga HTTP en streaming, SHA-256, CRC, rutas seguras e inventario ZIP.
2. `01_raw_schema_audit.ipynb`: lectura completa de 192 CSV, formato, esquema, nulos/vacíos, claves, duplicados, categorías, conciliación contable, indicadores y comparabilidad territorial nominal.
3. `02_clean_ids_harmonization.ipynb`: tipos, fechas, contratos de IDs, banderas conservadoras, Parquet por año, agregación provisional y bloqueo cartográfico explícito.
4. `03_geography_graph.ipynb`: fuente pública AMGE, parser, aristas elegibles, componentes y clases A/B/C/D por corte temporal.
5. `04_panel_build_audit.ipynb`: tres estrategias geográficas, cuatro backtests, cobertura, error, procedencia y fuga temporal.
6. `05_feature_model_evaluation.ipynb`: ECEG, agregados sexo–edad, feature mart A+B, modelos temporales, robustez y decisión.

Cada notebook detecta la raíz del proyecto, usa entradas persistidas y funciona con **Restart Kernel → Run All**. La ejecución automatizada usa un kernel nuevo por notebook:

```bash
uv run python scripts/run_notebooks.py --timeout 1800
```

## Índice de resultados

| Resultado | Notebook | Celda estable | Etiqueta | Artefacto |
|---|---|---|---|---|
| Manifiesto de fuentes | 00 | `download-official-sources` | `artifact-source-manifest` | `data/manifests/source_manifest.csv` |
| Inventario ZIP | 00 | `summarize-zip-members` | `artifact-zip-inventory` | `data/manifests/zip_member_inventory.csv` |
| Inventario físico | 01 | `run-physical-audit` | `artifact-raw-file-inventory` | `artifacts/tables/raw_file_inventory.parquet` |
| Categorías | 01 | `audit-categories` | `categories` | `artifacts/tables/category_inventory.csv` |
| Equivalencia de campos | 01 | `build-field-equivalence` | `artifact-field-equivalence` | `artifacts/tables/field_equivalence_matrix.csv` |
| Cobertura territorial nominal | 01 | `audit-territorial-comparability` | `territory` | `artifacts/tables/raw_section_frame_inventory.parquet` |
| Reporte resumido | 01 | `audit-final-checks` | `summary` | `artifacts/reports/raw_audit.html` |
| Resumen de limpieza | 02 | `run-harmonization` | `artifact-harmonization-summary` | `artifacts/tables/harmonization_year_summary.csv` |
| Bitácora de retención | 02 | `show-exclusion-log` | `artifact-exclusion-log` | `artifacts/tables/cleaning_exclusion_log.csv` |
| Agregado y conciliación | 02 | `validate-provisional-aggregation` | `artifact-aggregation-reconciliation` | `artifacts/tables/provisional_section_year_totals.parquet` |
| Transiciones nominales | 02 | `show-section-transitions` | `artifact-section-transitions` | `artifacts/tables/section_code_transition_summary.csv` |
| Eventos AMGE | 03 | `parse-amge-events` | `artifact-amge-events` | `artifacts/tables/amge_event_rows.parquet` |
| Clases territoriales | 03 | `build-confidence-classes` | `artifact-confidence-classes` | `artifacts/tables/section_confidence_by_election.parquet` |
| Métricas de backtest | 04 | `run-geography-backtests` | `artifact-backtest-metrics` | `artifacts/tables/backtest_metrics.csv` |
| Linaje de variables | 04 | `audit-variable-lineage` | `artifact-variable-lineage` | `artifacts/tables/variable_lineage.csv` |
| Reporte de evaluación | 04 | `write-evaluation-report` | `artifact-evaluation-report` | `artifacts/reports/public_lineage_evaluation.html` |
| Fuente ECEG | 05 | `prepare-eceg-source` | `artifact-eceg-manifest` | `data/manifests/eceg_source_manifest.csv` |
| Feature mart | 05 | `build-feature-mart` | `artifact-feature-mart` | `artifacts/tables/feature_mart_ab.parquet` |
| Métricas de modelos | 05 | `run-feature-model-backtests` | `artifact-model-metrics` | `artifacts/tables/model_backtest_metrics.csv` |
| Decisión de modelo | 05 | `run-feature-model-backtests` | `artifact-model-decision` | `artifacts/model_decision.json` |
| Reporte de modelos | 05 | `write-feature-model-report` | `artifact-feature-model-report` | `artifacts/reports/feature_model_evaluation.html` |

Las copias ejecutadas y HTML conservan código visible. Un fallo deja evidencia parcial y no se registra como éxito.
