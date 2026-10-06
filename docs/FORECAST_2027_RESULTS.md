# Resultados de la proyección experimental 2027 actualizada

Actualizado: 2026-10-06.

## Resultado operacional

- Snapshot: 70,751 secciones observadas en 2024.
- Boosting aplicado: 65,095 secciones A/B, mediante 59,772 unidades de modelado.
- Respaldo jerárquico: 5,656 secciones C/D.
- Baseline ponderado por lista nominal actual: 51.77%.
- Features del modelo: historia + contexto territorial relativo.
- Proyección experimental ponderada: **57.15% de participación**.
- Corrección nacional incluida: +5.21 pp.

El 57.15% es un promedio de predicciones seccionales ponderado con la lista nominal 2024 disponible. La versión anterior, sin contexto territorial, era 57.06%; el cambio es +0.09 pp. No es resultado oficial, estimación de votos emitidos ni intervalo nacional.

## Resultado por clase territorial

| Clase | Secciones | Estrategia | Predicción ponderada |
|---|---:|---|---:|
| A | 58,534 | boosting residual territorial | 58.35% |
| B | 6,561 | boosting territorial sobre componente oficial | 49.66% |
| C | 1,865 | respaldo jerárquico | 54.06% |
| D | 3,791 | respaldo jerárquico | 54.20% |

Los radios seccionales recalibrados al nominal 90% son 17.52 pp para A, 19.32 pp para B, 20.46 pp para C y 20.52 pp para D. Frente a la versión anterior, A se estrecha 0.46 pp y B 0.14 pp. Siguen siendo amplios porque la variación histórica es grande y sólo existe un análogo intermedio para calibrarlos.

## Comparación histórica de MAE

| Target | Baseline: última elección del mismo tipo | Boosting + corrección nacional | Diferencia |
|---:|---:|---:|---:|
| 2018 | 4.39 pp | **4.29 pp** | −0.10 pp |
| 2021 | 9.38 pp | **8.10 pp** | −1.29 pp |
| 2024 | **4.42 pp** | 4.64 pp | +0.22 pp |

El modelo territorial gana claramente en el análogo principal 2021 y reduce mucho el deterioro de 2024 respecto a la versión anterior: de +0.54 pp a +0.22 pp frente al baseline. Aun así, el baseline conserva ventaja en 2024, por lo que no puede afirmarse que el modelo sea universalmente superior.

No existe MAE 2027: el MAE requiere comparar con participación real y esa observación todavía no existe.

## Decisión

La proyección queda aprobada como artefacto experimental interno para análisis, escenarios y revisión territorial. No está aprobada para publicación como pronóstico oficial porque:

- usa geografía 2024, no un marco certificado 2027;
- los linajes disponibles terminan en 2022;
- los intervalos A/B dependen de un solo análogo intermedio fuera de tiempo, 2021;
- el modelo corregido fue peor que el baseline en el fold 2024.

La decisión y la especificación exacta están en `artifacts/forecast_2027_decision.json` y `artifacts/forecast_2027_model_registry.json`.
