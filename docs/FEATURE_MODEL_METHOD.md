# Método del feature mart y modelos temporales

Actualizado: 2026-10-05. Implementación principal: `src/radar27/modeling/feature_models.py`.

## Unidad y target

La unidad de modelado es una sección clase A o un componente oficial AMGE clase B. El target sigue siendo la participación oficial `SV/(SV+NV)`. Las clases C/D no reciben historia sintética; para cobertura operativa conservan la jerarquía documentada en `MODELING_CONTRACT_BASELINE.md`.

## Construcción de variables electorales

Los 54,872,712 registros originales se agregan primero por sección y año. Nunca se promedian tasas publicadas. Se suman `LN`, `SV` y `NV` para:

- total, mujeres y hombres;
- edades 18–29, 30–44, 45–64 y 65 o más.

Después de la agregación se calculan participación, cobertura identificada, composición de lista nominal y participación por grupo. Para cada target se generan rezagos genéricos, media, desviación, tendencia, cambios recientes y crecimiento de lista nominal usando únicamente elecciones con `election_year < target_year`.

El mart contiene 243,108 unidades-fold. Cada fila conserva unidad, clase, entidad, años de las fuentes, outcome, pesos y banderas de disponibilidad.

## Entrenamiento temporal

| Evaluación | Targets usados para entrenar |
|---:|---|
| 2018 | 2015 |
| 2021 | 2015, 2018 |
| 2024 | 2015, 2018, 2021 |

Imputación, escalamiento y categorías se ajustan exclusivamente con las filas de entrenamiento. Ridge predice directamente el target. El boosting aprobado aprende una corrección residual sobre el baseline de la elección previa de la misma familia:

`predicción = baseline + 0.25 × corrección_estimada`

El factor 0.25 se escogió conservadoramente usando el fold 2018, anterior al gate principal 2021. Cuando el baseline seccional/componente no existe, el mismo modelo produce una predicción directa; esa procedencia queda reflejada en la ganancia de cobertura. Todas las predicciones se limitan al intervalo `[0,1]` y se registra cuántas fueron recortadas.

## ECEG 2020

El ZIP oficial de INEGI queda congelado por URL, tamaño y SHA-256 en `configs/inegi_eceg.yaml` y `data/manifests/eceg_source_manifest.csv`. Contiene 68,806 secciones. Se seleccionaron 14 variables fuente para producir nueve razones interpretables de población, edad, educación, actividad económica, discapacidad, lengua indígena e internet.

La ficha y los metadatos declaran `modified: 2021-08-18`, posterior a la elección del 6 de junio de 2021. Por tanto:

- ECEG está prohibido en los backtests estrictos 2015, 2018 y 2021;
- sólo se prueba como información disponible al origen del pronóstico 2024;
- podrá considerarse para 2027, conservando explícitamente que representa una fotografía censal 2020;
- no se usa como crosswalk territorial.

## Selección

El candidato sólo se aprueba si:

1. mejora el MAE ponderado del fold principal 2021;
2. iguala al menos la cobertura A+B congelada;
3. ningún otro fold empeora más de 0.005 de MAE ponderado, equivalentes a 0.5 puntos porcentuales.

La importancia por permutación usa una muestra determinista máxima de 5,000 unidades y es descriptiva, no causal.
