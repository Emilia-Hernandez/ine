# RADAR 27 — Plan maestro de ejecución
## Protocolo para que un agente construya el proyecto de principio a fin con trazabilidad y auditoría

**Proyecto:** RADAR 27  
**Reto:** Predicción y escenarios de riesgo de abstención  
**Propósito de este archivo:** servir como contrato operativo. Un agente debe poder seguirlo sin reinterpretar el diseño, desde la descarga de los datos hasta la generación de modelos, mapas, dashboard y entregables.

---

# 0. Regla máxima

> **Nada entra al análisis si no puede rastrearse hasta su fuente, su transformación y su versión de código.**

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
- scripts reproducibles de descarga;
- diccionario de datos;
- reporte de calidad;
- dataset analítico versionado;
- geometrías validadas;
- EDA reproducible;
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
- registro de limitaciones y decisiones.

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
│   ├── LIMITATIONS.md
│   └── SOURCES.md
├── configs/
│   ├── sources.yaml
│   ├── features.yaml
│   ├── models.yaml
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
├── notebooks/
│   ├── 00_source_audit.ipynb
│   ├── 01_raw_eda.ipynb
│   ├── 02_panel_eda.ipynb
│   └── 03_model_diagnostics.ipynb
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
│   └── reports/
├── app/
│   └── streamlit_app.py
└── mlruns/
```

## Regla

Los notebooks son para inspección y comunicación.

Toda transformación que produzca un resultado final debe existir como código en `src/`.

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
- script/commit que ejecutó la descarga.

Guardar en:

`data/manifests/source_manifest.csv`

---

# 5. Fase 1 — Ingesta

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

Crear `docs/ID_CONTRACT.md`.

La llave maestra de sección debe definirse explícitamente.

Ejemplo provisional:

\[
section\_id =
ENTIDAD\_2D + SECCION\_4D
\]

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

Definir:

\[
participation=
\frac{voted}{nominal\_list}
\]

y documentar cualquier desviación de la definición oficial.

---

# 10. Fase 6 — Validación contable

Esta fase es obligatoria.

Para cada combinación donde aplique:

\[
voted + did\_not\_vote + unspecified
\approx nominal\_list
\]

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

Construir al menos dos tablas.

## A. `section_election_panel`

Una fila:

\[
section \times election
\]

Campos agregados:

- lista nominal;
- votos;
- abstención;
- participación;
- composición;
- metadatos territoriales.

## B. `section_demo_election_panel`

Mayor granularidad:

\[
section \times election \times sex \times age\_group
\]

Se utiliza para construir perfiles demográficos agregados, no necesariamente para el modelo principal.

Guardar en Parquet particionado por `election_year`.

---

# 12. Fase 8 — EDA obligatorio

El EDA no debe ser sólo visual.

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

y no depender de capturas manuales.

---

# 13. Fase 9 — Definición formal del target

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

\[
y_{i,t}=participation_{i,t}
\]

### Target B — deterioro relativo

\[
d_{i,t} =
participation_{i,t}
-
participation_{i,t-1}^{same-type}
\]

y clasificar:

\[
risk_{i,t}=1[d_{i,t}<-\tau]
\]

donde \(\tau\) se define ex ante.

## Preferencia

Entrenar ambos.

El dashboard puede utilizar:

- estimación continua;
- score de deterioro.

No fijar \(\tau\) después de ver qué valor produce las mejores métricas.

---

# 14. Fase 10 — Prevención de leakage

Crear `tests/test_leakage.py`.

Para cada ejemplo de predicción con target en \(t\):

\[
max(feature\_date) < target\_date
\]

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

\[
share_{18-24}
=
\frac{LN_{18-24}}{LN_{total}}
\]

Crear:

- shares de edad;
- share por sexo;
- edad media aproximada;
- índices de concentración etaria;
- brecha de participación por sexo.

No agregar una variable si el denominador o definición no es claro.

---

# 17. Fase 13 — Features espaciales

Para cada target \(t\), utilizar sólo datos de vecinos anteriores a \(t\).

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

\[
M2 = boosting(tabular)
\]

vs.

\[
M3 = boosting(tabular + spatial)
\]

Reportar mejora real.

---

# 18. Fase 14 — Análisis espacial descriptivo

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

Agregar \(z_i^{graph}\) al modelo y medir mejora.

### Vecindarios

Evaluar si vecinos en embedding:

- son geográficamente coherentes;
- comparten trayectorias;
- recuperan analogías útiles.

### Estabilidad

Reentrenar con varias seeds y medir similitud de vecinos.

---

# 20. Fase 16 — Embedding temporal

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

## M0 — Naive

Variantes:

- último same-type;
- media same-type;
- promedio territorial;
- trend extrapolation.

## M1 — Elastic Net

Preprocesamiento dentro del pipeline.

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

## Diseño conservador

Input nodo:

\[
X_i^{pre-target}
\]

Adjacency:

\[
A^{geo}
\]

Output:

\[
\hat y_i
\]

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

## Regresión

- MAE;
- RMSE;
- median AE;
- \(R^2\) como secundaria;
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

## Objetivo

Generar intervalos predictivos.

Usar calibration set separado.

No calibrar con el test final.

Reportar:

\[
Coverage =
P(Y_i \in [L_i,U_i])
\]

Evaluar cobertura global y por:

- entidad;
- urbano/rural/mixto;
- tamaño de sección;
- deciles de riesgo.

Si la cobertura es heterogénea, probar conformal estratificado o técnicas adaptativas simples.

---

# 26. Fase 22 — Explicabilidad

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

Construir índice de similitud.

Comparar tres espacios:

1. standardized handcrafted features;
2. graph embedding;
3. combined embedding.

Usar cosine distance.

Para una sección \(i\):

\[
NN_k(i)
=
\arg\min_j d(z_i,z_j)
\]

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

Ejecutar matriz:

\[
\delta \in
\{0.5,1.0,2.0,3.0\}
\]

y distintas capacidades.

Mostrar:

- cuántas secciones cambian de categoría;
- cobertura;
- beneficio hipotético;
- estabilidad del ranking.

Si la política sugerida cambia completamente con una variación pequeña del supuesto, declararla frágil.

---

# 33. Fase 29 — Priorización de recursos

## Baseline

Ranking por riesgo.

## Alternativa

\[
priority_i=
risk_i\times population_i\times confidence_i
\]

## Optimización

Si se utilizan costos:

\[
\max
\sum_i b_i a_i
\]

sujeto a:

\[
\sum_i c_i a_i \le B
\]

y:

\[
a_i \in \{0,1\}
\]

Usar OR-Tools o scipy.optimize según formulación.

## Guardrail

No inventar costos.

Si no existen:

- usar capacidad en número de territorios;
- o permitir al usuario introducir costos.

---

# 34. Fase 30 — Fairness y auditoría territorial

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
- script que la generó.

---

# 37. Fase 33 — Dashboard

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

Generar:

```text
artifacts/geo/risk_map.geojson
artifacts/geo/risk_map.gpkg
artifacts/tables/risk_scores.csv
artifacts/tables/model_metrics.csv
artifacts/tables/scenario_comparison.csv
artifacts/models/final_model.*
```

Cada tabla debe contener:

- `model_version`;
- `data_version`;
- `generated_at`;
- columnas documentadas.

---

# 39. Fase 35 — Auditoría de reproducibilidad

Desde un entorno limpio:

```bash
git clone ...
uv sync
dvc pull
make reproduce
```

Debe producir:

- panel;
- features;
- modelos;
- métricas;
- figuras;
- exportables.

Registrar duración y memoria.

No aceptar pasos manuales ocultos.

---

# 40. Fase 36 — Tests automatizados

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

## Dashboard

- archivo de datos disponible;
- columnas esperadas;
- app inicia.

---

# 41. Fase 37 — Logging de decisiones

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

Cada flecha debe apuntar a un script.

---

# 44. Fase 40 — Entregable técnico

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

No esconder errores o resultados negativos.

---

# 45. Fase 41 — Presentación de 10 slides

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
commit
```

Esto evita copiar cifras desactualizadas.

---

# 46. Fase 42 — Revisión final de lenguaje

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
- [ ] `make reproduce` funciona.

---

# 50. Orden exacto que debe seguir un agente

```text
1. Leer convocatoria y manual.
2. Crear repo y environment lock.
3. Registrar fuentes.
4. Descargar datos y calcular hashes.
5. Inventariar archivos.
6. Auditar schemas.
7. Definir contrato de IDs.
8. Conseguir y validar cartografía.
9. Armonizar columnas.
10. Reconciliar conteos.
11. Construir panel.
12. Ejecutar EDA.
13. Congelar target.
14. Congelar splits.
15. Construir features históricas.
16. Construir features relativas.
17. Construir grafo.
18. Construir features espaciales.
19. Entrenar baselines.
20. Entrenar Elastic Net.
21. Entrenar boosting.
22. Entrenar boosting + spatial.
23. Evaluar y registrar.
24. Calibrar incertidumbre.
25. Explicar modelo.
26. Entrenar Node2Vec.
27. Evaluar embedding.
28. Entrenar temporal embedding si procede.
29. Ejecutar ablations.
30. Entrenar GNN sólo si hay justificación.
31. Seleccionar modelo final.
32. Generar scores de riesgo.
33. Construir detector de anomalías.
34. Construir escenarios.
35. Ejecutar sensibilidad.
36. Construir priorización.
37. Generar mapas/exportables.
38. Construir dashboard.
39. Auditar fairness territorial.
40. Ejecutar tests.
41. Reproducir desde cero.
42. Congelar artefactos.
43. Escribir reporte.
44. Crear slides.
45. Auditar todas las cifras del pitch.
```

---

# 51. Comandos objetivo

El repositorio debe converger hacia algo parecido a:

```bash
make setup
make download
make audit-raw
make build-panel
make eda
make build-graph
make features
make train
make evaluate
make uncertainty
make explain
make scenarios
make export
make dashboard
make test
make reproduce
```

Cada comando debe ser idempotente cuando sea razonable.

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

---

# 54. Criterio final de calidad

El objetivo no es terminar con la frase:

> “Usamos embeddings, GNN y XGBoost.”

El objetivo es poder decir:

> **“Construimos un sistema reproducible. Cada capa fue comparada contra una alternativa más simple. Podemos mostrar qué información añadió, cuánto mejoró fuera de muestra, dónde falla, qué tan incierta es cada predicción y cómo cambian las decisiones cuando cambian los supuestos.”**

Ese es el estándar del proyecto.
