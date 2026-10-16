# Linaje de datos y controles de integridad

## Alcance

Esta revisión reconstruye el trayecto de datos a partir de los archivos locales, manifiestos, código y artefactos existentes. No ejecutó el pipeline completo porque éste sobrescribe `data/interim/` y `artifacts/`, lo que habría modificado evidencia original. Los cálculos independientes se guardaron únicamente en `audit/`.

## Flujo reconstruido

| Etapa | Entrada | Transformación principal | Salida observada | Control de auditoría |
|---|---|---|---|---|
| 1. Fuentes | CCPC 2009, 2012, 2015, 2018, 2021 y 2024; manual/cartografía | Descarga o incorporación manual | Archivos declarados en manifiesto | Siete archivos locales verificados por SHA-256 |
| 2. Extracción | Archivos CCPC | Normalización de columnas, entidad, sección, casilla y resultados | 54,872,712 registros de casilla | Conteos por elección y esquema revisados |
| 3. Agregación seccional | Casillas normalizadas | Suma de votos y lista nominal por sección-año | 64,934; 65,599; 68,362; 68,408; 68,812; 70,751 secciones por ciclo | Fórmula de participación contrastada con manual |
| 4. Armonización geográfica | Secciones históricas + equivalencias | Asignación a unidad de evaluación, clase A/B/C/D y confianza | Unidades comparables por ciclo | Llaves, duplicados, cobertura y clases conciliadas |
| 5. Mart temporal | Resultados históricos + competencia, concurrencia y contexto | Variables disponibles antes del target | 243,108 filas sección/unidad-año | Cero casos con `max_electoral_feature_year >= target_year` |
| 6. Backtesting | Mart temporal | Folds por año objetivo, persistencia y modelos tabulares | Predicciones 2018, 2021 y 2024 | Auditoría pareada independiente A–D |
| 7. Adaptación | Predicción base + shift + corrección estatal | Contracción del residual, suma de ajustes, recorte [0,1] | Predicción por unidad | Descomposición y muestras auditadas |
| 8. Desagregación | Unidades + secciones objetivo | Replicación/redistribución a sección 2024 | 70,751 predicciones seccionales | Llave única y rango [0,1] |
| 9. Riesgo | Predicciones históricas y finales | Clasificación de caída ≥2 pp y calibración | Probabilidades y magnitudes | Clase positiva, columna probabilística, AUC/Brier y calibración verificados |
| 10. Perfiles | Conteos CCPC + ECEG + reglas | Factores, arquetipos y fallback estatal | 70,751 perfiles | Conciliación específica de 38 secciones |
| 11. Priorización | Riesgo, caída y lista nominal | Percentiles/rangos | Banderas de riesgo y volumen | Empates, ceros y alternativas p80 recalculados |
| 12. Documentos | Tablas y gráficos derivados | Narrativa DOCX | 4 documentos en `deliverables/` | Renderizado visual de las 79 páginas y contraste de cifras |

## Volumen por elección

| Año | Filas de casilla | Secciones agregadas |
|---:|---:|---:|
| 2009 | 8,706,843 | 64,934 |
| 2012 | 8,604,456 | 65,599 |
| 2015 | 9,106,059 | 68,362 |
| 2018 | 9,251,122 | 68,408 |
| 2021 | 9,430,502 | 68,812 |
| 2024 | 9,773,730 | 70,751 |
| **Total** | **54,872,712** | — |

## Fórmula y unidades

La participación oficial se reconstruye como `SV / (SV + NV)`. `NS` no se incorpora al denominador ni se interpreta como abstención. Los pesos de evaluación son los registros identificados del año objetivo. Es importante no confundir tres objetos:

- agregado nacional por razón de sumas: `sum(SV) / sum(SV + NV)`;
- media ponderada de tasas seccionales o de unidades comparables;
- promedio simple de tasas.

El repositorio llama “nacional” al segundo objeto para el ajuste 2015→2021. Ésa es la fuente de la discrepancia de 0.4505 pp documentada en la auditoría.

## Geografía y cobertura

La salida final tiene 70,751 llaves únicas:

| Clase | Secciones | Interpretación operativa |
|---|---:|---|
| A | 58,534 | enlace de alta confianza |
| B | 6,561 | unidad agregada comparable |
| C | 1,865 | historia corta o enlace limitado |
| D | 3,791 | sin historia comparable suficiente |

La conciliación ECEG separa correctamente 65,095 secciones A/B de 65,057 A/B con descriptor ECEG agregado. Las 38 restantes conservan historia electoral local, pero usan referencia ECEG estatal. No son filas perdidas ni duplicadas.

Advertencia: 3,630 secciones C/D reciben descriptor ECEG por coincidencia directa de código 2020–2024. La igualdad de código no prueba continuidad territorial; sin geometrías o crosswalk certificado, debe etiquetarse como coincidencia no validada.

## Controles ejecutados

- Llave final única y conteo de 70,751: PASS.
- Distribución A/B/C/D: PASS.
- Probabilidades y predicciones en [0,1]: PASS.
- Llave mart `target_year + evaluation_unit_id`: PASS.
- Orden temporal de variables electorales: PASS.
- Hash local de siete fuentes declaradas: PASS.
- Ausencia de duplicados en la lista de 38 casos: PASS.

El detalle máquina-legible está en `results/integrity_checks.csv` y la conciliación de geografía en `results/eceg_reconciliation_summary.csv`.

## Riesgos de trazabilidad

1. `deliverables/` no está versionado; no existe una cadena de commit → artefacto → hash de entrega.
2. Conviven versiones largas y cortas sin designación inequívoca de documento canónico.
3. El README reporta 93 pruebas, mientras la ejecución actual contiene 100.
4. El snapshot final usa geografía 2024 para una predicción 2027; la evidencia AMGE inventariada llega a 2022.
5. No se verificó la fuente remota contra el servidor original en la fecha de auditoría; se verificó su integridad local contra el manifiesto.

