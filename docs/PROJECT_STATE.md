# Estado del proyecto

Actualizado: 2026-10-05.

Ejecución base combinada: `artifacts/runs/20261005T222756Z-phase1` (`success`; notebooks 00–01). Limpieza: `artifacts/runs/20261005T223526Z-data-foundation` (`success`; notebook 02). Linajes/evaluación: `artifacts/runs/20261005T225638Z-public-lineage-evaluation` (`success`; notebooks 03–04). Feature mart/modelos: `artifacts/runs/20261006T032315Z-feature-model-evaluation` (`success`; notebook 05).

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

## Comandos ejecutados

```bash
uv sync --locked
uv run python scripts/run_notebooks.py --only setup_sources_download --timeout 1800
uv run python scripts/run_notebooks.py --only raw_schema_audit --timeout 1800
uv run python scripts/run_notebooks.py --only clean_ids_harmonization --timeout 1800
uv run python scripts/run_notebooks.py --only public_geography_lineage --timeout 1800
uv run python scripts/run_notebooks.py --only panel_backtest_evaluation --timeout 1800
uv run python scripts/run_notebooks.py --only feature_model_evaluation --timeout 1800
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
- Modelo final 2027: **no entrenado**; boosting electoral aprobado como candidato de desarrollo.
- Crosswalk público: linajes AMGE implementados; geometrías completas no son necesarias para este baseline.
- Linajes públicos AMGE: **implementados hasta 2022**.
- Baseline temporal: **evaluado**; A+B aprobado como muestra principal.

## Bloqueos y pendientes

1. Incorporar relaciones públicas aprobadas durante 2023 o conservar 2024 como evidencia parcial.
2. Resolver vacíos de `DEF`/`DEL` y edades >100 sin imputación automática.
3. Contrastar agregados contra el dashboard con filtros/universo idénticos.
4. Diseñar intervalos predictivos y validación espacial por entidad para el candidato aprobado.
5. Definir el corte de información y el ensamblaje operacional para pronosticar 2027.

## Siguiente paso concreto

Calibrar incertidumbre del candidato aprobado mediante intervalos conformales temporalmente válidos y diagnóstico espacial por entidad. Después, congelar el corte de información para generar una primera proyección 2027, manteniendo la jerarquía documentada para C/D.
