# Dashboard interactivo de participación electoral 2027

RADAR 27 se publica como dos aplicaciones Dash independientes que comparten los artefactos
versionados del repositorio: el Explorador territorial y el Simulador de intervenciones. Cada
proceso registra solamente su layout y sus callbacks. El release vigente se resuelve desde
`dashboard/data/current_release.json`.

## Tecnología

- Python 3.12, Dash 3 y Plotly para la interfaz, callbacks y gráficas.
- Dash Leaflet con renderizador Canvas para zoom, pan, tooltip y selección.
- FlatGeobuf con índice espacial para solicitar únicamente el rectángulo visible.
- GeoPandas/Shapely para preparar copias simplificadas de visualización.
- Parquet/Zstandard para la tabla analítica en memoria.

No se ejecuta código de modelación desde el dashboard. Las predicciones, perfiles y señales se
leen tal como están en el handoff.

## Ejecutar

Desde la raíz del repositorio, con el entorno existente, arranque cada aplicación en una terminal:

```bash
.venv/bin/python -m dashboard.app
.venv/bin/python -m dashboard.simulator_app
```

El Explorador queda en <http://127.0.0.1:8050> y el Simulador en
<http://127.0.0.1:8051>. `RADAR27_EXPLORER_URL` y `RADAR27_SIMULATOR_URL` permiten cambiar los
enlaces entre servicios; en local se usan esos dos valores por defecto y en Render se usan las
URLs de producción.

Para instalar únicamente las dependencias del dashboard en otro entorno Python 3.12:

```bash
python -m pip install -r dashboard/requirements.txt
```

Los arranques de producción son:

```bash
gunicorn dashboard.explorer_app:server --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 120 --access-logfile - --error-logfile -
gunicorn dashboard.simulator_app:server --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 120 --access-logfile - --error-logfile -
```

Cada servicio expone su propio `/healthz`. Durante la primera etapa, `render.yaml` queda limitado
al nuevo servicio `radar27-simulador` para no modificar accidentalmente el `radar27` vigente.

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

La densidad usa `VIVPAR_HAB` de ECEG 2020 y el área de los polígonos INE del snapshot 2024,
calculada en EPSG:6933. Para evitar falsas equivalencias territoriales sólo se consideran
válidas 58,530 secciones estables clase A; 12,217 secciones B–D y cuatro valores censales
negativos quedan etiquetados y excluidos cuando el filtro es menor a 100%. La metodología
completa está en `docs/DENSITY_FILTER_METHOD.md`.

La incidencia usa SESNSP municipal 2025 y población municipal CONAPO a mitad de año. Es un
contexto municipal asignado a secciones, no una medición dentro de cada sección. Tiene cobertura
en 70,450 secciones; las 301 faltantes se incluyen cuando el filtro está en 100% y quedan fuera
en selecciones restrictivas. Véase `docs/SECURITY_METHODOLOGY.md`.

El filtro **Ataques político-criminales en el municipio**, bajo incidencia delictiva, usa Votar
entre Balas, de Data Cívica, con corte configurable al 24 de octubre de 2026. Cuenta `id_evento`
distintos con al menos una persona o instalación de nivel municipal. El selector ofrece acumulado
histórico y últimos 24 meses. El umbral entero conserva secciones con un valor municipal menor o
igual: en cero sólo municipios con cero eventos registrados. En el máximo se conservan también
las 136 secciones sin cruce municipal; con un umbral menor quedan excluidas. El conteo se usa como
contexto municipal de cada sección y no localiza ataques dentro de ella. La ficha derecha muestra
un resumen compacto. Véase `docs/VOTAR_ENTRE_BALAS_METHODOLOGY.md`.

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
| EI-A/B | Historia electoral incompleta | Amarillo dorado |
| EI-C/D | Comparabilidad territorial no validada | Amarillo claro |

EI-A/B (3,706) y EI-C/D (5,656) son categorías visuales; ambas conservan `EI` como estado
de evidencia insuficiente, no como séptimo perfil sustantivo.

Las definiciones exactas, reglas y limitaciones están en
`handoff/FINAL_2027_MUNICIPAL/RESUMEN_PERFILES.csv` y
`handoff/FINAL_2027_MUNICIPAL/GUIA_PARA_POLITOLOGOS.md`.

## Uso de la interfaz

1. Todas las categorías inician activas. Marque o desmarque perfiles en la columna izquierda;
   `Todos`, `Limpiar` y `Restaurar` administran la selección.
2. Densidad conserva el porcentaje superior del ranking nacional fijo. Seguridad conserva el
   porcentaje inferior y respeta completos los empates municipales. Ambos van de 1% a 100%;
   100% es neutro. `Restaurar` devuelve ambos a 100%.
3. El contador y el CSV usan la intersección exacta de perfiles, densidad y seguridad. El archivo
   contiene una fila única por sección y metadatos JSON de los filtros.
4. Use rueda, controles `+`/`−` o arrastre para navegar. El botón de casa recupera la vista
   nacional. El zoom nunca filtra las estadísticas.
5. Al acercarse, pase el cursor sobre una sección para ver su ficha breve y haga clic para
   seleccionarla. El borde azul identifica la sección activa sin recentrar el mapa.
6. `Limpiar selección` regresa a los agregados de los filtros que continúan activos. Si se
   desactiva el perfil de la sección activa, la selección se limpia automáticamente.
7. Edad y sexo son distribuciones del electorado identificado 2024; el tooltip muestra también
   su participación. El selector sociodemográfico cambia el indicador ECEG. La serie temporal
   distingue intermedias, presidenciales y la proyección 2027.
8. Seleccione el periodo y arrastre el control de ataques bajo incidencia. El máximo depende del
   periodo; al cambiarlo, un valor que lo supere se ajusta al nuevo máximo. El mapa, contador,
   resúmenes y CSV usan el mismo umbral. “Cero” significa ningún evento registrado para la medida
   y periodo; “sin dato” significa falta de cruce municipal verificable.

## Simulador de intervenciones

El Simulador es un servicio Dash independiente. Reutiliza el Parquet, las geometrías y las
funciones de densidad, incidencia y Votar entre Balas; no importa el layout ni los callbacks del
Explorador y no recalcula predicciones ni perfiles. P1/P2 tienen prioridad alta, P3/P6 media y
P4/P5 baja. EI-A/B y EI-C/D se incluyen por defecto como prioridad operativa media provisional,
sin cambiar su etiqueta ni interpretarlas como riesgo medio.

La cobertura acepta porcentaje o número entero. La selección agota alta, luego media y finalmente
baja. Dentro de cada nivel usa SHA-256 sobre semilla, espacio de nombres y `clave_seccion`, por lo
que es reproducible, independiente del orden de filas y anidada al aumentar cobertura. Una segunda
clave hash asigna exactamente una de seis políticas por sección; el escenario de eficacia sólo
cambia el efecto aplicado.

Los indicadores comparan las mismas secciones tratadas con proyección válida mediante media
simple. La participación simulada se limita a 100% y muestra simultáneamente los escenarios
pesimista, normal y optimista sin recalcular la selección ni la asignación. El mapa conserva una
única vista de asignación. El contorno discontinuo identifica una sección tratada ubicada en un
municipio con registros para el periodo activo; no atribuye el evento a la sección. Las dos
descargas incluyen el universo elegible o sus agregados y los parámetros necesarios para
reproducir la simulación.

## Rendimiento

La geometría nunca viaja dentro de un callback de filtros. Ambos servicios recuperan el mecanismo
poligonal de la versión `7d0a5a9`: en la vista nacional consultan por bounding box la capa
FlatGeobuf generalizada a 900 m y desde zoom 7 usan la capa poligonal de 75 m. Los bounding boxes
se cuantizan para que movimientos pequeños reutilicen rangos ya solicitados. No existe un nivel de
puntos ni una ruta `/map/sections-national-v1...geojson`.

Los assets versionados se sirven con caché inmutable durante un año. Cada capa conserva las
70,751 claves y las propiedades compactas necesarias para perfiles, densidad, incidencia y Votar
entre Balas. El Simulador actualiza selección y estilos mediante `hideout`, sin cambiar la URL de
geometría mientras no cambien zoom o bounds.
Los filtros se aplican en el cliente, las líneas estatales se sirven una sola vez y los agregados
se calculan sobre una selección compacta de columnas del Parquet local en memoria. El contrato
completo de 163 columnas se lee en lotes sólo al exportar y se transmite por streaming. El rango nacional de densidad se precalcula
offline y se filtra como un entero compacto; no se recalculan áreas ni joins al mover el slider.
La selección y los cambios de perfil no reinician el viewport.

La medición y la justificación completa están en
`docs/RADAR27_PERFORMANCE_OPTIMIZATION.md`.

## Actualizar los datos

Si se regenera el handoff, confirme primero que continúa siendo la versión canónica y ejecute:

```bash
.venv/bin/python -m dashboard.prepare_data
.venv/bin/pytest -q dashboard/tests
```

Antes de preparar el dashboard, regenere seguridad cuando cambien los originales:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_security_municipal.py
PYTHONPATH=src .venv/bin/python scripts/run_votar_entre_balas.py \
  --config configs/votar_entre_balas.yaml
```

Para inspeccionar la integración sin alterar el puntero del release vigente:

```bash
RADAR27_DASHBOARD_WORKING_COPY=1 .venv/bin/python -m dashboard.app
```

El preparador falla ante duplicados, pérdida de la relación 1:1, perfiles desconocidos o un
universo distinto. Genera:

- `dashboard/data/dashboard_sections.parquet`;
- `dashboard/data/section_housing_density.parquet`;
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

Las pruebas verifican universo, unicidad, conteos por perfil, cifras nacionales, integridad y
anidamiento de densidad, empates municipales de seguridad, límites 1/100, filtros vacíos,
exactitud del CSV, selección/limpieza, conmutación cartográfica, callbacks, las 70,751 geometrías,
unicidad de eventos Votar entre Balas, corte temporal, ventanas, cruce municipal, filtro por
conteo y ausencia de multiplicación al asignar contexto a secciones. También cubren los límites
0/100 del simulador, prioridad estricta, anidamiento, reproducibilidad, independencia del orden,
estabilidad de asignación, escenarios, valores faltantes, tope de 100% y totales directos.

## Limitaciones

- 2027 es una proyección de trabajo, no un resultado observado ni una inferencia causal.
- Los efectos del simulador son supuestos externos en puntos porcentuales y asumen alcance del
  100% de la población objetivo; no fueron estimados por el modelo y no crean un grupo de control.
- El snapshot territorial es una referencia 2024, no cartografía certificada para 2027.
- Las observaciones históricas directas por código no constituyen por sí mismas un crosswalk
  longitudinal para secciones modificadas.
- El libro AMGE público termina en 2022; la compatibilidad ECEG 2020→snapshot 2024 se limita a
  secciones clase A y no sustituye una certificación geométrica oficial completa.
- La edad/sexo electoral y la población residente ECEG tienen universos distintos y se muestran
  en paneles diferenciados.
- Donde no existe medición seccional defendible, el dashboard muestra “No disponible”; no
  sustituye silenciosamente con promedios estatales.
- Votar entre Balas depende de registros periodísticos y puede tener subregistro o cobertura
  territorial desigual. El año 2026 es parcial. El indicador es descriptivo y no fue incorporado
  al pronóstico vigente por falta de elecciones comparables y validación temporal estricta.
