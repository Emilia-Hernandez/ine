# Método de la red neuronal densa

Actualizado: 2026-10-06.

## Objetivo

Evaluar si una red neuronal densa mejora el HistGradientBoosting seleccionado. Sólo cambia la familia del algoritmo: se mantienen `territorial_context`, folds 2018/2021/2024, pesos, baseline, contracción residual 0.25 y corrección nacional.

## Arquitectura

Se usa `MLPRegressor`, una red *feed-forward* con:

- 64 neuronas en la primera capa oculta y 32 en la segunda;
- activación ReLU;
- optimizador Adam;
- regularización L2 `alpha=0.001`;
- lotes de 1,024 unidades;
- máximo 120 iteraciones;
- parada temprana después de 12 iteraciones sin mejora.

Una red densa combina todas las variables mediante capas de sumas ponderadas y transformaciones no lineales. A diferencia de un árbol, no crea reglas explícitas del tipo “si la participación anterior supera X”. Aprende superficies continuas que pueden representar interacciones complejas.

## Preparación y objetivo

Las variables numéricas se imputan con mediana y estandarizan; las categorías se codifican en indicadores. La participación directa y el residual también se centran y escalan con estadísticas ponderadas calculadas únicamente en el entrenamiento. La transformación se invierte antes de predecir.

La red principal estima:

```text
residual = participación real - baseline de misma familia
predicción = baseline + 0.25 × residual_estimado + corrección_nacional
```

Un segundo ajuste directo cubre unidades sin baseline. La validación interna de parada temprana es aleatoria, pero contiene exclusivamente elecciones anteriores al target evaluado.

## Gate

La red debe reducir el MAE ponderado 2021 frente al HistGradientBoosting y no empeorar 2018 ni 2024 más de 0.5 pp. Se prueba una sola arquitectura pequeña: buscar muchas arquitecturas con únicamente tres elecciones de evaluación sobreajustaría la selección.
