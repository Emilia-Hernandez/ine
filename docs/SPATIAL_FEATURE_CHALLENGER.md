# Challenger de variables espaciales explícitas

Actualizado: 2026-10-06.

## Objetivo

Evaluar si el grafo ayuda más como variables auditables que como embedding. La
comparación conserva HistGradientBoosting, muestra estable A, target, pesos,
contracción residual, corrección nacional y folds. Sólo cambia el bloque de features.

## Variables construidas

El bloque completo contiene 35 variables conocidas antes de cada elección.

Para cada una de cinco señales históricas —participación de la misma familia,
participación lag 1, cambio lag 1–lag 2, crecimiento de Lista Nominal y cobertura de
registros— se calculan cuatro estadísticas Rook:

- media vecinal;
- desviación estándar vecinal;
- diferencia nodo menos media vecinal;
- z-score del nodo en su vecindario, acotado a ±10.

Se añaden media y diferencia de participación a dos saltos, excluyendo el propio nodo
y sus vecinos directos; proporciones de vecinos que cruzan municipio o entidad; grado,
aislamiento, área, perímetro, compactación, coordenadas, densidad de Lista Nominal,
relación Lista/Padrón y crecimiento contra el último dato electoral.

Los campos de Lista Nominal y Padrón proceden del DBF del snapshot cartográfico previo
a cada elección. Ninguna variable usa `actual`, residuos del target ni geometría futura.

## Ablación de bloques

El conjunto completo de 35 variables mejoró 2018 y 2024, pero empeoró 2021. La
ablación mostró que la morfología y los campos del snapshot introducían el deterioro.
Se congeló entonces `neighbor_core`, con 24 variables:

- 20 estadísticas vecinales de las cinco señales históricas;
- dos señales exclusivas de segundo salto;
- dos proporciones de frontera administrativa.

## Resultado

MAE ponderado por registros identificados; menor es mejor.

| Año | Referencia | `neighbor_core` Rook | Mejora absoluta | Mejora relativa |
|---:|---:|---:|---:|---:|
| 2018 | 4.299 pp | 4.262 pp | 0.037 pp | 0.87% |
| 2021 | 8.218 pp | 8.169 pp | 0.049 pp | 0.60% |
| 2024 | 4.721 pp | 4.692 pp | 0.030 pp | 0.63% |

También aumenta la proporción de secciones dentro de ±5 pp en los tres folds. Rook
estricto supera ligeramente a la variante aumentada en el target principal; por ello
las aristas sintéticas no se incorporan al bloque promovido.

`neighbor_core` pasa el gate: mejora 2021 y no deteriora ningún otro fold. Se promueve
como challenger para la siguiente iteración en secciones estables A. Todavía no
reemplaza el modelo experimental 2027 A+B, porque las unidades de linaje B requieren
una definición de vecindad de componentes compatible.

## Artefactos

- configuración: `configs/spatial_feature_challenger.yaml`;
- features por año/topología: `artifacts/spatial_features/`;
- predicciones: `artifacts/tables/spatial_feature_predictions.parquet`;
- métricas: `artifacts/tables/spatial_feature_metrics.csv`;
- registro: `artifacts/tables/spatial_feature_registry.csv`;
- decisión: `artifacts/spatial_feature_decision.json`.

## Reproducción

```bash
uv run python scripts/run_spatial_feature_challenger.py
uv run pytest -q tests/test_spatial_feature_challenger.py
```

El siguiente paso metodológico es definir vecindad para componentes de linaje B y
repetir la evaluación sobre la muestra A+B antes de trasladar el bloque a 2027.
