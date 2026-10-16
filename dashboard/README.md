# Dashboard interactivo de participación electoral 2027

Aplicación local de una sola página para explorar las 70,751 secciones del handoff canónico
`handoff/FINAL_2027_MUNICIPAL/`. El mapa, los siete filtros, la ficha contextual y las cuatro
visualizaciones inferiores comparten un estado: perfiles activos, sección seleccionada y vista
geográfica. La navegación del mapa no modifica los agregados.

## Tecnología

- Python 3.12, Dash 3 y Plotly para la interfaz, callbacks y gráficas.
- Dash Leaflet con renderizador Canvas para zoom, pan, tooltip y selección.
- FlatGeobuf con índice espacial para solicitar únicamente el rectángulo visible.
- GeoPandas/Shapely para preparar copias simplificadas de visualización.
- Parquet/Zstandard para la tabla analítica en memoria.

No se ejecuta código de modelación desde el dashboard. Las predicciones, perfiles y señales se
leen tal como están en el handoff.

## Ejecutar

Desde la raíz del repositorio, con el entorno existente:

```bash
.venv/bin/python -m dashboard.app
```

Abrir <http://127.0.0.1:8050>. También puede usarse:

```bash
uv run python -m dashboard.app
# o
make dashboard
```

Para instalar únicamente las dependencias del dashboard en otro entorno Python 3.12:

```bash
python -m pip install -r dashboard/requirements.txt
```

## Fuentes y cobertura

La proyección y tipología provienen de `handoff/FINAL_2027_MUNICIPAL/SECCIONES_ELECTORALES_2027.csv`,
versión `radar27-final-2027-municipal.1`. La proyección central seleccionada es el Modelo A,
con componente nacional y corrección territorial centrada. El dashboard no usa las alternativas
municipales B/C como proyección central.

La cartografía proviene de `data/raw/public_ine/ine_secciones_2025_portal.zip`: snapshot del INE
creado el 9 de mayo de 2024. Sus 70,751 claves del universo canónico empatan 1:1; las dos
geometrías del archivo que no pertenecen al universo final se excluyen. Esta referencia no es
geometría certificada para 2027.

Las observaciones electorales usan conteos seccionales directos 2009, 2012, 2015, 2018, 2021 y
2024 de `artifacts/tables/provisional_section_year_totals.parquet`. Las tasas agregadas son razones
de sumas de votos y denominadores válidos. El segmento proyectado parte de la referencia
comparable 2021 del modelo y no de la elección presidencial de 2024.

La edad y el sexo describen el electorado identificado en los conteos censales INE 2024; no se
presentan como población residente. Tienen medición seccional directa para 58,534 secciones.
Las variables de población, actividad, escolaridad y vivienda provienen de ECEG 2020 y cubren
67,976 secciones. Cada panel muestra período, universo y cobertura; no se imputan valores
estatales como mediciones locales.

## Perfiles y colores

El orden cromático es tipológico, no una probabilidad continua de abstención:

| ID | Perfil | Color |
|---|---|---|
| P1 | Deterioro persistente | Vino oscuro |
| P2 | Deterioro proyectado | Rojo oscuro |
| P3 | Rezago persistente | Terracota |
| P4 | Recuperación | Naranja suave |
| P5 | Favorable y estable | Arena |
| P6 | Variable o no diferenciada | Beige claro |
| EI | Evidencia insuficiente | Gris casi blanco, con contorno tenue |

Las definiciones exactas, reglas y limitaciones están en
`handoff/FINAL_2027_MUNICIPAL/RESUMEN_PERFILES.csv` y
`handoff/FINAL_2027_MUNICIPAL/GUIA_PARA_POLITOLOGOS.md`.

## Uso de la interfaz

1. Todas las categorías inician activas. Marque o desmarque perfiles en la columna izquierda;
   `Todos`, `Limpiar` y `Restaurar` administran la selección.
2. Use rueda, controles `+`/`−` o arrastre para navegar. El botón de casa recupera la vista
   nacional. El zoom nunca filtra las estadísticas.
3. Al acercarse, pase el cursor sobre una sección para ver su ficha breve y haga clic para
   seleccionarla. El borde azul identifica la sección activa sin recentrar el mapa.
4. `Limpiar selección` regresa a los agregados de los perfiles que continúan activos. Si se
   desactiva el perfil de la sección activa, la selección se limpia automáticamente.
5. Edad y sexo son distribuciones del electorado identificado 2024; el tooltip muestra también
   su participación. El selector sociodemográfico cambia el indicador ECEG. La serie temporal
   distingue intermedias, presidenciales y la proyección 2027.

## Rendimiento

La geometría nunca viaja dentro de un callback de filtros. El navegador carga una capa nacional
simplificada a 900 m y, a partir de zoom 7, consulta por bounding box una capa de 75 m. Ambas
son copias de visualización indexadas en FlatGeobuf; las fuentes originales permanecen intactas.
Los filtros se aplican en el cliente, las líneas estatales se sirven una sola vez y los agregados
se calculan sobre un Parquet local en memoria. La selección y los cambios de perfil no reinician
el viewport.

## Actualizar los datos

Si se regenera el handoff, confirme primero que continúa siendo la versión canónica y ejecute:

```bash
.venv/bin/python -m dashboard.prepare_data
.venv/bin/pytest -q dashboard/tests
```

El preparador falla ante duplicados, pérdida de la relación 1:1, perfiles desconocidos o un
universo distinto. Genera:

- `dashboard/data/dashboard_sections.parquet`;
- `dashboard/data/manifest.json`;
- `dashboard/assets/sections_overview.fgb`;
- `dashboard/assets/sections_detail.fgb`;
- `dashboard/assets/state_boundaries.geojson`.

No ejecute pipelines predictivos para actualizar la interfaz: el insumo autorizado es el
handoff ya generado.

## Pruebas

```bash
.venv/bin/pytest -q dashboard/tests
```

Las pruebas verifican universo, unicidad, conteos por perfil, cifras nacionales, filtros vacíos,
selección/limpieza, conmutación de detalle cartográfico, renderizado de callbacks y validez de
las 70,751 geometrías en ambos niveles.

## Limitaciones

- 2027 es una proyección de trabajo, no un resultado observado ni una inferencia causal.
- El snapshot territorial es una referencia 2024, no cartografía certificada para 2027.
- Las observaciones históricas directas por código no constituyen por sí mismas un crosswalk
  longitudinal para secciones modificadas.
- La edad/sexo electoral y la población residente ECEG tienen universos distintos y se muestran
  en paneles diferenciados.
- Donde no existe medición seccional defendible, el dashboard muestra “No disponible”; no
  sustituye silenciosamente con promedios estatales.
