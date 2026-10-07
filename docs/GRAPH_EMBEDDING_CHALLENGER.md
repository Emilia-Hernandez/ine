# Challenger híbrido: variables tabulares + embedding de grafo

Actualizado: 2026-10-06.

## Pregunta evaluada

¿El contexto espacial ayuda si se representa como un embedding adicional, sin
pedirle al embedding que prediga por sí solo?

La comparación contiene únicamente:

1. HistGradientBoosting con las variables `territorial_context`;
2. el mismo HistGradientBoosting con 16 dimensiones GraphSAGE Rook adicionales;
3. el mismo HistGradientBoosting con 16 dimensiones GraphSAGE sobre el grafo
   aumentado adicionales.

No se entrenó ni evaluó un predictor basado sólo en el embedding.

## Contrato sin fuga

El encoder es un autoencoder GraphSAGE auto-supervisado. Su entrada tiene 82
columnas: 22 variables numéricas estandarizadas, 22 indicadores de faltantes y 38
indicadores categóricos. Dos capas de agregación `82 → 64 → 16` producen el
embedding. Durante el entrenamiento se oculta aleatoriamente 15% de la entrada y
se reconstruyen las variables conocidas mediante pérdida Smooth L1.

El encoder no recibe `actual`, residuales ni otra transformación del target. También
se evita usar la disponibilidad del target para seleccionar nodos: reconstruye todos
los nodos de los estados de ajuste y usa cinco estados completos únicamente para
parada temprana. Para cada fold sólo se ajusta con grafos anteriores:

| Evaluación | Grafos usados para ajustar el encoder |
|---:|---|
| 2018 | 2015 |
| 2021 | 2015, 2018 |
| 2024 | 2015, 2018, 2021 |

El encoder congelado genera después las 16 columnas del target. Esas columnas se
agregan a las 22 variables numéricas originales; el árbol conserva las variables
categóricas, el target residual, la contracción 0.25 y la corrección nacional ya
usados por la referencia.

## Resultado fuera de tiempo

MAE ponderado por registros identificados; menor es mejor. La referencia se volvió
a entrenar sobre exactamente las mismas secciones estables A que el modelo híbrido.

| Año | Sin embedding | + GraphSAGE Rook | Cambio Rook | + GraphSAGE aumentado |
|---:|---:|---:|---:|---:|
| 2018 | 4.299 pp | 4.323 pp | +0.024 pp | 4.302 pp |
| 2021 | 8.218 pp | 8.350 pp | +0.132 pp | 8.369 pp |
| 2024 | 4.721 pp | 4.687 pp | −0.035 pp | 4.681 pp |

El embedding espacial aporta una mejora pequeña en 2024, pero deteriora 2021, que
es el target principal congelado. Por tanto no se promueve. El resultado no invalida
usar embeddings como señal adicional; indica que este encoder auto-supervisado y
esta representación no generalizan mejor de forma consistente entre ciclos.

Las aristas sintéticas tampoco aportan una ventaja estable: casi empatan a Rook en
2018 y 2024 y empeoran ligeramente más en 2021.

## Artefactos

- configuración: `configs/graph_embedding_challenger.yaml`;
- embeddings por fold y topología: `artifacts/graph_embeddings/`;
- estados del encoder y SHA-256: `artifacts/models/graph_embedding/` y el registro;
- predicciones: `artifacts/tables/graph_embedding_predictions.parquet`;
- métricas: `artifacts/tables/graph_embedding_metrics.csv`;
- registro: `artifacts/tables/graph_embedding_registry.csv`;
- decisión: `artifacts/graph_embedding_decision.json`.

## Reproducción

```bash
uv run python scripts/run_graph_embedding_challenger.py
uv run pytest -q tests/test_graph_embedding_challenger.py
```

Una iteración futura puede probar un objetivo espacial contrastivo o reconstrucción
exclusiva desde vecinos, pero debe preespecificarse antes de volver a mirar el gate
2021 para no convertir tres elecciones en una búsqueda de hiperparámetros.

La reconstrucción exclusiva desde vecinos ya fue evaluada posteriormente; véase
`docs/NEIGHBOR_ONLY_EMBEDDING_CHALLENGER.md`.
