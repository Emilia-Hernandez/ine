# Votar entre Balas: integración municipal reproducible

## Alcance y decisión de modelado

Esta integración añade al dashboard un contexto municipal descriptivo de violencia
político-criminal. No modifica el pronóstico, los perfiles ni el release publicado. El puntero
`dashboard/data/current_release.json` permanece en `radar27-dashboard-security.5`, con modelo
`radar27-final-2027-municipal.1 / A_nacional_actual`. La copia de trabajo se activa únicamente con
`RADAR27_DASHBOARD_WORKING_COPY=1`.

Sandra Ley (2018), *To Vote or Not to Vote: How Criminal Violence Shapes Electoral
Participation*, aporta una motivación sustantiva: la violencia estratégica de organizaciones
criminales contra autoridades y candidaturas puede asociarse con desmovilización electoral. No
se traslada ese resultado como efecto causal al pronóstico 2027. La base disponible sólo permite
construir retrospectivamente cortes electorales comparables para 2021 y 2024, mientras el corte
2018 contiene apenas 35 eventos municipales antes del 30 de abril. Además, el snapshot actual no
permite probar cuándo se publicó cada registro histórico. Por ello no hay base suficiente para
estimar y validar fuera de muestra una mejora incremental sin riesgo de filtración temporal.

Las covariables quedan preparadas en `municipal_features_asof.parquet`. Una evaluación futura
debe usar elecciones completas como particiones temporales, nunca una división aleatoria entre
secciones, y snapshots archivados que acrediten disponibilidad en cada fecha de predicción.

## Fuente, versión y temporalidad

- Fuente: Data Cívica, México Evalúa y Animal Político, *Votar entre Balas*.
- Descarga oficial: `https://votarentrebalas.datacivica.org/app/download_zip`.
- Descargado: 2026-10-24 18:13:34 UTC.
- Corte analítico configurable: 2026-10-24.
- Último acontecimiento observado: 2026-09-29.
- Cobertura real del CSV: 2017-12-29 a 2026-09-29. La metodología publicada describe cobertura
  desde 2018; el único registro de 2017 se conserva y se reporta, no se oculta ni recodifica.
- El CSV no incluye fecha de publicación o alta del registro; `fecha` es la fecha del
  acontecimiento. Los cortes históricos son reconstrucciones por fecha del hecho, no snapshots
  históricos estrictamente *as-of*.

Los hashes SHA-256, URL, fecha de descarga y rutas se registran en
`data/manifests/votar_entre_balas_source_manifest.json`. Los originales se preservan sin editar en
`data/raw/votar_entre_balas/2026-10-24/`; la versión derivada es
`radar27-votar-entre-balas-2026-10-24.1`.

## Unidad de observación y limpieza

El CSV contiene 3,368 filas, de las cuales 286 son filas finales completamente vacías. Las 3,082
filas sustantivas representan personas o instalaciones atacadas, no necesariamente eventos
únicos. Hay 2,604 valores distintos y no nulos de `id_evento`; una fila carece de ese identificador
y queda en la auditoría, fuera de los conteos. Un evento puede tener varias víctimas o tipos de
ataque: 296 eventos ocupan más de una fila, con un máximo de 16. Por tanto:

- la unidad del indicador es `COUNT(DISTINCT id_evento)`;
- no se deduplica por nombre, fecha o municipio;
- se conserva una tabla limpia a nivel víctima/instalación y otra a nivel evento;
- un evento es municipal si al menos una de sus filas tiene `nivel_gob = Municipal`;
- los 67 eventos con más de un `tipo_evento` conservan todas sus categorías, sin sumarlas como
  ataques adicionales.

Las seis categorías documentadas y validadas son amenaza, atentado, ataque armado,
desaparición, secuestro y asesinato. La fuente también aporta víctima, género, afiliación/cargo,
nivel y área de gobierno, presunto agresor, fecha, entidad y municipio. Una fila carece de clave
municipal INEGI; no se le asigna geografía por nombre.

## Variables derivadas

Para cada municipio y fecha de corte se generan:

| Variable | Definición |
|---|---|
| `municipal_attacks_cumulative` | Eventos distintos hasta el corte con al menos un objetivo municipal. |
| `municipal_attacks_12m` | La misma medida en `(corte - 12 meses, corte]`. |
| `municipal_attacks_24m` | La misma medida en `(corte - 24 meses, corte]`. |
| `municipal_attacks_YYYY` | La misma medida dentro del año calendario, limitada por el corte. |
| `territorial_attacks_all_levels_*` | Eventos distintos ocurridos en el municipio, sin filtrar nivel de gobierno. Medida alternativa, nunca sumada a la principal. |

El año 2026 termina en el corte y se marca incompleto. Cero significa que existe correspondencia
geográfica pero la fuente no registra eventos en la ventana. Ausencia de correspondencia se
representa como nulo y `municipality_crosswalk_unavailable`, nunca como cero.

La interfaz permite filtrar con `municipal_attacks_cumulative` o `municipal_attacks_24m`. El
control selecciona secciones cuyo valor municipal sea menor o igual al umbral entero. Su máximo
es el máximo observado para el periodo activo. En el máximo el filtro es neutro y conserva las
secciones sin dato, identificadas en la ayuda; en cualquier umbral menor se excluyen. La selección
del mapa, los agregados y el CSV aplican la misma regla. Las demás medidas preparadas permanecen
en el pipeline para futuros análisis.

## Correspondencia geográfica y cobertura

Las claves municipales de la fuente son INEGI; las del handoff son claves electorales INE y no
son intercambiables. El cruce principal usa el catálogo oficial comparativo
`cat_municipios_2020_INEGI-INE-ECEG.xlsx`. Sus relaciones muchos-a-uno se preservan cuando más de
un municipio geoestadístico corresponde a un municipio electoral. Para municipios creados después
del catálogo sólo se permite una coincidencia exacta del nombre normalizado, única dentro de la
entidad; no se usa emparejamiento difuso.

- 844 claves municipales INEGI aparecen en la fuente y las 844 se cruzan.
- 2,603 de 2,604 eventos se asignan a un municipio electoral; uno queda sin asignar por falta de
  clave municipal en la fila fuente.
- El handoff contiene 2,477 municipios electorales: 2,469 tienen puente y ocho no lo tienen.
- 70,615 de 70,751 secciones tienen contexto municipal verificable; 136 quedan no disponibles.
- La medida principal acumula 2,052 eventos municipales; 2,051 se asignan al universo del
  dashboard. La alternativa acumula 2,604 eventos; 2,603 se asignan.

Cada valor municipal se repite como contexto en las secciones que pertenecen al municipio. Esa
repetición sirve sólo para consulta: los totales se calculan antes del join municipal–sección y
nunca se suman sobre las filas seccionales. Un ataque asociado al municipio no implica que haya
ocurrido en la sección seleccionada.

Como comprobación manual contra el CSV original, se recalcularon `acumulado / 12 meses / 2025 /
2026` para tres municipios: Acapulco de Juárez `22 / 1 / 7 / 1`, Cuernavaca `13 / 1 / 2 / 0` y
Celaya `43 / 0 / 8 / 0`. Los cuatro valores de cada municipio coinciden con las salidas del
pipeline; los conteos anuales usan 2026 sólo hasta la fecha de corte.

## Archivos y actualización

Configuración: `configs/votar_entre_balas.yaml`. Entrada: ZIP/CSV/PDF originales, catálogo
INEGI–INE y universo seccional canónico. Salidas reproducibles en
`artifacts/security/radar27-votar-entre-balas-2026-10-24.1/`:

- `clean_victim_records.parquet`;
- `events.parquet`;
- `municipality_crosswalk.parquet`;
- `municipal_features_asof.parquet`;
- `municipal_attacks_annual.parquet`;
- `section_veb_context.parquet`;
- `unmatched_records.csv`, `source_municipality_crosswalk_audit.csv` y `MANIFEST.json`.

Ejecución:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_votar_entre_balas.py \
  --config configs/votar_entre_balas.yaml
.venv/bin/python dashboard/prepare_data.py
RADAR27_DASHBOARD_WORKING_COPY=1 .venv/bin/python -m dashboard.app
```

Para actualizar, guarde un nuevo snapshot fechado, cambie versión/rutas/corte en el YAML y vuelva
a ejecutar. No sobrescriba un snapshot ni extienda el corte sin revisar cambios de esquema,
categorías, duplicados y geografía.

## Limitaciones interpretativas

La metodología de Votar entre Balas usa notas periodísticas localizadas mediante búsqueda
automatizada y revisión manual, y exige consistencia entre fuentes. Aun así, no es un censo:
puede haber subregistro, diferencias territoriales en cobertura mediática, retrasos de publicación
y cambios en la capacidad de detección. Ausencia de registros no prueba ausencia de violencia.
Tampoco se infiere causalidad sobre participación electoral. El indicador complementa, pero no
reemplaza, la tasa municipal SESNSP ya mostrada por el dashboard.

## Auditoría local y publicación

La integración se desarrolló en `codex/votar-entre-balas-integration`, creada desde el commit
local `7d0a5a98a6f4de00c91d0af02bb0c36c639f9eb7`. Había cambios locales previos y se preservaron.
El mismo commit era la punta observada de `origin/codex/render-free-deploy`, pero la configuración
del repositorio no acredita qué commit ejecuta Render; no se asume equivalencia. No se hizo push,
deploy ni cambio de configuración o variables de producción.

## Referencias

- Data Cívica, México Evalúa y Animal Político (2024), *Votar entre Balas*.
- Ley, Sandra (2018), “To Vote or Not to Vote: How Criminal Violence Shapes Electoral
  Participation”, *Journal of Conflict Resolution*, 62(9), 1963–1990,
  DOI: 10.1177/0022002717708600.
