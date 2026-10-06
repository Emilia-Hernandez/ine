# Método de incertidumbre y robustez espacial

Actualizado: 2026-10-06.

## Alcance

Esta fase evalúa el candidato `hist_gradient_boosting_electoral` aprobado en la fase anterior. No vuelve a seleccionar el modelo ni produce todavía un pronóstico 2027. Responde dos preguntas distintas:

1. si los errores observados antes de una elección permiten construir intervalos con cobertura útil en una elección posterior;
2. si el modelo conserva desempeño cuando se eliminan del entrenamiento entidades federativas completas.

La configuración congelada vive en `configs/uncertainty.yaml` y la implementación reutilizable en `src/radar27/modeling/uncertainty.py`.

## Intervalos conformales

Para cada unidad se usa el score de no conformidad `abs(prediction - actual)`. El radio es el cuantil conformal finito de rango `ceil((n + 1) * (1 - alpha))`, con `alpha=0.10`. Los límites se recortan a `[0, 1]`.

La calibración es móvil y sólo admite predicciones fuera de tiempo cuyo `target_year` sea estrictamente anterior al target evaluado:

- 2021 se calibra sólo con residuos 2018;
- 2024 se calibra con residuos 2018 y 2021.

Se calculan cuantiles separados para clases territoriales A/B cuando el estrato tiene al menos 500 unidades; de lo contrario se registra y aplica el cuantil global. La entidad, el tamaño de sección y el decil de riesgo se usan únicamente para diagnosticar cobertura, no para adaptar el intervalo con información del target.

Se reportan cobertura y anchura sin ponderar y ponderadas por registros identificados, globalmente y por entidad, clase territorial, tamaño y decil de riesgo.

## Validación espacial

Las 32 entidades se ordenan por ID y se reparten de forma determinista en cinco grupos. Para cada target 2018, 2021 y 2024 se realizan cinco reentrenamientos:

- el entrenamiento usa sólo targets anteriores;
- se eliminan todas las filas históricas de las entidades del grupo retenido;
- la evaluación usa exclusivamente el target de esas entidades;
- preprocesamiento, hiperparámetros y corrección residual son idénticos al candidato aprobado.

La comparación temporal ordinaria y la espacial se calcula sobre las mismas unidades. Esta prueba mide transferencia a territorios no vistos; no prescribe excluir historia estatal al entrenar el futuro modelo operacional.

## Controles de fuga

- `max_calibration_target_year < target_year` en todos los intervalos;
- `max_training_target_year < target_year` en todas las predicciones espaciales;
- la entidad de cada fila evaluada pertenece al grupo registrado como retenido;
- una sola predicción por unidad y target;
- predicciones e intervalos limitados a `[0, 1]`.

## Límites

- Sólo dos targets pueden evaluarse con residuos estrictamente anteriores.
- El fold 2018 ya intervino en la contracción residual del modelo; la cobertura 2021 es temporalmente honesta, pero no constituye un test totalmente intacto de selección.
- Dependencia espacial y cambios nacionales reducen la plausibilidad de intercambiabilidad conformal.
- La evidencia AMGE 2024 continúa parcial después de 2022.
