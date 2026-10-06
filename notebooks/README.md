# Notebooks RADAR 27

## Orden de la base de datos

1. `00_setup_sources_download.ipynb`: entorno, alcance, procedencia documental, descarga HTTP en streaming, SHA-256, CRC, rutas seguras e inventario ZIP.
2. `01_raw_schema_audit.ipynb`: lectura completa de 192 CSV, formato, esquema, nulos/vacíos, claves, duplicados, categorías, conciliación contable, indicadores y comparabilidad territorial nominal.
3. `02_clean_ids_harmonization.ipynb`: tipos, fechas, contratos de IDs, banderas conservadoras, Parquet por año, agregación provisional y bloqueo cartográfico explícito.
4. `03_geography_graph.ipynb`: fuente pública AMGE, parser, aristas elegibles, componentes y clases A/B/C/D por corte temporal.
5. `04_panel_build_audit.ipynb`: tres estrategias geográficas, cuatro backtests, cobertura, error, procedencia y fuga temporal.
6. `05_feature_model_evaluation.ipynb`: ECEG, agregados sexo–edad, feature mart A+B, modelos temporales, robustez y decisión.
7. `06_uncertainty_spatial_validation.ipynb`: intervalos conformales fuera de tiempo, cobertura por subgrupo y validación espacial reteniendo entidades completas.
8. `07_calibration_adaptation.ipynb`: corrección nacional por ciclo comparable, intervalos de análogo familiar y nuevo gate de preparación.
9. `09_feature_ablation.ipynb`: comparación controlada de historia, demografía electoral, ECEG y contexto territorial manteniendo fijo el boosting.
10. `10_tabular_challengers.ipynb`: comparación de cuatro familias de árboles con features, folds, baseline y corrección nacional constantes.
11. `08_forecast_2027_experimental.ipynb`: actualización final con las features y el modelo seleccionados, proyección sobre el snapshot 2024 y expansión A/B/C/D. El nombre 08 se conserva por procedencia; la canalización lo ejecuta después de 09 y 10.
12. `11_dense_neural_challenger.ipynb`: red MLP 64–32 con estandarización del objetivo y comparación temporal contra HistGradientBoosting.

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
| Intervalos conformales | 06 | `build-conformal-intervals` | `artifact-conformal-intervals` | `artifacts/tables/conformal_backtest_intervals.parquet` |
| Cobertura conformal | 06 | `build-conformal-intervals` | `artifact-conformal-coverage` | `artifacts/tables/conformal_coverage_metrics.csv` |
| Robustez espacial | 06 | `run-spatial-holdout` | `artifact-spatial-metrics` | `artifacts/tables/spatial_robustness_metrics.csv` |
| Decisión de incertidumbre | 06 | `write-uncertainty-decision` | `artifact-uncertainty-decision` | `artifacts/uncertainty_decision.json` |
| Reporte de incertidumbre | 06 | `write-uncertainty-report` | `artifact-uncertainty-report` | `artifacts/reports/uncertainty_spatial_validation.html` |
| Corrección nacional | 07 | `estimate-national-shift` | `artifact-shift-estimates` | `artifacts/tables/national_shift_estimates.csv` |
| Intervalos adaptativos | 07 | `compare-adaptive-intervals` | `artifact-adaptive-coverage` | `artifacts/tables/adaptive_interval_coverage.csv` |
| Decisión de adaptación | 07 | `write-adaptation-decision` | `artifact-adaptation-decision` | `artifacts/calibration_adaptation_decision.json` |
| Reporte de adaptación | 07 | `write-adaptation-report` | `artifact-adaptation-report` | `artifacts/reports/calibration_adaptation.html` |
| Feature mart 2027 | 08 | `build-forecast-2027-features` | `artifact-forecast-features` | `artifacts/tables/forecast_2027_feature_mart.parquet` |
| Predicciones seccionales 2027 | 08 | `expand-forecast-2027-sections` | `artifact-forecast-sections` | `artifacts/tables/forecast_2027_section_predictions.parquet` |
| Decisión 2027 | 08 | `write-forecast-2027-decision` | `artifact-forecast-decision` | `artifacts/forecast_2027_decision.json` |
| Reporte 2027 | 08 | `write-forecast-2027-report` | `artifact-forecast-report` | `artifacts/reports/forecast_2027_experimental.html` |
| Mart de ablación | 09 | `build-feature-ablation-mart` | `artifact-feature-ablation-mart` | `artifacts/tables/feature_ablation_mart.parquet` |
| Métricas de features | 09 | `run-feature-ablation` | `artifact-feature-ablation-metrics` | `artifacts/tables/feature_ablation_metrics.csv` |
| Decisión de features | 09 | `write-feature-ablation-decision` | `artifact-feature-ablation-decision` | `artifacts/feature_ablation_decision.json` |
| Reporte de ablación | 09 | `write-feature-ablation-report` | `artifact-feature-ablation-report` | `artifacts/reports/feature_ablation.html` |
| Predicciones de challengers | 10 | `run-tabular-challengers` | `artifact-challenger-predictions` | `artifacts/tables/tabular_challenger_predictions.parquet` |
| Métricas de challengers | 10 | `run-tabular-challengers` | `artifact-challenger-metrics` | `artifacts/tables/tabular_challenger_metrics.csv` |
| Decisión de challenger | 10 | `write-tabular-challenger-decision` | `artifact-challenger-decision` | `artifacts/tabular_challenger_decision.json` |
| Reporte de challengers | 10 | `write-tabular-challenger-report` | `artifact-challenger-report` | `artifacts/reports/tabular_challengers.html` |
| Predicciones de red densa | 11 | `run-dense-neural-challenger` | `artifact-neural-predictions` | `artifacts/tables/dense_neural_predictions.parquet` |
| Métricas de red densa | 11 | `run-dense-neural-challenger` | `artifact-neural-metrics` | `artifacts/tables/dense_neural_metrics.csv` |
| Decisión de red densa | 11 | `write-dense-neural-decision` | `artifact-neural-decision` | `artifacts/dense_neural_decision.json` |
| Reporte de red densa | 11 | `write-dense-neural-report` | `artifact-neural-report` | `artifacts/reports/dense_neural_challenger.html` |

Las copias ejecutadas y HTML conservan código visible. Un fallo deja evidencia parcial y no se registra como éxito.
