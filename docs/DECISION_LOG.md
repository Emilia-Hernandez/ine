# Registro de decisiones

## D-001 — Limitar el universo principal a elecciones federales

- Fecha: 2026-10-05
- Decisión: incluir 2009, 2012, 2015, 2018, 2021 y 2024; mantener separados voto anticipado, prisión preventiva y Poder Judicial.
- Evidencia: estructura de la página oficial y alcance del reto.
- Riesgo: perder información especial; se conserva como fuente potencial separada.
- Reversible: sí, tras comprobar definiciones y solapamiento.

## D-002 — Adoptar el denominador oficial de participación

- Fecha: 2026-10-05
- Decisión: `SV/(SV+NV)` para participación y `NV/(SV+NV)` para abstención; `NS/LN` por separado.
- Alternativa descartada: `SV/LN` como participación oficial.
- Evidencia: manual pp. 17–18 y TXT de los ZIP.
- Riesgo: diferencias frente a cálculos previos sobre LN; se conserva `SV/LN` sólo como sensibilidad.
- Reversible: no sin contradecir la definición oficial consultada.

## D-003 — Leer identificadores y categorías como texto

- Fecha: 2026-10-05
- Decisión: lectura inicial `VARCHAR`, conversiones numéricas auditadas.
- Evidencia: necesidad de preservar IDs, vacíos y códigos categóricos.
- Riesgo: mayor costo de lectura; mitigado con DuckDB.
- Reversible: sí, después de definir contratos por campo.

## D-004 — No armonizar territorios en la fase 1

- Fecha: 2026-10-05
- Decisión: medir coincidencias nominales y cambios, sin inventar crosswalks.
- Evidencia: sección referida al año correspondiente; marcos DERFE 2021/2023 distintos; altas/bajas de códigos.
- Riesgo: retrasa el panel; evita comparaciones territoriales inválidas.
- Reversible: cuando exista cartografía/crosswalk oficial validado.

## D-005 — No recodificar no binario ni edades extremas

- Fecha: 2026-10-05
- Decisión: conservar `SEXO=2` sólo en 2024 y edades 18–140 tal como aparecen.
- Evidencia: diccionario 2024 y categorías observadas.
- Riesgo: categorías escasas o errores posibles; deben aclararse antes de modelar.
- Reversible: sí, mediante regla documentada posterior.

## D-006 — Limpiar sin excluir y señalar anomalías revisables

- Fecha: 2026-10-05
- Decisión: conservar las 54,872,712 filas; mantener distritos vacíos como nulos, edades >100 con bandera y cocientes de denominador cero como nulos.
- Evidencia: la identidad contable y unicidad se mantienen; no existe base documental para imputar o eliminar.
- Riesgo: los extremos pueden incluir errores fuente; quedan localizables y no se usan silenciosamente.
- Reversible: sí, mediante una regla posterior explícita y cuantificada.

## D-007 — Distinguir código observado de ID territorial armonizado

- Fecha: 2026-10-05
- Decisión: usar `section_key_observed` sólo dentro del marco de cada elección y prohibir una llave longitudinal por ahora.
- Evidencia: el INE reporta 69,548 secciones en mayo de 2023 frente a 70,751 códigos en CCPC 2024; hay altas, bajas y cambios de metadatos.
- Riesgo: impide modelos longitudinales inmediatos; evita atribuir continuidad geométrica no demostrada.
- Reversible: únicamente con geometría/crosswalk oficial validado.

## D-008 — Tratar el agregado sección–año como provisional

- Fecha: 2026-10-05
- Decisión: permitir agregación de conteos por código observado para conciliación, etiquetada `observed_code_not_longitudinal_crosswalk`.
- Evidencia: los totales agregados concilian exactamente con los crudos en los seis años.
- Riesgo: un consumidor podría confundirlo con panel; nombre, campo de estado y documentación lo prohíben.
- Reversible: sí, cuando exista una unidad geográfica común validada.

## D-009 — Usar la publicación AMGE como fuente pública de linaje

- Fecha: 2026-10-05
- Decisión: usar el libro DERFE 2005–2022 enlazado en `INE-CT-R-0175-2023`; validar su hash y conservar fila de Excel y documentos jurídicos.
- Evidencia: la carpeta pública sigue disponible sin autenticación y contiene origen, destino, programa, caso y fecha.
- Riesgo: no cubre actualizaciones de 2023; 2024 se etiqueta como evidencia parcial.
- Reversible: sí, incorporando anexos públicos posteriores con el mismo contrato.

## D-010 — Agregar familias territoriales, nunca repartir conteos

- Fecha: 2026-10-05
- Decisión: para divisiones/fusiones oficiales, sumar todos los miembros del componente y recalcular tasas; prohibir pesos inventados padre→hijos.
- Evidencia: AMGE permite relaciones uno-a-muchos y muchos-a-uno, pero no ofrece pesos poblacionales históricos comparables.
- Riesgo: reduce resolución en secciones modificadas.
- Reversible: sólo si una fuente oficial publica asignaciones exhaustivas de población/lista nominal.

## D-011 — Adoptar A+B como muestra principal y jerarquía para cobertura

- Fecha: 2026-10-05
- Decisión: clases A+B para entrenamiento/evaluación principal; respaldo sección→linaje→municipio→entidad→nacional para cobertura.
- Evidencia: en 2015→2021 A+B eleva cobertura de 85.03% a 93.77% y reduce MAE ponderado de 9.46 a 9.38 pp; la jerarquía alcanza 100% con 9.47 pp.
- Riesgo: el desempeño del baseline sigue siendo modesto y 2024 tiene evidencia AMGE parcial.
- Reversible: sí, manteniendo folds y comparando modelos futuros contra este baseline.

## D-012 — Tratar disponibilidad de ECEG como restricción temporal

- Fecha: 2026-10-05
- Decisión: prohibir ECEG 2020 en backtests estrictos 2015, 2018 y 2021; evaluarlo sólo para 2024 y conservarlo como candidato para 2027.
- Evidencia: la ficha y metadatos oficiales indican modificación el 18 de agosto de 2021, posterior a la jornada del 6 de junio.
- Riesgo: se pierde una covariable útil en el gate 2021; se evita fuga temporal.
- Reversible: sólo si se documenta una versión equivalente que hubiera estado disponible antes del target.

## D-013 — Calcular razones después de agregar conteos

- Fecha: 2026-10-05
- Decisión: sumar numeradores y denominadores por sección/componente antes de obtener tasas de participación y composición.
- Evidencia: las unidades tienen tamaños distintos y el promedio simple de tasas no reproduce el universo.
- Riesgo: ninguna pérdida de información; aumenta el costo de procesar 54.9 millones de filas.
- Reversible: no sin introducir ponderación estadísticamente incorrecta.

## D-014 — Usar corrección residual contraída

- Fecha: 2026-10-05
- Decisión: el boosting electoral corrige 25% del residual estimado sobre el baseline; el factor se calibra con 2018, antes del gate 2021.
- Evidencia: la predicción directa mejoraba 2021 pero fallaba severamente en 2018; la contracción limita el deterioro fuera del fold principal.
- Riesgo: sacrifica parte de la mejora máxima posible en 2021.
- Reversible: sí, mediante calibración anidada con más elecciones o un criterio previamente congelado.

## D-015 — Aprobar boosting electoral como candidato de desarrollo

- Fecha: 2026-10-05
- Decisión: promover `hist_gradient_boosting_electoral` a la siguiente fase, no todavía a producción 2027.
- Evidencia: en 2021 reduce MAE ponderado de 9.38 a 8.97 pp y eleva cobertura de 93.77% a 96.10%; los deterioros 2018/2024 son 0.46/0.26 pp, dentro del máximo de 0.5 pp.
- Riesgo: error absoluto todavía elevado, pocos folds y evidencia 2024 parcial.
- Reversible: sí; el baseline, predicciones y gate permanecen congelados.
