# RADAR 27 — dos servicios Dash independientes

Fecha de validación local: 2026-10-28 (America/Mexico_City).

## Arquitectura preparada

| Servicio | Entrada Gunicorn | Puerto local | URL de producción |
|---|---|---:|---|
| Explorador territorial | `dashboard.explorer_app:server` | 8050 | `https://radar27.onrender.com` |
| Simulador de intervenciones | `dashboard.simulator_app:server` | 8051 | `https://radar27-simulador.onrender.com` |

El Explorador registra siete callbacks, ninguno con IDs `sim-*`. El Simulador registra cinco
callbacks, ninguno de gráficas, selección o paneles del Explorador. Cada servicio carga su propio
proceso, Parquet y mapa. Comparten archivos versionados del repositorio, no memoria de proceso.

Los enlaces se configuran con `RADAR27_EXPLORER_URL` y `RADAR27_SIMULATOR_URL`. Sin `RENDER`, los
valores predeterminados son `http://127.0.0.1:8050` y `http://127.0.0.1:8051`. En Render son las
URLs de la tabla anterior. En esta primera etapa `render.yaml` declara exclusivamente
`radar27-simulador`, con despliegue automático desactivado, para no modificar el servicio
`radar27` vigente.

## Cartografía recuperada

El historial identifica `7d0a5a9` como la versión del Explorador de una sola aplicación con
polígonos. Se recuperó su mecanismo:

- `sections_overview.fgb`, polígonos simplificados a 900 m desde la vista nacional;
- `sections_detail.fgb`, polígonos simplificados a 75 m desde zoom 7;
- consultas FlatGeobuf por `bbox`, caché HTTP de assets versionados y filtros en cliente;
- 70,751 claves únicas en cada capa, sólo geometrías `Polygon`/`MultiPolygon`.

No existe una ruta activa `/map/sections-national-v1...geojson`, un nivel nacional de puntos,
`pointToLayer`, `representative_point` ni un callback de tres niveles. Se eliminaron el artefacto
de puntos, su constructor y su script. Cambiar filtros, cobertura o semilla actualiza `hideout` y
no cambia la URL cartográfica mientras zoom y bounds no cambien.

## Pruebas y mediciones locales

Entorno: macOS, Python 3.12.13, Gunicorn 23, un worker `gthread` y dos hilos por servicio. Estas
mediciones no sustituyen una prueba posterior en Render.

| Medida | Explorador | Simulador |
|---|---:|---:|
| Import, layout y datos | 0.891 s | 0.834 s |
| RSS después de import y datos | 262.66 MiB | 256.59 MiB |
| Pico local funcional | 341.34 MiB (secuencia 10/25/50/66/100% y figuras) | 399.42 MiB (100% de cobertura) |
| Cambio interactivo medido en navegador | 1.588 s (quitar P1, 70,751→68,033) | 0.086 s (100%→25%) |
| Vista nacional | visible en menos de 2 s según logs HTTP | visible y utilizable en menos de 2 s según logs HTTP |
| Solicitudes de la capa seccional inicial | 5 rangos HTTP 206 | 5 rangos HTTP 206 |
| Transferencia seccional inicial | 21,278,224 B | 21,278,224 B |

El volumen nacional coincide con la capa poligonal histórica. Es deliberadamente mayor que el
experimento de puntos descartado. El navegador mostró los polígonos nacionales, zoom, colores,
agregados y ambos enlaces de navegación.

Casos del Simulador verificados:

- 0%: cero seleccionadas y resultados no disponibles;
- 25%: 17,688 seleccionadas, 2,776 alta, 14,912 media y cero baja;
- 100%: 70,751 seleccionadas, 2,776 alta, 50,992 media y 16,983 baja;
- semilla 42 al 25%: 54.69% base, 54.97% pesimista, 55.43% normal y 55.97% optimista;
- CSV de secciones por streaming: HTTP 200, 42,545,469 B al 25%, 1.288 s;
- CSV agregado: HTTP 200, 6,407 B al 25%, 0.349 s;
- pico al generar ambos CSV al 100% por lotes: 403.06 MiB.

El CSV seccional del Simulador se transmite en lotes de 2,000 filas. La versión que construía
una cadena completa alcanzó 537 MiB y fue descartada antes de entregar el cambio.

El CSV nacional del Explorador también se consumió completo: HTTP 200, 188,391,005 B y 11.518 s.
El perfil reproducible alcanzó 404.80 MiB para una exportación y 473.62 MiB para dos solicitudes
concurrentes serializadas (23.155 s en total). El margen local del peor caso frente a 512 MiB es
38.38 MiB, por lo que debe comprobarse expresamente en Render y no aumentar workers.

## Límites vigentes de Render Free

Según la documentación oficial consultada el 2026-10-28:

- la instancia `free` dispone de 0.1 CPU y 512 MB de RAM;
- cada servicio se suspende tras 15 minutos sin tráfico entrante y el arranque en frío tarda
  aproximadamente un minuto;
- las 750 horas gratuitas son compartidas por workspace y mes; dos servicios siempre activos
  necesitarían aproximadamente 1,440 horas en un mes de 30 días, por lo que ambos sólo caben en
  Free si su suspensión por inactividad reduce el consumo conjunto;
- el filesystem es efímero, pero RADAR 27 sólo lee archivos versionados incluidos en el deploy;
- Free no ofrece escalado a más de una instancia ni discos persistentes.

Fuentes: [Deploy for Free](https://render.com/docs/free),
[Compute Plans](https://render.com/docs/compute-plans) y
[Render FAQ](https://render.com/docs/faq).

## Despliegue seguro

1. Revisar `git diff` y agregar sólo los archivos listados para esta tarea; no usar `git add .`.
2. Ejecutar `.venv/bin/pytest -q dashboard/tests`.
3. Ejecutar una vez por proceso:

   ```bash
   .venv/bin/python scripts/profile_dashboard_services.py explorer
   .venv/bin/python scripts/profile_dashboard_services.py simulator
   .venv/bin/python scripts/profile_dashboard_services.py simulator --exports
   .venv/bin/python -m scripts.profile_dashboard_render --full-export
   ```

4. No sincronizar un Blueprint con el servicio vigente. Crear manualmente `radar27-simulador`
   desde la rama autorizada usando los valores de `render.yaml`, con Auto-Deploy desactivado.
5. Publicar `radar27-simulador` y comprobar `/healthz`, mapa, 0/25/100%, semilla y ambos CSV.
   No modificar todavía el servicio `radar27` vigente.
6. Publicar el Explorador sólo en una etapa posterior y con autorización expresa.
7. Medir en Render arranque en frío, tiempo hasta mapa, rangos y volumen en DevTools, latencia de
   callbacks y memoria/reinicios en logs. La validación local no demuestra por sí sola que el
   rendimiento público esté resuelto.
8. Conservar disponible el deploy previo hasta que ambos health checks y recorridos funcionales
   hayan pasado. Si falla alguno, usar el rollback de Render al deploy anterior; no revertir datos
   ni commits ajenos.
