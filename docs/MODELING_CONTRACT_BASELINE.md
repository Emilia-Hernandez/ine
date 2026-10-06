# Contrato de evaluación geográfica y baseline

Actualizado: 2026-10-05. Implementación: `src/radar27/modeling/lineage_evaluation.py`.

## Propósito

Comparar estrategias de continuidad territorial manteniendo fijo un predictor simple. Esta fase evalúa la geografía y el mecanismo de cobertura; no selecciona todavía el modelo final para 2027.

## Target

Unidad de target: sección observada o componente oficial, según escenario.

`participation = SV / (SV + NV)`

Si `SV+NV=0`, el target no es evaluable. La sección puede recibir una predicción, pero no entra al cálculo del error.

## Folds congelados

| Feature | Target | Familia | Uso |
|---:|---:|---|---|
| 2009 | 2015 | intermedia | backtest histórico |
| 2012 | 2018 | presidencial | backtest histórico |
| 2015 | 2021 | intermedia | análogo principal de 2027 |
| 2018 | 2024 | presidencial | robustez; AMGE sólo llega a 2022 |

En todos los casos `feature_year < target_year`.

## Predictor

El predictor base es la participación de la elección anterior de la misma familia. Toda agregación usa razón de sumas, no promedio simple de tasas.

## Escenarios

1. **stable_only:** clase A, mismo código en la elección previa.
2. **stable_plus_lineage:** clase A más componentes B. Los componentes se evalúan como unidades agregadas.
3. **hierarchical_fallback:** todas las secciones con target definido; prioridad de predicción:
   - misma sección;
   - componente AMGE oficial;
   - municipio objetivo;
   - entidad objetivo;
   - nacional.

Cada predicción conserva `prediction_source`, `feature_year`, `target_year`, escenario y evidencia geográfica.

## Métricas

- MAE y RMSE no ponderados;
- sesgo `prediction - actual`;
- MAE/RMSE ponderados por registros identificados `SV+NV`;
- MAE ponderado por lista nominal;
- proporción dentro de ±5 puntos porcentuales;
- cobertura sobre secciones con target definido;
- cobertura de lista nominal evaluable.

## Variables

El registro completo está en `configs/features.yaml` y `artifacts/tables/variable_lineage.csv`. Cada fila declara descripción, columnas fuente, transformación, disponibilidad temporal, riesgo de fuga, política de faltantes e implementación.

## Variables prohibidas en esta evaluación

- participación de la elección objetivo como predictor;
- conteos de la elección objetivo para producir la predicción;
- eventos AMGE con año efectivo igual o posterior al target;
- pesos inventados para distribuir una sección origen;
- geometría o covariables no registradas en la receta.

## Decisión preespecificada

Adoptar A+B como muestra principal si aumenta cobertura frente a A sin empeorar el MAE ponderado del fold 2021. Usar el respaldo jerárquico para cobertura nacional y conservar clase/fuente como señales explícitas de incertidumbre.
