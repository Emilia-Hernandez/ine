# Reporte de limpieza y armonización provisional

Actualizado: 2026-10-05. Ejecución auditada: `artifacts/runs/20261005T223526Z-data-foundation` (`success`, 42.216 s).

## Resultado

La transformación produjo seis Parquet tipados bajo `data/interim/harmonized_demographic/` y conservó exactamente **54,872,712** filas. No excluyó registros. Los `record_id` son únicos, no hay conteos negativos ni categorías sin mapear, y en cada fila se conserva `LN = SV + NV + NS`.

| Año | Filas | Secciones observadas | Edad >100 | DEF nulo | DEL nulo | Denominador SV+NV=0 | SEXO=2 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2009 | 8,706,843 | 64,934 | 32,761 | 28,477 | 28,477 | 142,141 | 0 |
| 2012 | 8,604,456 | 65,599 | 10,318 | 15,677 | 15,677 | 9,839 | 0 |
| 2015 | 9,106,059 | 68,362 | 12,123 | 0 | 0 | 309,186 | 0 |
| 2018 | 9,251,122 | 68,408 | 10,320 | 0 | 0 | 363,901 | 0 |
| 2021 | 9,430,502 | 68,812 | 13,216 | 0 | 0 | 246,681 | 0 |
| 2024 | 9,773,730 | 70,751 | 12,891 | 0 | 20,912 | 323,984 | 105 |

Las banderas pueden traslaparse y no representan exclusiones. La bitácora máquina-legible está en `artifacts/tables/cleaning_exclusion_log.csv`.

## Indicadores

- participación: `SV/(SV+NV)`;
- abstención: `NV/(SV+NV)`;
- no especificado: `NS/LN`;
- cobertura identificada: `(SV+NV)/LN`;
- sensibilidad, nunca indicador oficial: `SV/LN`.

Se suman numeradores y denominadores antes de calcular cualquier razón. Cuando el denominador es cero, el cociente es nulo.

## Conciliación

El agregado provisional por elección y `section_key_observed` conserva exactamente las filas demográficas y los totales `LN`, `SV`, `NV` y `NS` de los seis archivos crudos. No se detectaron conflictos internos de municipio, distrito o tipo de sección dentro de una misma elección/código observado.

Entre 2021 y 2024 coinciden nominalmente 67,976 códigos; 836 aparecen sólo en 2021 y 2,775 sólo en 2024. Dentro de los códigos compartidos cambian municipio 190, distrito federal 13,183, distrito local 21,026 y tipo de sección 324 veces. Son comparaciones de metadatos, no pruebas geométricas.

## Decisión territorial

No se aplicó crosswalk. La página de cartografía especializada del INE señala que el Marco Geográfico Seccional y el Catálogo de Secciones deben solicitarse por acceso a la información. El reporte DERFE de 2023 aporta un conteo de referencia, pero no una correspondencia histórica a nivel de polígono.

Estado: capa limpia **aprobada**; panel longitudinal **no construido**; cartografía/crosswalk **pendiente**.
