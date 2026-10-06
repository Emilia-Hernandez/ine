# RADAR 27

RADAR 27 es un proyecto reproducible para el Reto 2 del hackathon del INE. Construye una base longitudinal de participación electoral por sección, documenta cambios del Marco Geográfico Electoral, genera variables históricas por sexo y edad y compara modelos temporales sin utilizar información posterior a cada elección evaluada.

El repositorio contiene código, notebooks fuente, configuraciones, pruebas, documentación y manifiestos con URLs y hashes. **No contiene datos crudos, datos intermedios ni artefactos generados.** Esos directorios se reconstruyen localmente y están excluidos por `.gitignore`.

## Resultado actual

- Se auditaron 54,872,712 registros CCPC de elecciones federales 2009–2024.
- Los linajes territoriales públicos se clasifican como A/B/C/D.
- El universo principal usa secciones estables A y componentes oficiales B; C/D conservan respaldo jerárquico explícito.
- El candidato de desarrollo aprobado es un boosting electoral residual: en el fold principal 2021 reduce el MAE ponderado de 9.38 a 8.97 puntos porcentuales y aumenta cobertura de 93.77% a 96.10%.
- ECEG 2020 se usa sólo en la prueba secundaria 2024 porque su fecha oficial de modificación es posterior a la elección de 2021.
- La retención espacial de entidades no deteriora el error agregado. Una corrección basada en el ciclo anterior de la misma familia reduce el MAE 2021 a 8.31 pp, y el intervalo de análogo familiar eleva su cobertura de 62.35% a 90.41%.
- La cobertura adaptativa 2024 queda en 87.08%: se habilita experimentación interna 2027, pero todavía no intervalos publicables como garantía de 90%.
- La primera proyección experimental sobre el snapshot territorial 2024 cubre 70,751 secciones y produce 57.06% de participación ponderada; no es un pronóstico oficial ni tiene MAE 2027 observable.
- La ablación mantiene fijo el boosting y selecciona contexto territorial: reduce el MAE frente al conjunto actual en 2018, 2021 y 2024. ECEG mejora sólo 0.025 pp en su único fold válido y no se promueve al predictor puntual.

Los detalles metodológicos y límites están en `docs/FEATURE_MODEL_METHOD.md`, `docs/FEATURE_ABLATION_RESULTS.md`, `docs/FORECAST_2027_RESULTS.md` y `docs/DECISION_LOG.md`.

## Clonar y preparar el entorno

Requisitos probados:

- Git;
- Python 3.12;
- `uv`;
- aproximadamente 6 GB libres para descargas, extracciones, entorno y artefactos;
- conexión a internet para obtener las fuentes públicas.

```bash
git clone git@github.com:Emilia-Hernandez/ine.git
cd ine
uv sync --locked
```

Si se prefiere HTTPS:

```bash
git clone https://github.com/Emilia-Hernandez/ine.git
cd ine
uv sync --locked
```

El proyecto usa el entorno creado por `uv`; no es necesario activar `.venv` para ejecutar los comandos `uv run`.

## Dónde guardar los datos

Las rutas son relativas a la raíz del repositorio. No cambie nombres ni mueva archivos entre carpetas: los notebooks y las pruebas validan tamaños y SHA-256.

Después de preparar todas las fuentes, la estructura relevante debe ser:

```text
data/
├── raw/
│   ├── ccpc/
│   │   ├── 2009/DatosAbiertos_DECEyEC_ConteosCensales2009.zip
│   │   ├── 2012/DatosAbiertos_DECEyEC_ConteosCensales2012.zip
│   │   ├── 2015/DatosAbiertos_DECEyEC_ConteosCensales2015.zip
│   │   ├── 2018/DatosAbiertos_DECEyEC_ConteosCensales2018.zip
│   │   ├── 2021/DatosAbiertos_DECEyEC_ConteosCensales2021.zip
│   │   └── 2024/DatosAbiertos_DECEyEC_ConteosCensales2024.zip
│   ├── reference/Manual-Conteos-Censales-2009-2024.pdf
│   ├── public_ine/amge_2005_2022_onedrive.zip       # respaldo opcional
│   └── inegi/eceg_2020_csv.zip
├── interim/
│   ├── extracted/<año>/                             # generado por notebook 00
│   ├── harmonized_demographic/<año>/                # generado por notebook 02
│   ├── public_ine/amge_2005_2022.xlsx               # requerido por notebook 03
│   └── inegi/eceg_2020/                             # generado por notebook 05
└── manifests/                                       # sí está versionado
```

### 1. CCPC y manual del INE

El notebook 00 descarga automáticamente el manual y los seis ZIP desde las URLs declaradas en `configs/sources.yaml`, valida firma/CRC/hash y los guarda exactamente en `data/raw/ccpc/<año>/` y `data/raw/reference/`.

```bash
uv run python scripts/run_notebooks.py --only setup_sources_download --timeout 1800
```

No es necesario descargar esos siete archivos manualmente. Si ya existen, el proceso los verifica y se detiene si su contenido no corresponde al manifiesto.

### 2. Libro público AMGE 2005–2022

El INE publicó el libro dentro de una respuesta de transparencia. Descargue la carpeta pública indicada en `configs/public_geography.yaml`:

<https://1drv.ms/f/s!AtO0oFXXb9dE-b1Y9VF2635ojiBCLg?e=bzcsdF>

Del ZIP descargado extraiga `Relación de casos AMGE 2005-2022_Ago22.xlsx`, renómbrelo y colóquelo en:

```text
data/interim/public_ine/amge_2005_2022.xlsx
```

SHA-256 esperado del libro:

```text
a844e36c288a359a3e3fd05afc2a861f12a8d6df954238e1b28722e9705fed79
```

Opcionalmente conserve el ZIP original en `data/raw/public_ine/amge_2005_2022_onedrive.zip`; su SHA-256 registrado es:

```text
bf63c09dcc5cea00c25e2da0c353e308069c694284300f8df810e553f8cbcddf
```

El notebook 03 rechazará un libro con otro hash.

### 3. ECEG 2020 de INEGI

Descargue la distribución CSV oficial:

<https://www.inegi.org.mx/contenidos/programas/ccpv/2020/datosabiertos/geoelectorales/eceg_2020_csv.zip>

Guárdela sin extraer ni renombrar en:

```text
data/raw/inegi/eceg_2020_csv.zip
```

Tamaño esperado: `20,609,412` bytes. SHA-256 esperado:

```text
db357fee6f869ec10c7c996e72d4ab6a339d10b20b8043f63ab5a256339708fe
```

El notebook 05 valida el ZIP y extrae sólo los miembros necesarios bajo `data/interim/inegi/eceg_2020/`.

## Ejecutar la reproducción completa

Los notebooks se ejecutan con kernels independientes y entradas persistidas. El orden es obligatorio:

```bash
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
```

También se pueden ejecutar todos, después de colocar el libro AMGE y el ZIP ECEG en sus rutas:

```bash
uv run python scripts/run_notebooks.py --timeout 1800
```

Cada ejecución crea `artifacts/runs/<run_id>/` con notebooks ejecutados, HTML, logs, hashes y registro de artefactos. `artifacts/`, `data/raw/` y `data/interim/` no se versionan.

## Qué hace cada notebook

| Notebook | Propósito | Salidas principales |
|---|---|---|
| `00_setup_sources_download.ipynb` | Descarga segura de CCPC y manual; SHA-256, CRC, rutas y manifiestos. | `data/raw/`, `data/interim/extracted/`, manifiestos. |
| `01_raw_schema_audit.ipynb` | Audita 192 CSV: esquema, categorías, nulos, duplicados, rangos, contabilidad y granularidad. | Inventarios y reporte de auditoría. |
| `02_clean_ids_harmonization.ipynb` | Tipifica IDs y fechas, conserva anomalías explícitas y concilia agregados sección–año. | Parquet limpios y agregado provisional. |
| `03_geography_graph.ipynb` | Interpreta el libro AMGE, construye aristas/componentes y clases territoriales A/B/C/D. | Linajes y clases por corte temporal. |
| `04_panel_build_audit.ipynb` | Compara A, A+B y respaldo jerárquico con cuatro folds y un baseline común. | Métricas, predicciones y linaje de variables. |
| `05_feature_model_evaluation.ipynb` | Construye variables sexo–edad, integra ECEG con control temporal y evalúa ridge/boosting. | Feature mart, modelos, errores estratificados y decisión. |
| `06_uncertainty_spatial_validation.ipynb` | Calibra intervalos fuera de tiempo y retiene entidades completas. | Cobertura por subgrupo, robustez espacial y decisión de preparación. |
| `07_calibration_adaptation.ipynb` | Corrige el desplazamiento nacional con el ciclo comparable anterior y evalúa intervalos adaptativos. | Predicciones corregidas, comparación de cobertura y gate experimental 2027. |
| `08_forecast_2027_experimental.ipynb` | Entrena el modelo territorial seleccionado hasta 2024 y proyecta sobre el snapshot más reciente. | Predicciones A/B/C/D, intervalos recalibrados, registro y decisión experimental. |
| `09_feature_ablation.ipynb` | Mantiene fijo el boosting y compara historia, demografía, ECEG y contexto territorial. | Métricas por grupo, decisión de features y ruta para challengers. |
| `10_tabular_challengers.ipynb` | Mantiene fijas las features territoriales y compara HistGradientBoosting, XGBoost, LightGBM y Extra Trees. | Predicciones, métricas, registro y decisión de modelo. |
| `11_dense_neural_challenger.ipynb` | Compara una red densa 64–32 contra el árbol seleccionado con el mismo experimento. | Predicciones, métricas, diagnóstico de entrenamiento y decisión. |

El código que ejecutan los notebooks vive en `src/radar27/`; `scripts/build_notebooks.py` genera las fuentes `.ipynb` con IDs de celda estables y `scripts/run_notebooks.py` registra cada corrida.

## Pruebas y controles

Después de producir los datos y artefactos:

```bash
uv run ruff check src scripts tests
uv run pytest -q
```

Las pruebas comprueban hashes, conteos de filas, conciliación, unicidad, cobertura territorial, fuga temporal, reproducción del baseline, intervalos, retención espacial, adaptación por familia, proyección 2027 y ablación de variables. En la corrida de referencia pasan 41 pruebas.

## Política de versionado

Se versionan:

- código en `src/` y `scripts/`;
- notebooks fuente sin outputs;
- configuraciones y lockfile;
- pruebas y documentación;
- manifiestos pequeños en `data/manifests/`.

No se versionan:

- ZIP, CSV, XLSX o Parquet de datos;
- datos extraídos o armonizados;
- artefactos, modelos o notebooks ejecutados;
- `.venv`, `.env`, `.DS_Store`, `.obsidian`, cachés o archivos temporales.

Consulte `docs/PROJECT_STATE.md` para el estado actual y `docs/SOURCES.md` para la procedencia completa.
