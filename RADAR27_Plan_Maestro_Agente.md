# RADAR 27 — Plan maestro de ejecución
## Protocolo de ejecución en notebooks con trazabilidad, explicación y reproducción por el equipo

**Proyecto:** RADAR 27  
**Reto:** Predicción y escenarios de riesgo de abstención  
**Propósito de este archivo:** servir como contrato operativo. Un agente debe poder seguirlo sin reinterpretar el diseño, desde la descarga de los datos hasta la generación de modelos, mapas, dashboard y entregables. Toda etapa analítica se ejecutará en notebooks Jupyter con código visible, resultados e interpretación en Markdown. El equipo deberá poder reproducir la ejecución de referencia después de clonar el repositorio y obtener los datos y dependencias documentados.

---

# 0. Regla máxima

> **Nada entra al análisis si no puede rastrearse hasta su fuente, su transformación, su versión de código y el notebook y celda que lo produjeron.**

El proyecto debe priorizar:

1. reproducibilidad;
2. ausencia de leakage;
3. trazabilidad;
4. claridad;
5. validez fuera de muestra;
6. parsimonia;
7. interpretabilidad;
8. sofisticación únicamente cuando aporte valor.

No se debe optimizar por usar el modelo más complejo.

---

# 1. Definición de “terminado”

El proyecto sólo está completo cuando existen:

- datos crudos inmutables;
- manifiesto de fuentes y hashes;
- notebook reproducible de descarga y utilidades de ingesta auditables;
- diccionario de datos;
- reporte de calidad;
- dataset analítico versionado;
- geometrías validadas;
- EDA reproducible con tablas, figuras, código e interpretación dentro de notebooks;
- targets formalmente definidos;
- features documentadas;
- splits temporales congelados;
- baselines;
- modelos challengers;
- tabla de comparación fuera de muestra;
- intervalos de incertidumbre;
- explicación global y local;
- mapa de riesgo;
- escenarios sin/con intervención;
- semáforo territorial;
- dashboard ejecutable;
- archivos GeoJSON/GPKG/CSV finales;
- pruebas automatizadas;
- logs de experimentos;
- README de reproducción;
- reporte metodológico;
- presentación de máximo 10 diapositivas;
- registro de limitaciones y decisiones;
- notebooks de todas las etapas, con Markdown antes y después de cada bloque analítico;
- copias ejecutadas y HTML con código visible;
- registro de artefactos que relacione cada resultado con su notebook/celda;
- reproducción de referencia comprobada por otro integrante desde un clon limpio.

---

# 2. Stack recomendado

## Lenguaje

Python 3.12.

## Gestión de entorno

Preferencia:

- `uv` para dependencias y lockfile.

Archivos obligatorios:

- `pyproject.toml`
- `uv.lock`
- `.python-version`

## Datos

- DuckDB: consultas y ensamblado del panel.
- PyArrow/Parquet: almacenamiento analítico.
- Pandas o Polars: transformaciones locales.
- GeoPandas/Shapely: geometría.
- PySAL: autocorrelación espacial.
- NetworkX o igraph: prototipado de grafos.

## Modelos

- scikit-learn;
- LightGBM o XGBoost;
- SHAP;
- MAPIE o implementación propia validada para conformal prediction;
- PyTorch/PyTorch Geometric únicamente para challengers de embeddings/GNN.

## Notebooks y ejecución

- JupyterLab e ipykernel para trabajar y ejecutar manualmente;
- nbformat y nbclient para ejecución automatizada con kernel limpio;
- nbconvert para HTML de auditoría con código visible.

Incluir estas dependencias en el lockfile y verificar que el kernel use el entorno del proyecto.

## Tracking

- Git;
- DVC para datos/artefactos grandes;
- MLflow local para experimentos;
- hashes SHA-256 adicionales para fuentes crudas.

## Calidad

- Ruff;
- Pytest;
- Pandera para contratos de datos;
- pre-commit.

## Visualización

- Matplotlib para gráficos analíticos;
- Plotly para interacción;
- Streamlit para demo;
- PyDeck/MapLibre/Folium para mapas según rendimiento.

No añadir una librería nueva si una ya incluida resuelve el problema.

---

# 3. Estructura del repositorio

```text
radar27/
├── README.md
├── pyproject.toml
├── uv.lock
├── .python-version
├── .gitignore
├── dvc.yaml
├── params.yaml
├── Makefile
├── data/
│   ├── raw/                 # inmutable
│   ├── interim/
│   ├── processed/
│   ├── external/
│   └── manifests/
├── docs/
│   ├── DATA_DICTIONARY.md
│   ├── DATA_LINEAGE.md
│   ├── MODELING_CONTRACT.md
│   ├── ID_CONTRACT.md
│   ├── DECISION_LOG.md
│   ├── REPRODUCTION_AUDIT.md
│   ├── LIMITATIONS.md
│   └── SOURCES.md
├── configs/
│   ├── sources.yaml
│   ├── features.yaml
│   ├── models.yaml
│   ├── notebook_pipeline.yaml
│   ├── reproduction_reference.yaml
│   └── dashboard.yaml
├── src/radar27/
│   ├── ingest/
│   ├── clean/
│   ├── validate/
│   ├── geo/
│   ├── features/
│   ├── graph/
│   ├── embeddings/
│   ├── models/
│   ├── uncertainty/
│   ├── explain/
│   ├── scenarios/
│   ├── optimize/
│   └── viz/
├── scripts/
│   └── run_notebooks.py      # ejecuta notebooks; no contiene otro análisis
├── notebooks/
│   ├── README.md
│   ├── 00_setup_sources_download.ipynb
│   ├── 01_raw_schema_audit.ipynb
│   ├── 02_clean_ids_harmonization.ipynb
│   ├── 03_geography_graph.ipynb
│   ├── 04_panel_build_audit.ipynb
│   ├── 05_eda.ipynb
│   ├── 06_targets_splits_features.ipynb
│   ├── 07_baselines_regressions.ipynb
│   ├── 08_boosting_backtests.ipynb
│   ├── 09_embeddings_analogues.ipynb
│   ├── 10_gnn_challenger.ipynb
│   ├── 11_comparison_robustness_selection.ipynb
│   ├── 12_uncertainty_explanations.ipynb
│   ├── 13_risk_anomalies.ipynb
│   ├── 14_scenarios_optimization.ipynb
│   ├── 15_maps_exports_dashboard.ipynb
│   └── 16_reproducibility_audit.ipynb
├── tests/
│   ├── test_ids.py
│   ├── test_schemas.py
│   ├── test_targets.py
│   ├── test_leakage.py
│   ├── test_geo.py
│   └── test_pipeline.py
├── artifacts/
│   ├── figures/
│   ├── tables/
│   ├── models/
│   ├── geo/
│   ├── reports/
│   └── runs/                # notebooks ejecutados, HTML y registros por run_id
├── app/
│   └── streamlit_app.py
└── mlruns/
```

## 3.1 Regla obligatoria: análisis en notebooks

**Los notebooks son la fuente ejecutable y auditable del análisis.** La descarga y sus comprobaciones, limpieza, armonización, EDA, transformaciones, grafos, embeddings, regresiones, entrenamiento, evaluación, incertidumbre, explicabilidad, escenarios, optimización y visualizaciones deben ejecutarse desde notebooks y mostrar sus resultados en ellos.

Cada notebook debe permitir responder: **¿qué datos entraron, qué código produjo este resultado, qué parámetros se usaron y cómo se interpreta?** No basta con cargar una imagen, una tabla de coeficientes o un modelo generado fuera del notebook.

`src/radar27/` puede contener utilidades reutilizables y comprobadas para descargas, validación, geometría, serialización y funciones compartidas con la app. Los notebooks deben mostrar las llamadas, sus argumentos y sus comprobaciones. Las decisiones analíticas, fórmulas, filtros, especificaciones de regresión, preprocesamiento, separación de folds, entrenamiento y construcción de figuras deben ser visibles en celdas. Si se extrae una función analítica común a `src/`, el notebook debe enlazar su implementación relativa y mostrar su código relevante en una celda de auditoría o apéndice; no duplicar una segunda implementación que pueda divergir. La app debe reutilizar esa misma lógica cuando la necesite.

No aceptar una única celda `run_pipeline()` o `train_all()` que oculte todo el procedimiento. Tampoco mantener un pipeline alternativo de scripts que produzca los resultados oficiales por una ruta diferente. Los scripts de ejecución automatizan los notebooks; no sustituyen su análisis.

La aplicación Streamlit sigue siendo una app: consume los artefactos exportados por los notebooks y reutiliza las funciones compartidas de escenarios. Todas las cifras, mapas y simulaciones de la demo deben tener un equivalente reproducible y explicado dentro de un notebook.

## 3.2 Índice obligatorio de notebooks

Crear `notebooks/README.md` con esta ruta de lectura y `configs/notebook_pipeline.yaml` con el orden real de ejecución, entradas, salidas, dependencias y condiciones de activación. Los números fijan el orden de lectura; el manifiesto fija las dependencias. No ejecutar simplemente todos los archivos encontrados por orden alfabético.

| Notebook | Contenido y resultados auditables |
|---|---|
| `00_setup_sources_download.ipynb` | Entorno, configuración, fuentes, descarga, hashes e inventario de ZIP. |
| `01_raw_schema_audit.ipynb` | Auditoría física, esquemas por año, nulos, duplicados y diccionario inicial. |
| `02_clean_ids_harmonization.ipynb` | Contrato de IDs, limpieza, homologación, exclusiones y reconciliación contable. |
| `03_geography_graph.ipynb` | Cartografía, CRS, joins, geometrías, vecinos y grafo de contigüidad. |
| `04_panel_build_audit.ipynb` | Construcción de ambos paneles, cobertura y validaciones. |
| `05_eda.ipynb` | EDA temporal, territorial y demográfico, Moran/LISA, tablas y mapas descriptivos. |
| `06_targets_splits_features.ipynb` | Target, corte informativo, folds congelados, features históricas, relativas y espaciales. |
| `07_baselines_regressions.ipynb` | Baselines y Elastic Net; cualquier otra regresión que se justifique, con especificación y diagnósticos. |
| `08_boosting_backtests.ipynb` | Boosting tabular y espacial, tuning permitido, predicciones fuera de muestra y métricas. |
| `09_embeddings_analogues.ipynb` | Node2Vec, embedding temporal si procede, análogos, UMAP y estabilidad. |
| `10_gnn_challenger.ipynb` | Challenger opcional: arquitectura, entrenamiento, validación y resultados por seed. |
| `11_comparison_robustness_selection.ipynb` | Ablaciones, comparación por fold, sensibilidad, errores por territorio y selección final. |
| `12_uncertainty_explanations.ipynb` | Calibración separada, cobertura, intervalos, SHAP y explicación local/global. |
| `13_risk_anomalies.ipynb` | Scores, semáforo, cambios atípicos, revisión de casos y mapas de incertidumbre. |
| `14_scenarios_optimization.ipynb` | Escenarios con/sin intervención, sensibilidad, priorización y optimización. |
| `15_maps_exports_dashboard.ipynb` | Mapas finales, exportables y equivalencia de resultados con la app. |
| `16_reproducibility_audit.ipynb` | Verificación de artefactos, comparación con la referencia y resumen de reproducibilidad. |

Las secciones metodológicas posteriores conservan sus requisitos, pero deben implementarse en el notebook asignado. Todos los notebooks analíticos se ejecutan con kernel independiente y entradas explícitas; comparten archivos versionados, no variables en memoria.

`07` y `08` se ejecutan antes de los challengers. `09` y `10` deben reportar métricas comparables a los baselines; `11` integra la evidencia. Después de seleccionar el modelo se repiten su calibración y explicación oficiales en `12`; exploraciones preliminares deben identificarse como tales. `16` lee los registros ya producidos por `00`–`15`; el runner agrega su estado final después, sin crear una dependencia circular.

## 3.3 Contrato de Markdown, código y resultados

Cada notebook debe abrir con Markdown que explique:

- pregunta que responde y lugar en el proyecto;
- entradas, versiones/hashes y notebooks previos necesarios;
- unidad de observación, muestra y fechas disponibles;
- métodos, supuestos y criterios de aceptación;
- outputs que generará y tiempo/memoria aproximados medidos.

Cada bloque analítico debe seguir esta secuencia:

1. **Markdown antes del código:** qué se hará, por qué, variables y unidades, filtros, supuestos y qué resultado se espera comprobar.
2. **Celda de código visible:** cálculos, parámetros y llamadas relevantes; usar IDs de celda estables y etiquetas para ubicar resultados.
3. **Output inmediatamente debajo:** figura, tabla, coeficientes, métricas o validaciones; mostrar también observaciones excluidas y advertencias pertinentes.
4. **Markdown después del resultado:** cómo leerlo, hallazgos obtenidos, magnitud, comparación con baseline, limitaciones y decisión que permite tomar.

La explicación posterior debe hablar de los resultados reales de esa ejecución. No dejar frases genéricas como “interpretar aquí” ni inventar una mejora antes de entrenar. Las cifras y comparaciones que cambian al reejecutar deben generarse desde los objetos calculados mediante texto Markdown renderizado con `IPython.display.Markdown`, junto con una celda Markdown de interpretación metodológica. Las conclusiones cualitativas escritas a mano deben señalar el `run_id` al que corresponden y revisarse al cambiar datos/modelos; una conclusión no revisada debe marcarse como pendiente en la nueva ejecución.

Evitar celdas enormes que mezclen carga, ajuste, evaluación y veinte gráficos. Separar esos pasos para que el equipo pueda auditar cada uno. No ocultar código en las versiones HTML de auditoría. SQL, fórmulas de transformación y filtros también deben verse.

Al final de cada notebook incluir Markdown con hallazgos, verificaciones aprobadas/fallidas, decisiones, limitaciones, outputs y siguiente paso. La ausencia de datos suficientes o el descarte de un challenger también son resultados documentables.

### Requisito especial para cada regresión y modelo

Mostrar explícitamente:

- target, unidad, horizonte y ecuación/especificación cuando aplique;
- lista de regresores/features, transformaciones, categorías de referencia e imputación;
- filas, secciones y elecciones usadas para train, validación, calibración y test;
- pipeline, estimador, hiperparámetros efectivos, seed y código de `fit`/`predict`;
- tuning/early stopping dentro de entrenamiento/validación, sin usar test para elegir parámetros;
- evaluación por fold y contra baseline, sin limitarse a resultados in-sample;
- diagnósticos relevantes, fallos y tiempo de ejecución.

Para Elastic Net mostrar coeficientes, intercepto y escala de las variables. Si se incorporan regresiones econométricas, explicar la interpretación de coeficientes, unidades, ponderaciones y la elección de errores estándar frente a dependencia territorial/temporal. No agregar OLS o regresiones adicionales sólo para llenar el notebook. No atribuir p-valores convencionales a coeficientes penalizados ni presentar asociaciones como causalidad.

Para boosting mostrar configuración, curvas de entrenamiento cuando estén disponibles, importancia y SHAP en el notebook correspondiente. Para embeddings/GNN mostrar inputs, máscaras, aristas permitidas, arquitectura, función de pérdida, entrenamiento y criterios de parada. Un bucle es válido si su código está visible y los resultados identifican cada combinación de modelo, fold y seed.

### Requisito especial para cada figura

La celda debe contener el código que construye la figura a partir de los datos y la exporta. Usar el mismo objeto para mostrarla en el notebook y guardarla. Adjuntar Markdown que explique ejes, unidades, colores, población, ponderación y significado del patrón observado. En mapas, explicar CRS, cobertura, datos faltantes y umbrales de la leyenda. En intervalos predictivos, distinguir cobertura nominal y observada.

## 3.4 Ejecución desde cero y estado limpio

La primera celda de código configura una raíz de proyecto detectable desde la ubicación del notebook, rutas relativas, `params.yaml`, perfil y semillas. Nunca incluir rutas personales absolutas, `os.chdir` a una carpeta del autor, claves, tokens o datos pegados manualmente.

Todos los notebooks deben funcionar con **Restart Kernel → Run All**, de arriba hacia abajo, si sus dependencias declaradas están disponibles. La secuencia completa debe reconstruirlas desde los datos crudos. No depender de celdas ejecutadas fuera de orden, widgets ajustados manualmente ni variables de otro notebook. Cada notebook comprueba los hashes de sus entradas y falla con un mensaje útil si falta un requisito.

Crear `scripts/run_notebooks.py` como orquestador mediante `nbclient` y `nbformat`, con ejecución separada por notebook y exportación mediante `nbconvert`. Debe:

1. leer el manifiesto de notebooks y resolver sus dependencias;
2. validar parámetros, datos, entorno y perfil antes de entrenar;
3. generar un `run_id` único y registrar commit, cambios locales, lockfile, configuración, plataforma y hardware;
4. ejecutar cada notebook con kernel nuevo, directorio de trabajo definido, timeout configurable y `allow_errors=False`;
5. escribir copias ejecutadas en `artifacts/runs/<run_id>/notebooks/` y HTML con código visible en `artifacts/runs/<run_id>/html/`;
6. guardar logs, tiempos, outputs y manifiestos por ejecución sin sobrescribir evidencia anterior;
7. detenerse ante un error, conservar el notebook parcial y no declarar una ejecución incompleta como reproducida;
8. validar artefactos y emitir un resumen final de gates, comparaciones y discrepancias.

Los notebooks fuente en `notebooks/` conservan celdas de código y Markdown en Git, con outputs pesados limpios antes del commit. Conservar las copias ejecutadas completas y HTML mediante DVC o el almacenamiento de artefactos documentado. El README debe ofrecer ambos: abrir el código y leer una ejecución completa con sus resultados. No limpiar los outputs de la copia auditada.

Definir perfiles explícitos en `params.yaml`: `core` para la solución tabular completa y `full` para incluir challengers habilitados. Una prueba reducida debe llamarse `smoke` y no validar las cifras oficiales. La referencia final registra su perfil y lista exacta de notebooks/modelos. No omitir entrenamiento silenciosamente ni usar outputs guardados para simular una reejecución. Un challenger descartado requiere motivo y gate registrado; si contribuye a las cifras del reporte, su ejecución es obligatoria en el perfil de referencia.

## 3.5 Trazabilidad de una cifra hasta su celda

Crear `artifacts/runs/<run_id>/artifact_registry.csv` con una fila por figura, tabla, mapa, modelo, predicción y exportable. Campos mínimos:

```text
artifact_id, artifact_path, artifact_sha256, artifact_type,
notebook_path, notebook_source_sha256, cell_id, cell_tag,
input_manifest_path, config_sha256, git_commit, run_id,
model_id, fold_id, seed, generated_at
```

El hash del notebook en el registro corresponde al archivo fuente ejecutado. Registrar el hash de la copia ejecutada sólo después de guardar sus outputs, en el manifiesto de ejecución, para evitar referencias circulares. Registrar también implementaciones compartidas y hashes de sus archivos cuando una celda las utilice. Para salidas generadas dentro de un bucle, un mismo `cell_id` puede tener varios artefactos distinguidos por modelo/fold/seed. Los manifiestos de entrada deben resolver las dependencias anteriores hasta sus datos crudos.

Los IDs de celda deben conservarse al editar; no referenciar sólo “celda 17”, porque su posición puede cambiar. Las figuras/tablas llevan un `artifact_id` que permite buscar su notebook y celda en el registro. Las cifras del reporte y del pitch deben enlazar a ese registro. `notebooks/README.md` incluye un índice: resultado → notebook → celda/tag → artefacto.

## 3.6 Reproducción por otro integrante del equipo

El README debe describir un camino completo desde un clon limpio, requisitos para instalar `uv` y `make`, sistema operativo probado, recursos medidos y acceso a datos. Implementar esta interfaz:

```bash
git clone <URL_REAL_DEL_REPO> radar27
cd radar27
uv sync --locked
make fetch-data
make reproduce
```

El agente sustituirá el marcador por la URL real cuando exista el repositorio; estos comandos son el contrato a implementar, no evidencia de que el proyecto ya se ejecutó.

`make fetch-data` obtiene la instantánea cruda congelada desde un remoto DVC configurado y accesible al equipo. Si no se usa remoto, debe descargar las fuentes oficiales y validar que coincidan con los hashes de referencia. Si una fuente cambió, se detiene y documenta la diferencia; no sustituye los datos en silencio. Documentar permisos y variables de entorno necesarios sin incluir credenciales. Clonar el repo por sí solo no descarga automáticamente datos grandes.

`make reproduce` reejecuta los notebooks del perfil oficial desde los crudos disponibles, reconstruye limpieza, features, ajustes, métricas, mapas y escenarios, y compara contra `configs/reproduction_reference.yaml`. Ese archivo debe guardar la ejecución de referencia, perfil, hashes, artefactos comparables y tolerancias predefinidas. No limitarse a recuperar los modelos ya entrenados con DVC.

Para ejecutar manualmente:

```bash
uv run jupyter lab
```

Leer `notebooks/README.md` y ejecutar cada notebook en el orden declarado mediante Restart Kernel → Run All. Todos los parámetros deben venir de configuración; editar configuración crea una nueva ejecución y no reproduce automáticamente la referencia.

La comprobación debe exigir igualdad exacta en IDs, splits, conteos y hashes de crudos. Para resultados numéricos de modelos, definir tolerancias antes de comparar, según plataforma y algoritmo. Separar timestamps/metadatos de los valores analíticos: una nueva fecha de ejecución no es una diferencia de resultados. No exigir identidad binaria de PNG, HTML o modelos serializados entre plataformas; verificar datos de figura, parámetros y predicciones. Registrar cualquier no determinismo de GPU y variación fuera de tolerancia como discrepancia.

**Criterio de aceptación:** otro integrante del equipo ejecuta el perfil oficial desde un clon limpio, sin instrucciones privadas del autor, y obtiene resultados analíticos concordantes dentro de las tolerancias registradas. Su informe debe distinguir qué se reprodujo, qué falló y qué no se ejecutó. Crear este protocolo no equivale a superar esa auditoría: sólo declarar éxito tras realizarla.

---

# 4. Registro de fuentes

Crear `configs/sources.yaml` con:

```yaml
ccpc:
  portal:
    url: "https://www.ine.mx/transparencia/datos-abiertos/visualizacion-datos/conteos-censales-participacion/"
  manual:
    url: "https://www.ine.mx/wp-content/uploads/2025/06/Manual-Conteos-Censales-2009-2024.pdf"
  elections:
    2024:
      url: "https://www.ine.mx/wp-content/uploads/2025/08/DatosAbiertos_DECEyEC_ConteosCensales2024.zip"
    2021:
      url: "https://www.ine.mx/wp-content/uploads/2022/04/DatosAbiertos_DECEyEC_ConteosCensales2021.zip"
    2018:
      url: "https://www.ine.mx/wp-content/uploads/2022/04/DatosAbiertos_DECEyEC_ConteosCensales2018.zip"
    2015:
      url: "https://www.ine.mx/wp-content/uploads/2022/04/DatosAbiertos_DECEyEC_ConteosCensales2015.zip"
    2012:
      url: "https://www.ine.mx/wp-content/uploads/2022/04/DatosAbiertos_DECEyEC_ConteosCensales2012.zip"
    2009:
      url: "https://www.ine.mx/wp-content/uploads/2022/04/DatosAbiertos_DECEyEC_ConteosCensales2009.zip"
```

Agregar posteriormente la URL exacta de la cartografía realmente utilizada.

## Cada descarga debe registrar

- URL;
- fecha/hora UTC;
- código HTTP;
- tamaño;
- nombre original;
- SHA-256;
- Content-Type;
- Last-Modified si existe;
- ETag si existe;
- notebook/celda, utilidad de descarga y commit que ejecutaron la descarga.

Guardar en:

`data/manifests/source_manifest.csv`

---

# 5. Fase 1 — Ingesta

**Ejecución y evidencia:** `notebooks/00_setup_sources_download.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

## 5.1 Descargar automáticamente

Crear:

`src/radar27/ingest/download_ccpc.py`

Debe:

1. leer `sources.yaml`;
2. descargar en streaming;
3. escribir primero a `.part`;
4. validar respuesta HTTP;
5. calcular SHA-256;
6. renombrar sólo al finalizar;
7. no sobreescribir un archivo existente con hash diferente;
8. registrar metadatos;
9. reintentar con backoff;
10. fallar de forma explícita ante contenido HTML/error disfrazado de ZIP.

## 5.2 Validar cada ZIP

Para cada archivo:

- `zipfile.is_zipfile`;
- listar miembros;
- comprobar CRC;
- registrar filenames;
- prohibir path traversal;
- extraer sólo a una carpeta propia por año.

## 5.3 Inmutabilidad

`data/raw/` nunca se modifica.

Si un error de fuente requiere corrección:

- descargar nueva versión;
- guardar como nueva instantánea;
- registrar hash;
- no reemplazar silenciosamente.

## Gate 1

No avanzar hasta tener:

- seis archivos de elecciones;
- hashes;
- inventario de archivos internos;
- manual;
- cartografía identificada.

---

# 6. Fase 2 — Auditoría física de archivos

**Ejecución y evidencia:** `notebooks/01_raw_schema_audit.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

Antes de unir nada:

crear una tabla por archivo con:

- ruta;
- extensión;
- encoding;
- separador;
- filas;
- columnas;
- nombres originales;
- tipos inferidos;
- porcentaje de nulos;
- valores únicos;
- duplicados;
- rango numérico;
- muestra de valores.

Guardar:

`artifacts/tables/raw_file_inventory.parquet`

y

`artifacts/reports/raw_audit.html`

## Nunca asumir que los seis años tienen el mismo esquema

Construir una matriz:

| Campo conceptual | 2009 | 2012 | 2015 | 2018 | 2021 | 2024 |
|---|---:|---:|---:|---:|---:|---:|
| entidad | | | | | | |
| municipio | | | | | | |
| distrito | | | | | | |
| sección | | | | | | |
| sexo | | | | | | |
| edad | | | | | | |
| lista nominal | | | | | | |
| sí votó | | | | | | |
| no votó | | | | | | |

No continuar con armonización hasta entender esta tabla.

---

# 7. Fase 3 — Contrato de IDs

**Ejecución y evidencia:** `notebooks/02_clean_ids_harmonization.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

Crear `docs/ID_CONTRACT.md`.

La llave maestra de sección debe definirse explícitamente.

Ejemplo provisional:

$$
section\_id =
ENTIDAD\_2D + SECCION\_4D
$$

pero NO implementar esta fórmula hasta verificar los catálogos reales.

## Reglas

- conservar IDs como strings;
- nunca perder ceros a la izquierda;
- no utilizar nombres como llave;
- registrar crosswalks;
- comprobar unicidad;
- registrar secciones faltantes por año;
- cuantificar altas/bajas de IDs.

## Pruebas

- `section_id` no nulo;
- ID válido según catálogo;
- duplicados explicados por dimensiones de sexo/edad;
- agregación reproduce totales esperados.

---

# 8. Fase 4 — Cartografía

**Ejecución y evidencia:** `notebooks/03_geography_graph.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

La página oficial indica que la plataforma 2009–2024 toma como base cartografía electoral con corte a mayo de 2023.

## Acción

Obtener shapefile o geometría oficial compatible con el marco utilizado.

No usar una cartografía de otra fecha sin documentarlo.

## Validaciones

- CRS;
- geometrías válidas;
- polígonos vacíos;
- self-intersections;
- duplicados;
- cobertura de IDs;
- número de secciones;
- áreas imposibles;
- overlaps relevantes.

Corregir sólo problemas geométricos técnicos, nunca alterar IDs.

Guardar:

`data/processed/sections_2023.gpkg`

## Grafo de contigüidad

Construir Queen contiguity.

Para cada sección:

- vecinos;
- grado;
- componentes conexos.

Secciones sin vecinos:

1. auditar si son islas o geometrías problemáticas;
2. no conectarlas artificialmente al grafo principal sin etiqueta;
3. opcionalmente crear un grafo alternativo KNN por centroides para análisis de sensibilidad.

---

# 9. Fase 5 — Estandarización de datos

**Ejecución y evidencia:** `notebooks/02_clean_ids_harmonization.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

Crear un esquema canónico.

Ejemplo:

```text
election_year
election_family
entity_id
municipality_id
district_federal_id
section_id
section_type
sex
age
age_group_5y
life_stage
indigenous_reference
afromexican_reference
nominal_list
voted
did_not_vote
unspecified_vote
```

## Reglas de transformación

- nombres snake_case;
- strings normalizados;
- categorías explícitas;
- números parseados con errores detectados;
- porcentajes recalculados desde conteos cuando sea posible;
- no confiar en porcentaje publicado si existen numerador y denominador sin comprobarlo.

Definir, conforme al manual oficial de la plataforma (págs. 17–18) y sujeto a la comprobación de los campos de cada ZIP:

$$
participation=
\frac{voted}{voted + did\_not\_vote}
$$

$$
abstention=
\frac{did\_not\_vote}{voted + did\_not\_vote}
$$

$$
unspecified\_share=
\frac{unspecified}{nominal\_list}
$$

Los registros no especificados no se clasifican como abstención. Si el denominador es cero, el indicador es no definido. Para agregar territorios o grupos, sumar numeradores y denominadores compatibles antes de dividir. `voted / nominal_list` puede calcularse únicamente como indicador adicional de sensibilidad, con nombre propio; no presentarlo como la participación oficial.

**Trazabilidad de la corrección (2026-10-05):** la versión provisional anterior definía `participation = voted / nominal_list`. Se sustituyó por las fórmulas de las páginas 17–18 del manual oficial a petición explícita del alcance de la fase 1. La comprobación contra los TXT incluidos en los ZIP se documenta en `notebooks/01_raw_schema_audit.ipynb` y `docs/INDICATOR_DEFINITIONS.md`.

---

# 10. Fase 6 — Validación contable

**Ejecución y evidencia:** `notebooks/02_clean_ids_harmonization.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

Esta fase es obligatoria.

Para cada combinación donde aplique:

$$
voted + did\_not\_vote + unspecified
\approx nominal\_list
$$

Definir tolerancia sólo después de entender el esquema.

Reagregar datos y comparar contra totales publicados del INE.

## Reportar

- filas que no cuadran;
- magnitud del error;
- años afectados;
- territorios afectados;
- decisión tomada.

No corregir automáticamente diferencias sin explicación.

---

# 11. Fase 7 — Panel analítico

**Ejecución y evidencia:** `notebooks/04_panel_build_audit.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

Construir al menos dos tablas.

## A. `section_election_panel`

Una fila:

$$
section \times election
$$

Campos agregados:

- lista nominal;
- votos;
- abstención;
- participación;
- composición;
- metadatos territoriales.

## B. `section_demo_election_panel`

Mayor granularidad:

$$
section \times election \times sex \times age\_group
$$

Se utiliza para construir perfiles demográficos agregados, no necesariamente para el modelo principal.

Guardar en Parquet particionado por `election_year`.

---

# 12. Fase 8 — EDA obligatorio

**Ejecución y evidencia:** `notebooks/05_eda.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

El EDA debe calcularse y visualizarse en `05_eda.ipynb`. Cada tabla, estadístico y gráfico debe mostrar su código y explicar la pregunta, denominador, ponderación y resultado observado. No limitarse a cargar imágenes exportadas.

## 12.1 Integridad

- cobertura por año;
- secciones presentes;
- nulos;
- cambios de esquema;
- tamaño de lista nominal;
- votos no especificados.

## 12.2 Distribuciones

Por año:

- participación;
- abstención;
- lista nominal;
- edad;
- sexo;
- tipo de sección.

## 12.3 Tiempo

- promedio nacional;
- mediana entre secciones;
- percentiles;
- cambio same-type;
- volatilidad territorial.

## 12.4 Geografía

- mapas;
- Moran's I global;
- LISA;
- hotspots/coldspots descriptivos.

## 12.5 Demografía

- participación por sexo;
- edad/grupo quinquenal;
- brechas;
- heterogeneidad territorial.

## 12.6 Elección

Separar:

```text
midterm:       2009, 2015, 2021, target 2027
presidential:  2012, 2018, 2024
```

## Salida

Generar automáticamente:

`artifacts/reports/eda_report.html`

a partir del notebook ejecutado, con código y outputs visibles; no depender de capturas manuales.

---

# 13. Fase 9 — Definición formal del target

**Ejecución y evidencia:** `notebooks/06_targets_splits_features.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

Antes de entrenar cualquier modelo crear:

`docs/MODELING_CONTRACT.md`

Debe congelar:

- unidad;
- horizonte;
- target;
- fecha de corte informativa;
- variables permitidas;
- variables prohibidas;
- evaluación.

## Target primario recomendado

No decidir definitivamente hasta auditar datos.

Dos candidatos:

### Target A — participación futura

$$
y_{i,t}=participation_{i,t}
$$

### Target B — deterioro relativo

$$
d_{i,t} =
participation_{i,t}
-
participation_{i,t-1}^{same-type}
$$

y clasificar:

$$
risk_{i,t}=1[d_{i,t}<-\tau]
$$

donde $\tau$ se define ex ante.

## Preferencia

Entrenar ambos.

El dashboard puede utilizar:

- estimación continua;
- score de deterioro.

No fijar $\tau$ después de ver qué valor produce las mejores métricas.

---

# 14. Fase 10 — Prevención de leakage

**Ejecución y evidencia:** `notebooks/06_targets_splits_features.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

Crear `tests/test_leakage.py`.

Para cada ejemplo de predicción con target en $t$:

$$
max(feature\_date) < target\_date
$$

Ninguna feature puede utilizar:

- participación del target;
- vecinos en el target;
- variables post-target;
- estadísticas calculadas usando el dataset completo si incluyen el target;
- normalizaciones estimadas con test.

## Pipelines

Todos los escaladores, imputadores, PCA/autoencoders y transformadores supervisados se ajustan dentro del fold de entrenamiento.

---

# 15. Fase 11 — Splits congelados

**Ejecución y evidencia:** `notebooks/06_targets_splits_features.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

Guardar un archivo:

`data/processed/model_splits.parquet`

Nunca cambiar los splits para mejorar métricas.

## Evaluación temporal

Diseñar folds según disponibilidad real.

Ejemplo conceptual:

- predecir 2015 con información anterior a 2015;
- predecir 2018 con información anterior a 2018;
- predecir 2021 con información anterior a 2021;
- predecir 2024 con información anterior a 2024.

Pero para evaluar el objetivo 2027, distinguir folds de:

- mismo tipo de elección;
- tipo distinto.

La evaluación principal debe resaltar el fold comparable de elección intermedia.

## Holdout geográfico adicional

Reservar grupos territoriales completos en una prueba de robustez para medir generalización espacial.

Opciones:

- estados;
- bloques contiguos;
- GroupKFold por entidad.

---

# 16. Fase 12 — Feature engineering

**Ejecución y evidencia:** `notebooks/06_targets_splits_features.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

Todas las features deben documentarse en `configs/features.yaml`.

Cada feature tendrá:

```yaml
name:
description:
source_columns:
available_from:
transformation:
leakage_risk:
missing_policy:
```

## 16.1 Nivel histórico

- `last_same_type_participation`
- `mean_same_type_participation`
- `last_any_participation`
- `mean_all_participation`

## 16.2 Dinámica

- `same_type_delta_1`
- `same_type_slope`
- `all_election_slope`
- `historical_sd`
- `max_drawdown`
- `recent_change`
- `recovery_index`

## 16.3 Tipo de elección

- `mean_presidential`
- `mean_midterm`
- `presidential_midterm_gap`
- `gap_trend`

## 16.4 Relativas

- diferencia vs estado;
- diferencia vs municipio;
- percentil dentro de estado;
- z-score dentro de entidad.

Los benchmarks siempre se calculan usando datos disponibles antes del target.

## 16.5 Sociodemográficas

Construir proporciones, no sólo conteos.

Ejemplo:

$$
share_{18-24}
=
\frac{LN_{18-24}}{LN_{total}}
$$

Crear:

- shares de edad;
- share por sexo;
- edad media aproximada;
- índices de concentración etaria;
- brecha de participación por sexo.

No agregar una variable si el denominador o definición no es claro.

---

# 17. Fase 13 — Features espaciales

**Ejecución y evidencia:** `notebooks/06_targets_splits_features.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

Para cada target $t$, utilizar sólo datos de vecinos anteriores a $t$.

Features:

- mean neighbor participation;
- median neighbor participation;
- std neighbor participation;
- min/max;
- gap sección–vecinos;
- neighbor trend;
- share neighbors deteriorating;
- Local Moran lag;
- degree.

## Ablación

Comparar:

$$
M2 = boosting(tabular)
$$

vs.

$$
M3 = boosting(tabular + spatial)
$$

Reportar mejora real.

---

# 18. Fase 14 — Análisis espacial descriptivo

**Ejecución y evidencia:** `notebooks/05_eda.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

Antes de GNN:

1. Moran's I global;
2. Local Moran's I;
3. Getis-Ord si resulta útil;
4. mapas de:
   - High-High;
   - Low-Low;
   - High-Low;
   - Low-High.

No interpretar autocorrelación como causalidad.

Registrar pesos espaciales y definición de vecindad.

---

# 19. Fase 15 — Embedding de grafo

**Ejecución y evidencia:** `notebooks/09_embeddings_analogues.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

## Primera opción: Node2Vec

Ventajas:

- barato;
- no necesita labels;
- sencillo de auditar;
- buen baseline de representación.

Entrenar sobre el grafo geográfico.

Hipertparámetros a registrar:

- dimensions;
- walk_length;
- num_walks;
- p;
- q;
- window;
- seed.

## Leakage

El grafo puede usar geometría, porque no depende del resultado futuro.

No construir aristas a partir de participación del target.

## Evaluaciones del embedding

### Predictiva

Agregar $z_i^{graph}$ al modelo y medir mejora.

### Vecindarios

Evaluar si vecinos en embedding:

- son geográficamente coherentes;
- comparten trayectorias;
- recuperan analogías útiles.

### Estabilidad

Reentrenar con varias seeds y medir similitud de vecinos.

---

# 20. Fase 16 — Embedding temporal

**Ejecución y evidencia:** `notebooks/09_embeddings_analogues.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

No utilizar un Transformer grande. Sólo seis elecciones no justifican una arquitectura enorme.

## Baseline

Features manuales de trayectoria.

## Challenger

Autoencoder pequeño o encoder enmascarado.

Input:

- historia disponible antes del target;
- máscaras de ausencia.

Latente:

8–32 dimensiones máximo inicialmente.

## Validación

El embedding sólo se conserva si supera las features manuales en:

- predicción;
- clustering/analogías;
- estabilidad.

Visualizar con UMAP únicamente para exploración, no como prueba cuantitativa.

---

# 21. Fase 17 — Modelos

**Ejecución y evidencia:** `notebooks/07_baselines_regressions.ipynb`, `notebooks/08_boosting_backtests.ipynb`, `notebooks/09_embeddings_analogues.ipynb`, `notebooks/10_gnn_challenger.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

## M0 — Naive

Variantes:

- último same-type;
- media same-type;
- promedio territorial;
- trend extrapolation.

## M1 — Elastic Net

Preprocesamiento dentro del pipeline. Mostrar en `07_baselines_regressions.ipynb` la especificación, regresores, escalado, regularización, `fit`, `predict`, coeficientes y métricas por fold, con interpretación de unidades y límites.

## M2 — LightGBM/XGBoost

Evitar tuning masivo.

Usar:

- early stopping;
- regularización;
- search pequeño y documentado.

## M3 — Boosting + spatial

Modelo candidato fuerte.

## M4 — Boosting + embeddings

Ablación de:

- graph embedding;
- temporal embedding;
- ambos.

## M5 — GNN

Sólo después de M0–M4.

Candidatos:

- GraphSAGE;
- GAT.

No entrenar más de dos arquitecturas distintas durante el hackathon.

---

# 22. Fase 18 — GNN

**Ejecución y evidencia:** `notebooks/10_gnn_challenger.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

## Diseño conservador

Input nodo:

$$
X_i^{pre-target}
$$

Adjacency:

$$
A^{geo}
$$

Output:

$$
\hat y_i
$$

o riesgo.

## Condiciones de adopción

La GNN se convierte en modelo final únicamente si:

1. supera consistentemente al mejor tabular;
2. mejora en más de un fold;
3. no depende de una única seed;
4. no destruye calibración;
5. puede explicarse razonablemente.

Si no:

> documentar el resultado negativo y conservar el mejor modelo sencillo.

Eso fortalece el reporte.

---

# 23. Fase 19 — Métricas

**Ejecución y evidencia:** `notebooks/07_baselines_regressions.ipynb`, `notebooks/08_boosting_backtests.ipynb`, `notebooks/09_embeddings_analogues.ipynb`, `notebooks/10_gnn_challenger.ipynb`, `notebooks/11_comparison_robustness_selection.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

## Regresión

- MAE;
- RMSE;
- median AE;
- $R^2$ como secundaria;
- error ponderado por lista nominal;
- error por estado;
- error por tipo de sección.

## Clasificación

- PR-AUC;
- ROC-AUC;
- Brier score;
- log loss;
- recall@5%;
- recall@10%;
- precision@5%;
- precision@10%.

## Ranking

- NDCG@K;
- overlap top-K entre predicción y riesgo observado.

## Incertidumbre

- empirical coverage;
- interval width;
- coverage por subgrupo.

---

# 24. Fase 20 — Selección de modelo

**Ejecución y evidencia:** `notebooks/11_comparison_robustness_selection.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

Nunca elegir el modelo por una sola métrica.

Crear scorecard:

| Criterio | Peso interno |
|---|---:|
| desempeño temporal | alto |
| desempeño same-type | muy alto |
| calibración | alto |
| estabilidad | alto |
| interpretabilidad | medio |
| complejidad operativa | medio |
| tiempo de inferencia | bajo/medio |

No producir un número arbitrario de “puntuación total” para justificar el ganador.

Tomar la decisión mediante criterios predefinidos y documentar trade-offs.

---

# 25. Fase 21 — Conformal prediction

**Ejecución y evidencia:** `notebooks/12_uncertainty_explanations.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

## Objetivo

Generar intervalos predictivos.

Usar calibration set separado.

No calibrar con el test final.

Reportar:

$$
Coverage =
P(Y_i \in [L_i,U_i])
$$

Evaluar cobertura global y por:

- entidad;
- urbano/rural/mixto;
- tamaño de sección;
- deciles de riesgo.

Si la cobertura es heterogénea, probar conformal estratificado o técnicas adaptativas simples.

---

# 26. Fase 22 — Explicabilidad

**Ejecución y evidencia:** `notebooks/12_uncertainty_explanations.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

## Global

- gain/importance;
- SHAP summary;
- partial dependence sólo para variables seleccionadas.

## Local

Para cada sección:

- top 5 SHAP positivos;
- top 5 negativos;
- valor observado de cada feature;
- comparación con benchmark.

## Cuidado

SHAP explica la predicción del modelo.

No significa:

> “esta variable causa abstención”.

El dashboard debe usar lenguaje como:

> “factores asociados al pronóstico”.

---

# 27. Fase 23 — Territorios análogos

**Ejecución y evidencia:** `notebooks/09_embeddings_analogues.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

Construir índice de similitud.

Comparar tres espacios:

1. standardized handcrafted features;
2. graph embedding;
3. combined embedding.

Usar cosine distance.

Para una sección $i$:

$$
NN_k(i)
=
\arg\min_j d(z_i,z_j)
$$

## Validación

Los análogos deben revisarse manualmente en una muestra.

Reportar:

- similitud de trayectoria;
- similitud demográfica;
- distancia geográfica;
- consistencia del vecino.

No utilizar vecinos del target para filtrar resultados.

---

# 28. Fase 24 — Anomaly detection

**Ejecución y evidencia:** `notebooks/13_risk_anomalies.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

Baseline:

- z-score del cambio;
- residual respecto de vecinos.

Challengers:

- Isolation Forest;
- LOF.

No etiquetar una anomalía como irregularidad.

Nombre recomendado:

**“cambio atípico de participación”**.

Auditar top 100 manualmente.

---

# 29. Fase 25 — Construcción del score de riesgo

**Ejecución y evidencia:** `notebooks/13_risk_anomalies.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

No ocultar la fórmula.

Preferencia:

separar paneles en vez de comprimir todo de inmediato.

## Outputs

### Structural risk
Basado en persistencia y nivel relativo.

### Emerging risk
Basado en deterioro predicho.

### Uncertainty
Anchura de intervalo.

### Anomaly
Indicador separado.

Si se crea un score total:

- normalizar;
- publicar fórmula;
- hacer sensibilidad;
- evitar pesos elegidos post hoc.

---

# 30. Fase 26 — Semáforo

**Ejecución y evidencia:** `notebooks/13_risk_anomalies.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

El semáforo debe derivarse de reglas reproducibles.

No usar “rojo = top 33%” sin justificar.

Opción:

- rojo: riesgo alto y/o deterioro material;
- amarillo: riesgo intermedio;
- verde: riesgo bajo;
- gris: incertidumbre/datos insuficientes.

Los thresholds se congelan y documentan.

Incluir sensibilidad a thresholds alternativos.

---

# 31. Fase 27 — Escenarios de intervención

**Ejecución y evidencia:** `notebooks/14_scenarios_optimization.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

Crear módulo puro:

`src/radar27/scenarios/simulate.py`

Input:

- baseline;
- territorios seleccionados;
- uplift supuesto;
- regla de asignación;
- capacidad;
- incertidumbre.

Output:

- resultado por sección;
- agregado;
- delta;
- población/lista nominal cubierta.

## Regla

Los escenarios son hipotéticos.

Guardar metadatos:

```text
scenario_id
model_version
uplift_assumption
selection_rule
capacity
created_at
```

Nunca guardar sólo el mapa sin sus parámetros.

---

# 32. Fase 28 — Análisis de sensibilidad de escenarios

**Ejecución y evidencia:** `notebooks/14_scenarios_optimization.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

Ejecutar matriz:

$$
\delta \in
\{0.5,1.0,2.0,3.0\}
$$

y distintas capacidades.

Mostrar:

- cuántas secciones cambian de categoría;
- cobertura;
- beneficio hipotético;
- estabilidad del ranking.

Si la política sugerida cambia completamente con una variación pequeña del supuesto, declararla frágil.

---

# 33. Fase 29 — Priorización de recursos

**Ejecución y evidencia:** `notebooks/14_scenarios_optimization.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

## Baseline

Ranking por riesgo.

## Alternativa

$$
priority_i=
risk_i\times population_i\times confidence_i
$$

## Optimización

Si se utilizan costos:

$$
\max
\sum_i b_i a_i
$$

sujeto a:

$$
\sum_i c_i a_i \le B
$$

y:

$$
a_i \in \{0,1\}
$$

Usar OR-Tools o scipy.optimize según formulación.

## Guardrail

No inventar costos.

Si no existen:

- usar capacidad en número de territorios;
- o permitir al usuario introducir costos.

---

# 34. Fase 30 — Fairness y auditoría territorial

**Ejecución y evidencia:** `notebooks/11_comparison_robustness_selection.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

Aunque no sea un modelo individual, evaluar distribución del error.

Tabla obligatoria:

- MAE/recall por entidad;
- tipo de sección;
- quintil de lista nominal;
- referente indígena cuando sea válido;
- referente afromexicano cuando sea válido.

Objetivo:

detectar si el modelo funciona mucho peor en algún conjunto territorial.

No optimizar directamente con atributos sensibles sin una justificación documentada.

---

# 35. Fase 31 — Robustez

**Ejecución y evidencia:** `notebooks/11_comparison_robustness_selection.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

Ejecutar:

## Ablation tests

- sin sociodemografía;
- sin geografía;
- sin presidenciales;
- sin embeddings;
- sin features espaciales.

## Sensibilidad

- thresholds;
- seeds;
- hiperparámetros;
- definición de vecindad;
- ponderación por lista nominal.

## Placebo/leakage check

Introducir intencionalmente una feature futura en un test de desarrollo y verificar que `test_leakage.py` la bloquee.

---

# 36. Fase 32 — Visualizaciones analíticas

**Ejecución y evidencia:** `notebooks/05_eda.ipynb`, `notebooks/12_uncertainty_explanations.ipynb`, `notebooks/13_risk_anomalies.ipynb`, `notebooks/14_scenarios_optimization.ipynb`, `notebooks/15_maps_exports_dashboard.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

Crear automáticamente:

1. participación nacional por año;
2. distribución por elección;
3. cambio same-type;
4. mapa 2009;
5. mapa 2015;
6. mapa 2021;
7. mapa de tendencia;
8. Moran scatter;
9. mapa LISA;
10. error de backtest;
11. predicted vs actual;
12. calibración;
13. cobertura conformal;
14. SHAP summary;
15. ablation table;
16. mapa de riesgo estructural;
17. mapa de riesgo emergente;
18. mapa de incertidumbre;
19. mapa de anomalías;
20. escenarios lado a lado.

Cada figura:

- título;
- unidad;
- fuente;
- fecha;
- notas;
- notebook, ID/tag de celda y `artifact_id` que la generaron;
- código de construcción, output visible y Markdown de interpretación;
- parámetros, hashes de datos y commit de ejecución.

---

# 37. Fase 33 — Dashboard

**Ejecución y evidencia:** `notebooks/15_maps_exports_dashboard.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

## Framework

Streamlit.

## Páginas

### 1. Panorama nacional
- mapa;
- distribución;
- filtros.

### 2. Riesgo
- estructural;
- emergente;
- total;
- incertidumbre.

### 3. Explorar sección
- trayectoria;
- comparables;
- explicación;
- análogos.

### 4. Escenarios
- baseline;
- uplift;
- capacidad;
- regla;
- dos mapas.

### 5. Metodología
- modelo;
- backtesting;
- métricas;
- limitaciones.

## Rendimiento

No servir geometrías full-resolution si hacen lenta la app.

Crear una versión simplificada sólo para visualización, preservando la original para análisis.

---

# 38. Fase 34 — Exportables

**Ejecución y evidencia:** `notebooks/15_maps_exports_dashboard.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

Generar:

```text
artifacts/geo/risk_map.geojson
artifacts/geo/risk_map.gpkg
artifacts/tables/risk_scores.csv
artifacts/tables/model_metrics.csv
artifacts/tables/scenario_comparison.csv
artifacts/models/final_model.*
```

Los paths anteriores describen la estructura de la publicación aprobada. Las ejecuciones de trabajo deben escribir bajo `artifacts/runs/<run_id>/` con esa estructura, sin sobrescribir versiones previas. La app debe seleccionar explícitamente la ejecución aprobada; evitar leer un modelo de una ejecución y features de otra.

Cada tabla debe contener:

- `model_version`;
- `data_version`;
- `generated_at`;
- `run_id` y referencia al `artifact_id`;
- columnas documentadas.

---

# 39. Fase 35 — Auditoría de reproducibilidad

**Ejecución y evidencia:** `notebooks/16_reproducibility_audit.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

Desde un clon limpio y con el perfil oficial, seguir los comandos de la sección 3.6. El runner debe reejecutar los notebooks, con kernels nuevos, y reconstruir los resultados desde los crudos congelados. Obtener los archivos con DVC no sustituye esta ejecución.

Debe producir y comparar:

- panel y features;
- ajustes de regresiones y modelos;
- predicciones fuera de muestra y métricas;
- calibración, explicaciones y scores;
- figuras, mapas, escenarios y exportables;
- notebooks ejecutados con outputs y HTML con código visible;
- registros de artefactos y resumen de diferencias contra la referencia.

Registrar duración, memoria, configuración, versiones y hardware. Crear `docs/REPRODUCTION_AUDIT.md` con autor de la auditoría, referencia, comandos, tolerancias, diferencias y estado final. Verificar tanto Restart Kernel → Run All en los notebooks como la secuencia automatizada completa.

No aceptar pasos manuales ocultos, dependencia de outputs antiguos ni omisiones silenciosas. La auditoría pasa únicamente si otra persona reproduce las cifras de referencia dentro de las tolerancias predefinidas. Mientras no se haga, reportarla como pendiente.

---

# 40. Fase 36 — Tests automatizados

**Ejecución y evidencia:** `notebooks/16_reproducibility_audit.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

## Data tests

- IDs;
- rangos;
- relaciones contables;
- duplicados;
- coverage.

## Geo tests

- geometrías;
- CRS;
- joins;
- vecinos.

## Model tests

- splits;
- leakage;
- deterministic seed where possible;
- predict schema.

## Scenario tests

- uplift 0 → resultado baseline;
- capacidad 0 → ninguna zona intervenida;
- monotonicidad cuando corresponda;
- no superar bounds 0–1.

## Notebooks

- IDs de celda únicos/estables y tags de resultados;
- manifiesto de entradas, salidas y dependencias válido;
- ejecución con kernel limpio, sin errores ni estado oculto;
- código y outputs visibles para todo resultado oficial;
- registro de artefactos resuelve notebook/celda y hashes;
- interpretación numérica generada desde los resultados actuales;
- fallos de gates bloquean los notebooks dependientes;
- comparación con referencia dentro de tolerancias declaradas;
- app y notebook producen el mismo escenario con iguales parámetros.

## Dashboard

- archivo de datos disponible;
- columnas esperadas;
- app inicia.

---

# 41. Fase 37 — Logging de decisiones

**Ejecución y evidencia:** `notebooks/16_reproducibility_audit.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

Crear `docs/DECISION_LOG.md`.

Formato:

```markdown
## D-017 — Usar Queen contiguity
Fecha:
Autor:
Decisión:
Alternativas:
Evidencia:
Riesgos:
Impacto:
Reversible:
```

Registrar decisiones importantes, incluyendo las que descartan técnicas.

---

# 42. Fase 38 — Model cards

**Ejecución y evidencia:** `notebooks/11_comparison_robustness_selection.ipynb`, `notebooks/12_uncertainty_explanations.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

Para el modelo final crear:

`docs/MODEL_CARD.md`

Debe incluir:

- propósito;
- target;
- entrenamiento;
- datos;
- evaluación;
- limitaciones;
- subgrupos;
- incertidumbre;
- uso previsto;
- usos no previstos;
- fecha;
- commit;
- hash del modelo.

---

# 43. Fase 39 — Data lineage

**Ejecución y evidencia:** `notebooks/16_reproducibility_audit.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

Crear `docs/DATA_LINEAGE.md`.

Ejemplo:

```text
INE ZIP 2021
  ↓ extract
raw tables
  ↓ canonicalize
2021_clean.parquet
  ↓ aggregate
section_election_panel
  ↓ feature builder
model_matrix_2021
  ↓ model
predictions
  ↓ risk/scenario
dashboard dataset
```

Cada flecha debe apuntar al notebook y al ID/tag de celda que ejecutan esa transformación, a sus entradas y salidas versionadas y a las utilidades compartidas usadas. Enlazar el registro de artefactos de la ejecución correspondiente.

---

# 44. Fase 40 — Entregable técnico

**Ejecución y evidencia:** `notebooks/16_reproducibility_audit.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

La convocatoria pide un reporte metodológico y preventivo de 10–15 cuartillas.

Estructura propuesta:

1. Resumen ejecutivo.
2. Problema.
3. Datos.
4. Calidad y armonización.
5. Definición de riesgo.
6. Métodos.
7. Validación.
8. Resultados.
9. Incertidumbre.
10. Explicabilidad.
11. Escenarios.
12. Priorización.
13. Limitaciones.
14. Recomendaciones de implementación.
15. Apéndice técnico fuera del cuerpo si el formato lo permite.

No esconder errores o resultados negativos. Cada resultado del reporte debe enlazar a su artefacto y notebook/celda de origen; las explicaciones del reporte deben concordar con la ejecución congelada.

---

# 45. Fase 41 — Presentación de 10 slides

**Ejecución y evidencia:** `notebooks/16_reproducibility_audit.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

Generar después de congelar resultados.

Nunca antes.

Cada cifra en slides debe provenir de un archivo versionado.

Crear:

`artifacts/presentation/slide_numbers.csv`

con:

```text
slide
claim
value
source_artifact
artifact_id
notebook_path
cell_id
run_id
commit
```

Esto evita copiar cifras desactualizadas.

---

# 46. Fase 42 — Revisión final de lenguaje

**Ejecución y evidencia:** `notebooks/16_reproducibility_audit.ipynb`. Aplicar el contrato de código, outputs y Markdown de la sección 3.

Buscar frases causalmente indebidas:

- “provoca”
- “causa”
- “debido a”
- “la intervención aumentará”

Sustituir según corresponda por:

- “se asocia con”;
- “el modelo utiliza”;
- “bajo el escenario supuesto”;
- “la simulación produciría”.

Buscar inferencias individuales:

- “los jóvenes de esta sección no votan”.

Sustituir:

- “la participación agregada del grupo de edad en esta sección es menor”.

---

# 47. Cronograma recomendado

## Día 1
- repo;
- descargas;
- hashes;
- inventario;
- schema audit.

## Día 2
- armonización;
- IDs;
- cartografía;
- panel;
- validación.

## Día 3
- EDA;
- target;
- splits;
- baseline.

## Día 4
- feature engineering;
- boosting;
- spatial features.

## Día 5
- backtesting;
- uncertainty;
- SHAP.

## Día 6
- graph embeddings;
- temporal embeddings;
- ablations.

## Día 7
- GNN challenger sólo si todo lo anterior está estable.

## Día 8
- escenarios;
- priorización;
- dashboard.

## Día 9
- auditoría;
- exportables;
- reporte.

## Día 10
- presentación;
- pitch;
- reproducción desde cero.

Si hay más tiempo, usarlo para robustez y comunicación, no para añadir modelos arbitrariamente.

---

# 48. Prioridades si se queda corto el tiempo

## No sacrificar

1. datos correctos;
2. baseline;
3. backtesting;
4. modelo fuerte tabular;
5. incertidumbre;
6. mapa;
7. escenarios;
8. auditabilidad.

## Sacrificar primero

1. GAT;
2. segundo autoencoder;
3. animaciones;
4. hiperparameter tuning exhaustivo;
5. múltiples dashboards.

---

# 49. Checklist del agente antes de declarar éxito

## Datos
- [ ] Todos los archivos tienen SHA-256.
- [ ] No se modificó `raw`.
- [ ] Existe source manifest.
- [ ] Existe diccionario.
- [ ] IDs auditados.
- [ ] Geometría auditada.
- [ ] Totales reconciliados.

## Modelado
- [ ] Target congelado.
- [ ] Splits congelados.
- [ ] Leakage tests pasan.
- [ ] Baselines entrenados.
- [ ] Challenger entrenado.
- [ ] Ablations terminadas.
- [ ] Backtesting reportado.
- [ ] Métricas por territorio/subgrupo.
- [ ] Incertidumbre calibrada.

## Avanzado
- [ ] Spatial features evaluadas.
- [ ] Embedding de grafo evaluado.
- [ ] Temporal embedding evaluado o formalmente descartado.
- [ ] GNN evaluada o formalmente descartada.
- [ ] Anomaly detector auditado.

## Producto
- [ ] Semáforo reproducible.
- [ ] Escenarios etiquetados como hipotéticos.
- [ ] Priorización con supuestos explícitos.
- [ ] Dashboard funcional.
- [ ] GeoJSON/GPKG exportado.
- [ ] CSV final exportado.

## Auditoría
- [ ] MLflow actualizado.
- [ ] DVC actualizado.
- [ ] Decision log actualizado.
- [ ] Model card.
- [ ] Data lineage.
- [ ] Limitations.
- [ ] Todas las etapas analíticas se ejecutan en los notebooks asignados.
- [ ] Cada bloque analítico tiene Markdown previo, código, output e interpretación posterior.
- [ ] Regresiones/modelos muestran especificación, ajuste, predicción y evaluación.
- [ ] Figuras y tablas tienen `artifact_id` y notebook/celda de origen.
- [ ] Notebooks corren con Restart Kernel → Run All y dependencias declaradas.
- [ ] Copias ejecutadas y HTML con código visible conservados.
- [ ] Configuración, entorno, datos y perfil oficial están congelados.
- [ ] `make reproduce` reejecuta los notebooks desde crudos y compara contra la referencia.
- [ ] Otra persona completó la reproducción desde un clon limpio.
- [ ] `docs/REPRODUCTION_AUDIT.md` documenta resultados y diferencias.

---

# 50. Orden exacto que debe seguir un agente

1. Leer convocatoria y manual; registrar fuentes y alcance.
2. Crear repo, entorno bloqueado, índice y manifiesto de notebooks.
3. Implementar y ejecutar `00`–`04`: descarga, auditoría, IDs, limpieza, cartografía y panel; no saltar gates.
4. Ejecutar `05`: EDA con código, outputs e interpretación; documentar decisiones.
5. Ejecutar `06`: congelar targets/splits y construir features sin leakage.
6. Ejecutar `07` y `08`: baselines, regresiones y boosting; evaluar fuera de muestra.
7. Ejecutar `09` y, si se justifica, `10`: embeddings, análogos y GNN; registrar adopción o descarte.
8. Ejecutar `11`: ablaciones, robustez, auditoría territorial y selección del modelo.
9. Ejecutar `12`: calibración y explicaciones oficiales del modelo seleccionado.
10. Ejecutar `13`: scores, anomalías y semáforo con fórmulas transparentes.
11. Ejecutar `14`: escenarios, sensibilidad y priorización con supuestos explícitos.
12. Ejecutar `15`: mapas, exportables y pruebas de equivalencia con la app.
13. Implementar/completar tests y congelar configuración y referencia.
14. Ejecutar la secuencia completa y `16` desde un clon limpio; conservar el informe de reproducción.
15. Congelar la ejecución aprobada, escribir reporte y slides, y rastrear todas las cifras a notebook/celda.

Actualizar el Markdown de cada notebook conforme se obtengan resultados y registrar decisiones. El índice anterior manda sobre cualquier listado de fases que sugiera ejecutar calibración oficial antes de la selección final.

---

# 51. Comandos objetivo

El repositorio debe implementar:

```bash
make setup
make fetch-data
make notebooks
make reproduce
make test
make dashboard
```

- `make setup`: sincroniza el entorno bloqueado e instala el kernel del proyecto.
- `make fetch-data`: obtiene la instantánea cruda y comprueba hashes; no descarga modelos para sustituir entrenamiento.
- `make notebooks`: ejecuta la secuencia declarada para el perfil elegido y genera notebooks ejecutados/HTML y artefactos.
- `make reproduce`: ejecuta la secuencia del perfil de referencia desde crudos, corre comprobaciones y compara resultados; debe detectar diferencias.
- `make test`: ejecuta pruebas de contratos, leakage, escenarios y ejecución.
- `make dashboard`: inicia la app con una ejecución aprobada explícita.

Se pueden conservar atajos como `make eda`, `make train` o `make scenarios`, siempre que ejecuten los notebooks correspondientes y resuelvan sus dependencias validadas. No deben implementar otro pipeline de análisis.

No ejecutar automáticamente `fetch-data` sobre una instantánea válida para actualizarla. Cada nueva ejecución conserva evidencia en su propio `run_id`. Registrar omisiones explícitas de challengers y no considerar una prueba `smoke` como reproducción oficial.

---

# 52. Fuentes oficiales iniciales

## Plataforma CCPC

https://www.ine.mx/transparencia/datos-abiertos/visualizacion-datos/conteos-censales-participacion/

## Manual

https://www.ine.mx/wp-content/uploads/2025/06/Manual-Conteos-Censales-2009-2024.pdf

## CCPC 2024

https://www.ine.mx/wp-content/uploads/2025/08/DatosAbiertos_DECEyEC_ConteosCensales2024.zip

## CCPC 2021

https://www.ine.mx/wp-content/uploads/2022/04/DatosAbiertos_DECEyEC_ConteosCensales2021.zip

## CCPC 2018

https://www.ine.mx/wp-content/uploads/2022/04/DatosAbiertos_DECEyEC_ConteosCensales2018.zip

## CCPC 2015

https://www.ine.mx/wp-content/uploads/2022/04/DatosAbiertos_DECEyEC_ConteosCensales2015.zip

## CCPC 2012

https://www.ine.mx/wp-content/uploads/2022/04/DatosAbiertos_DECEyEC_ConteosCensales2012.zip

## CCPC 2009

https://www.ine.mx/wp-content/uploads/2022/04/DatosAbiertos_DECEyEC_ConteosCensales2009.zip

## Elección federal 2027

https://portal.ine.mx/voto-y-elecciones/elecciones-2027/

## Geografía electoral

https://www.ine.mx/productos-geografia-electoral-descargables/

---

# 53. Advertencias que el agente no puede ignorar

1. Los datos son agregados; no inferir comportamiento individual.
2. El reto es de participación, no de preferencia partidista.
3. No usar información futura en ningún fold.
4. No presentar escenarios como efectos causales.
5. No elegir modelo por complejidad.
6. No ocultar incertidumbre.
7. No modificar datos crudos.
8. No sobrescribir versiones.
9. No aceptar joins silenciosamente muchos-a-muchos.
10. No eliminar observaciones sin registrar motivo.
11. No imputar una variable estructural sin justificar.
12. No normalizar usando test.
13. No usar el target para crear el grafo.
14. No interpretar SHAP como causalidad.
15. No publicar un score sin definición.
16. No crear un semáforo sin thresholds reproducibles.
17. No utilizar una cartografía incompatible sin documentarlo.
18. No afirmar que 2009–2024 constituyen una serie temporal larga.
19. No esconder que el backtest same-type tiene pocos cortes temporales.
20. No prometer precisión de 2027 que los datos no permitan sostener.
21. No entregar regresiones, EDA o visualizaciones oficiales sin código y outputs en notebooks.
22. No depender del orden manual de ejecución ni de variables que no se construyan en Run All.
23. No dejar interpretaciones de cifras de otra ejecución sin marcar/revisar.
24. No presentar archivos recuperados del almacenamiento como modelos reentrenados.
25. No declarar reproducibilidad sólo porque el notebook funciona en la máquina del autor.

---

# 54. Criterio final de calidad

El objetivo no es terminar con la frase:

> “Usamos embeddings, GNN y XGBoost.”

El objetivo es poder decir:

> **“Construimos un sistema reproducible. Cada capa fue comparada contra una alternativa más simple. Podemos mostrar qué información añadió, cuánto mejoró fuera de muestra, dónde falla, qué tan incierta es cada predicción y cómo cambian las decisiones cuando cambian los supuestos.”**

El equipo debe poder abrir cualquier resultado, encontrar su notebook y celda, leer por qué se calculó, interpretar lo obtenido y regenerarlo desde un clon limpio. Ese es el estándar del proyecto.
