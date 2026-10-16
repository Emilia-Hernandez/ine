# Validación metodológica y de modelos

## Dictamen

La solución demuestra capacidad predictiva útil en el fold intermedio 2021, pero no evidencia generalización estable entre familias electorales. La especificación final se seleccionó usando repetidamente los mismos tres folds y no conserva una elección completamente intacta. Las métricas deben presentarse como validación de desarrollo.

## Predicción de participación

### Comparación pareada independiente

Todas las cifras siguientes usan exactamente las mismas unidades y pesos para cada modelo dentro de cada año.

| Año | Unidades | Secciones | A: cambio completo | B: residual nacional | C: repositorio | D: persistencia |
|---:|---:|---:|---:|---:|---:|---:|
| 2018 | 58,624 | 62,899 | 9.063% | 9.063% | 4.467% | **4.386%** |
| 2021 | 58,069 | 62,936 | 6.956% | **6.897%** | 7.329% | 9.385% |
| 2024 | 56,007 | 61,329 | 4.604% | 5.011% | 4.487% | **4.421%** |

Los modelos A y B aplican el residual sin la contracción 0.25, por lo que su falla en 2018 no contradice que la regularización sea útil. Sí muestra que la elección del factor domina la estabilidad.

### Diferencia C frente a persistencia

| Año | Δ MAE ponderado | IC95% bootstrap por entidad | Entidades donde C mejora |
|---:|---:|---:|---:|
| 2018 | +0.0817 pp | [−0.4321, +0.6639] pp | 14/32 |
| 2021 | −2.0555 pp | [−3.1461, −0.9098] pp | 22/32 |
| 2024 | +0.0656 pp | [−0.3047, +0.4471] pp | 15/32 |

Sólo 2021 muestra una mejora amplia y estadísticamente distinguible de cero bajo este bootstrap. Las presidenciales son equivalentes a persistencia dentro de la incertidumbre. El sesgo nacional ponderado de C es +1.214 pp, −1.279 pp y +2.881 pp en 2018, 2021 y 2024.

### Muestras documentadas versus muestras pareadas

Las tablas finales del proyecto no usan el mismo universo para modelo y baseline:

| Año | Modelo reportado | Baseline comparable | Diferencia de unidades | Diferencia de secciones |
|---:|---:|---:|---:|---:|
| 2018 | 58,695 | 58,624 | 71 | 71 |
| 2021 | 59,582 | 58,069 | 1,513 | 1,565 |
| 2024 | 57,977 | 56,007 | 1,970 | 1,971 |

Toda comparación final debe recalcularse sobre intersecciones idénticas o separar explícitamente cobertura y precisión.

## Ajuste nacional y descomposición

El target del árbol es `actual − participación previa de la misma familia`. La salida suma `baseline + 0.25×residual + shift + corrección estatal`. Como el residual no se centra, la corrección aprendida puede retener componente agregado.

| Cantidad 2015→2021 | Valor |
|---|---:|
| Media ponderada A/B usada por el repositorio | +5.21497 pp |
| Media simple A/B | +5.70804 pp |
| Razón de sumas nacional | +4.76442 pp |

En la predicción 2027, la media ponderada del residual aprendido es +1.3732 pp; después de la contracción aporta +0.3433 pp. El shift externo aporta +5.2150 pp. No existe ortogonalidad ni una identificación causal del solapamiento.

La salida nacional ponderada cambia de 57.3067% a 56.8565% al sustituir el shift por la razón de sumas. El impacto es −0.4501 pp y 70,655 secciones cambian antes del redondeo.

## Clasificador de riesgo

### Orientación

La clase positiva es correctamente `participation_same_type − actual >= 0.02`. La columna `predict_proba[:,1]` corresponde a dicha clase. Se descarta una inversión mecánica de clase.

### Transferencia 2024

| Modelo | ROC-AUC | PR-AUC | Brier | Log loss |
|---|---:|---:|---:|---:|
| Constante, prevalencia entrenamiento | 0.500 | 0.507 | 0.302 | 0.808 |
| Baseline histórico de una variable | **0.605** | **0.619** | **0.268** | **0.732** |
| Logístico simple | 0.456 | 0.478 | 0.293 | 0.797 |
| Actual calibrado | 0.423 | 0.451 | 0.327 | 0.873 |
| Score actual invertido, diagnóstico | 0.577 | 0.548 | 0.289 | 0.788 |

El modelo actual queda por debajo del azar en ranking y peor que una constante en Brier. Con umbral 0.5, sensibilidad ponderada=4.11%, especificidad=92.09% y accuracy=47.52%. El IC95% por entidad de AUC es [0.340, 0.522], con 94% de réplicas bajo 0.5. El punto es adverso, aunque el intervalo todavía cruza 0.5.

La calibración es también inversa en los extremos: el primer decil predice 19.9% y observa 55.0%; el décimo predice 54.1% y observa 32.4%. La explicación más prudente es cambio de régimen y especificación insuficiente.

En 2021 el modelo calibrado obtiene AUC=0.7473 y Brier=0.1702, pero el mismo fold intervino en selección y calibración. No es validación externa.

## Intervalos e incertidumbre

Las coberturas 90.41% y 87.08% citadas en documentos pertenecen a una etapa previa de intervalos adaptativos, no a un backtest de la especificación final completa. La salida final usa reglas distintas: adaptación estatal en A/B y componente jerárquico/nacional para C/D, mientras el punto final incluye corrección estatal. No se encontró una prueba de cobertura del sistema entregado.

Las 20 réplicas bootstrap del pipeline son insuficientes para caracterizar incertidumbre de ciclo y sólo miden estabilidad limitada de modelo/pesos. No deben interpretarse como intervalo predictivo electoral integral.

## Selección y sobreajuste de validación

- 2018 participa en la elección del factor de contracción 0.25.
- 2021 se usa para grupos de variables, algoritmo, corrección estatal y calibración.
- 2024 participa en gates de robustez y evaluación del clasificador.
- No hay un fold intacto después de tomar esas decisiones.
- No se encontró una tabla completa de candidatos para justificar 0.25.

La recomendación es congelar código/configuración antes de observar la siguiente elección y registrar un protocolo ex ante. Con la evidencia actual, la solución es experimental.

## Segmentación y perfiles

Los clusters auxiliares tienen silhouette≈0.170 y ARI≈0.932. La estabilidad algorítmica es buena, pero la separación sustantiva es débil. Cinco de seis arquetipos no muestran consistencia histórica; sólo la brecha masculina conserva señal. Deben presentarse como descriptores, no como tipos causales ni segmentos de intervención demostrados.

## Decisiones recomendadas

1. Centrar el target por un shift definido ex ante y entrenar sólo el residual centrado.
2. Mantener la contracción, pero elegirla mediante protocolo anidado y publicar todos los candidatos.
3. Comparar contra persistencia en muestra pareada y reportar IC por entidad.
4. Retirar el score presidencial; para 2027 etiquetarlo experimental y sin calibración externa.
5. No emitir estimación puntual 2030 hasta actualizar geografía y validar una elección presidencial nueva.
6. Recalibrar cobertura para la especificación final, con bootstrap suficiente y agrupación geográfica.

## Figuras reproducibles

- `figures/model_comparison.svg`: MAE ponderado de A–D por año.
- `figures/classifier_2024_benchmarks.svg`: AUC y Brier de benchmarks 2024.
- `figures/classifier_2024_calibration.svg`: probabilidad predicha frente a frecuencia observada por decil.

Se regeneran con `audit/AUDIT_TESTS/make_figures.py` a partir de los CSV de `audit/results/`.
