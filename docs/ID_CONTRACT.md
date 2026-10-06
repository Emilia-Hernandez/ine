# Contrato de identificadores

Actualizado: 2026-10-05. Implementación: `src/radar27/clean/harmonize.py` y `configs/harmonization.yaml`.

## Alcance

Este contrato normaliza la **serialización** de los identificadores observados en cada elección. No crea una clave maestra territorial ni afirma que dos secciones con el mismo código tengan el mismo polígono en años distintos.

| Campo canónico | Regla | Ejemplo | Alcance |
|---|---|---|---|
| `entity_id` | entero fuente, texto de 2 dígitos | `09` | elección fuente |
| `municipality_id` | entero fuente, texto de 3 dígitos | `002` | dentro de entidad y elección |
| `municipality_key_observed` | `entity_id:municipality_id` | `09:002` | elección fuente |
| `section_number` | entero fuente, texto de 4 dígitos | `0123` | dentro de entidad y elección |
| `section_key_observed` | `entity_id:section_number` | `09:0123` | elección fuente |
| `district_federal_id` | texto de 2 dígitos o nulo fuente | `05` | marco DERFE documentado por archivo |
| `district_local_id` | texto de 2 dígitos o nulo fuente | `12` | marco DERFE documentado por archivo |
| `record_id` | `año:entidad:sección:sexo:edad(3)` | `2024:09:0123:1:034` | fila demográfica única |

Los ceros a la izquierda son una decisión de representación reversible. Los rangos se validaron contra los valores observados, pero los anchos no sustituyen un catálogo geográfico oficial.

## Contrato temporal

`FELECCION` no se parsea de forma automática. Cada año debe coincidir exactamente con su literal fuente y se mapea a una fecha ISO configurada. Esto evita interpretar `06/02/2024` como 6 de febrero cuando la jornada fue el 2 de junio.

| Año | Literal fuente | Fecha ISO | Familia |
|---:|---|---|---|
| 2009 | `5/7/2009` | `2009-07-05` | intermedia |
| 2012 | `1/7/2012` | `2012-07-01` | presidencial |
| 2015 | `7/6/2015` | `2015-06-07` | intermedia |
| 2018 | `1/7/2018` | `2018-07-01` | presidencial |
| 2021 | `6/6/2021` | `2021-06-06` | intermedia |
| 2024 | `06/02/2024` | `2024-06-02` | presidencial |

## Nulos y categorías

- `DEF` y `DEL` vacíos permanecen nulos; no se imputan.
- `SEXO=0/1/2` se etiqueta hombre/mujer/no binario sin crear la categoría `2` en años donde no existe.
- `TIPOSEC=U/M/R` se etiqueta urbana/mixta/rural.
- edades mayores de 100 se conservan con `age_review_flag=true`.
- razones con denominador cero quedan nulas.
- ninguna fila se excluye en esta fase.

## Estado longitudinal

`section_key_observed` es libre de colisiones dentro de cada elección, pero **no es** `harmonized_section_id`. El informe DERFE del segundo trimestre de 2023 reporta 69,548 secciones, frente a 70,751 códigos observados en la fuente CCPC 2024. Además, la documentación fuente usa marcos distritales DERFE 2021 para 2009–2021 y DERFE 2023 para 2024.

No existe en el proyecto una geometría ni un crosswalk oficial validado. Por ello:

- `provisional_section_year_totals.parquet` sólo agrega por código observado;
- no se permite usarlo como panel territorial definitivo;
- no se asignan referentes indígena o afromexicano ausentes de los CSV;
- la siguiente acción territorial es solicitar y validar los productos cartográficos especializados del INE.
