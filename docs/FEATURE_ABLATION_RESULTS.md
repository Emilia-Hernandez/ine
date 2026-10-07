# Resultados de ablación de variables

Actualizado: 2026-10-07. Métrica: MAE ponderado, después de la corrección nacional común.

## Grupos con backtest temporal completo

| Features | 2018 | 2021 | 2024 |
|---|---:|---:|---:|
| Historia mínima | 4.99 pp | 8.16 pp | 4.97 pp |
| Demografía electoral | 4.84 pp | 8.31 pp | 4.96 pp |
| **Contexto territorial** | **4.29 pp** | **8.10 pp** | **4.64 pp** |
| Demografía + contexto | 4.26 pp | 8.10 pp | 4.64 pp |
| Competencia previa | 4.30 pp | 8.09 pp | 4.67 pp |
| Concurrencia local | **4.18 pp** | 7.82 pp | 4.64 pp |
| **Competencia + concurrencia** | 4.21 pp | **7.81 pp** | 4.65 pp |
| Competencia + concurrencia + ciclo estatal | 4.21 pp | 7.90 pp | **4.41 pp** |

Frente al contexto territorial vigente, `competition_concurrency` mejora 0.080 pp en 2018 y 0.291 pp en el análogo principal 2021; en 2024 empeora sólo 0.014 pp, dentro del gate de 0.5 pp. Se promueve el bloque combinado. La señal dominante es concurrencia local; competencia aislada aporta poco, pero mejora ligeramente el fold principal al combinarse.

Las variables de sexo y edad sí están construidas y siguen disponibles para segmentación, explicaciones y escenarios, pero no mejoraron el MAE del modelo puntual de forma consistente.

El ciclo estatal mejora 2024 en 0.237 pp, pero empeora el target principal 2021 en 0.088 pp y queda prácticamente neutro en 2018. Por tanto, no se promueve como feature libre del boosting. Su señal se evalúa aparte como una corrección jerárquica transparente y contraída; véase `docs/ENTITY_CYCLE_ADAPTATION.md`.

## ECEG 2020

| Features 2024 | MAE ponderado |
|---|---:|
| Contexto territorial | 4.636 pp |
| Demografía + contexto | 4.644 pp |
| Demografía + ECEG | 4.927 pp |
| **Combinación completa** | **4.611 pp** |

La combinación completa mejora contexto territorial sólo 0.025 pp. El umbral congelado exigía 0.1 pp y ECEG sólo cuenta con un target válido. Por tanto, ECEG no se promueve al modelo puntual 2027. Permanece útil para descripción de vulnerabilidad y escenarios, donde la interpretación sustantiva puede importar más que una diferencia mínima de MAE.

## Comparación contra baseline

El bloque promovido obtiene 4.21 pp frente a 4.39 del baseline en 2018; 7.81 frente a 9.38 en 2021; y 4.65 frente a 4.42 en 2024. Mejora los dos primeros folds, pero el baseline todavía gana por 0.23 pp en 2024.

## Decisión y modelos avanzados

- Grupo seleccionado para la siguiente iteración 2027: `competition_concurrency`.
- Ciclo estatal como feature del árbol: no promovido; conservar la versión explícita de reversión a la media que sí supera su gate independiente.
- ECEG: no promovido al predictor puntual; conservar para segmentación y escenarios.
- Siguiente comparación prudente: challengers tabulares como XGBoost/LightGBM o Extra Trees usando exactamente estas features y folds.
- Redes neuronales densas: secundarias, porque hay muchas unidades pero sólo cuatro elecciones etiquetadas y el riesgo temporal de sobreajuste es alto.
- Embeddings/GNN: la vecindad espacial 2024 ya está disponible en `artifacts/graphs/`; debe evaluarse como challenger sólo en un corte temporal compatible. El grafo AMGE continúa siendo linaje, no vecindad.

La decisión máquina-legible está en `artifacts/feature_ablation_decision.json`.
