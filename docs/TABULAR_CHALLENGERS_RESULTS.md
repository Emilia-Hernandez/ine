# Resultados de challengers tabulares

Actualizado: 2026-10-06. Métrica: MAE ponderado después de la corrección nacional común.

| Modelo | 2018 | 2021 | 2024 |
|---|---:|---:|---:|
| **HistGradientBoosting** | 4.206 pp | **7.807 pp** | **4.651 pp** |
| XGBoost | **4.110 pp** | 7.818 pp | 4.676 pp |
| LightGBM | 4.429 pp | 7.895 pp | 4.726 pp |
| Extra Trees | 4.340 pp | 8.080 pp | 4.768 pp |

## Resultado

No se promueve ningún challenger. `HistGradientBoostingRegressor` conserva el menor MAE en el target principal 2021. XGBoost quedó muy cerca: fue peor por 0.012 puntos porcentuales en 2021 y por 0.025 pp en 2024, aunque mejoró 2018 por 0.096 pp.

El control reproduce exactamente los resultados del grupo `competition_concurrency` de la fase anterior. Esto confirma que la comparación mantuvo fijas las features y la canalización.

## Comparación contra el baseline

El baseline de referencia —participación anterior de la misma familia para sección estable o linaje oficial— tiene MAE de 4.386 pp en 2018, 9.385 pp en 2021 y 4.421 pp en 2024. El modelo seleccionado lo mejora por 0.180 pp en 2018 y 1.578 pp en 2021, pero sigue 0.230 pp por detrás en 2024.

## Qué mejoró esta fase

- Se sustituyó una comparación hipotética por evidencia homogénea para cuatro familias.
- XGBoost y LightGBM quedaron instalados y versionados en el entorno reproducible.
- Cada modelo tiene predicciones por unidad, métricas, tiempos, hiperparámetros y años de entrenamiento auditables.
- Se evitó promover XGBoost por una diferencia prácticamente nula en 2021 y se conservó el modelo más simple que ganó el gate.

## Siguiente decisión

Una red neuronal densa puede probarse como challenger secundario, pero la ganancia probable es limitada porque existen muchas secciones y sólo cuatro elecciones etiquetadas. La vecindad espacial 2024 ya se construyó por separado del grafo AMGE y habilita un challenger GNN para cortes compatibles; no debe aplicarse retrospectivamente como si fuera la topología de 2009–2021. El siguiente paso de mayor valor es comparar ese challenger contra la referencia congelada con los mismos folds y gates.

La decisión máquina-legible está en `artifacts/tabular_challenger_decision.json`.
