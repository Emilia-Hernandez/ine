# Método de continuidad territorial con fuentes públicas

Actualizado: 2026-10-05.

## Fuente utilizada

La fuente de linaje es el libro **Relación de secciones con actualizaciones al Marco Geográfico Electoral 2005–2022**, publicado por DERFE mediante la resolución `INE-CT-R-0175-2023`. La resolución y su carpeta de entrega son públicas; el archivo se obtuvo sin autenticación ni una nueva solicitud.

| Elemento | Valor |
|---|---|
| Resolución oficial | `https://repositoriodocumental.ine.mx/xmlui/bitstream/handle/123456789/152095/ine-ct-r-0175-2023.pdf` |
| Carpeta pública | `https://1drv.ms/f/s!AtO0oFXXb9dE-b1Y9VF2635ojiBCLg?e=bzcsdF` |
| Libro | `Relación de casos AMGE 2005-2022_Ago22.xlsx` |
| Bytes | 376,914 |
| SHA-256 | `a844e36c288a359a3e3fd05afc2a861f12a8d6df954238e1b28722e9705fed79` |
| Cobertura declarada | 2005–2022 |

El manifiesto máquina-legible está en `data/manifests/public_geography_manifest.csv`.

## Interpretación del libro

La hoja tiene campos separados para entidad, geografía origen, geografía destino, programa, caso, documentos jurídicos y fecha de actualización. La lectura aplica estas reglas:

1. Las filas físicas se conservan con `source_excel_row`.
2. Los encabezados fusionados de entidad/evento se propagan sólo para reconstruir el contexto visual del libro.
3. Un guion (`608-617`) significa rango inclusivo.
4. Una coma o “Y” (`38 Y 39`) significa códigos discretos, no rango.
5. Cada código se serializa como `entidad:sección`.
6. Se crean aristas únicamente para `DIVISIÓN DE SECCIONES` y `FUSIÓN DE SECCIONES` con ambos lados completos y forma uno-a-muchos o muchos-a-uno.
7. Reasignaciones de fracciones, cambios de límites, georreferencias y relaciones incompletas se registran como ambiguas; no generan linaje cuantitativo.

Resultados del parser:

- 2,663 filas-evento con afectación seccional;
- 1,469 filas-evento elegibles para linaje;
- 7,819 aristas origen–destino;
- 11,631 registros de sección afectada, incluyendo rol y tipo de afectación.

## Componentes territoriales

Para cada elección objetivo `t` se filtran eventos con `effective_year < t`. Esta desigualdad estricta es conservadora: evita usar una actualización del mismo año que pudiera haber ocurrido después de la jornada.

Las aristas elegibles se convierten en componentes conexos no dirigidos. Un componente representa una familia de secciones relacionadas por divisiones o fusiones oficiales. Para compararla entre años:

- se suman `SV`, `NV`, `NS` y `LN` de todos sus miembros observados;
- se calcula participación después de agregar;
- jamás se reparte un conteo de la sección origen entre descendientes;
- si cualquier miembro tiene además un evento ambiguo, el componente completo pasa a clase D.

## Clases de confianza

| Clase | Interpretación |
|---|---|
| A | Código con historia suficiente, rezago de la misma familia, municipio/tipo estables y sin eventos AMGE previos. |
| B | Miembro de un componente oficial de división o fusión, sin evidencia ambigua. |
| C | Sección nueva o con historia corta; no tiene rezago comparable suficiente. |
| D | Cambio AMGE ambiguo, relación incompleta o metadatos territoriales variables. |

La clase se recalcula en cada corte temporal; no se asigna retrospectivamente usando eventos futuros.

## Fuentes registradas pero no usadas como crosswalk

- El Marco Geográfico Seccional de diciembre de 2022 está públicamente disponible en la misma respuesta, pero no fue necesario para el backtest de linajes y no se descargó en esta fase.
- El Tableau CCPC declara cartografía de mayo de 2023 y permite descargas, pero no se usó como fuente de relaciones origen–destino.
- ECEG 2020 de INEGI se reserva para covariables sociodemográficas; una fotografía 2020 no constituye una correspondencia histórica.

## Limitación 2024

El libro termina en 2022. La clasificación 2024 y su backtest son una robustez parcial: no incorporan todavía todas las modificaciones aprobadas en 2023. La evaluación principal para 2027 es 2015→2021, completamente contenida dentro de la cobertura pública del libro.
