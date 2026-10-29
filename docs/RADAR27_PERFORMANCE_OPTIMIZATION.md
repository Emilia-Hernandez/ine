# RADAR 27 — optimización de rendimiento y cartografía

> **Experimento retirado.** La representación nacional de puntos descrita aquí se descartó el
> 2026-10-28. La arquitectura vigente vuelve a las capas poligonales y separa Explorador y
> Simulador; véase `docs/RADAR27_TWO_SERVICES_DEPLOYMENT.md`.

Fecha: 2026-10-28 (America/Mexico_City).

## Alcance y resultado

Esta intervención reduce la latencia cartográfica sin modificar perfiles, predicciones, filtros,
prioridades, escenarios, tablas ni exportaciones. El cambio está preparado localmente en
`codex/render-performance`; no se ha creado commit, publicado rama ni desplegado en Render.

La vista nacional deja de solicitar el FlatGeobuf completo de 20.1–21.3 MB y usa un GeoJSON gzip
determinista de 1,832,311 bytes. Conserva las 70,751 claves seccionales y los campos compactos
`k`, `p`, `r`, `s`, `a` y `b`. Cada punto se calcula con `representative_point()` en EPSG:6933 y
se usa sólo cuando un polígono seccional no es identificable a escala nacional.

## Diagnóstico de referencia

La versión pública anterior respondió el FlatGeobuf nacional con `Cache-Control: no-cache` y
`CF-Cache-Status: DYNAMIC`. Dos solicitudes públicas de 2,800,000 bytes al mismo rango tardaron
7.710 s y 9.250 s; el inicio de transferencia fue 1.578 s y 2.168 s. A ese rendimiento, descargar
20,149,104 bytes explica cargas totales del orden de 50–60 s. Además, explorador y simulador
montaban desde el inicio dos componentes que apuntaban a la misma geometría nacional.

El cuello de botella principal era la combinación de:

- transferencia regional lenta desde una instancia Render Free;
- una capa nacional mucho mayor de lo que permite su escala visual;
- rangos sin caché reutilizable;
- montaje anticipado de la geometría del simulador;
- renderizado de decenas de miles de elementos vectoriales en el navegador.

## Arquitectura implementada

| Nivel | Zoom | Representación | Transferencia |
|---|---:|---|---|
| Nacional | 4–5 | 70,751 puntos interiores, Canvas | un GeoJSON gzip de 1.83 MB |
| Regional | 6 | polígonos simplificados a 900 m | FlatGeobuf por bbox de 1° |
| Detalle | 7–16 | polígonos simplificados a 75 m | FlatGeobuf por bbox de 0.25° |

Los bounding boxes llevan margen y se ajustan a una cuadrícula. Así, páns pequeños producen la
misma consulta y pueden reutilizar caché. Las rutas de releases y la capa nacional se sirven con
`public, max-age=31536000, immutable`; la URL nacional contiene los primeros 12 caracteres del
SHA-256 para que una futura cartografía no reutilice bytes antiguos. Los rangos FlatGeobuf siguen
admitiendo `206 Partial Content`. El mapa y los callbacks pesados del simulador no se activan hasta
abrir su pestaña.

En la vista nacional el explorador conserva todos sus filtros. El simulador dibuja únicamente las
secciones seleccionadas, por prioridad y contexto municipal. Al acercar reaparecen polígonos y
tooltips completos. Los sliders costosos actualizan al soltar el control (`mouseup`), no durante
cada píxel de arrastre.

## Medición antes/después

| Indicador | Antes | Después local | Cambio |
|---|---:|---:|---:|
| Geometría inicial por mapa | 21,278,224 B | 1,832,311 B | −91.39% |
| Geometría inicial potencial de dos mapas | 42,556,448 B | 1,832,311 B | −95.69% |
| Componentes cartográficos que cargan al inicio | 2 | 1 | −50% |
| Respuesta inicial oculta del simulador | 959,864 B | 0 B | −100% |
| Respuesta al abrir el simulador (17,688 tratadas) | 959,864 B | 379,315 B | −60.48% |
| Solicitud local de capa nacional | — | 0.014 s total; 0.001 s hasta primer byte | referencia local |
| Simulación de 70,751 elegibles | 516.5 ms | 518.8 ms | sin regresión material |

Los tiempos públicos anteriores y los tiempos locales posteriores no son una comparación de red
equivalente: la versión optimizada todavía no se ha desplegado. La comparación defendible previa
al despliegue es el volumen transferido y el número de solicitudes iniciales. El primer despliegue
debe volver a medir TTFB, transferencia, carga visual y rangos desde Render.

La medición actual con un worker y dos hilos alcanzó 334.91 MiB para una simulación de 17,688
tratadas, 411.48 MiB para una exportación nacional y **477.92 MiB de pico** para dos
exportaciones serializadas. El margen local respecto de 512 MiB fue 34.08 MiB. La nueva capa se
sirve desde disco comprimido y no se carga en el proceso de datos; no añade un DataFrame
residente. Canvas reduce el coste del DOM en el cliente. Este pico es una medición en macOS y
requiere confirmación en Render, cuyo límite de memoria puede aplicarse de forma distinta.

## CDN y caché

No se introduce un proveedor nuevo en este cambio. Reducir la primera transferencia a 1.83 MB,
hacerla de una sola respuesta y permitir caché inmutable elimina primero la causa dominante sin
sumar credenciales, orígenes ni operación externa. Un CDN de objetos puede evaluarse después del
despliegue si el TTFB de Render continúa alto; la ruta y el nombre versionado permiten migrarlo sin
cambiar la lógica de filtros.

## Reproducibilidad

La capa nacional se genera junto con `dashboard.prepare_data` o de forma aislada:

```bash
PYTHONPATH=. .venv/bin/python scripts/build_national_map.py
```

El gzip fija `mtime=0`, por lo que la misma entrada produce los mismos bytes. En esta medición:

```text
7fbdc8971d4f9c56f4ffe9d7cc1ffc60ba9487bd80fbfd06ee81e0ccf3b17a32  sections_national_v1.geojson.gz
```

La capa nacional y el release activo tienen exactamente las mismas 70,751 claves y cero
diferencias en las seis propiedades compactas.

## Verificación realizada

- 163 pruebas generales: correctas.
- 64 pruebas del dashboard, publicación, seguridad municipal y Votar entre Balas: correctas; 6
  omitidas por sus condiciones declaradas.
- 29 pruebas cartográficas/datos focalizadas: correctas; 6 omitidas.
- `ruff`, `node --check` y `git diff --check`: correctos.
- Gunicorn con el comando de Render: `/healthz` 200, capa nacional 200 con gzip/caché y rango
  FlatGeobuf 206 para ambos archivos del release activo.
- Navegador local: mapa nacional, transición a polígonos, simulador diferido, cifras y tablas
  visibles sin regresión. Los filtros y colores se comprobaron además con pruebas JavaScript.

La medición local posterior registra 0.014 s para la transferencia comprimida de la capa nacional
y una simulación de 17,688 tratadas en 372.3 ms. No se cronometró con precisión el primer píxel
útil, cada cambio de zoom, el cambio de pestaña ni el dibujo completo en móvil; esas mediciones
se harán en DevTools sobre el despliegue real. Las exportaciones se verificaron con pruebas y
el perfilador; no se realizó una descarga manual desde el navegador en esta revisión.

## Preparación para Git

El puntero vigente usa `asset_prefix` igual a
`/assets/releases/radar27-dashboard-intervention-simulator.1`. En ese directorio existen
`sections_overview.fgb` y `sections_detail.fgb`; el primero tiene el mismo SHA-256 que la copia
de trabajo usada para generar la capa nacional. Los 70,751 identificadores y las seis propiedades
compactas coinciden. Los dos FGB y el puntero ya están versionados. La capa nacional nueva no está
excluida por `.gitignore` y pesa 1,832,311 bytes. Las dependencias de ejecución ya están en
`dashboard/requirements.txt`; la generación offline usa GeoPandas del entorno de desarrollo.

Archivos exactos de esta optimización para incorporar al futuro commit:

```text
dashboard/README.md
dashboard/app.py
dashboard/assets/map.js
dashboard/assets/sections_national_v1.geojson.gz
dashboard/map_assets.py
dashboard/map_geometry.py
dashboard/prepare_data.py
dashboard/simulator_ui.py
dashboard/tests/test_dashboard_data.py
dashboard/tests/test_map_performance.py
docs/RADAR27_PERFORMANCE_OPTIMIZATION.md
scripts/build_national_map.py
```

Los cambios actuales en las copias raíz de `sections_overview.fgb`, `sections_detail.fgb`,
`dashboard_sections.parquet` y `manifest.json`, así como el resto de archivos de investigación y
entregables sin seguimiento, preceden a esta optimización y no pertenecen al commit propuesto.

Para publicar después, revisar primero la rama configurada en el panel de Render. En la última
auditoría local, `origin/codex/render-free-deploy` contenía el simulador y `render.yaml` tenía
`autoDeployTrigger: off`. Para preparar exclusivamente los doce archivos anteriores:

```bash
git add -- dashboard/README.md dashboard/app.py dashboard/assets/map.js \
  dashboard/assets/sections_national_v1.geojson.gz dashboard/map_assets.py \
  dashboard/map_geometry.py dashboard/prepare_data.py dashboard/simulator_ui.py \
  dashboard/tests/test_dashboard_data.py dashboard/tests/test_map_performance.py \
  docs/RADAR27_PERFORMANCE_OPTIMIZATION.md scripts/build_national_map.py
git diff --cached --stat
git diff --cached --check
git commit -m "perf: load national map progressively on Render Free"
git push -u origin codex/render-performance
```

Integrar mediante PR a la rama que Render confirme para el servicio, sin force push. En Render,
usar **Deploy latest commit** y verificar el commit, `/healthz`, la URL nacional con hash y gzip,
los rangos 206, ambos mapas y la memoria en los logs. Ninguno de estos pasos se ha ejecutado en
esta revisión.

## Comprobaciones posteriores al despliegue

1. Confirmar el commit y la rama servidos por Render.
2. Verificar `/healthz` y ausencia de reinicios por memoria.
3. Medir una carga con caché vacío y otra con caché caliente.
4. Confirmar una única descarga inicial de `sections-national-v1.geojson` y ninguna geometría del
   simulador antes de abrir su pestaña.
5. Acercar a zoom 6 y 7; comprobar respuestas 206, bboxes regionales y reutilización al hacer pan.
6. Repetir en escritorio y móvil; revisar consola y waterfall de red.
