# Metodología técnica corregida

## 1. Fuentes

- Conteos Censales de Participación Ciudadana del INE: 2009, 2012, 2015, 2018, 2021 y 2024.
- Manual de variables CCPC.
- ECEG 2020 del INEGI para descriptores sociodemográficos agregados.
- Relaciones geográficas y snapshot seccional 2024 disponibles en el repositorio.

Los archivos originales no se sobrescriben. `MANIFIESTO_RESULTADOS_ANTERIORES.csv` conserva tamaño y SHA-256 de los seis artefactos auditados usados como entrada.

## 2. Universo

La base maestra contiene 70,751 secciones únicas: 58,534 A, 6,561 B, 1,865 C y 3,791 D. Los modelos locales se aplican sólo a A/B. C/D conservan una referencia jerárquica explícita.

## 3. Definición de participación

\[
p = \frac{SV}{SV + NV}
\]

`NS` no se incluye en el denominador ni se interpreta como abstención. Los agregados nacionales se calculan como razón de sumas, no como promedio simple de tasas.

## 4. Variables

El modelo utiliza historia de participación, tendencia, dispersión, cobertura, competencia previa y concurrencia electoral. La lista exacta se resuelve desde `configs/feature_ablation.yaml`, grupo `competition_concurrency`. La imputación, estandarización y codificación se ajustan sólo con entrenamiento.

## 5. Comparabilidad temporal

Cada fold utiliza targets anteriores al año evaluado. `max_electoral_feature_year < target_year` se verifica para todo el mart. El target se construye sólo para unidades con referencia de la misma familia y pesos preelectorales disponibles.

La geografía objetivo sigue siendo el snapshot 2024. Esto no certifica las claves 2027.

## 6. Targets y descomposición corregida

Para una unidad `i` y elección `t`:

\[
g_t = P^{nat}_{t-6} - P^{nat}_{t-12}
\]

`g_t` usa las dos elecciones anteriores de la misma familia disponibles antes de `t`. Para 2027, `g=0.0476442`.

El residual inicial es:

\[
r_{it}=y_{it}-b_{it}-g_t
\]

Después se centra por fold con lista nominal preelectoral `w`:

\[
r^c_{it}=r_{it}-\frac{\sum_i w_{it}r_{it}}{\sum_iw_{it}}
\]

Las predicciones residuales también se centran con pesos disponibles antes del target. Esto impide que el árbol vuelva a introducir un componente agregado. La corrección estatal anterior se elimina.

## 7. Modelos evaluados

- A: persistencia histórica.
- B: árbol que predice el cambio completo sin shift adicional.
- C: residual centrado con componente nacional y sin contracción.
- D: residual centrado con contracciones 0, 0.10, 0.25, 0.50, 0.75 y 1.00.
- E: especificación auditada anterior, sólo como referencia.

Todos se evalúan en la misma intersección de observaciones dentro de cada año.

## 8. Baseline operativo

La persistencia es el modelo operativo. Para A/B usa la elección intermedia anterior comparable. Para C/D usa la referencia jerárquica existente y queda etiquetada como no local.

El residual centrado con contracción 0.25 supera el gate interno de desarrollo: mejora el MAE ponderado 0.271 pp en 2018 y 1.272 pp en 2021, y empeora 0.139 pp en 2024. Sólo la mejora 2021 tiene un intervalo bootstrap por entidad completamente bajo cero.

Al no existir validación externa intacta, el modelo avanzado no se promueve a operación. Se conserva como escenario exploratorio.

## 9. Validación

| Año | Unidades | Secciones | MAE persistencia | MAE residual centrado 0.25 | Δ frente a persistencia |
|---:|---:|---:|---:|---:|---:|
| 2018 | 58,624 | 62,899 | 4.386% | 4.115% | −0.271 pp |
| 2021 | 58,069 | 62,936 | 9.385% | 8.112% | −1.272 pp |
| 2024 | 56,007 | 61,329 | 4.421% | 4.560% | +0.139 pp |

Los intervalos de diferencia usan 500 réplicas bootstrap agrupadas por entidad. Las métricas son de desarrollo, no validación externa.

## 10. Métricas

Se reportan MAE, RMSE, bias, versiones ponderadas por registros identificados, participación nacional observada/predicha, cobertura, errores por entidad y errores por banda de participación previa.

## 11. Corrección del ajuste nacional

La versión anterior sumaba +5.21497 pp, media ponderada del panel A/B, a un residual no centrado. La versión corregida:

1. Usa +4.76442 pp, razón de sumas nacional 2015–2021.
2. Resta el componente antes de entrenar.
3. Centra el target y la predicción residual.
4. Elimina la corrección estatal adicional.
5. Aplica el mismo procedimiento en backtest y producción.

## 12. Perfiles

Los tres clusters se conservan como patrones descriptivos sólo para 65,095 secciones A/B con conteos locales por edad y sexo. Se usan nombres neutrales. Las 5,656 C/D quedan sin perfil.

La silhouette histórica es aproximadamente 0.170 y la estabilidad algorítmica ARI es aproximadamente 0.932. La separación sustantiva es baja. Sólo el arquetipo de brecha desfavorable a hombres se conserva como patrón históricamente consistente.

## 13. Clasificaciones de riesgo

El score del clasificador se exporta sólo para A/B y se denomina `score`, no probabilidad validada. El p80 inclusivo se calcula sobre 65,095 casos. Umbral=0.4457185; seleccionados=14,821; proporción=22.77%; empates=3,867.

La magnitud `volumen_exploratorio_caida_positiva` se deriva del escenario exploratorio. No se denomina quintil de volumen. Sólo 68 secciones tienen caída puntual positiva después de la corrección.

## 14. Incertidumbre

No se reutilizan los intervalos anteriores porque no validaban la especificación final. La base exporta etiquetas cualitativas:

- A/B: incertidumbre de modelo no cuantificada.
- C/D: incertidumbre geográfica y de modelo alta.

No se afirma cobertura nominal.

## 15. Limitaciones

- Todos los folds históricos participaron en desarrollo.
- Sólo hay una elección intermedia útil para evaluar transferencia.
- El score falla en 2024 presidencial y no se extrapola a 2030.
- La geografía 2027 no está certificada.
- ECEG corresponde a 2020; 38 A/B usan fallback estatal y 3,630 C/D tienen coincidencia de código no validada geométricamente.
- Los resultados agregados no identifican mecanismos individuales ni efectos causales.

## 16. Reproducibilidad

```bash
PYTHONPATH=src .venv/bin/python scripts/run_validated_handoff.py
PYTHONPATH=src .venv/bin/pytest -q
.venv/bin/ruff check src scripts tests
```

Configuración: `configs/validated_handoff.yaml`. Implementación: `src/radar27/modeling/validated_handoff.py`. Semilla: 2701. Las salidas se escriben en `handoff/`; ningún artefacto original se modifica.

