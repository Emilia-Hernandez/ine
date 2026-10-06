# Resultados del feature mart y modelos

Actualizado: 2026-10-05. Gate principal: 2015/2018 → 2021. Métrica primaria: MAE ponderado por `SV+NV`.

## Decisión

Se aprueba `hist_gradient_boosting_electoral` para la siguiente fase, todavía como candidato de desarrollo y no como pronóstico final 2027.

| Modelo 2021 | Cobertura | MAE ponderado | Sesgo | Dentro de ±5 pp |
|---|---:|---:|---:|---:|
| Baseline A+B | 93.77% | 9.38 pp | −5.71 pp | 31.27% |
| Boosting electoral residual | **96.10%** | **8.97 pp** | −5.01 pp | **32.24%** |
| Ridge electoral | 96.10% | 11.29 pp | −6.91 pp | 25.15% |

El boosting reduce el error ponderado en 0.42 pp, una mejora relativa aproximada de 4.45%, y representa 1,565 secciones evaluables adicionales. El resultado sigue mostrando un error alto y sesgo negativo: el modelo mejora el baseline, pero todavía no debe venderse como una estimación precisa de 2027.

## Robustez

| Target | Baseline A+B | Boosting electoral | Diferencia | Gate ≤ 0.50 pp |
|---:|---:|---:|---:|---|
| 2018 | 4.39 pp | 4.84 pp | +0.46 pp | pasa; calibración |
| 2021 | 9.38 pp | **8.97 pp** | −0.42 pp | principal |
| 2024 | 4.42 pp | 4.69 pp | +0.26 pp | pasa |

La contracción residual evita el deterioro severo observado con una predicción directa. El fold 2018 sirvió para escoger conservadoramente la contracción y no es una validación intacta; 2024 funciona como robustez posterior, aunque con cartografía parcial. El modelo gana en el análogo principal y permanece dentro del límite documentado.

## Aporte de ECEG

En 2024, añadir ECEG reduce el MAE ponderado del boosting de 4.69 a 4.65 pp, una mejora de apenas 0.03 pp. Ambos siguen por encima del baseline A+B de 4.42 pp. ECEG se conserva como señal secundaria para experimentación 2027, pero esta prueba no justifica promoverlo por sí solo.

## Variables con mayor importancia descriptiva en 2021

Las primeras señales por permutación son:

1. diferencia entre participación de la elección de la misma familia y la elección inmediatamente anterior;
2. cambio de participación entre los dos rezagos más recientes;
3. participación del segundo rezago;
4. volatilidad histórica;
5. tendencia histórica anual.

Las variables de sexo y edad aportan menos al ajuste residual agregado. La importancia no implica causalidad.

## Límites

- Sólo existen seis elecciones y tres folds entrenables para modelos supervisados.
- 2018 tiene un único target previo para entrenamiento.
- El fold 2024 conserva evidencia territorial parcial porque AMGE termina en 2022.
- El shift nacional entre elecciones continúa dominando parte del error.
- La fase posterior construyó intervalos predictivos, pero éstos no alcanzan la cobertura requerida en 2021; no existe todavía un pronóstico 2027. Véase `docs/UNCERTAINTY_SPATIAL_RESULTS.md`.

Ejecución reproducible de referencia: `artifacts/runs/20261006T032315Z-feature-model-evaluation` (`success`). La decisión máquina-legible está en `artifacts/model_decision.json`; métricas y predicciones están en `artifacts/tables/model_backtest_metrics.csv` y `artifacts/tables/model_backtest_predictions.parquet`.
