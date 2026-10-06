# Estado del proyecto

Actualizado: 2026-10-06.

Ejecución base combinada: `artifacts/runs/20261005T222756Z-phase1` (`success`; notebooks 00–01). Limpieza: `artifacts/runs/20261005T223526Z-data-foundation` (`success`; notebook 02). Linajes/evaluación: `artifacts/runs/20261005T225638Z-public-lineage-evaluation` (`success`; notebooks 03–04). Feature mart/modelos: `artifacts/runs/20261006T032315Z-feature-model-evaluation` (`success`; notebook 05). Incertidumbre/espacio: `artifacts/runs/20261006T145041Z-radar27-pipeline` (`success`; notebook 06). Adaptación de calibración: `artifacts/runs/20261006T155852Z-radar27-pipeline` (`success`; notebook 07). Proyección experimental 2027: `artifacts/runs/20261006T161557Z-radar27-pipeline` (`success`; notebook 08). Ablación de variables: `artifacts/runs/20261006T163019Z-radar27-pipeline` (`success`; notebook 09).

## Alcance completado

- entorno Python 3.12 bloqueado con `uv`;
- configuración y runner con kernel nuevo, detención ante errores, notebooks ejecutados, HTML, logs y hashes;
- descarga HTTP y validación de manual + seis ZIP oficiales;
- extracción segura separada de crudos;
- inventario de 204 miembros ZIP (192 CSV, 6 TXT, 6 directorios);
- lectura completa de 54,872,712 filas;
- auditoría de formatos, esquemas, vacíos, claves, duplicados, categorías, rangos, conciliación e IDs territoriales;
- corrección trazable de participación/abstención en el plan maestro;
- documentación inicial de fuentes, indicadores, diccionario, auditoría y decisiones.
- tipado y serialización reproducible de 54,872,712 filas sin exclusiones;
- IDs de registro únicos, fechas exactas y nulos semánticos;
- agregado provisional sección–año con conciliación exacta y estado geográfico explícito;
- contrato de IDs y evidencia oficial del bloqueo cartográfico.
- ingesta auditable de la publicación pública AMGE 2005–2022;
- 2,663 eventos, 7,819 aristas elegibles y clases A/B/C/D por corte temporal;
- cuatro backtests congelados de tres estrategias geográficas;
- linaje por variable, procedencia por predicción y pruebas de fuga temporal.
- ingesta validada de 68,806 secciones ECEG 2020 y restricción explícita de disponibilidad;
- 406,866 agregados sección–año de composición y comportamiento;
- feature mart A+B con 243,108 unidades-fold;
- backtests estrictamente temporales de ridge y boosting, error por entidad/clase e importancia;
- boosting electoral residual aprobado: 8.97 pp de MAE ponderado y 96.10% de cobertura en 2021.
- intervalos conformales móviles al 90% evaluados sin usar residuos del target;
- cobertura conformal global de 62.35% en 2021 y 97.10% en 2024;
- validación espacial de cinco grupos, 32 entidades y tres cortes temporales;
- diagnóstico espacial agregado sin deterioro de MAE, con heterogeneidad estatal explícita;
- corrección nacional por ciclo comparable: MAE 2021 de 8.97 a 8.31 pp y sesgo de −4.60 a −1.59 pp;
- intervalo de análogo familiar con cobertura 90.41% en 2021 y 87.08% en 2024;
- canalización experimental 2027 habilitada; garantía pública de intervalos todavía bloqueada.
- feature mart operacional 2027 construido con corte electoral máximo 2024;
- boosting residual reentrenado con 2015–2024 y especificación congelada;
- 70,751 secciones del snapshot 2024 proyectadas: 65,095 con modelo A/B y 5,656 con respaldo C/D;
- participación experimental ponderada de 57.06%, etiquetada no publicable.
- seis grupos de features comparados con el mismo boosting y los mismos folds;
- contexto territorial promovido: MAE 8.10 pp en 2021 y mejora frente al conjunto actual en los tres folds;
- ECEG no promovido al predictor puntual: mejora de sólo 0.025 pp en 2024;
- sexo/edad y ECEG conservados para segmentación, interpretación y escenarios.

## Archivos clave

- `configs/sources.yaml`
- `configs/notebook_pipeline.yaml`
- `data/manifests/source_manifest.csv`
- `data/manifests/zip_member_inventory.csv`
- `artifacts/tables/raw_file_inventory.parquet`
- `artifacts/tables/raw_year_summary.json`
- `artifacts/tables/category_inventory.csv`
- `artifacts/tables/field_equivalence_matrix.csv`
- `artifacts/tables/raw_section_frame_inventory.parquet`
- `artifacts/reports/raw_audit.html`
- `notebooks/00_setup_sources_download.ipynb`
- `notebooks/01_raw_schema_audit.ipynb`
- `notebooks/02_clean_ids_harmonization.ipynb`
- `artifacts/tables/harmonization_year_summary.csv`
- `artifacts/tables/cleaning_exclusion_log.csv`
- `artifacts/tables/provisional_section_year_totals.parquet`
- `artifacts/tables/aggregation_reconciliation.csv`
- `artifacts/tables/section_code_transition_summary.csv`
- `docs/ID_CONTRACT.md`
- `docs/HARMONIZATION_REPORT.md`
- `notebooks/03_geography_graph.ipynb`
- `notebooks/04_panel_build_audit.ipynb`
- `configs/public_geography.yaml`
- `configs/evaluation.yaml`
- `configs/features.yaml`
- `artifacts/tables/backtest_metrics.csv`
- `artifacts/tables/backtest_predictions.parquet`
- `artifacts/tables/variable_lineage.csv`
- `docs/PUBLIC_GEOGRAPHY_METHOD.md`
- `docs/MODELING_CONTRACT_BASELINE.md`
- `docs/EVALUATION_RESULTS.md`
- `notebooks/05_feature_model_evaluation.ipynb`
- `configs/inegi_eceg.yaml`
- `configs/modeling.yaml`
- `artifacts/tables/feature_mart_ab.parquet`
- `artifacts/tables/model_backtest_metrics.csv`
- `artifacts/model_decision.json`
- `docs/FEATURE_MODEL_METHOD.md`
- `docs/MODEL_EVALUATION_RESULTS.md`
- `notebooks/06_uncertainty_spatial_validation.ipynb`
- `configs/uncertainty.yaml`
- `artifacts/tables/conformal_backtest_intervals.parquet`
- `artifacts/tables/conformal_coverage_metrics.csv`
- `artifacts/tables/spatial_holdout_predictions.parquet`
- `artifacts/tables/spatial_robustness_metrics.csv`
- `artifacts/uncertainty_decision.json`
- `docs/UNCERTAINTY_SPATIAL_METHOD.md`
- `docs/UNCERTAINTY_SPATIAL_RESULTS.md`
- `notebooks/07_calibration_adaptation.ipynb`
- `configs/calibration_adaptation.yaml`
- `artifacts/tables/national_shift_estimates.csv`
- `artifacts/tables/shift_corrected_predictions.parquet`
- `artifacts/tables/adaptive_interval_predictions.parquet`
- `artifacts/tables/adaptive_interval_coverage.csv`
- `artifacts/calibration_adaptation_decision.json`
- `docs/CALIBRATION_ADAPTATION_METHOD.md`
- `docs/CALIBRATION_ADAPTATION_RESULTS.md`
- `notebooks/08_forecast_2027_experimental.ipynb`
- `configs/forecast_2027.yaml`
- `artifacts/tables/forecast_2027_feature_mart.parquet`
- `artifacts/tables/forecast_2027_model_units.parquet`
- `artifacts/tables/forecast_2027_section_predictions.parquet`
- `artifacts/tables/forecast_2027_summary.csv`
- `artifacts/forecast_2027_model_registry.json`
- `artifacts/forecast_2027_decision.json`
- `docs/FORECAST_2027_METHOD.md`
- `docs/FORECAST_2027_RESULTS.md`
- `notebooks/09_feature_ablation.ipynb`
- `configs/feature_ablation.yaml`
- `artifacts/tables/feature_ablation_mart.parquet`
- `artifacts/tables/feature_ablation_predictions.parquet`
- `artifacts/tables/feature_ablation_metrics.csv`
- `artifacts/feature_ablation_decision.json`
- `docs/FEATURE_ABLATION_METHOD.md`
- `docs/FEATURE_ABLATION_RESULTS.md`
- `notebooks/10_tabular_challengers.ipynb`
- `configs/tabular_challengers.yaml`
- `artifacts/tables/tabular_challenger_predictions.parquet`
- `artifacts/tables/tabular_challenger_metrics.csv`
- `artifacts/tables/tabular_challenger_registry.csv`
- `artifacts/tabular_challenger_decision.json`
- `docs/TABULAR_CHALLENGERS_METHOD.md`
- `docs/TABULAR_CHALLENGERS_RESULTS.md`
- `notebooks/11_dense_neural_challenger.ipynb`
- `configs/dense_neural_challenger.yaml`
- `artifacts/tables/dense_neural_predictions.parquet`
- `artifacts/tables/dense_neural_metrics.csv`
- `artifacts/tables/dense_neural_registry.csv`
- `artifacts/dense_neural_decision.json`
- `docs/DENSE_NEURAL_METHOD.md`
- `docs/DENSE_NEURAL_RESULTS.md`

## Comandos ejecutados

```bash
uv sync --locked
uv run python scripts/run_notebooks.py --only setup_sources_download --timeout 1800
uv run python scripts/run_notebooks.py --only raw_schema_audit --timeout 1800
uv run python scripts/run_notebooks.py --only clean_ids_harmonization --timeout 1800
uv run python scripts/run_notebooks.py --only public_geography_lineage --timeout 1800
uv run python scripts/run_notebooks.py --only panel_backtest_evaluation --timeout 1800
uv run python scripts/run_notebooks.py --only feature_model_evaluation --timeout 1800
uv run python scripts/run_notebooks.py --only uncertainty_spatial_validation --timeout 1800
uv run python scripts/run_notebooks.py --only calibration_adaptation --timeout 1800
uv run python scripts/run_notebooks.py --only feature_ablation --timeout 1800
uv run python scripts/run_notebooks.py --only tabular_challengers --timeout 1800
uv run python scripts/run_notebooks.py --only forecast_2027_experimental --timeout 1800
uv run python scripts/run_notebooks.py --only dense_neural_challenger --timeout 1800
uv run pytest -q
```

## Estado metodológico

- Participación oficial comprobada: `SV/(SV+NV)`.
- Abstención oficial comprobada: `NV/(SV+NV)`.
- NS queda fuera de ambas y se reporta como `NS/LN`.
- Unidad real: sección × sexo × edad por elección, no casilla.
- Esquema: 16 columnas comunes; semántica territorial no totalmente común.
- Capa limpia por elección: **construida y conciliada**.
- Agregado sección–año por código observado: **construido, provisional**.
- Panel longitudinal de evaluación: **construido** con clases A/B/C/D; el panel de producción 2027 sigue pendiente.
- Target de evaluación: **congelado** como `SV/(SV+NV)`; target futuro 2027 aún no observable.
- Modelo 2027: **actualizado como experimento** con contexto territorial sobre snapshot 2024; no aprobado para publicación ni denominado modelo final oficial.
- Features seleccionadas para la siguiente iteración: **historia + contexto territorial**; ECEG permanece fuera del predictor puntual.
- Familia tabular seleccionada: **HistGradientBoosting residual**; XGBoost quedó casi empatado, pero no ganó el gate 2021.
- Red neuronal densa: **evaluada y no promovida**; empeoró 2021 y falló robustez en 2018.
- Crosswalk público: linajes AMGE implementados; geometrías completas no son necesarias para este baseline.
- Linajes públicos AMGE: **implementados hasta 2022**.
- Baseline temporal: **evaluado**; A+B aprobado como muestra principal.

## Bloqueos y pendientes

1. Incorporar relaciones públicas aprobadas durante 2023 o conservar 2024 como evidencia parcial.
2. Resolver vacíos de `DEF`/`DEL` y edades >100 sin imputación automática.
3. Contrastar agregados contra el dashboard con filtros/universo idénticos.
4. Obtener geometrías/adyacencias actualizadas antes de embeddings espaciales o GNN; ampliar evidencia temporal antes de publicar incertidumbre 2027.

## Siguiente paso concreto

Priorizar la adquisición y validación de geometrías/adyacencias seccionales antes de embeddings o GNN. Mientras tanto, conservar HistGradientBoosting como modelo experimental y mejorar evidencia temporal e incertidumbre.
