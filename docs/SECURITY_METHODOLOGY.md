# Metodología de incidencia delictiva municipal registrada

## Fuentes y versión

- SESNSP, incidencia delictiva municipal del fuero común, metodología CNSP/38/15 para 2015–2025. Original conservado: `data/raw/sesnsp/Municipal-Delitos-2015-2025_sep2026.zip`, SHA-256 `ae8561a42e5595dd518c59cd0d115aba0adcc95b72a10cadbc4fa383a9723a86`.
- CONAPO, reconstrucción y proyecciones municipales 1990–2040, población a mitad de año. Original conservado: `data/raw/conapo/00_Republica_mexicana.zip`, SHA-256 `b878a88b58f0f51bb9ea6259c2fafde8e440afdd07cd06e075ff1faeb6a895ee`.
- Versión procesada: `radar27-security-municipal-2025.1`.

El archivo SESNSP fue descargado desde su página oficial en octubre de 2026 y declara corte retrospectivo a septiembre de 2026. Contiene 2,562,994 filas para 2015–2025. No se mezcla con el RNID iniciado en 2026. El sitio oficial define la incidencia como presuntos delitos registrados en averiguaciones previas o carpetas de investigación y reportados por procuradurías y fiscalías; no es una medición de delitos ocurridos ni de seguridad individual.

La página oficial de CONAPO fecha el producto municipal el **9 de mayo de 2024**. El producto reconstruye 1990–2020 y proyecta 2021–2040; por tanto, esta versión concreta no estaba publicada en los cortes de abril de 2018, abril de 2021 ni abril de 2024. Se conserva como denominador retrospectivo armonizado, no como información conocida ex ante.

## Construcción

Cada fila SESNSP es una modalidad terminal. La incidencia total se obtiene sumando sus doce columnas mensuales una sola vez; no se suman simultáneamente tipo, subtipo y modalidad como si fueran tablas agregadas distintas. El pipeline verifica la unicidad de la combinación municipio, año, bien jurídico, tipo, subtipo y modalidad, y rechaza conteos negativos.

La tasa principal es:

`delitos registrados / población municipal a mitad de año × 100,000`.

La tasa violenta experimental suma homicidio doloso, lesiones dolosas, feminicidio, abuso/acoso/hostigamiento sexual, rapto, secuestro, trata, tráfico de menores, violación, violencia de género y violencia familiar. La lista exacta está versionada en el manifest. No se usa lista nominal como denominador.

Las claves SESNSP y CONAPO se normalizan como `EE:MMM`, preservando ceros iniciales. El join se valida `1:1` en municipio-año y `m:1` al asignarlo a secciones. Nombres nunca son la llave. En 2025 hay indicador válido para 70,450 secciones y 301 quedan faltantes. Todas las secciones de un municipio comparten el mismo contexto; no se infiere incidencia seccional.

Para el experimento, la tasa estatal de referencia se calcula sólo con municipios que tienen tasa y denominador válidos. Esto corrige el error de `radar27-security-ablation.1` por el que un único denominador nulo propagaba `NaN` a toda una entidad. El municipio inválido permanece faltante: no se imputa ni se transforma en cero.

## Ranking y filtro

El ranking nacional se fija sobre secciones con indicador válido. Se ordena de menor a mayor tasa. Los municipios empatados en el umbral se conservan completos mediante `security_rank_start` y `security_rank_end`, por lo que el porcentaje efectivo puede superar el solicitado. A 100% el filtro es neutro e incluye también las 301 secciones sin cobertura; en valores restrictivos los faltantes quedan fuera sin ser calificados como altos o bajos.

## Temporalidad experimental y clasificación *as-of*

Los folds usan cortes abril de 2018, abril de 2021 y abril de 2024. La ventana de 12 meses termina en el mes del corte; la ventana de 24 meses abarca desde mayo de dos años antes hasta abril del año objetivo. Las pruebas verifican que no entra ningún periodo posterior al corte.

Conviene distinguir tres conceptos:

- **Periodo de referencia:** los meses SESNSP incluidos son anteriores o iguales al corte.
- **Disponibilidad de publicación:** no se conservan snapshots SESNSP publicados antes de cada elección; el archivo usado fue revisado en septiembre de 2026.
- **Revisión retrospectiva:** tanto el snapshot SESNSP como los denominadores CONAPO actuales pueden incorporar correcciones o reconstrucciones conocidas después del periodo evaluado.

En consecuencia, `radar27-security-ablation.2` es una **evaluación retrospectiva con datos revisados**, no una validación histórica en tiempo real ni un backtest *as-of*. La densidad territorial usada por M4 también procede del snapshot vigente y se etiqueta como contextual retrospectiva. No se hacen afirmaciones causales.

No se localizó en los insumos conservados una serie completa de snapshots municipales SESNSP ni versiones municipales CONAPO contemporáneas a los tres cortes. Una sensibilidad verdaderamente *as-of* sigue abierta y requeriría obtener, autenticar y versionar esos archivos históricos; no se sustituyen silenciosamente en este análisis.

## Cobertura y unidad de evaluación

La cobertura transversal del dashboard (70,450 de 70,751 secciones en 2025) no es comparable directamente con la cobertura histórica del experimento. Tras corregir la referencia estatal, la muestra común M1–M4 conserva 58,006 de 58,069 unidades en 2021 y 55,944 de 56,007 en 2024. Las 63 pérdidas de cada fold corresponden a tres municipios sin registros SESNSP en la ventana aplicable. El detalle incremental, los motivos superpuestos y los desgloses territoriales están en `artifacts/experiments/security_ablation/radar27-security-ablation.2/COVERAGE_AUDIT.csv`.

M4 conserva densidad faltante mediante el soporte nativo de `HistGradientBoostingRegressor` y el indicador `density_missing` ya declarado. No imputa densidad ni usa cero como sustituto. Las métricas de ranking usan unidades de evaluación sin ponderar; las secciones representadas y los electores se informan por separado.
