# Auditoría de las cinco observaciones críticas

## Archivos implicados

| Problema | Implementación y evidencia principal |
|---:|---|
| 1 | `calibration_adaptation.py`, `feature_enrichment.py`, `forecast_2027.py`, `national_shift_estimates.csv`, mart y predicciones finales |
| 2 | pipeline de riesgo, `turnout_decline_risk_backtest_predictions.parquet`, métricas y calibración |
| 3 | `section_risk_profiles_2027.parquet`, reglas A/B/C/D, cobertura ECEG y arquetipos |
| 4 | construcción de percentiles/prioridad y perfil final seccional |
| 5 | backtests tabulares, transferencia intermedia, adaptación estatal y reportes de evaluación |

Cada sección contrasta la hipótesis original con una prueba independiente; no se modificó el modelo de producción.

## 1 Ajuste nacional de 5.21 puntos

**Estado: FAIL — severidad alta.**

### Definición implementada

El árbol residual se entrena con:

`y_residual = participación observada − participación de la elección anterior de la misma familia`.

La predicción corriente usa:

`clip(baseline misma familia + 0.25 × residual aprendido + shift previo + corrección estatal, 0, 1)`.

Por tanto, el target del árbol es el cambio completo, no un residuo al que ya se haya descontado un efecto nacional.

### Cómo se obtuvo 5.21

`estimate_national_shift()` toma las unidades A/B con ambas tasas disponibles, calcula el cambio por unidad y promedia con pesos `target_identified_records` del año objetivo. Para 2015→2021 intervienen 58,069 unidades que representan 62,936 secciones y 82,478,886 registros identificados de 2021.

| Estimador 2015→2021 | Resultado |
|---|---:|
| Media ponderada A/B usada por el repositorio | +5.21497 pp |
| Media simple A/B | +5.70804 pp |
| Cambio nacional por razón de sumas, todo el universo | +4.76442 pp |

La etiqueta “cambio nacional” es incorrecta. La diferencia de 0.45055 pp proviene del universo comparable y de ponderar cambios seccionales con el denominador del año objetivo, no de restar dos agregados nacionales.

### ¿Hay doble conteo?

Hay **solapamiento matemático no controlado**, porque el residual aprendido contiene cualquier componente agregado presente en el cambio observado y después se añade otro desplazamiento. La media ponderada de la corrección aprendida para 2027 es +1.3732 pp sin contracción y +0.3433 pp después del factor 0.25. Luego se añaden +5.2150 pp. El modelo no impone que el componente aprendido sume cero, de modo que la afirmación documental de que ambos efectos están “separados” no está demostrada.

No es posible afirmar que exactamente 0.3433 pp correspondan al mismo fenómeno causal que el shift. Sí es inequívoco que la descomposición no es ortogonal y que añade un componente agregado aprendido distinto de cero encima del supuesto agregado.

### Experimento A–D sobre la misma muestra

MAE ponderado:

| Año | A cambio completo sin ajuste | B target residualizado por shift | C repositorio actual | D persistencia |
|---:|---:|---:|---:|---:|
| 2018 | 9.063% | 9.063% | 4.467% | 4.386% |
| 2021 | 6.956% | **6.897%** | 7.329% | 9.385% |
| 2024 | 4.604% | 5.011% | 4.487% | **4.421%** |

El modelo B mejora marginalmente a A en 2021 y empeora en 2024; A y B aplican el residual completo y por eso fallan severamente en 2018. Esto confirma la utilidad de regularizar, pero no justifica sumar un shift a un target no centrado. La formulación recomendada es entrenar el residual después de descontar un componente agregado definido ex ante y aplicar contracción sólo al residuo centrado.

### Impacto

Usar el cambio nacional por razón de sumas en la salida 2027 reduce el agregado de 57.3067% a 56.8565%. La diferencia afecta 70,655 secciones antes de redondeo. Se requiere recalcular pronóstico, magnitud y volumen.

## 2 Clasificador de riesgo 2024

**Estado: FAIL para transferencia presidencial; PASS para orientación de clase. Severidad alta.**

La clase positiva está correctamente codificada como `participation_same_type − actual >= 0.02`. `predict_proba[:,1]` es la probabilidad de esa clase. No se encontró una inversión de columnas.

| Modelo 2024 | ROC-AUC | PR-AUC | Brier | Log loss |
|---|---:|---:|---:|---:|
| Constante con prevalencia de entrenamiento | 0.500 | 0.507 | 0.302 | 0.808 |
| Constante con prevalencia de prueba, sólo diagnóstico | 0.500 | 0.507 | 0.250 | 0.693 |
| Baseline histórico de una variable | **0.605** | **0.619** | **0.268** | **0.732** |
| Logístico simple | 0.456 | 0.478 | 0.293 | 0.797 |
| Modelo actual calibrado | 0.423 | 0.451 | 0.327 | 0.873 |
| Score actual invertido, diagnóstico | 0.577 | 0.548 | 0.289 | 0.788 |

Con umbral 0.5, el modelo actual tiene sensibilidad ponderada 4.11%, especificidad 92.09% y accuracy ponderada 47.52%. La curva de calibración es adversa: el decil de menor probabilidad predice 19.9% y observa 55.0%; el decil de mayor probabilidad predice 54.1% y observa 32.4%.

El IC95% bootstrap por entidad de la AUC calibrada es [0.340, 0.522]. El punto está por debajo de azar, pero el intervalo incluye 0.5; no se demuestra inversión estadística al 5%. La inversión mejora, pero sigue por debajo del baseline histórico. El diagnóstico más compatible es cambio de régimen más especificación insuficiente, no un error mecánico de `predict_proba`.

Para 2027, 2021 es el único análogo intermedio, pero su Brier de 0.170 se eligió y calibró usando el mismo fold. La probabilidad 2027 debe presentarse como experimental, no calibrada externamente.

## 3 Diferencia de 38 secciones

**Estado: PASS con corrección documental menor.**

Los universos son:

- 65,095 secciones A/B con historia electoral comparable.
- 65,057 secciones A/B con descriptores ECEG completos agregados a la unidad.
- 38 secciones A, ninguna B, sin ECEG completo en la unidad; usan referencia ECEG estatal.
- 5,656 secciones C/D; 3,630 tienen coincidencia directa de clave ECEG 2020 y 2,026 usan referencia estatal.

El total reportado de 2,064 referencias estatales ECEG es `2,026 C/D + 38 A`. No hay duplicados y las 70,751 llaves concilian exactamente. La lista nominal de los 38 casos está en `results/eceg_38_section_reconciliation.csv`.

La hipótesis original es correcta sólo para ECEG. No debe describirse a esas 38 como carentes de toda información local: conservan conteos CCPC locales. Dos de ellas (`05:0153` y `25:1994`) también usan referencia estatal en al menos un factor de arquetipo.

Existe un riesgo adicional: las 3,630 coincidencias directas de clave ECEG para C/D no prueban equivalencia geométrica 2020–2024. Al ser C/D precisamente clases de historia corta o ambigua, deben etiquetarse como coincidencia de código no validada o excluirse de caracterizaciones locales hasta tener crosswalk.

## 4 Percentiles p80

**Estado: FAIL de interpretación, PASS de implementación. Severidad media.**

| Indicador | p80 del valor | Empates | Regla actual | Estricto `>` | Inclusivo `>=` | Top 20% con desempate |
|---|---:|---:|---:|---:|---:|---:|
| Riesgo | 0.4457185 | 3,867 | 15,631 (22.09%) | 11,764 (16.63%) | 15,631 (22.09%) | 14,151 (20.00%) |
| Volumen | 0 | 60,860 | 9,891 (13.98%) | 9,891 (13.98%) | 70,751 (100%) | 14,151 (20.00%) |

El 22.1% de riesgo proviene de incluir todo el empate creado por la calibración isotónica. El 14% de volumen es exactamente el conjunto con volumen positivo; 86.02% tiene cero porque el pronóstico no anticipa caída puntual. `rank(method="average") >= .8` actúa como una regla estricta frente al bloque de ceros.

Recomendación: conservar empates en riesgo e informar 22.09%, salvo que exista una capacidad operativa fija que justifique desempatar. Para volumen, renombrar la categoría a “caída puntual positiva” y no describirla como p80. Si se necesita 20% exacto, preespecificar un segundo criterio sustantivo; la clave de sección sólo sirve para reproducibilidad, no para política pública.

## 5 Generalización entre elecciones

**Estado: WARNING alto.**

En muestras pareadas, el modelo actual cambia el MAE ponderado frente a persistencia en:

- 2018 presidencial: +0.0817 pp; IC95% por entidad [−0.432, +0.664] pp.
- 2021 intermedia: −2.0555 pp; IC95% [−3.146, −0.910] pp.
- 2024 presidencial: +0.0656 pp; IC95% [−0.305, +0.447] pp.

La mejora intermedia es amplia dentro de los datos observados. Las diferencias presidenciales son pequeñas e inciertas. El sesgo ponderado del modelo es +1.214 pp en 2018, −1.279 pp en 2021 y **+2.881 pp en 2024**; por tanto, no subestima sistemáticamente las presidenciales, sino que sobreestima 2024.

El experimento de transferencia del repositorio sólo puede evaluar 2021: modelo compartido 8.098 pp, sólo intermedias 8.494 pp y dos cabezas 8.174 pp. La diferencia del enfoque de dos cabezas tiene IC que incluye cero. No existe evidencia suficiente para un modelo específico por familia.

Para 2030 no hay evidencia de transportabilidad presidencial. La persistencia fue igual o mejor en ambos folds presidenciales, el riesgo 2024 falló y el marco geográfico futuro no está certificado. Debe evitarse una predicción puntual 2030 hasta actualizar geografía, calendario, competencia y backtesting; como mínimo se requiere un escenario de baseline, rango amplio y una advertencia explícita de no validación.
