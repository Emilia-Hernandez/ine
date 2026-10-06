# Resultados de ablación de variables

Actualizado: 2026-10-06. Métrica: MAE ponderado, después de la corrección nacional común.

## Grupos con backtest temporal completo

| Features | 2018 | 2021 | 2024 |
|---|---:|---:|---:|
| Historia mínima | 4.99 pp | 8.16 pp | 4.97 pp |
| Demografía electoral | 4.84 pp | 8.31 pp | 4.96 pp |
| **Contexto territorial** | **4.29 pp** | **8.10 pp** | **4.64 pp** |
| Demografía + contexto | 4.26 pp | 8.10 pp | 4.64 pp |

El contexto territorial mejora el conjunto actualmente usado en los tres folds: −0.56 pp en 2018, −0.21 pp en 2021 y −0.32 pp en 2024. Demografía + contexto obtiene 4.258 pp en 2018, pero es apenas 0.004 pp peor que contexto solo en el target principal 2021 y 0.008 pp peor en 2024. Se promueve `territorial_context` por parsimonia y desempeño principal.

Las variables de sexo y edad sí están construidas y siguen disponibles para segmentación, explicaciones y escenarios, pero no mejoraron el MAE del modelo puntual de forma consistente.

## ECEG 2020

| Features 2024 | MAE ponderado |
|---|---:|
| Contexto territorial | 4.636 pp |
| Demografía + contexto | 4.644 pp |
| Demografía + ECEG | 4.927 pp |
| **Combinación completa** | **4.611 pp** |

La combinación completa mejora contexto territorial sólo 0.025 pp. El umbral congelado exigía 0.1 pp y ECEG sólo cuenta con un target válido. Por tanto, ECEG no se promueve al modelo puntual 2027. Permanece útil para descripción de vulnerabilidad y escenarios, donde la interpretación sustantiva puede importar más que una diferencia mínima de MAE.

## Comparación contra baseline

El contexto territorial obtiene 4.29 pp frente a 4.39 del baseline en 2018; 8.10 frente a 9.38 en 2021; y 4.64 frente a 4.42 en 2024. Mejora el análogo principal y reduce mucho el deterioro 2024 del modelo anterior, pero el baseline todavía gana por 0.22 pp en 2024.

## Decisión y modelos avanzados

- Grupo seleccionado para la siguiente iteración 2027: `territorial_context`.
- ECEG: no promovido al predictor puntual; conservar para segmentación y escenarios.
- Siguiente comparación prudente: challengers tabulares como XGBoost/LightGBM o Extra Trees usando exactamente estas features y folds.
- Redes neuronales densas: secundarias, porque hay muchas unidades pero sólo cuatro elecciones etiquetadas y el riesgo temporal de sobreajuste es alto.
- Embeddings/GNN: esperar hasta disponer de geometrías/adyacencias territoriales actualizadas. El grafo AMGE actual describe linajes, no vecindad espacial completa.

La decisión máquina-legible está en `artifacts/feature_ablation_decision.json`.
