# Plan de corrección previo a entrega

## Gate de entrega

No entregar mientras permanezcan abiertos P0 o P1. La corrección debe congelar primero el objetivo del Reto 2 y después regenerar artefactos/documentos desde una especificación única.

## P0 — descalificación o conclusión central

### P0.1 Completar el paquete obligatorio del Reto 2

**Acciones:** producir PDF de 10–15 páginas; escenario base y al menos una intervención hipotética; semáforo y recomendaciones preventivas; mapa ejecutable; base anonimizada de entrega. Marcar la intervención como escenario, no como efecto causal.

**Criterio de cierre:** los cinco elementos abren desde un paquete limpio y el PDF remite a rutas/URLs válidas.

### P0.2 Redefinir el ajuste nacional

**Acciones:** elegir explícitamente entre razón de sumas nacional y efecto de panel comparable. Si el objetivo es “nacional”, usar razón de sumas. Restarlo del target de entrenamiento, centrar el residual por fold y reañadirlo una sola vez.

**Criterio de cierre:** la media ponderada del residuo de entrenamiento es aproximadamente cero por fold y una prueba impide sumar dos componentes agregados.

### P0.3 Rehacer validación pareada

**Acciones:** intersecar IDs válidos antes de calcular todas las métricas; publicar cobertura y precisión separadamente; usar bootstrap por entidad.

**Criterio de cierre:** modelo y baseline tienen conteos idénticos en cada tabla comparativa.

## P1 — validez y uso responsable

### P1.1 Limitar el clasificador

Retirar resultados presidenciales y cualquier uso 2030. Para 2027, mostrarlo como score experimental, acompañarlo con baseline histórico y no afirmar calibración externa.

### P1.2 Recalcular incertidumbre final

Construir intervalos alrededor de la misma especificación de punto entregada. Evaluar cobertura por año, clase geográfica y entidad; aumentar réplicas y agrupar el remuestreo.

### P1.3 Reservar validación futura

Congelar configuración, hash y protocolo antes del siguiente resultado electoral. No volver a elegir hiperparámetros con el fold reservado.

### P1.4 Corregir geografía prospectiva

Actualizar snapshot y equivalencias 2027 antes de producción. Etiquetar coincidencias C/D ECEG como no validadas hasta disponer de geometría/crosswalk.

## P2 — interpretación y comunicación

### P2.1 Percentiles

Conservar todos los empates de riesgo e informar 22.09%, o definir capacidad y desempate sustantivo. Renombrar volumen como “caída puntual positiva” (9,891; 13.98%), no “quintil superior”.

### P2.2 Perfiles

Separar perfiles descriptivos de evidencia de intervención. Informar que cinco de seis arquetipos no son históricamente consistentes y que la segmentación tiene separación baja.

### P2.3 Documentación

Eliminar lenguaje de “modelo final”, corregir +5.21, muestras, sesgo 2024 y cobertura de intervalos. Designar una única versión canónica y numerar secciones consecutivamente.

## P3 — ingeniería y gobernanza

- Actualizar README de 93 a 100 pruebas, después de fijar el conjunto definitivo.
- Incorporar lockfile y manifiesto de artefactos.
- Añadir ejecución no destructiva con `--output-root`.
- Versionar entregables o publicar un paquete firmado con hashes.
- Aumentar bootstrap de 20 a una cifra justificada por estabilidad de cuantiles.

## Matriz de ejecución

Las estimaciones son esfuerzo técnico neto, no calendario institucional.

| ID | Severidad | Impacto | Dependencias | Tiempo estimado | ¿Reentrena? | ¿Cambia documentos/visualizaciones? |
|---|---|---|---|---:|---|---|
| P0.1 | Crítica | Evita descalificación | Definir escenario e insumos de mapa | 3–5 días | No necesariamente | Sí, ambos |
| P0.2 | Alta | Cambia forecast nacional | Decisión sobre estimador agregado | 0.5–1 día | Sí | Sí, ambos |
| P0.3 | Alta | Corrige descomposición | P0.2 | 1–2 días | Sí | Sí, ambos |
| P0.4 | Alta | Corrige comparación central | Predicciones históricas congeladas | 0.5 día | No | Sí, tablas/gráficas |
| P1.1 | Alta | Evita reclamo de prueba externa | Especificación congelada | Prospectivo | Sí, futuro | Sí |
| P1.2 | Alta | Limita uso indebido | Ninguna | 0.5 día | Sólo si se reemplaza | Sí |
| P1.3 | Alta | Corrige intervalos | P0.2–P0.3 | 1–2 días | Sí | Sí |
| P1.4 | Alta | Validez territorial | Insumo oficial futuro | Externo | Sí al actualizar | Sí, mapa |
| P2.1–P2.2 | Media | Corrige priorización | Forecast regenerado | 0.5 día | No | Sí |
| P2.3 | Media | Evita sobreinterpretación | Revisión sustantiva | 0.5 día | No | Sí |
| P2.4–P2.5 | Media | Robustez auditable | Protocolo de selección | 1–2 días | Sí | Sí, anexos |
| P2.6–P2.7 | Media | Entrega inequívoca | Todas las cifras finales | 1–2 días | No | Sí |
| P3.* | Baja | Reproducibilidad/editorial | Cierre metodológico | 1–2 días | No | Parcial |

## Secuencia recomendada

1. Congelar copia de evidencia y decidir definición nacional.
2. Corregir target/decomposición y validación pareada.
3. Regenerar predicción, magnitud, volumen e intervalos.
4. Rediseñar el escenario de intervención y mapa.
5. Reescribir el PDF canónico.
6. Ejecutar pruebas limpias, generar manifiesto y hacer revisión final independiente.
