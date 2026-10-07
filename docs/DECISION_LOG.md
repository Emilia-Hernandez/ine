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

## D-016 — Calibrar intervalos sólo con residuos fuera de tiempo anteriores

- Fecha: 2026-10-06
- Decisión: usar conformal de residuo absoluto al 90% con calibración móvil; 2021 recibe únicamente residuos 2018 y 2024 recibe 2018–2021.
- Evidencia: la restricción `max_calibration_target_year < target_year` pasa en todas las unidades y evita calibrar con el test evaluado.
- Riesgo: sólo hay dos evaluaciones de cobertura y la intercambiabilidad temporal es débil.
- Reversible: sí, mediante un método adaptativo preespecificado y evaluado con la misma restricción temporal.

## D-017 — No declarar listos los intervalos 2027

- Fecha: 2026-10-06
- Decisión: conservar el boosting como candidato, pero bloquear una proyección 2027 con intervalos publicables.
- Evidencia: cobertura nominal 90%; observada 62.35% en 2021 y 97.10% en 2024. El diagnóstico espacial agregado no empeora el MAE en 2018, 2021 ni 2024.
- Riesgo: retrasar la proyección; evita comunicar incertidumbre falsamente calibrada.
- Reversible: cuando un método temporalmente válido supere el piso de cobertura congelado sin deteriorar materialmente la anchura.

## D-018 — Corregir el centro con el ciclo anterior de la misma familia

- Fecha: 2026-10-06
- Decisión: sumar al candidato el cambio nacional ponderado observado seis años antes en la misma familia electoral.
- Evidencia: en 2021 reduce MAE ponderado de 8.97 a 8.31 pp y sesgo de −4.60 a −1.59 pp; en 2024 empeora 0.27 pp, dentro del límite de 0.5 pp.
- Riesgo: un único ciclo previo puede no representar 2027.
- Reversible: sí; la predicción original y la corrección quedan en columnas separadas.

## D-019 — Promover el análogo familiar sólo para experimentación

- Fecha: 2026-10-06
- Decisión: usar el intervalo de análogo familiar como candidato de la canalización experimental 2027, sin prometer cobertura pública.
- Evidencia: cobertura 90.41% en 2021 y 87.08% en 2024, ambas sobre el piso diagnóstico de 85%, pero 2024 bajo el nominal de 90%.
- Riesgo: 2021 requiere un arranque frío basado en el baseline 2015 y los intervalos son anchos.
- Reversible: sí; se conservan los tres métodos y todas sus métricas.

## D-020 — Emitir una proyección 2027 sólo como snapshot experimental

- Fecha: 2026-10-06
- Decisión: entrenar el boosting residual congelado con targets hasta 2024, aplicar +5.21 pp de corrección nacional y expandir a las 70,751 secciones del snapshot 2024 con respaldo jerárquico para C/D.
- Evidencia: el modelo corregido mejora el baseline en 2021 por 1.07 pp de MAE, pero lo empeora en 2024 por 0.54 pp; no existe outcome 2027 para calcular error.
- Riesgo: la geografía futura puede cambiar y el promedio proyectado puede confundirse con un resultado oficial.
- Reversible: sí; baseline, residual, ajuste nacional, intervalo y fuente territorial permanecen en columnas separadas.

## D-021 — Promover contexto territorial y no ECEG al predictor puntual

- Fecha: 2026-10-06
- Decisión: seleccionar historia + contexto relativo de entidad/nación para la siguiente iteración 2027; conservar sexo/edad y ECEG para segmentación y escenarios.
- Evidencia: frente al conjunto actual, el contexto reduce MAE 0.56 pp en 2018, 0.21 pp en 2021 y 0.32 pp en 2024. La combinación completa con ECEG mejora sólo 0.025 pp adicionales en 2024, debajo del umbral de 0.1 pp.
- Riesgo: los agregados estatales no sustituyen vecindad espacial y ECEG sólo tiene un target temporalmente válido.
- Reversible: sí; predicciones y registros de los seis grupos quedan conservados.

## D-022 — Retener HistGradientBoosting frente a challengers tabulares

- Fecha: 2026-10-06
- Decisión: conservar `HistGradientBoostingRegressor` residual; no promover XGBoost, LightGBM ni Extra Trees.
- Evidencia: con features, folds y ajustes constantes, los MAE 2021 fueron 8.098 pp para HistGradientBoosting, 8.104 para XGBoost, 8.196 para LightGBM y 8.446 para Extra Trees. XGBoost mejoró 2018 a 4.145 pp, pero no ganó el target principal.
- Riesgo: una especificación distinta podría cambiar el orden; una búsqueda amplia con sólo tres targets aumentaría el sobreajuste de selección.
- Reversible: sí; se conservan configuración, versiones, predicciones, métricas y registro de las cuatro familias.

## D-023 — Actualizar 2027 con contexto territorial y recalibrar intervalos

- Fecha: 2026-10-06
- Decisión: reemplazar el conjunto electoral anterior por `territorial_context` en la proyección experimental 2027 y recalibrar los radios A/B con sus propios errores fuera de tiempo 2021.
- Evidencia: el MAE baja de 8.31 a 8.10 pp en 2021 y de 4.96 a 4.64 pp en 2024; los radios A/B bajan de 17.98/19.46 a 17.52/19.32 pp. El promedio 2027 cambia de 57.06% a 57.15%.
- Riesgo: el centro sigue usando geografía 2024 y los intervalos sólo tienen un análogo intermedio; no es un pronóstico oficial publicable.
- Reversible: sí; features, componente residual, ajuste nacional, radios y procedencia quedan separados en los artefactos.

## D-024 — No promover la red neuronal densa

- Fecha: 2026-10-06
- Decisión: retener HistGradientBoosting y conservar la red MLP 64–32 sólo como challenger documentado.
- Evidencia: la red obtiene MAE de 5.262, 8.903 y 4.665 pp en 2018, 2021 y 2024, frente a 4.286, 8.098 y 4.636 pp del árbol. Falla el target principal y el límite de robustez 2018.
- Riesgo: otra arquitectura podría rendir mejor, pero una búsqueda amplia sobre tres targets sobreajustaría la elección del modelo.
- Reversible: sí; arquitectura, escalas, iteraciones, predicciones y métricas quedan registradas.

## D-025 — Adoptar contigüidad Rook para el grafo espacial 2024

- Fecha: 2026-10-06
- Decisión: construir el grafo GNN del universo CCPC 2024 con la capa nacional oficial del INE creada el 9 de mayo de 2024; exigir 1 m de frontera compartida después de normalizar precisión a 0.1 m y excluir contactos sólo por punto.
- Evidencia: las 70,751 llaves CCPC tienen geometría válida; resultan 201,286 aristas Rook y dos respaldos sintéticos explícitos para nodos aislados. La matriz final es simétrica, no tiene diagonal ni nodos de grado cero.
- Riesgo: el snapshot no representa automáticamente elecciones anteriores ni certifica la geografía 2027; las dos aristas de isla representan proximidad, no colindancia.
- Reversible: sí; contactos, longitudes, distancias, tipo de arista, fuente, hash y umbrales se conservan para repetir o ablar la construcción.

## D-026 — Congelar topologías contemporáneas para el backtest GNN

- Fecha: 2026-10-06
- Decisión: usar para 2015, 2018, 2021 y 2024 una capa seccional oficial creada antes de cada elección; inducir el grafo únicamente sobre secciones estables de clase A y prohibir el relleno con geometría futura.
- Evidencia: las coberturas de llaves CCPC son 100.00%, 99.93%, 98.29% y 100.00%, respectivamente. Los cuatro grafos pasan simetría, diagonal cero y ausencia de aislados después del respaldo explícito de islas.
- Riesgo: 47 secciones de 2018 y 1,179 de 2021 no tienen geometría en su corte contemporáneo; se excluyen y no se imputan.
- Reversible: sí; archivos originales, hashes, fechas internas, reparaciones, exclusiones y aristas quedan preservados por año.

## D-027 — Congelar el contrato de datos del challenger GNN

- Fecha: 2026-10-06
- Decisión: usar el grupo `territorial_context`, cinco entidades completas como validación espacial fija y ajustar imputación/escalado sólo con nodos `fit_mask` de años estrictamente anteriores al test.
- Evidencia: se producen bundles de 60,983, 60,430, 59,963 y 58,534 nodos; todas las variables electorales y de contexto tienen año fuente menor al target. Las pruebas verifican dimensiones, máscaras y aristas bidireccionales.
- Riesgo: la clase A privilegia continuidad geográfica y reduce cobertura; una sola partición estatal no mide toda la variabilidad espacial.
- Reversible: sí; features crudas, máscaras de faltantes, pesos, particiones, parámetros por fold y dos variantes de topología se guardan por separado.

## D-028 — Evaluar el embedding sólo como señal tabular adicional

- Fecha: 2026-10-06
- Decisión: usar un autoencoder GraphSAGE sin etiquetas para generar 16 variables y agregarlas al HistGradientBoosting; no evaluar ni promover un predictor compuesto únicamente por embeddings.
- Evidencia: con la misma muestra estable A, GraphSAGE Rook cambia el MAE frente al árbol sin embedding en +0.024 pp en 2018, +0.132 pp en 2021 y −0.035 pp en 2024. La topología aumentada tampoco mejora el target principal.
- Riesgo: el objetivo de reconstrucción puede privilegiar información ya disponible para el árbol y no aislar suficiente señal vecinal; sólo existen tres folds fuera de tiempo.
- Reversible: sí; las 16 columnas se agregan sin sustituir features, y referencia, embeddings, pesos, predicciones y estados del encoder quedan separados.

## D-029 — No promover el embedding GraphSAGE auto-supervisado

- Fecha: 2026-10-06
- Decisión: mantener `hist_gradient_boosting_without_embedding` para la siguiente iteración.
- Evidencia: el gate exige mejorar 2021; el MAE pasa de 8.218 a 8.350 pp con Rook y a 8.369 pp con aristas aumentadas. La mejora 2024 no compensa ese deterioro.
- Riesgo: descartar toda señal espacial por una sola formulación sería prematuro; la decisión aplica sólo al encoder congelado actual.
- Reversible: sí; una alternativa contrastiva preespecificada puede evaluarse con los mismos folds, sin reusar 2021 para búsqueda amplia.

## D-030 — No promover el embedding exclusivamente vecinal

- Fecha: 2026-10-06
- Decisión: conservar el árbol sin embedding después de evaluar una representación de 16 dimensiones que depende sólo del promedio de vecinos y se añade como señal tabular.
- Evidencia: frente al árbol, Rook cambia el MAE en +0.180 pp en 2018, +0.007 pp en 2021 y −0.013 pp en 2024. La variante aumentada cambia +0.171, +0.012 y −0.035 pp. Ninguna mejora el target principal 2021.
- Riesgo: el resultado puede depender de una inestabilidad real de la autocorrelación electoral entre ciclos; ampliar arquitecturas con tres folds aumentaría el sobreajuste de selección.
- Reversible: sí; encoder, embeddings, topologías, predicciones y referencia permanecen separados. La siguiente alternativa recomendada son estadísticas vecinales explícitas, no otra búsqueda neuronal amplia.

## D-031 — Promover el núcleo espacial explícito en secciones estables

- Fecha: 2026-10-06
- Decisión: agregar al HistGradientBoosting 24 variables `neighbor_core` calculadas con Rook estricto: 20 estadísticas de cinco señales históricas, dos señales de segundo salto y dos proporciones de frontera administrativa.
- Evidencia: frente a la misma referencia estable A, reduce el MAE ponderado de 4.299 a 4.262 pp en 2018, de 8.218 a 8.169 pp en 2021 y de 4.721 a 4.692 pp en 2024. El bloque completo de 35 variables no se promueve porque empeora 2021.
- Riesgo: la ganancia es consistente pero pequeña y sólo está validada en clase A; los componentes de linaje B aún no tienen vecindad definida.
- Reversible: sí; features, topologías, predicciones, métricas y ablación completa se conservan por separado. La promoción aplica a la siguiente iteración estable A, no sustituye todavía el modelo experimental 2027 A+B.

## D-032 — Promover competencia previa y concurrencia local

- Fecha: 2026-10-06
- Decisión: promover `competition_concurrency` para el modelo experimental A+B de 2027 y conservar HistGradientBoosting como familia tabular.
- Evidencia: frente a `territorial_context`, el MAE cambia de 4.286 a 4.206 pp en 2018, de 8.098 a 7.807 pp en 2021 y de 4.636 a 4.651 pp en 2024. El deterioro 2024 de 0.014 pp queda dentro del gate de 0.5 pp. Ninguna familia alternativa gana el target principal.
- Riesgo: la mayor parte de la ganancia proviene de concurrencia; competencia aislada es débil y el calendario 2027 puede cambiar antes de la jornada.
- Reversible: sí; fuentes SICEE, hashes, consolidación de coaliciones, calendario con fecha de conocimiento, métricas y configuración quedan separados.

## D-033 — Separar el ciclo estatal del predictor y promover reversión parcial

- Fecha: 2026-10-07
- Decisión: no promover `entity_cycle_context` como feature libre del árbol; aplicar después del modelo una corrección estatal explícita con shrinkage −0.50 sobre el cambio de participación de la misma familia relativo al cambio nacional.
- Evidencia: como feature, el bloque cambia el MAE de 7.807 a 7.895 pp en 2021 y no pasa el gate. Como corrección contraída, reduce 2021 a 7.351 pp y 2024 de 4.651 a 4.516 pp; 2018 sube de 4.206 a 4.478 pp, dentro del máximo de deterioro de 0.5 pp.
- Riesgo: sólo existen tres folds estrictos y el signo negativo refleja reversión, no persistencia; el baseline simple aún gana ligeramente en 2018 y 2024.
- Reversible: sí; la capa, su rejilla, métricas, predicciones y decisión están separadas del modelo base y pueden desactivarse sin reentrenarlo.

## D-034 — No promover el grafo de similitud sociodemográfica

- Fecha: 2026-10-07
- Decisión: conservar el modelo `competition_concurrency` con corrección estatal y no añadir estadísticas ni embeddings del grafo de pares sociodemográficos.
- Evidencia: el mejor candidato es el embedding `neighbor-only` sobre vecinos mutuos `k=16`. Frente a la referencia cambia el MAE en +0.118 pp en 2018, +0.008 pp en 2021 y −0.039 pp en 2024. No mejora el target principal. Las estadísticas explícitas y las combinaciones rinden peor en 2021.
- Riesgo: la topología se limita a composición sexo–edad rezagada; ECEG no se incluye porque sólo permitiría un backtest válido en 2024. Otra fuente con varios cortes históricos podría cambiar la conclusión.
- Reversible: sí; grafos, escaladores por fold, estadísticas, embeddings, estados del encoder, métricas y decisión se conservan como artefactos independientes.

## D-035 — Separar el paquete de perfiles del diseño de política

- Fecha: 2026-10-07
- Decisión: implementar los pasos 1–6 como una entrega predictiva y descriptiva de sección, municipio y entidad; diferir la evaluación causal hasta que el equipo de ciencia política defina la intervención.
- Evidencia: los conteos CCPC permiten medir directamente tasas por sexo y edad, y el ranking cubre las 70,751 secciones. El clasificador de caída ≥2 pp alcanza ROC AUC ponderada 0.747 en el análogo intermedio 2021, pero sólo 0.423 en la sensibilidad presidencial 2024.
- Riesgo: confundir asociación, perfil o prioridad estadística con una recomendación de tratamiento; mitigado al separar probabilidad, magnitud y volumen, etiquetar C/D, documentar la transferencia débil y prohibir lenguaje causal.
- Reversible: sí; umbrales, calibrador, perfiles y reglas de ranking están configurados y los datos subyacentes permanecen separados.

## D-036 — Calibrar el riesgo 2027 al análogo intermedio 2021

- Fecha: 2026-10-07
- Decisión: usar la predicción estrictamente fuera de tiempo de 2021 para calibrar probabilidades 2027; conservar 2018 y 2024 como pruebas de sensibilidad, no mezclarlas en el calibrador final.
- Evidencia: 2021 comparte la familia intermedia con 2027 y obtiene Brier 0.170, ROC AUC 0.747 y captura 41.61% de los casos positivos dentro del 20% del electorado priorizado. La transferencia 2024 invierte el orden de riesgo.
- Riesgo: sólo existe un análogo intermedio completo para calibración; las probabilidades tienen incertidumbre estructural que un intervalo binomial no captura.
- Reversible: sí; probabilidades crudas, calibradas por fold, tablas de confiabilidad y año de calibración quedan registrados.

## D-037 — Sustituir clusters exclusivos por arquetipos superpuestos

- Fecha: 2026-10-07
- Decisión: promover seis puntajes continuos 0–100 y etiquetas multilabel p80 como salida principal; conservar los tres clusters sólo como resumen exploratorio secundario.
- Evidencia: los clusters son estables por submuestra (ARI 0.932), pero tienen separación débil (silhouette 0.170). En el backtest completo, sólo la brecha desfavorable a hombres tiene lift positivo y AUC >0.5 en los tres targets.
- Riesgo: un arquetipo descriptivo puede confundirse con un factor causal o una población objetivo; se reporta consistencia temporal por separado y se prohíbe esa interpretación.
- Reversible: sí; puntajes, umbrales p75/p80/p85, etiquetas, clusters y métricas permanecen en columnas y tablas separadas.

## D-038 — Cuantificar estabilidad por entidad y usar ECEG sólo para descripción

- Fecha: 2026-10-07
- Decisión: ejecutar 20 réplicas bootstrap bayesianas con pesos por entidad y añadir nueve descriptores ECEG 2020 sin incorporarlos al clasificador.
- Evidencia: 9,875 secciones permanecen robustamente en el quintil superior de riesgo, mientras 7,674 cambian de estado según la réplica. ECEG aporta contexto de escolaridad, internet, actividad, discapacidad y composición, con procedencia territorial explícita.
- Riesgo: el bootstrap mide estabilidad geográfica del modelo, no incertidumbre por cambio de ciclo; ECEG es una fotografía 2020 y no prueba mecanismos causales.
- Reversible: sí; réplicas, registro, intervalos, procedencia ECEG y predictor permanecen separados.
