# Resultados de la evaluación territorial

Actualizado: 2026-10-05. Target: participación oficial. Predictor común: última elección de la misma familia.

## Resultado principal: 2015 → 2021

| Escenario | Cobertura secciones evaluables | Cobertura LN evaluable | MAE | MAE ponderado por SV+NV | Sesgo | Dentro de ±5 pp |
|---|---:|---:|---:|---:|---:|---:|
| Sólo A | 85.03% | 85.52% | 9.96 pp | 9.46 pp | −5.71 pp | 31.29% |
| A + linajes B | 93.77% | 92.24% | 9.97 pp | 9.38 pp | −5.71 pp | 31.27% |
| Respaldo jerárquico | 100.00% | 100.00% | 9.98 pp | 9.47 pp | −5.54 pp | 31.11% |

Los linajes oficiales agregan 5,862 secciones evaluables frente al panel A y reducen ligeramente el error ponderado. Se cumple la regla preespecificada para adoptar A+B como muestra principal.

El sesgo negativo significa `predicción − real < 0`: usar la participación de 2015 subestima en promedio la de 2021. No debe interpretarse como falla cartográfica; demuestra que un rezago simple no modela cambios nacionales entre elecciones intermedias.

## Robustez por fold

MAE ponderado por registros identificados:

| Target | Sólo A | A+B | Jerárquico | Estado de evidencia |
|---:|---:|---:|---:|---|
| 2015 | 6.91 pp | 6.81 pp | 6.95 pp | AMGE completo para el corte |
| 2018 | 4.41 pp | 4.39 pp | 4.53 pp | AMGE completo para el corte |
| 2021 | 9.46 pp | 9.38 pp | 9.47 pp | análogo principal 2027 |
| 2024 | 4.50 pp | 4.42 pp | 4.79 pp | parcial; AMGE termina en 2022 |

A+B mejora ligeramente el MAE ponderado en los cuatro folds y eleva cobertura de manera sustancial. El respaldo jerárquico sacrifica algo de precisión para cubrir todos los targets definidos.

## Procedencia del respaldo 2021

| Fuente | Secciones predichas |
|---|---:|
| misma sección 2015 | 65,582 |
| componente AMGE | 1,164 |
| municipio | 1,984 |
| entidad | 82 |
| nacional | 0 |

De las 68,812 secciones observadas en 2021, 67,119 tienen target oficial definido; las restantes tienen `SV+NV=0` y no pueden aportar error, aunque reciben predicción.

## Error jerárquico 2021 por clase

| Clase | Secciones evaluables | MAE |
|---|---:|---:|
| A | 58,561 | 10.05 pp |
| B | 5,769 | 9.39 pp |
| C | 46 | 9.59 pp |
| D | 2,743 | 9.80 pp |

Las cifras por clase se calculan únicamente donde el target está definido. La clase sigue siendo relevante como incertidumbre metodológica aunque el error medio de este baseline no sea peor en todos los estratos.

## Decisión

- Entrenamiento/evaluación principal posterior: clases A+B.
- Cobertura nacional operativa: respaldo jerárquico con `prediction_source` y clase visibles.
- Casos C/D: no recibirán historia sintética; se reportarán con mayor incertidumbre.
- El baseline de último valor no es suficiente como modelo final: en 2021 su error ponderado ronda 9.4 pp y sólo 31% queda dentro de ±5 pp.
- Siguiente fase: construir features históricas y demográficas auditadas, manteniendo estos mismos folds y comparando contra este baseline.

Ejecución reproducible de referencia: `artifacts/runs/20261005T225638Z-public-lineage-evaluation` (`success`). Artefactos: `backtest_metrics.csv`, `backtest_predictions.parquet`, `backtest_errors_by_class.csv`, `fallback_source_counts.csv` y `public_lineage_evaluation.html`.
