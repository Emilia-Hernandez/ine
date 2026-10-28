# RADAR 27 — auditoría de despliegue en Render Free

Fecha de la medición original: 2026-10-20 (America/Mexico_City).
Actualización de publicación: 2026-10-28.

## Decisión

La aplicación es viable en una instancia de 512 MiB con **un worker y dos hilos**, después de
separar la tabla analítica de ejecución del contrato completo de exportación y serializar las
descargas grandes. No debe desplegarse la implementación anterior: superaba 512 MiB al cargar
datos y alcanzaba aproximadamente 1.55 GiB al exportar el universo nacional.

El release autorizado vigente es `radar27-dashboard-intervention-simulator.1`, que sustituye a
`radar27-dashboard-security.5` sin sobrescribirlo. El puntero fija el modelo
`radar27-final-2027-municipal.1`, `A_nacional_actual`; el experimento
`radar27-security-ablation.2` no se lee ni se distribuye. `render.yaml` desactiva despliegues
automáticos para que un experimento o un cambio de datos no publique predicciones por accidente.

La actualización incorpora la pestaña del simulador y 16 columnas descriptivas de Votar entre
Balas. Después de limitar el frame de cálculo del simulador a sus 10 columnas de entrada, el pico
medido para una simulación de 17,688 secciones bajó de 489.86 a 335.66 MiB sin cambiar resultados.
La exportación nacional de 180 columnas alcanzó 411.17 MiB; dos solicitudes simultáneas,
serializadas, alcanzaron 479.59 MiB. Ambos casos permanecen bajo el límite de 512 MiB.

## Arquitectura de ejecución

| Recurso | Uso en el servidor | Disco | Memoria de datos |
|---|---:|---:|---:|
| `dashboard_sections.parquet` | 64 columnas para UI; 163 sólo por lotes al exportar | 30.8 MB | 45.54 MiB (DataFrame Arrow) |
| `section_housing_density.parquet` | No se carga aparte; sus campos aprobados ya están unidos | 1.8 MB | 0 MiB adicional |
| `sections_overview.fgb` | Archivo estático por viewport y HTTP Range | 20.1 MB | 0 MiB en el servidor |
| `sections_detail.fgb` | Archivo estático desde zoom 7 y HTTP Range | 53.8 MB | 0 MiB en el servidor |
| `state_boundaries.geojson` | Archivo estático | 1.0 MB | 0 MiB en el servidor |
| Manifest y puntero | Metadatos pequeños al importar | <10 KB | despreciable |

El release distribuible ocupa aproximadamente 102 MiB. No necesita handoffs, artefactos de
entrenamiento, datos crudos, notebooks, GeoPandas, Shapely, LightGBM, XGBoost, Torch ni
scikit-learn. `dashboard/prepare_data.py`, `scripts/publish_dashboard.py` y todos los pipelines de
seguridad/modelación son procesos exclusivamente offline.

Los únicos archivos requeridos al arrancar son `current_release.json`, el Parquet aprobado, los
assets CSS/JavaScript y los assets congelados del release. Todas las rutas se resuelven desde
`Path(__file__)`; no hay rutas absolutas de macOS en ejecución.

Dependencias web directas: Dash, dash-leaflet, dash-extensions, Flask, Gunicorn, NumPy, pandas,
Plotly y PyArrow. Python queda fijado en 3.12.13. GeoPandas fue retirado del entorno web y se
mantiene sólo en el entorno de preparación del proyecto.

## Memoria y tiempos

Mediciones RSS en macOS con Python 3.12.13. Docker no estaba activo, por lo que no se pudo crear
un cgroup de 512 MiB; se midió el worker real y se tomó 512 MiB como límite duro. El script
reproducible es `scripts/profile_dashboard_render.py`.

### Antes de optimizar

| Escenario | RSS / pico |
|---|---:|
| Python antes de imports | 18.81 MiB |
| Imports | 87.98 MiB |
| Parquet completo, 163 columnas | 507.39 MiB |
| Filtros conjuntos 10 / 25 / 50 / 66 / 100% | 513.62 / 527.89 / 548.67 / 603.48 / 718.11 MiB |
| Exportación pequeña con `dcc.send_string()` | 718.47 MiB |
| Exportación nacional con `dcc.send_string()` | 1,547.98 MiB pico |

### Implementación preparada

| Escenario | RSS pico | Tiempo local |
|---|---:|---:|
| Importar app, cargar datos y construir layout | 240.36 MiB | 0.78 s |
| Filtros conjuntos 10 / 25 / 50 / 66 / 100% | 247.31 / 258.66 / 277.67 / 293.83 / 300.88 MiB | 0.02–0.10 s |
| Selección y cuatro figuras | 300.88 MiB | 0.04 s combinado |
| CSV nacional por streaming, 70,751 × 164 | 410.64 MiB | 11.13 s |
| Dos solicitudes nacionales concurrentes, serializadas | 407.42 MiB | 11.19 s y 22.66 s |

El CSV validado mide 170,615,275 bytes, contiene 70,751 filas, 70,751 claves únicas y 164
columnas (las 163 originales más `metadatos_filtros_json`). Conserva UTF-8 con BOM, claves con
ceros iniciales, todos los campos, filtros y versión del modelo. Las descargas grandes se
serializan para mantener un margen de ~104 MiB; los callbacks siguen respondiendo mediante el
segundo hilo.

## Pruebas de producción

Comando probado:

```bash
gunicorn dashboard.app:server --bind 127.0.0.1:8051 --workers 1 --threads 2 --timeout 120 --access-logfile - --error-logfile -
```

Render sustituye el bind por `0.0.0.0:$PORT`, como se define en `render.yaml`.

- `/`, `/_dash-layout`, `/_dash-dependencies` y `/healthz`: HTTP 200.
- `/healthz` informa el release y modelo aprobados sin forzar una nueva carga de datos.
- FlatGeobuf respondió `206 Partial Content`, `Accept-Ranges: bytes` y el `Content-Range`
  esperado para una solicitud de 1,024 bytes.
- Callbacks HTTP reales de 10, 25, 50, 66 y 100%: 53–122 ms y conteos consistentes.
- Selección seccional por mapa verificada en navegador; ficha, cuatro gráficos y agregados se
  actualizaron.
- Zoom y cambio a la geometría detallada verificados; el mapa se renderiza en Canvas.
- Vista de 1,440 × 900 y vista compacta de 319 px verificadas sin desbordamiento horizontal.
- Consola del navegador: cero errores o advertencias.
- Reinicio de Gunicorn y recuperación de `/healthz`: correctos.
- CSV nacional: HTTP 200, streaming sin `Content-Length`, conteos y metadatos verificados.

## Configuración y publicación

`render.yaml` usa el plan `free`, runtime Python, región Ohio, health check `/healthz`, instalación
sin caché y despliegue automático desactivado. El comando de inicio crea un único proceso de
datos con dos hilos. No se requieren secretos ni variables privadas.

`.gitignore` excluye releases históricos y permite únicamente
`radar27-dashboard-security.5`. Esto conserva los históricos locales, evita distribuirlos y
mantiene explícito el release autorizado. No se sobrescribió ningún release.

Hashes SHA-256 principales del paquete:

```text
8db656a5d91d4a9e75386e83495774746a6970d943463f5f1c780b19b5816909  dashboard_sections.parquet
33b836fea422266286debbfccabc3893c7b7b8d7867ac8f86283ab3fc1c165c0  manifest.json
78000204e0c0f8cb3a3130e8bf463a38634583ed32c7caf2481c6738d292ef95  sections_overview.fgb
0fa3390113e9e7f9297c987e3816ec92bcc9f8d3ae031f11e52a1a02ee6f2a8b  sections_detail.fgb
e9603e745436d7157a9096485a3009e3765d5ed0b34d2b716c4bd006b533ea2b  state_boundaries.geojson
```

## Operación del despliegue

El servicio público existente responde en `https://radar27.onrender.com/healthz`. En esta
actualización no hay una sesión autenticada de Render ni una credencial/API configurada. Como
`autoDeployTrigger` permanece desactivado deliberadamente, después de actualizar la rama de
producción se debe iniciar manualmente **Deploy latest commit** en el panel y comprobar el health
check, el commit desplegado y los logs de arranque.
