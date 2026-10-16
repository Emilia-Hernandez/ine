# Reproducibilidad

## Estado

**Reproducibilidad parcial y verificable, no reproducción limpia completa.** La evidencia local, artefactos y cálculos independientes concilian; el pipeline completo no se ejecutó porque sobrescribe artefactos originales y la auditoría tenía prohibido modificarlos.

## Entorno observado

| Componente | Versión |
|---|---:|
| Python | 3.12.13 |
| DuckDB | 1.5.6 |
| pandas | 2.3.3 |
| pyarrow | 21.0.0 |
| scikit-learn | 1.9.1 |
| NumPy | 2.5.3 |
| PyYAML | 6.0.3 |

Commit observado: `21ec39b` (`Add electoral context and turnout risk profiles`). `deliverables/` y `audit/` no están versionados en el estado revisado.

## Verificaciones ejecutadas

```bash
.venv/bin/pytest -q
.venv/bin/ruff check src scripts tests
PYTHONPATH=src .venv/bin/python audit/AUDIT_TESTS/run_audit.py
.venv/bin/python audit/AUDIT_TESTS/make_figures.py
```

Resultados:

- 100 pruebas del proyecto: PASS.
- lint de `src scripts tests`: PASS.
- auditoría independiente: genera resultados y completa assertions.
- advertencia no bloqueante de CPU durante pruebas.

## Reejecución de la auditoría

Desde la raíz del repositorio:

```bash
PYTHONPATH=src .venv/bin/python audit/AUDIT_TESTS/run_audit.py
.venv/bin/python audit/AUDIT_TESTS/make_figures.py
PYTHONPATH=src .venv/bin/pytest -q audit/AUDIT_TESTS/test_audit.py
```

Salidas esperadas:

- `audit/results/national_adjustment_*.csv|parquet`
- `audit/results/national_shift_definition.csv`
- `audit/results/classifier_*.csv|parquet`
- `audit/results/eceg_*.csv|json`
- `audit/results/percentile_*.csv|parquet`
- `audit/results/integrity_checks.csv`
- `audit/figures/*.svg`

Las semillas están fijadas en 2701. Los bootstraps de auditoría usan 500 réplicas y muestreo por entidad.

## Límites

1. La reproducción parte de artefactos locales ya construidos; no demuestra que una máquina limpia descargue y regenere todo sin intervención.
2. No se consultaron orígenes remotos; los SHA-256 prueban integridad respecto del manifiesto local, no autenticidad actual del servidor.
3. Los cuatro DOCX se renderizaron y revisaron visualmente, pero no son el formato PDF requerido por la convocatoria.
4. No existe un lockfile único que capture sistema operativo, bibliotecas nativas y todos los paquetes.
5. No hay hash publicado del entregable final ni manifiesto que vincule documento, tablas y commit.

## Requisitos para reproducción limpia

- Añadir un modo `--output-root` para que el pipeline no escriba sobre evidencia.
- Fijar dependencias con hashes y documentar versión de sistema.
- Crear un comando único que descargue/verifique, transforme, entrene, evalúe y exporte.
- Generar `artifact_manifest.csv` con ruta, SHA-256, filas, columnas, commit y timestamp.
- Versionar sólo el reporte canónico, su PDF, la base anonimizada y el mapa ejecutable.
- Incorporar una prueba de humo desde un directorio temporal vacío.
