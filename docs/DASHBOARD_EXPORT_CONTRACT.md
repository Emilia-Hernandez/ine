# Contrato de selección y exportación

`dashboard.data_layer.select_frame()` es la fuente única del conjunto activo. Intersecta `perfil_visual_id`, el porcentaje superior nacional de densidad y el porcentaje inferior nacional de incidencia municipal. El zoom, el viewport y el clic de detalle no alteran el conjunto exportable.

El CSV usa UTF-8 con BOM, conserva claves como texto y contiene exactamente una fila por `clave_seccion`. Exporta todas las columnas del release publicado, entre ellas identificación territorial, historia electoral y conteos disponibles, predicción y baseline, señales, perfiles sustantivos y visuales, demografía, densidad, seguridad, calidad, procedencia y versiones. Los faltantes permanecen vacíos; no se convierten a cero.

`metadatos_filtros_json` registra en cada fila los filtros, el universo, el conteo, el porcentaje efectivo de seguridad, la versión del modelo y la hora de generación. Esto mantiene un solo botón principal sin perder trazabilidad. En una selección vacía el archivo conserva encabezados y cero filas de datos.

Los campos de seguridad incluyen `tasa_incidencia_total_100k`, numerador, población CONAPO, año, claves municipales, disponibilidad, percentil, fuentes y versión metodológica. Su nivel territorial es municipal asignado a sección. Los campos de linaje y `fuente_historia_electoral` deben usarse para evitar interpretar observaciones agregadas como votos seccionales independientes.
