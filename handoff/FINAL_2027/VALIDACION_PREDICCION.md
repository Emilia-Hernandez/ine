# Validación de la predicción 2027

## Especificación elegida

La proyección central es el HistGradientBoosting residual corregido, centrado por fold y contraído 0.25. El baseline de persistencia se conserva sólo como comparación. La alternativa con peso doble para caídas no superó la regla conjunta y no fue promovida (`weighted_alternative_failed_joint_gate;retain_corrected_advanced_model`).

La tasa se calcula como `SV/(SV+NV)`. La predicción separa: referencia 2021 + componente nacional + 0.25 × corrección territorial centrada. No se suma corrección estatal adicional.

## Componente nacional

| Escenario | Componente 2027 | Regla | Seleccionado |
|---|---:|---|---|
| A_cero | 0.000000 | sin cambio nacional | False |
| B_ultimo_cambio | 0.047644 | cambio nacional intermedio más reciente | False |
| C_media_historica | 0.038886 | media aritmética preespecificada de los dos cambios intermedios disponibles | True |

Se seleccionó 3.8886 pp: media aritmética de 2009→2015 y 2015→2021. Es una regla conservadora explícita, no optimizada contra 2027. Para el backtest 2021 sólo se usó 2009→2015, disponible antes de la elección.

## Resultados

La proyección nacional ponderada es 55.6623%; persistencia es 51.7738%. En 2021 el modelo avanzado obtuvo precision 0.9014, recall 0.0038, F1 0.0076, balanced accuracy 0.5018 y MAE 8.6110%. Las métricas completas de 2018, 2021 y 2024 están en `METRICAS_DETECCION_CAIDAS.csv`.

## Limitaciones

2021 es la principal referencia de desarrollo, no una validación externa intacta. Sólo hay dos transiciones intermedias observadas. 2018 y 2024 pertenecen a la familia presidencial y se reportan como contexto de generalización. La proyección 2027 depende de calendario conocido a 2026-07-30 y de geografía 2024 aún no certificada para 2027.
