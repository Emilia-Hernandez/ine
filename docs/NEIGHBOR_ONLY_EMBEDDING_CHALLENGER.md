# Challenger híbrido: embedding exclusivamente vecinal

Actualizado: 2026-10-06.

## Pregunta

El primer autoencoder GraphSAGE podía conservar información del propio nodo. Esta
variante comprueba si mejora la generalización cuando las 16 dimensiones adicionales
contienen exclusivamente información de sus vecinos.

El embedding sigue siendo una señal añadida al HistGradientBoosting. No se usa como
predictor aislado.

## Garantía arquitectónica

Para el nodo `i` se calcula una sola agregación:

```text
vecinos_i = media(X_j para cada j vecino de i)
embedding_i = Linear(ReLU(Linear(vecinos_i)))
```

No existe rama `self`, no se añade diagonal a la matriz y no se hace una segunda
propagación. Esto último evita reintroducir `X_i` por el recorrido `i → j → i`. Las
capas del encoder no tienen sesgo: una sección aislada produce exactamente un vector
de ceros y no recibe una conexión inventada.

El decoder intenta reconstruir las 82 variables conocidas del nodo a partir del
embedding vecinal. El entrenamiento es auto-supervisado, no recibe `actual` ni
residuales y usa sólo grafos anteriores al target. Una prueba automatizada altera
`X_i` y exige que `embedding_i` permanezca idéntico mientras cambia el embedding de
sus vecinos.

## Resultado fuera de tiempo

MAE ponderado por registros identificados; menor es mejor. Las unidades, features
tabulares, pesos, contracción residual y corrección nacional son idénticos a la
referencia.

| Año | Sin embedding | Vecinos Rook | Cambio Rook | Vecinos aumentado | Cambio aumentado |
|---:|---:|---:|---:|---:|---:|
| 2018 | 4.299 pp | 4.479 pp | +0.180 pp | 4.471 pp | +0.171 pp |
| 2021 | 8.218 pp | 8.225 pp | +0.007 pp | 8.230 pp | +0.012 pp |
| 2024 | 4.721 pp | 4.709 pp | −0.013 pp | 4.687 pp | −0.035 pp |

La restricción vecinal reduce fuertemente el deterioro 2021 del encoder anterior:
de +0.132 a +0.007 pp. Sin embargo, no mejora el target principal y empeora 2018 en
0.180 pp. El gate congelado no permite promoverlo.

El patrón sugiere que la señal local puede aportar en 2024, pero su relación con la
participación no es estable entre ciclos. La topología aumentada mejora más 2024,
aunque tampoco supera el gate principal.

## Artefactos y reproducción

- configuración: `configs/neighbor_only_embedding_challenger.yaml`;
- embeddings: `artifacts/neighbor_only_embeddings/`;
- modelos: `artifacts/models/neighbor_only_embedding/`;
- predicciones: `artifacts/tables/neighbor_only_embedding_predictions.parquet`;
- métricas: `artifacts/tables/neighbor_only_embedding_metrics.csv`;
- registro: `artifacts/tables/neighbor_only_embedding_registry.csv`;
- decisión: `artifacts/neighbor_only_embedding_decision.json`.

```bash
uv run python scripts/run_neighbor_only_embedding_challenger.py
uv run pytest -q tests/test_neighbor_only_embedding_challenger.py
```

El próximo experimento espacial, si se realiza, debería probar estadísticas vecinales
explícitas y auditables —media, dispersión y diferencia nodo–vecindario de variables
rezagadas— antes de ampliar la búsqueda de arquitecturas neuronales.
