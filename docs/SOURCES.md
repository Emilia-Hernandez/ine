# Fuentes y procedencia

Fecha de comprobación HTTP de la instantánea final: **2026-10-05 UTC**. Notebook/celda: `notebooks/00_setup_sources_download.ipynb` / `download-official-sources`.

## Universo

La página oficial separa **Elecciones Federales** del **Poder Judicial**. El universo principal de esta fase contiene únicamente 2009, 2012, 2015, 2018, 2021 y 2024. Voto en prisión preventiva 2024, voto anticipado 2024 y el proceso judicial 2024–2025 se registran pero no se descargan ni se agregan al panel principal.

Página oficial: <https://ine.mx/transparencia/datos-abiertos/visualizacion-datos/conteos-censales-participacion/>

## Archivos descargados

| Fuente | Bytes | SHA-256 |
|---|---:|---|
| Manual 2009–2024 | 2,624,288 | `90bd0e45e28a4f231ad468e3c797eb262f5c1363e53fc089bd69d6d764e5c4cd` |
| CCPC 2009 | 40,203,573 | `e626e9528a91206c23fc8f96987e1a297db285e7cbc0fa1e37a18ed473ebf61c` |
| CCPC 2012 | 39,515,896 | `5999f86e21154138b904723cb5d55ebde9e108ac72872f2ff5695d9eb8fde9cd` |
| CCPC 2015 | 42,594,136 | `7435ac54a3a6aebf5d9c9466a064b320b64bf5ff8b4d8ae787bad898497341da` |
| CCPC 2018 | 43,389,665 | `b20981a0aea1ac773e7bc0b54784bba7619346585ba3996744ad22458279dd8b` |
| CCPC 2021 | 44,357,326 | `29bdfaaa33be5151c2ae8c8e406d8a27976006d11e6cbe201ac05cc04def4849` |
| CCPC 2024 | 82,419,841 | `c0de34d04e782ad99579b83591a6e3e6c8d1e20f4914d4845743bd79d2bd28b2` |

Las URLs solicitadas y finales coincidieron en las siete descargas. Todas respondieron HTTP 200; los ZIP respondieron `application/zip` y superaron firma, CRC y control de rutas. Los encabezados `Last-Modified` y `ETag` están en `data/manifests/source_manifest.csv`.

## Documentos consultados

| Documento real | SHA-256 | Uso |
|---|---|---|
| `Convocatoria_Hackaton-1.pdf` | `9df0f6aa9ee916d5b9c6e1b670bdcd0aec80427337f101ed0b80b5f4f44fa55e` | Requisitos y entregables del Reto 2 |
| `Manual-Conteos-Censales-2009-2024.pdf` | `90bd0e45e28a4f231ad468e3c797eb262f5c1363e53fc089bd69d6d764e5c4cd` | Definiciones del tablero; versión de junio de 2025 |
| `RADAR27_Plan_Maestro_Agente.md` | El hash cambia al corregir la fórmula provisional; véase Git | Contrato de notebooks 00–16 |
| `RADAR27_Propuesta_Equipo_Obsidian.md` | `d768461b63caa11d371add817e0e7556f66357a3949ee20ededb348b26c7b78d` | Contexto metodológico |

Cada ZIP contiene un TXT de descripción de campos. Los TXT 2009–2021 son idénticos (`d86b8dbb4c63eb4ef87dc2881de2589b80ef5188b75c1630552dc4f31b14e4e0`); el de 2024 tiene hash `5f3405c39b33e8332a097affbaaf22cd2725a85bae70c4a3b8868c9a087ea0f8`.

## Cartografía

La página de la plataforma declara cartografía con corte a mayo de 2023. La página oficial de [productos cartográficos especializados](https://www.ine.mx/voto-y-elecciones/especializados/) indica que el Marco Geográfico Seccional y el Catálogo de Secciones se obtienen mediante solicitud de acceso a la información debido a su peso; no ofrece ahí un crosswalk histórico directo.

El [informe de actividades DERFE del segundo trimestre de 2023](https://repositoriodocumental.ine.mx/xmlui/bitstream/handle/123456789/152317/crfe-5se-2023-07-12-p3-1-informe.pdf) reporta 2,469 municipios y 69,548 secciones en abril, mayo y junio de 2023, además de trabajos de reseccionamiento e integración. La fuente CCPC 2024 contiene 70,751 códigos `entidad:sección`; esa diferencia refuta una equivalencia simple entre el conjunto observado y el corte cartográfico de referencia.

Todavía no se descargó ni validó una geometría/crosswalk. El TXT de 2009–2021 documenta `DEF` y `DEL` en marco DERFE 2021; el de 2024 los documenta en marco DERFE 2023; `SECCION` se refiere al año correspondiente. Por ello la compatibilidad cartográfica sigue **pendiente**, no asumida.

## Actualizaciones al Marco Geográfico Electoral

La resolución pública [INE-CT-R-0175-2023](https://repositoriodocumental.ine.mx/xmlui/bitstream/handle/123456789/152095/ine-ct-r-0175-2023.pdf) enlaza una carpeta pública con la relación DERFE de actualizaciones 2005–2022. El libro descargado contiene 376,914 bytes y SHA-256 `a844e36c288a359a3e3fd05afc2a861f12a8d6df954238e1b28722e9705fed79`.

La fuente se usa para linajes de división/fusión y banderas de ambigüedad, no como geometría. Su cobertura termina en 2022; por ello cualquier resultado 2024 se marca parcial.

## Covariables INEGI

Las [Estadísticas Censales a Escalas Geoelectorales 2020](https://www.inegi.org.mx/app/descarga/ficha.html?ag=0&f=csv&tit=540314) se descargaron desde la distribución CSV oficial. El ZIP tiene 20,609,412 bytes y SHA-256 `db357fee6f869ec10c7c996e72d4ab6a339d10b20b8043f63ab5a256339708fe`; contiene 68,806 secciones únicas.

La ficha y los metadatos incluidos declaran identificador `MEX-INEGI.ESD2.01-CPV-2020`, referencia censal 15 de marzo de 2020 y modificación 18 de agosto de 2021. Esta última fecha es posterior a la elección federal de 2021: ECEG no se usa en el gate principal 2021, sólo en una prueba secundaria 2024. No se considera crosswalk histórico. La validación está en `data/manifests/eceg_source_manifest.csv` y la selección de variables en `artifacts/tables/eceg_selected_variable_dictionary.csv`.
