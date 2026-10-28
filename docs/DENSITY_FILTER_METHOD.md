# Densidad de viviendas y filtro territorial

Actualizado: 2026-10-16.

## Fuentes y variable

El numerador procede del paquete oficial **Estadísticas Censales a Escalas
Geoelectorales 2020** de INEGI, ya congelado en el proyecto como
`data/raw/inegi/eceg_2020_csv.zip`. El archivo fue validado por tamaño, CRC y SHA-256 en
`src/radar27/ingest/eceg.py`; su manifiesto está en
`data/manifests/eceg_source_manifest.csv`.

- Archivo: `conjunto_de_datos/INE_SECCION_2020.csv`.
- Fecha de referencia: 15 de marzo de 2020.
- Mnemónico verificado en el diccionario incluido: `VIVPAR_HAB`.
- Definición: viviendas particulares habitadas; excluye viviendas particulares sin
  información de ocupantes.
- Columna interna preexistente: `eceg_inhabited_private_dwellings`.

El descriptor oficial declara un dominio no negativo. Cuatro secciones estables contienen
`-6`; se conservan en la tabla para trazabilidad, pero se etiquetan
`invalid_eceg_value` y no reciben densidad.

El denominador espacial procede de
`data/raw/public_ine/ine_secciones_2025_portal.zip`, cuyo contenido corresponde al snapshot
INE del 9 de mayo de 2024 usado por todo el dashboard. La fuente tiene 70,753 polígonos;
70,751 pertenecen al universo canónico de RADAR 27.

## Compatibilidad territorial

ECEG representa la geografía electoral 2020 y el dashboard usa un snapshot 2024. Una
coincidencia del código `entidad:sección` no demuestra que el polígono sea idéntico entre
ambos cortes. Por ello la densidad sólo se calcula para secciones clase A del contrato
territorial existente: códigos estables, con municipio y tipo estables y sin eventos AMGE
previos. No se reparten viviendas de una sección origen entre descendientes ni se agregan
o interpolan clases B–D.

Esta decisión es deliberadamente conservadora. El libro público AMGE termina en 2022 y no
cubre todas las modificaciones de 2023; por tanto, incluso la clase A es una compatibilidad
auditada con la mejor evidencia disponible, no una certificación geométrica oficial
2020→2024.

## Cálculo y tabla canónica

`dashboard.prepare_data.build_density_table`:

1. valida CRS, claves únicas, geometrías vacías/inválidas y geometrías exactamente
   duplicadas;
2. reproyecta los polígonos completos a **EPSG:6933**, una proyección equivalente global;
3. calcula `area_km2 = geometry.area / 1_000_000` sin usar bounding boxes;
4. calcula `VIVPAR_HAB / area_km2` sólo cuando la sección es clase A, el valor censal es
   no negativo y el área es finita y positiva;
5. ordena densidad descendente y desempata por `section_id` ascendente.

El resultado reproducible es `dashboard/data/section_housing_density.parquet`, con:

- `section_id`, `entidad`, `seccion`;
- `viviendas_habitadas_2020`, `area_km2`, `densidad_viviendas_km2`;
- `density_data_status`, `density_source_year`, `density_rank`.

Cobertura del snapshot actual:

| Estado | Secciones |
|---|---:|
| `valid` | 58,530 |
| `incompatible_2020_2024_geography` | 12,217 |
| `invalid_eceg_value` | 4 |
| Total | 70,751 |

La cobertura válida es 82.73%. Todas las 70,751 secciones tienen área positiva; no se
detectaron claves ni geometrías duplicadas.

## Semántica e integración interactiva

El ranking nacional se precalcula una vez durante la preparación. Para un valor `p < 100`,
el filtro conserva las primeras `ceil(58,530 * p / 100)` secciones. Los perfiles se aplican
después por intersección y nunca cambian el ranking. Para `p = 100`, el filtro se desactiva
y conserva las 70,751 secciones, incluidas las que no tienen densidad válida. Para `p = 0`,
la selección queda vacía de forma controlada.

FlatGeobuf contiene sólo la clave, el perfil y el rango entero de densidad. El navegador
filtra esas propiedades; no recibe viviendas, áreas ni listas masivas de claves. Los callbacks
usan el mismo rango precalculado para mapa, KPIs y gráficas. Las participaciones observadas
siguen siendo razones de sumas, y la proyección sigue ponderada por lista nominal 2024. El
filtro no reentrena modelos ni cambia perfiles o predicciones.

`Todos` y `Limpiar` continúan administrando sólo perfiles. `Restaurar` recupera todos los
perfiles y densidad 100%, de acuerdo con su semántica de restauración global.

## Reproducir y validar

```bash
.venv/bin/python -m dashboard.prepare_data
.venv/bin/pytest -q dashboard/tests
```

El manifiesto `dashboard/data/manifest.json` registra fuente, CRS, cobertura y estados de la
densidad generada.
