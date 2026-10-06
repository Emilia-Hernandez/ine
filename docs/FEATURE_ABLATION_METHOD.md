# Método de ablación de variables

Actualizado: 2026-10-06.

## Objetivo

Medir qué grupos de variables mejoran realmente la predicción. El algoritmo se mantiene fijo como `HistGradientBoostingRegressor` residual; sólo cambia la matriz de features. Así una diferencia de MAE puede atribuirse a información adicional y no a otro modelo o hiperparámetro.

## Baseline y modelo

El baseline continúa siendo la participación de la elección anterior de la misma familia para sección estable o componente oficial. El boosting predice un residual, aplica contracción 0.25 y después recibe la misma corrección nacional usada en la proyección experimental.

## Grupos evaluados

- `historical_core`: participaciones rezagadas, tendencia, volatilidad, tamaño, cobertura y clase B.
- `electoral_demographics`: añade composición y participación histórica por sexo y edad.
- `territorial_context`: añade promedios y dispersiones rezagados por entidad y nación, diferencias relativas y tipo de unidad territorial.
- `demographics_context`: combina demografía electoral y contexto territorial.
- `demographics_eceg`: añade escolaridad, analfabetismo, actividad económica, discapacidad, lengua indígena e internet.
- `full_enriched`: combina demografía, contexto y ECEG.

Los agregados territoriales se calculan sólo con features conocidas antes del target. No usan el outcome del año evaluado.

## Disponibilidad temporal

Los cuatro grupos sin ECEG se evalúan en 2018, 2021 y 2024 con entrenamiento estrictamente anterior. ECEG fue modificado oficialmente el 18 de agosto de 2021, por lo que sus grupos sólo se evalúan en el origen 2024. Para ese origen, la fotografía 2020 se adjunta también a las filas históricas de entrenamiento como información disponible al momento de pronosticar 2024; no se interpreta como un backtest estricto 2015–2021.

## Gates

El mejor grupo estricto debe mejorar el target principal 2021 y no empeorar ningún otro fold más de 0.5 pp frente al conjunto actual. ECEG debe mejorar al menos 0.1 pp en 2024 para justificar nueve variables adicionales y una validación de un solo target.
