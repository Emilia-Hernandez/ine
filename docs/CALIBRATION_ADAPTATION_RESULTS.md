# Resultados de adaptación de calibración

Actualizado: 2026-10-06.

## Corrección nacional

| Target | Fuente comparable | Corrección | MAE original | MAE corregido | Sesgo original | Sesgo corregido |
|---:|---:|---:|---:|---:|---:|---:|
| 2021 | 2015 | +3.01 pp | 8.97 pp | **8.31 pp** | −4.60 pp | **−1.59 pp** |
| 2024 | 2018 | +0.66 pp | 4.69 pp | 4.96 pp | +2.44 pp | +3.10 pp |

En el fold principal, el MAE ponderado mejora 0.66 pp, equivalente a 7.31%, y el sesgo absoluto baja 65.37%. El costo en 2024 es 0.27 pp de MAE, dentro del límite preespecificado de 0.5 pp.

El cambio comparable observado en 2021 produce un parámetro experimental de **+5.21 pp para 2027**. Es una corrección previa al modelo, no una proyección terminada.

## Intervalos

| Método | Target | Cobertura | Cobertura ponderada | Anchura media |
|---|---:|---:|---:|---:|
| Móvil original | 2021 | 62.35% | 66.26% | 20.32 pp |
| Móvil original | 2024 | 97.10% | 98.01% | 31.80 pp |
| Móvil, centro corregido | 2021 | 65.67% | 68.84% | 20.31 pp |
| Móvil, centro corregido | 2024 | 95.84% | 97.08% | 29.60 pp |
| **Análogo familiar, centro corregido** | **2021** | **90.41%** | **91.95%** | 36.46 pp |
| **Análogo familiar, centro corregido** | **2024** | **87.08%** | **89.46%** | 20.32 pp |

La corrección del centro por sí sola no arregla la cobertura: el radio calibrado con elecciones de otra familia sigue siendo inadecuado. Cambiar también la referencia de calibración recupera 28.06 pp de cobertura en 2021. En 2024 reduce la sobrecobertura y estrecha el intervalo 36.10%, aunque queda 2.92 pp por debajo del nominal sin ponderar.

## Decisión

- La corrección nacional pasa los gates de desempeño principal y robustez.
- El análogo familiar supera el piso diagnóstico de 85% en 2021 y 2024.
- Se habilita una primera canalización **experimental** 2027.
- Los intervalos todavía **no son publicables como garantía de 90%**, porque 2024 alcanza 87.08%.

La decisión máquina-legible está en `artifacts/calibration_adaptation_decision.json`.
