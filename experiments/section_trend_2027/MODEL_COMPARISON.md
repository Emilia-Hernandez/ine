# Comparación de modelos — tendencia seccional 2027

## Diseño fijado antes de observar resultados

- Backtest único: predicción de 2021 usando solamente 2009 y 2015.
- Evento de caída: cambio menor o igual a -1 punto porcentual, sin optimizar el umbral.
- A: modelo nacional corregido vigente, residual centrado y contracción 0.25; se reutilizó su predicción guardada, sin reentrenamiento.
- B: `P2015 + (P2015 - P2009)`.
- C: 50% del cambio seccional y 50% del cambio municipal histórico calculado sin la propia sección. El peso 0.50 es fijo, no fue seleccionado por desempeño. Si un municipio no tiene otra sección comparable se usa la entidad sin la propia sección.
- D: persistencia (`P2015`).
- B y C se recortan al dominio [0, 1] para evaluar tasas válidas; los valores sin recorte y la bandera de recorte se conservan en el CSV.

## Muestra estrictamente pareada

El universo objetivo 2021 contiene 68,812 secciones observadas; 59,963 son clase A. El modelo A dispone de 57,074 predicciones seccionales. La intersección con historia completa y referencias válidas produce **56,302 secciones** (81.82% del universo objetivo). Todos los modelos se evalúan sobre esas mismas filas. Se observaron 16,340 caídas materiales.

## Resultados 2021

| Modelo | Precision | Recall | F1 | Bal. acc. | MAE | RMSE | Bias | VP | FP | FN | VN | Caídas pred. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A_modelo_avanzado_actual | 0.8955 | 0.0037 | 0.0073 | 0.5017 | 8.59% | 11.01% | -2.62% | 60 | 7 | 16,280 | 39,955 | 67 |
| B_tendencia_seccional_simple | 0.1464 | 0.1477 | 0.1471 | 0.3978 | 13.62% | 17.49% | -1.84% | 2,414 | 14,070 | 13,926 | 25,892 | 16,484 |
| C_tendencia_seccional_regularizada | 0.1386 | 0.1370 | 0.1378 | 0.3944 | 13.19% | 16.84% | -2.02% | 2,239 | 13,915 | 14,101 | 26,047 | 16,154 |
| D_persistencia | 0.0000 | 0.0000 | 0.0000 | 0.5000 | 9.94% | 12.83% | -5.71% | 0 | 0 | 16,340 | 39,962 | 0 |

Las métricas continuas están expresadas como proporciones; por ejemplo, MAE 13.62% equivale a 13.62 puntos porcentuales.

## Diferencias clave

- B frente a persistencia: Δ precision +0.1464, Δ recall +0.1477, Δ F1 +0.1471, Δ MAE +3.68 pp.
- C frente a persistencia: Δ precision +0.1386, Δ recall +0.1370, Δ F1 +0.1378, Δ MAE +3.25 pp.
- B frente a A: Δ precision -0.7491, Δ recall +0.1441, Δ F1 +0.1398, Δ MAE +5.03 pp.
- C frente a A: Δ precision -0.7569, Δ recall +0.1334, Δ F1 +0.1305, Δ MAE +4.60 pp.

## Alcance de la evidencia

Este backtest valida una extrapolación basada en **una** transición (2009→2015); no valida exactamente la regla 2027, que promedia dos transiciones. No se usó ningún valor 2021 como feature de B, C o D. La predicción A se toma del artefacto canónico previo.
