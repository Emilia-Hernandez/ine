# Diccionario de datos limpio

Unidad observada comprobada: **elección × entidad × sección × sexo × edad**, distribuida en un CSV por entidad. No hay casilla, fila “Total” ni porcentajes publicados en estos archivos.

| Campo | Definición documental | Tipo conservador | Observaciones iniciales |
|---|---|---|---|
| `AELEC` | Año de elección | texto → entero validado | Un único año correcto por ZIP. |
| `FELECCION` | Fecha de jornada electoral | texto | Formatos distintos entre versiones; no parsear sin regla explícita. |
| `EDOCVE` | Clave INE de entidad | texto | Valores 1–32; preservar como ID, no como medida. |
| `EDONOM` | Nombre de entidad | texto | No usar como llave. |
| `MPIOCVE` | Clave INE de municipio | texto | Cambios territoriales posibles entre años. |
| `MPIONOM` | Nombre de municipio | texto | Contiene comas citadas en algunos registros; parser CSV debe respetar comillas. |
| `SECCION` | Sección electoral en el año correspondiente | texto | Repetir código no demuestra polígono idéntico. |
| `TIPOSEC` | U urbana, M mixta, R rural | categoría | Las tres categorías aparecen en cada año. |
| `DEF` | Distrito electoral federal | texto | Marco DERFE 2021 en 2009–2021; DERFE 2023 en 2024. Hay 28,477 vacíos en 2009 y 15,677 en 2012. |
| `DEL` | Distrito electoral local | texto | Mismos marcos documentados; 28,477 vacíos en 2009, 15,677 en 2012 y 20,912 en 2024. |
| `SEXO` | 0 hombres, 1 mujeres; 2 no binario en 2024 | categoría | `2` aparece sólo en 2024: 105 filas y LN=105. Antes es categoría no disponible, no cero. |
| `EDAD` | Años cumplidos al día de la elección | entero auditado | Rango observado 18–140. Hay registros >100 en todos los años; el manual agrupa 100+, pero el TXT no explica top-coding ni extremos. No recodificar aún. |
| `LN` | Lista nominal de cuadernillos catalogados | entero no negativo | Mínimo observado 1. |
| `SV` | Registros con marca de voto | entero no negativo | Puede ser cero. |
| `NV` | Registros sin marca de voto | entero no negativo | Puede ser cero. |
| `NS` | Participación no especificada | entero no negativo | No es abstención ni voto nulo. |

Campos mostrados por el tablero pero ausentes de los CSV generales: referente indígena, referente afromexicano y porcentajes publicados. Su origen debe localizarse en catálogos/enriquecimientos oficiales antes de utilizarlos. No deben interpretarse como atributos individuales.

## Campos canónicos producidos en el notebook 02

| Campo | Tipo | Definición |
|---|---|---|
| `election_year` | entero | Año validado contra `AELEC`. |
| `election_family` | texto | `midterm` o `presidential`, configurado. |
| `election_date` | fecha | Jornada ISO validada contra el literal fuente. |
| `source_election_date` | texto | `FELECCION` intacta para trazabilidad. |
| `entity_id`, `municipality_id`, `section_number` | texto | IDs serializados a 2, 3 y 4 dígitos. |
| `municipality_key_observed`, `section_key_observed` | texto | Claves compuestas válidas dentro de una elección; no armonizadas entre años. |
| `district_federal_id`, `district_local_id` | texto nulo | Dos dígitos cuando existen; vacíos fuente como nulo. |
| `section_type_code`, `section_type` | categoría | Código fuente y etiqueta española. |
| `sex_code`, `sex` | categoría | Código fuente y etiqueta; no binario sólo donde está observado. |
| `age`, `age_review_flag` | entero, booleano | Edad fuente y bandera `age > 100`. |
| `nominal_list`, `voted`, `did_not_vote`, `unspecified` | entero | Conteos fuente tipados. |
| `identified_records` | entero | `voted + did_not_vote`. |
| `participation`, `abstention` | decimal nulo | Razones sobre registros identificados. |
| `unspecified_share`, `identified_coverage` | decimal nulo | Razones sobre lista nominal. |
| `voted_over_nominal_sensitivity` | decimal nulo | Sensibilidad `SV/LN`, no participación oficial. |
| `record_id` | texto | Llave única de fila: año, entidad, sección, sexo y edad. |
| `source_file` | texto | CSV estatal de procedencia. |

Véase `docs/ID_CONTRACT.md` para límites y reglas de serialización.
