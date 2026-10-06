# Resultados de challengers tabulares

Actualizado: 2026-10-06. Métrica: MAE ponderado después de la corrección nacional común.

| Modelo | 2018 | 2021 | 2024 |
|---|---:|---:|---:|
| **HistGradientBoosting** | 4.286 pp | **8.098 pp** | **4.636 pp** |
| XGBoost | **4.145 pp** | 8.104 pp | 4.667 pp |
| LightGBM | 4.339 pp | 8.196 pp | 4.727 pp |
| Extra Trees | 4.381 pp | 8.446 pp | 4.813 pp |

## Resultado

No se promueve ningún challenger. `HistGradientBoostingRegressor` conserva el menor MAE en el target principal 2021. XGBoost quedó muy cerca: fue peor por sólo 0.006 puntos porcentuales en 2021 y por 0.031 pp en 2024, aunque mejoró 2018 por 0.140 pp. LightGBM y Extra Trees quedaron detrás en los tres resultados decisivos o no compensaron su mayor complejidad.

El control reproduce exactamente los resultados del grupo territorial de la fase anterior. Esto confirma que la comparación mantuvo fijas las features y la canalización.

## Comparación contra el baseline

El baseline de referencia —participación anterior de la misma familia para sección estable o linaje oficial— tiene MAE de 4.386 pp en 2018, 9.385 pp en 2021 y 4.421 pp en 2024. El modelo seleccionado lo mejora por 0.100 pp en 2018 y 1.287 pp en 2021, pero sigue 0.215 pp por detrás en 2024.

## Qué mejoró esta fase

- Se sustituyó una comparación hipotética por evidencia homogénea para cuatro familias.
- XGBoost y LightGBM quedaron instalados y versionados en el entorno reproducible.
- Cada modelo tiene predicciones por unidad, métricas, tiempos, hiperparámetros y años de entrenamiento auditables.
- Se evitó promover XGBoost por una diferencia prácticamente nula en 2021 y se conservó el modelo más simple que ganó el gate.

## Siguiente decisión

Una red neuronal densa puede probarse como challenger secundario, pero la ganancia probable es limitada porque existen muchas secciones y sólo cuatro elecciones etiquetadas. Antes de una GNN o embeddings espaciales hace falta una geometría/adyacencia seccional actualizada: el grafo AMGE disponible describe cambios de linaje, no vecindad completa. El siguiente paso de mayor valor es actualizar la proyección experimental 2027 con las features territoriales ya seleccionadas y recalcular sus intervalos; después puede evaluarse la red densa sin bloquear esa integración.

La decisión máquina-legible está en `artifacts/tabular_challenger_decision.json`.
