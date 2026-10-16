# Validación de la predicción municipal 2027

## Decisión

Se seleccionó **A_nacional_actual** mediante la regla congelada: mejorar recall y F1 de caídas en 2021, no reducir balanced accuracy y limitar el deterioro de MAE a 0.5 pp. Entre B y C se prefiere C cuando queda dentro de tolerancias preespecificadas de F1 (0.002) y MAE (0.002). Motivo: `municipal_models_failed_prespecified_2021_joint_gate`.

## Backtest 2021

| Modelo | MAE | Precision | Recall | F1 | Balanced accuracy | Unidades |
|---|---:|---:|---:|---:|---:|---:|
| A_nacional_actual | 0.0861 | 0.9014 | 0.0038 | 0.0076 | 0.5018 | 58,069 |
| B_municipal | 0.1301 | 0.1572 | 0.1666 | 0.1618 | 0.4003 | 58,069 |
| C_municipal_jerarquico | 0.1287 | 0.1571 | 0.1653 | 0.1611 | 0.4010 | 58,069 |

Las métricas 2018 y 2024 se conservan como contexto secundario. Todas las comparaciones son pareadas y usan exactamente el umbral de −1 pp.

## Formulación y temporalidad

Modelo A conserva el componente nacional anterior. B usa la trayectoria municipal local. C usa `w_m × cambio municipal + (1-w_m) × referencia estatal`, donde `w_m = cobertura electoral × (n-1)/n` y `n` es el número de unidades comparables del municipio. La regla penaliza falta de cobertura y baja precisión leave-one-out sin parámetros optimizados. El residual objetivo es el cambio seccional menos el componente municipal realizado, excluyendo la unidad de su referencia municipal; se centra dentro de municipio y fold. Para 2021 el offset usa sólo 2009→2015. Para 2027 usa 2009, 2015 y 2021.

No se suma ajuste nacional o estatal después del componente municipal. Las cuatro variables vecinales proceden de grafos temporales ya validados y sólo usan elecciones anteriores al target.

## Limitaciones

2021 ya participó en el desarrollo y no es validación externa intacta. Los componentes de linaje pueden resumir cambios de composición. 2018 carece de una transición presidencial previa en los datos y B/C usan offset cero documentado. La geografía 2027 no está certificada.
