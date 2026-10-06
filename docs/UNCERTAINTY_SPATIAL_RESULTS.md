# Resultados de incertidumbre y robustez espacial

Actualizado: 2026-10-06. Cobertura nominal: 90%.

> Seguimiento: el notebook 07 añadió una corrección nacional y un intervalo de análogo familiar. Esa fase habilita experimentación interna 2027, aunque mantiene bloqueada la publicación de una garantía nominal. Véase `docs/CALIBRATION_ADAPTATION_RESULTS.md`.

## Intervalos conformales

| Target | Años de calibración | Cobertura | Cobertura ponderada | Anchura media |
|---:|---|---:|---:|---:|
| 2021 | 2018 | 62.35% | 66.26% | 20.32 pp |
| 2024 | 2018, 2021 | 97.10% | 98.01% | 31.80 pp |

La calibración 2018 no anticipa el desplazamiento de participación de 2021: falla el piso diagnóstico preespecificado de 85%. Incorporar residuos 2021 produce intervalos conservadores para 2024. Esta asimetría indica cambio temporal fuerte, no un error de implementación, y prohíbe presentar todavía intervalos 2027 como calibrados.

En 2021 la cobertura es 62.42% para clase A y 58.57% para B. La heterogeneidad por entidad es sustancial; el mínimo observado es 2.82% en la entidad 29. En 2024 las coberturas de A y B suben a 97.11% y 96.66%, respectivamente.

## Retención espacial de entidades

| Target | MAE ponderado temporal | MAE ponderado con entidades retenidas | Diferencia |
|---:|---:|---:|---:|
| 2018 | 4.84 pp | 4.78 pp | −0.06 pp |
| 2021 | 8.97 pp | 8.78 pp | −0.18 pp |
| 2024 | 4.69 pp | 4.45 pp | −0.23 pp |

No aparece deterioro espacial agregado. El resultado no implica que todas las entidades sean equivalentes: en 2018 la entidad 16 empeora 2.05 pp y en 2024 la entidad 29 empeora 1.01 pp. El promedio favorable sugiere que retirar el indicador categórico de la entidad puede reducir sobreajuste en algunos grupos; debe tratarse como una hipótesis para la siguiente iteración, no como causalidad.

## Decisión

- El diagnóstico espacial agregado pasa el máximo de deterioro configurado.
- La calibración conformal falla por cobertura insuficiente en 2021.
- El candidato predictivo sigue aprobado para desarrollo, pero **no está listo para una proyección 2027 con intervalos publicables**.
- El siguiente experimento debe modelar el cambio nacional entre tipos de elección y comparar intervalos adaptativos preespecificados, sin usar el target para recalibrarse.

La decisión máquina-legible está en `artifacts/uncertainty_decision.json`. Los resultados detallados están en `conformal_coverage_metrics.csv`, `conformal_calibration_summary.csv`, `spatial_robustness_metrics.csv` y sus Parquet de predicciones.
