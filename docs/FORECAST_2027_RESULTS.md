# Resultados de la proyección experimental 2027 actualizada

Actualizado: 2026-10-07.

## Resultado operacional

- Snapshot: 70,751 secciones observadas en 2024.
- Boosting aplicado: 65,095 secciones A/B, mediante 59,772 unidades de modelado.
- Respaldo jerárquico: 5,656 secciones C/D.
- Baseline ponderado por lista nominal actual: 51.77%.
- Features del modelo: historia + contexto territorial relativo + competencia federal previa + concurrencia local 2027.
- Proyección experimental ponderada: **57.31% de participación**.
- Corrección nacional incluida: +5.21 pp.
- Corrección estatal incluida: −0.50 × el desvío del cambio estatal 2015–2021 respecto al nacional.

El 57.31% es un promedio de predicciones seccionales ponderado con la lista nominal 2024 disponible. Antes de la corrección estatal, la versión con competencia y concurrencia era 57.29%; el nuevo ajuste cambia poco el agregado nacional (+0.02 pp), pero redistribuye la predicción entre entidades. No es resultado oficial, estimación de votos emitidos ni intervalo nacional.

## Resultado por clase territorial

| Clase | Secciones | Estrategia | Predicción ponderada |
|---|---:|---|---:|
| A | 58,534 | boosting residual enriquecido | 58.38% |
| B | 6,561 | boosting enriquecido sobre componente oficial | 50.42% |
| C | 1,865 | respaldo jerárquico | 54.00% |
| D | 3,791 | respaldo jerárquico | 55.14% |

Los radios seccionales recalibrados al nominal 90% son 16.09 pp para A, 17.43 pp para B, 20.46 pp para C y 20.52 pp para D. Siguen siendo amplios porque la variación histórica es grande y sólo existe un análogo intermedio para calibrarlos.

## Comparación histórica de MAE

| Target | Baseline: última elección del mismo tipo | Boosting + correcciones nacional/estatal | Diferencia |
|---:|---:|---:|---:|
| 2018 | **4.39 pp** | 4.48 pp | +0.09 pp |
| 2021 | 9.38 pp | **7.35 pp** | −2.03 pp |
| 2024 | **4.42 pp** | 4.52 pp | +0.10 pp |

El modelo corregido gana claramente en el análogo principal 2021 y mejora frente a su propia versión sin corrección en 2024. El baseline simple conserva una ventaja pequeña en 2018 y 2024, por lo que no puede afirmarse que el modelo sea universalmente superior.

No existe MAE 2027: el MAE requiere comparar con participación real y esa observación todavía no existe.

## Decisión

La proyección queda aprobada como artefacto experimental interno para análisis, escenarios y revisión territorial. No está aprobada para publicación como pronóstico oficial porque:

- usa geografía 2024, no un marco certificado 2027;
- los linajes disponibles terminan en 2022;
- los intervalos A/B dependen de un solo análogo intermedio fuera de tiempo, 2021;
- el modelo corregido fue peor que el baseline en el fold 2024.

La decisión y la especificación exacta están en `artifacts/forecast_2027_decision.json` y `artifacts/forecast_2027_model_registry.json`.
