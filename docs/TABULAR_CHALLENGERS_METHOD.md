# Método de challengers tabulares

Actualizado: 2026-10-06.

## Objetivo

Comprobar si otra familia de árboles mejora al `HistGradientBoostingRegressor` actual. La comparación cambia sólo el algoritmo: conserva las features `competition_concurrency`, los folds temporales 2018/2021/2024, el baseline, los pesos, la contracción residual 0.25 y la corrección nacional.

## Qué predice cada modelo

El baseline es la participación de la elección anterior de la misma familia electoral para una sección estable o un componente de linaje oficial. Cada modelo aprende el **residual**: la diferencia entre la participación observada y ese baseline. La corrección aplicada es sólo 25% del residual estimado, para limitar cambios inestables entre ciclos. Si una unidad no tiene baseline, un segundo ajuste de la misma familia predice la participación directamente.

Después se aplica la misma corrección nacional estimada con el ciclo comparable anterior. Por ello, cualquier diferencia de MAE entre filas se atribuye a la familia del algoritmo, no a datos o calibraciones diferentes.

## Familias

- `HistGradientBoostingRegressor` (referencia): construye árboles pequeños secuencialmente; cada árbol corrige errores de los anteriores y el histograma acelera el ajuste.
- `XGBRegressor`: también es boosting secuencial, con regularización, muestreo de filas/variables y optimización eficiente por histogramas.
- `LGBMRegressor`: boosting por árboles que crecen priorizando las hojas con mayor ganancia; suele ser rápido y flexible en tablas grandes.
- `ExtraTreesRegressor`: promedia muchos árboles independientes con cortes muy aleatorios; reduce varianza, pero no corrige errores secuencialmente.

Se congeló una especificación moderada por familia antes de comparar resultados. No se hizo una búsqueda extensa de hiperparámetros: con sólo tres elecciones de prueba, elegir entre muchas configuraciones sobreajustaría precisamente esos folds.

## Evaluación y gate

Para cada target sólo se entrena con elecciones anteriores. El MAE se pondera por registros identificados (`votó + no votó`). El target principal es 2021, fijado desde fases anteriores. Un challenger se promueve únicamente si:

1. reduce el MAE ponderado 2021 frente a la referencia; y
2. no empeora 2018 ni 2024 por más de 0.5 puntos porcentuales.

Los hiperparámetros, versiones, tiempos, años de entrenamiento y columnas usadas quedan registrados en `artifacts/tables/tabular_challenger_registry.csv`.
