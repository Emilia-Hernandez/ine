# Auditoría integral de RADAR 27

## Veredicto general

**NO LISTO POR PROBLEMAS CRÍTICOS.**

El repositorio contiene una base técnica considerable, fuentes con hashes verificables, validación temporal explícita, 100 pruebas automatizadas que pasan y una trazabilidad mejor que la habitual en un prototipo de hackathon. Sin embargo, la entrega actual no satisface todavía requisitos obligatorios del Reto 2 y varias afirmaciones centrales no son metodológicamente defendibles tal como están redactadas.

La causa inmediata para no entregar no es sólo estadística. La convocatoria exige para el Reto 2 al menos dos escenarios, incluido uno con intervención hipotética, recomendaciones preventivas, un mapa ejecutable de escenarios y la base anonimizada. El propio proyecto declara diferidos esos pasos y `deliverables/` contiene únicamente cuatro archivos DOCX, sin el mapa de escenarios ni la base de entrega. La convocatoria señala que omitir un entregable mínimo causa descalificación.

## Hallazgos que cambian las conclusiones

1. **El parámetro +5.21 pp está mal descrito como cambio nacional.** El cambio nacional 2015–2021 calculado como razón de sumas es **+4.7644 pp**. El valor **+5.2150 pp** es la media ponderada del cambio de unidades A/B comparables, usando como peso los registros identificados del año objetivo 2021. No incluye todo el universo y no equivale al agregado nacional. Sustituirlo por el cambio nacional por razón de sumas reduce la predicción nacional 2027 de 57.3067% a 56.8565%, una diferencia de **−0.4501 pp**, y cambia 70,655 predicciones seccionales.

2. **La descomposición del ajuste nacional no está identificada.** El árbol se entrena contra el cambio completo `actual − participación previa de la misma familia`; luego se añade otro componente agregado. No existe una restricción que obligue a la corrección aprendida a tener media nacional cero. Para 2027, la corrección aprendida aporta en promedio ponderado +0.3433 pp después del factor 0.25, antes de añadir +5.2150 pp. No puede afirmarse que el modelo “separa” efectos seccionales y nacionales. El solapamiento observable es +0.3433 pp, aunque no es posible atribuir causalmente toda esa media al mismo factor latente.

3. **Modelo y baseline no se comparan sobre la misma muestra en las tablas finales.** El modelo actual evalúa 71, 1,513 y 1,970 unidades más que la persistencia en 2018, 2021 y 2024, respectivamente. La documentación afirma que se usaron los mismos universos. En una comparación pareada, el modelo actual mejora 2021 en 2.056 pp de MAE ponderado, pero empeora 2018 en 0.082 pp y 2024 en 0.066 pp. Los intervalos bootstrap por entidad de las dos diferencias presidenciales incluyen cero.

4. **No queda un conjunto de prueba verdaderamente independiente.** El fold 2021 se usa repetidamente para escoger variables, algoritmo, corrección estatal y especificaciones; 2018 fija el factor 0.25 y 2024 participa en gates de robustez. Las métricas finales son resultados de desarrollo, no una estimación insesgada de generalización. La mejora 2021 es real dentro de la muestra histórica analizada, pero su magnitud está sujeta a sesgo de selección.

5. **El clasificador de riesgo no es utilizable fuera del análogo intermedio sin una advertencia fuerte.** En 2024, AUC=0.4227 y Brier=0.3266. Un predictor constante con prevalencia de entrenamiento obtiene Brier=0.3017, y un baseline histórico de una variable obtiene AUC=0.6055 y Brier=0.2685. Invertir el score mejora AUC a 0.5773, pero no supera el baseline histórico. El bootstrap por entidad da IC95% [0.340, 0.522] para la AUC actual: el punto es adverso, aunque no es concluyente frente a 0.5 al 5%.

6. **El p80 no produce dos quintiles comparables.** En riesgo, 3,867 empates en 44.5719% elevan el grupo alto a 15,631 secciones (22.09%). En volumen, 60,860 secciones tienen exactamente cero; el p80 es cero y la regla actual selecciona sólo las 9,891 con volumen positivo (13.98%). No es un error de suma, pero la etiqueta “quinto superior” es incorrecta para volumen.

7. **Las 38 secciones están conciliadas.** Son 38 secciones clase A con perfil electoral local, pero sin descriptor ECEG completo en la unidad; reciben referencia ECEG estatal. La cifra 65,057 corresponde a A/B con ECEG agregado, mientras 65,095 es el total A/B. No hay duplicados. Dos de esas 38 también usan referencia estatal en al menos un factor de arquetipo.

## Qué sí quedó comprobado

- Los siete archivos CCPC/manual enumerados en `source_manifest.csv` existen y sus SHA-256 coinciden.
- El target oficial es `SV/(SV+NV)`; `NS` no se mezcla con abstención.
- El orden temporal `max_electoral_feature_year < target_year` se cumple en las 243,108 filas del mart principal.
- La clase positiva del clasificador es caída de al menos 2 pp; `predict_proba[:,1]` corresponde a esa clase.
- Hay 70,751 llaves seccionales únicas, con 58,534 A, 6,561 B, 1,865 C y 3,791 D.
- Todas las probabilidades y predicciones finales están dentro de [0,1].
- Las cifras principales de riesgo, perfiles y prioridad se reproducen desde los artefactos.
- `pytest -q` pasa **100 pruebas** y `ruff check src scripts tests` no reporta errores.

## Qué no quedó validado

- Una reproducción limpia de extremo a extremo desde cero. El pipeline escribe sobre `data/interim/` y `artifacts/`; hacerlo habría violado la instrucción de no modificar artefactos originales. Se validaron hashes, artefactos y cálculos independientes dentro de `audit/`.
- Concordancia en línea de cada fuente con el servidor original a la fecha de esta auditoría; sólo se validó la integridad local contra los manifiestos versionados.
- Cobertura real de los intervalos entregados con la especificación final completa. Las coberturas 90.41%/87.08% pertenecen a una etapa anterior del pipeline; los radios finales mezclan centros y reglas distintas para A/B y C/D.
- Transportabilidad a 2030. No existe una prueba presidencial favorable y la geografía 2027/2030 no está certificada.

## Correcciones imprescindibles antes de entregar

1. Completar los entregables obligatorios del Reto 2: escenario sin intervención, intervención hipotética explícitamente no causal, mapa ejecutable, base de entrega y recomendaciones preventivas.
2. Corregir la definición del “ajuste nacional”; decidir y documentar si se desea razón de sumas nacional o efecto de panel comparable.
3. Reentrenar una formulación residual centrada antes de añadir un componente nacional; no sumar componentes no ortogonales.
4. Rehacer todas las comparaciones modelo-baseline sobre intersecciones idénticas y reportar intervalos por entidad.
5. Congelar una especificación y reservar la siguiente elección disponible como prueba; mientras tanto, presentar 2021 como resultado de desarrollo.
6. Retirar la probabilidad de riesgo de cualquier uso presidencial y no extrapolar a 2030.
7. Renombrar el corte de volumen como “volumen positivo” o adoptar una regla operativa de capacidad; explicar los empates del riesgo.
8. Exportar el reporte final a PDF de 10–15 páginas, versionarlo, registrar su hash y eliminar la ambigüedad entre versiones largas y cortas.

## Resultado de la revisión cuantitativa

Se inventariaron **42 afirmaciones cuantitativas centrales**. Se recalcularon **38/42 (90.5%)**; 35 coincidieron con su artefacto, tres quedaron demostradas como descripciones incorrectas o comparaciones no equivalentes y cuatro permanecen sin verificación limpia. “Comprobada” incluye tanto una coincidencia como una falsificación reproducible; no significa que la afirmación sea correcta.

