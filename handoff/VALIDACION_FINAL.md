# Validación final del handoff técnico

Fecha de cierre: 2026-10-15  
Versión: `radar27-validated-handoff-2026.1`

## Dictamen

El paquete queda listo para entrega como **handoff técnico conservador y
reproducible**. No queda habilitado como candidatura final del INE ni como
pronóstico oficial: no existe validación externa independiente y la evidencia
geográfica local para las secciones C/D sigue siendo insuficiente.

La única predicción operativa autorizada en el paquete es
`A_persistence`. El modelo centrado con contracción 0.25 se conserva como
resultado de desarrollo y exploración. El score de riesgo y los perfiles P1–P3
son descriptivos y experimentales, no probabilidades validadas ni efectos
causales.

## Evidencia de verificación

- Suite completa: **110 pruebas aprobadas, 0 fallas**.
- Pruebas adversariales de auditoría: **9 aprobadas, 0 fallas**.
- Calidad estática con Ruff: **sin observaciones**.
- Advertencia no bloqueante: Joblib no pudo detectar núcleos físicos y utilizó
  el conteo de núcleos lógicos; no altera datos, estimaciones ni resultados.
- Maestro final: **70,751 filas, 44 columnas y 32 entidades**.
- Diccionario: **44 variables**, en correspondencia exacta con el maestro.
- Integridad: una fila por sección, identificadores preservados como texto,
  predicciones acotadas y muestras pareadas entre modelos por fold.
- Reproducibilidad: configuración, semilla, código de generación, hashes de los
  resultados anteriores y artefactos intermedios de validación incluidos.

## Correcciones cerradas

1. El componente nacional se redefine como diferencia entre razones nacionales
   de sumas de las dos elecciones previas disponibles de la misma familia. No
   usa información futura ni promedia cambios estatales.
2. El residuo de entrenamiento se centra dentro de cada fold con ponderadores
   nominales preelectorales; las predicciones se recentran con la muestra de
   evaluación correspondiente.
3. Se comparan persistencia, cambio completo, modelo centrado sin contracción,
   seis niveles de contracción y el modelo heredado sobre muestras idénticas.
4. La selección se separa del uso operativo: la contracción 0.25 supera el gate
   interno de desarrollo, pero la persistencia permanece operativa por falta de
   validación externa.
5. Se elimina la corrección libre por ciclo estatal de la ruta operativa.
6. Los intervalos heredados y sus coberturas dejan de respaldar afirmaciones
   operativas. El bootstrap por entidad se conserva sólo como incertidumbre del
   backtest.
7. El score se limita a las 65,095 secciones A/B con evidencia local; el umbral
   p80 inclusivo selecciona 14,821 secciones e informa 3,867 empates.
8. Los perfiles P1–P3 se asignan únicamente a A/B. Las 5,656 secciones C/D
   permanecen sin perfil ni score local y conservan una procedencia jerárquica
   explícita.
9. Los 38 casos A/B sin agregado ECEG local conservan su perfil electoral local
   y etiquetan el descriptor ECEG como respaldo estatal.
10. Toda afirmación vigente queda vinculada a tablas, configuración y reglas
    legibles por máquina.

## Qué sí puede utilizarse

- El maestro como inventario seccional con identificadores, entidad, clase de
  linaje, procedencia y cobertura.
- Las participaciones históricas y la referencia histórica, respetando las
  columnas de disponibilidad y procedencia.
- `prediccion_operativa_2027` como baseline conservador de persistencia, no como
  pronóstico oficial.
- Los perfiles P1–P3 de secciones A/B para exploración descriptiva y formulación
  de hipótesis.
- Las métricas de backtest, sensibilidad y estratificación para revisión
  metodológica interna.

## Qué sigue siendo experimental

- La predicción centrada con contracción 0.25 y su agregado nacional de
  56.5381%.
- El score y la etiqueta de riesgo alto, incluido su umbral p80.
- Los perfiles P1–P3 como segmentación para análisis, no como clasificación
  causal o estable fuera de muestra.
- La magnitud puntual de caída y el escenario de electores adicionales no
  participantes.

## Qué no debe utilizarse

- El ajuste nacional heredado de aproximadamente +5.21 puntos porcentuales como
  si fuera un componente nacional estimado de manera válida.
- Los intervalos y coberturas heredados como garantía de incertidumbre.
- El score presidencial 2024 como probabilidad transferible a 2027 o 2030.
- Los perfiles para atribuir causas, recomendar intervenciones individuales o
  inferir características personales.
- Variables ECEG estatales como si fueran evidencia local para secciones C/D.
- La proyección experimental anterior de 57.31% como cifra vigente.

## Riesgos y pendientes externos

- Ejecutar validación externa independiente, con especificación y criterios
  congelados antes de abrir la muestra de evaluación.
- Incorporar o construir un crosswalk geográfico temporal validado para C/D
  antes de asignarles atributos o perfiles locales.
- Someter metodología, lenguaje y reglas de uso a revisión sustantiva por
  especialistas electorales y jurídicos.
- Reestimar sólo cuando existan nuevas fuentes preelectorales verificables y
  conservar la separación entre desarrollo y evaluación.

Hasta cerrar esos pendientes, cualquier comunicación debe denominar a este
paquete **handoff técnico validado internamente** y no “modelo final”, “candidato
ganador”, “pronóstico oficial” ni “sistema de alerta validado”.
