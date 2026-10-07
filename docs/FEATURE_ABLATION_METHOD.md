# Método de ablación de variables

Actualizado: 2026-10-07.

## Objetivo

Medir qué grupos de variables mejoran realmente la predicción. El algoritmo se mantiene fijo como `HistGradientBoostingRegressor` residual; sólo cambia la matriz de features. Así una diferencia de MAE puede atribuirse a información adicional y no a otro modelo o hiperparámetro.

## Baseline y modelo

El baseline continúa siendo la participación de la elección anterior de la misma familia para sección estable o componente oficial. El boosting predice un residual, aplica contracción 0.25 y después recibe la misma corrección nacional usada en la proyección experimental.

## Grupos evaluados

- `historical_core`: participaciones rezagadas, tendencia, volatilidad, tamaño, cobertura y clase B.
- `electoral_demographics`: añade composición y participación histórica por sexo y edad.
- `territorial_context`: añade promedios y dispersiones rezagados por entidad y nación, diferencias relativas y tipo de unidad territorial.
- `demographics_context`: combina demografía electoral y contexto territorial.
- `competition_context`: añade margen, concentración HHI, número efectivo de opciones y concentración en las dos primeras candidaturas de la elección federal previa de la misma familia.
- `concurrency_context`: añade si existe elección local concurrente y si la boleta incluye ejecutivo local, congreso y/o autoridades municipales.
- `competition_concurrency`: combina competencia previa y calendario local con el contexto territorial.
- `entity_cycle_context`: añade nivel y cambio estatal entre las dos elecciones previas de la misma familia, además de su diferencia respecto al cambio nacional.
- `demographics_eceg`: añade escolaridad, analfabetismo, actividad económica, discapacidad, lengua indígena e internet.
- `full_enriched`: combina demografía, contexto y ECEG.

Los agregados territoriales se calculan sólo con features conocidas antes del target. No usan el outcome del año evaluado.

La competencia se deriva de resultados definitivos SICEE 2009, 2012, 2015, 2018 y 2021. Los votos marcados por partido y por combinación se consolidan a nivel candidatura únicamente en los distritos donde la coalición estuvo activa. Para componentes de linaje, primero se suman los votos de sus secciones miembro y después se calculan las métricas; no se promedian porcentajes seccionales.

La concurrencia procede del calendario oficial conocido antes de cada jornada. Es información del diseño de la elección objetivo, no un resultado posterior. La configuración 2027 está congelada al 6 de octubre de 2026.

El ciclo estatal se calcula con agregados territoriales SICEE y excluye el voto en el extranjero. La participación es `TOTAL_VOTOS / LISTA_NOMINAL`. Cada target usa dos elecciones estrictamente anteriores: 2003–2009 para 2015, 2006–2012 para 2018, 2009–2015 para 2021, 2012–2018 para 2024 y 2015–2021 para 2027.

## Disponibilidad temporal

Los ocho grupos sin ECEG se evalúan en 2018, 2021 y 2024 con entrenamiento estrictamente anterior. ECEG fue modificado oficialmente el 18 de agosto de 2021, por lo que sus grupos sólo se evalúan en el origen 2024. Para ese origen, la fotografía 2020 se adjunta también a las filas históricas de entrenamiento como información disponible al momento de pronosticar 2024; no se interpreta como un backtest estricto 2015–2021.

## Gates

El mejor grupo estricto debe mejorar el target principal 2021 y no empeorar ningún otro fold más de 0.5 pp frente al conjunto actual. ECEG debe mejorar al menos 0.1 pp en 2024 para justificar nueve variables adicionales y una validación de un solo target.
