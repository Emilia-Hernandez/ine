# Método de adaptación al cambio nacional

Actualizado: 2026-10-06.

## Problema

El intervalo conformal móvil del notebook 06 usó errores 2018 para calibrar 2021. Aunque el procedimiento no tenía fuga, la hipótesis de estabilidad temporal falló: 2018 fue una elección presidencial con errores relativamente pequeños, mientras que 2021 fue intermedia y tuvo un desplazamiento nacional positivo que el modelo subestimó. El radio de 10.19 pp resultó demasiado estrecho y cubrió sólo 62.35% de las unidades.

La solución no puede usar el resultado 2021 para corregir su propia predicción. Esta fase utiliza exclusivamente información del ciclo anterior de la misma familia electoral.

## Corrección del centro

Para un target `t`, se estima:

```text
national_shift(t) = weighted_mean(actual(t-6) - same_family_lag(t-6))
corrected_prediction(t) = clip(model_prediction(t) + national_shift(t), 0, 1)
```

Los pesos son registros identificados del año fuente. Por tanto:

- 2021 usa el cambio nacional 2009→2015, observado en 2015;
- 2024 usa el cambio nacional 2012→2018, observado en 2018;
- el parámetro experimental 2027 usa el cambio nacional 2015→2021, conocido desde 2021.

No se aprende un factor con 2021 o 2024. La regla transporta una vez el cambio de la familia comparable previa.

## Intervalos comparados

Se conservan tres candidatos:

1. `rolling_conformal_original_center`: método del notebook 06;
2. `rolling_conformal_shift_corrected`: mismo esquema móvil, recalculado sobre centros corregidos;
3. `family_analogue_shift_corrected`: centro corregido y radio obtenido de la última elección de la misma familia.

Para 2021 no existe predicción fuera de tiempo del boosting en 2015 porque falta historia entrenable. Se usa explícitamente el error del baseline de mismo tipo como arranque frío. Para 2024 se usan las predicciones fuera de tiempo del candidato en 2018.

El tercer método usa el cuantil finito al 90% y estratos A/B con mínimo de 500 unidades. Es un intervalo empírico de análogo familiar: debido al arranque frío 2015 y a la dependencia temporal, no se presenta como una garantía conformal formal.

## Gates

- mejorar MAE ponderado 2021;
- no empeorar 2024 en más de 0.5 pp;
- cobertura global mínima de 85% en todos los targets para habilitar experimentación 2027;
- cobertura nominal de 90% en todos los targets para considerar los intervalos publicables.

Todas las fuentes de corrección y calibración deben cumplir `source_target_year < target_year`.
