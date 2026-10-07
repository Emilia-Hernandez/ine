# Challenger de similitud sociodemográfica

Actualizado: 2026-10-07.

## Pregunta

¿Ayuda conectar secciones y componentes territoriales con pares de composición sexo–edad semejante, aunque estén geográficamente separados, y añadir ese contexto al boosting vigente?

Se comparan tres representaciones sobre dos grafos k-NN:

1. estadísticas explícitas de los pares;
2. embedding `neighbor-only` de 16 dimensiones;
3. estadísticas explícitas y embedding combinados.

La referencia es el modelo vigente `competition_concurrency` con corrección nacional y corrección estatal de ciclo −0.50. Modelo, folds, ponderación y residual shrinkage permanecen fijos.

## Construcción temporal del grafo

Las aristas se forman únicamente con cinco proporciones observadas en la elección anterior:

- mujeres en lista nominal;
- edades 18–29;
- edades 30–44;
- edades 45–64;
- edades 65 o más.

No se usan participación, target, residuales ni ECEG. Para cada fold, imputación y estandarización se ajustan sólo con años anteriores y excluyendo las cinco entidades reservadas para validación del encoder. Se construyen dos sensibilidades: vecinos mutuos `k=8` y `k=16`. Los nodos sin relación mutua reciben una única conexión al vecino más cercano para evitar aislados.

El grafo admite aristas entre entidades. En promedio, 88.4% de las aristas `k=8` y 88.6% de las `k=16` cruzan una frontera estatal, confirmando que la topología representa similitud estructural y no vecindad geográfica.

## Representaciones

Las estadísticas explícitas calculan media, dispersión, diferencia nodo–pares y z-score para cinco señales históricas de participación y tendencia. Añaden además grado, distancia sociodemográfica media y proporción de pares de otra entidad.

El encoder `neighbor-only` no tiene rama propia ni recibe etiquetas. Reconstruye variables electorales conocidas del nodo exclusivamente desde el promedio de sus pares; sus 16 dimensiones se agregan como columnas al HistGradientBoosting. El embedding nunca se usa como predictor aislado.

## Resultados fuera de tiempo

MAE ponderado; menor es mejor.

| Variante | 2018 | 2021 | 2024 |
|---|---:|---:|---:|
| Referencia actual | **4.478 pp** | **7.351 pp** | 4.516 pp |
| Explícitas, k=8 | 4.609 pp | 7.403 pp | 4.517 pp |
| Explícitas, k=16 | 4.516 pp | 7.429 pp | 4.479 pp |
| Embedding, k=8 | 4.541 pp | 7.366 pp | 4.494 pp |
| Embedding, k=16 | 4.595 pp | 7.359 pp | **4.478 pp** |
| Combinadas, k=8 | 4.666 pp | 7.414 pp | 4.486 pp |
| Combinadas, k=16 | 4.597 pp | 7.424 pp | 4.480 pp |

El embedding `k=16` es el mejor candidato en el target principal, pero empeora 2021 en 0.008 pp frente a la referencia. Mejora 2024 en 0.039 pp y supera a las estadísticas explícitas en 2021, pero no pasa el requisito de mejorar el fold principal. Ninguna variante se promueve y la proyección 2027 permanece sin cambios.

## Lectura

El resultado es informativo: la similitud sociodemográfica contiene señal, especialmente en 2024, pero esa señal ya está en gran medida absorbida por la historia territorial, competencia, concurrencia y corrección estatal. El embedding comprime mejor el contexto de pares que las estadísticas manuales, aunque no aporta una mejora temporal suficientemente estable.

No se recomienda ampliar la búsqueda de arquitecturas o valores de `k` usando estos mismos tres folds. Una extensión futura tendría que aportar nueva información —por ejemplo, una fuente sociodemográfica con varios cortes históricos— y no sólo otra transformación de las mismas proporciones.

## Reproducción

```bash
make sociodemographic-similarity
uv run pytest -q tests/test_sociodemographic_similarity_challenger.py
```

Configuración, predicciones, métricas, grafos, embeddings y decisión se guardan por separado bajo `configs/sociodemographic_similarity_challenger.yaml` y `artifacts/sociodemographic_similarity*`.
