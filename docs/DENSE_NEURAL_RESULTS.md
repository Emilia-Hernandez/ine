# Resultados de la red neuronal densa

Actualizado: 2026-10-06. Métrica: MAE ponderado después de la corrección nacional común.

| Modelo | 2018 | 2021 | 2024 |
|---|---:|---:|---:|
| **HistGradientBoosting** | **4.286 pp** | **8.098 pp** | **4.636 pp** |
| Red densa 64–32 | 5.262 pp | 8.903 pp | 4.665 pp |

## Decisión

La red no se promueve. En el target principal 2021 empeora 0.805 pp frente al árbol seleccionado. En 2018 empeora 0.976 pp, excediendo el límite de robustez de 0.5 pp. En 2024 queda cerca, sólo 0.029 pp por detrás, pero un empate en un fold no compensa el deterioro de los otros dos.

## Interpretación

El conjunto contiene muchas secciones, pero sólo cuatro elecciones etiquetadas. Muchas filas no equivalen a muchos regímenes temporales independientes: las secciones de una misma elección comparten el mismo contexto nacional. La red tiene más libertad para aprender interacciones y por ello puede ajustarse a patrones de los pocos ciclos disponibles que no se repiten en el siguiente.

La estandarización del objetivo redujo el fallo inicial de escala y dejó una comparación técnicamente válida. Aun así, el ensamble de árboles fue más estable. Se conserva `hist_gradient_boosting` para la proyección experimental 2027.

La decisión máquina-legible está en `artifacts/dense_neural_decision.json`.
