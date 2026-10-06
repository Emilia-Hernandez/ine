# Auditoría inicial de datos

Evidencia principal: `notebooks/01_raw_schema_audit.ipynb`, ejecución combinada exitosa `20261005T222756Z-phase1`.

## Volumen y unidad

| Año | CSV | Filas | Secciones nominales | Municipios nominales | LN agregada |
|---:|---:|---:|---:|---:|---:|
| 2009 | 32 | 8,706,843 | 64,934 | 2,458 | 77,481,831 |
| 2012 | 32 | 8,604,456 | 65,599 | 2,455 | 76,490,962 |
| 2015 | 32 | 9,106,059 | 68,362 | 2,458 | 83,563,462 |
| 2018 | 32 | 9,251,122 | 68,408 | 2,463 | 89,123,997 |
| 2021 | 32 | 9,430,502 | 68,812 | 2,468 | 93,532,133 |
| 2024 | 32 | 9,773,730 | 70,751 | 2,477 | 98,330,348 |

Total: **54,872,712 filas**. La clave candidata `AELEC × EDOCVE × SECCION × SEXO × EDAD` es única en todos los años. No se detectaron duplicados exactos.

## Formato físico

- 2009–2021: UTF-8 sin BOM, fin de línea LF;
- 2024: UTF-8 con BOM, fin de línea CRLF;
- separador coma y comillas dobles; nombres municipales pueden contener comas;
- 16 columnas comunes en los seis años;
- lectura conservadora como texto antes de conversión explícita;
- 192 archivos, 3,727,157,564 bytes extraídos.

## Integridad

- `LN = SV + NV + NS` en las 54,872,712 filas; cero discrepancias;
- cero `LN=0`;
- existen filas con `SV+NV=0`: 142,141 (2009), 9,839 (2012), 309,186 (2015), 363,901 (2018), 246,681 (2021) y 323,984 (2024); su participación oficial es no definida a esa granularidad;
- vacíos documentados en `DEF`/`DEL`, no imputados;
- 2024 contiene `SEXO=2` con LN=105; la categoría no existe en versiones anteriores;
- edades observadas hasta 140; los valores >100 se conservan y se marcan para aclaración documental.

## Comparabilidad territorial nominal

| Par | Compartidos | Sólo año previo | Sólo año actual |
|---|---:|---:|---:|
| 2009–2012 | 63,789 | 1,145 | 1,810 |
| 2012–2015 | 65,378 | 221 | 2,984 |
| 2015–2018 | 68,361 | 1 | 47 |
| 2018–2021 | 67,633 | 775 | 1,179 |
| 2021–2024 | 67,976 | 836 | 2,775 |

Entre los 67,976 códigos compartidos 2021–2024 cambian 190 asignaciones de municipio, 13,183 de distrito federal, 21,026 de distrito local y 324 tipos de sección. Parte del cambio distrital es consistente con marcos DERFE distintos, pero esto es una hipótesis hasta validar catálogos/crosswalks.

## Hechos, hipótesis y preguntas

**Hechos comprobados:** esquemas de 16 campos iguales; granularidad sección × sexo × edad; conciliación exacta; ausencia de columnas indígena/afromexicana; categorías y vacíos descritos; marcos distritales documentados distintos.

**Hipótesis:** los referentes indígena/afromexicano y parte de la armonización del tablero provienen de catálogos externos; los cambios distritales reflejan redistritación; edades extremas pueden ser edades reales, errores o reglas no documentadas.

**Pendientes:** localizar catálogos y crosswalks oficiales; determinar marco de sección por archivo; aclarar edades >100; explicar vacíos de distritos; contrastar agregados con el dashboard bajo filtros idénticos; decidir retrospectiva en cartografía común frente a backtest históricamente estricto.
