# Grafo de vecindad seccional para GNN

Actualizado: 2026-10-06.

## Resultado

El grafo espacial de trabajo representa las **70,751 secciones observadas en CCPC 2024**. La
cartografía oficial cubre el 100% de esas llaves. El resultado tiene 201,288 aristas no dirigidas:
201,286 de contigüidad territorial y 2 conexiones sintéticas, identificadas como tales, para
polígonos aislados. La matriz es simétrica, no contiene autoaristas y ningún nodo queda con grado
cero.

Este grafo no sustituye al grafo AMGE. AMGE prueba continuidad histórica por división o fusión;
la capa descrita aquí prueba vecindad espacial en el corte 2024. Son relaciones diferentes y deben
entrar a una GNN como canales o tipos de arista distintos si se combinan.

## Fuentes y evidencia

| Uso | Fuente | Evidencia conservada |
|---|---|---|
| Geometría y claves | [INE, capa nacional “Sección”](https://pautas.ine.mx/transparencia/mapas/index_2025.html) | El portal declara que los archivos son Shapefile comprimidos y ofrece la descarga nacional de Sección. |
| Archivo exacto | [ZIP oficial](https://pautas.ine.mx/transparencia/mapas/cob_2024/SECCION.zip) | 102,602,388 bytes; SHA-256 `7098010b3c58d708afc8c0f166552fc3713699c4f39508f6fe42be5f9069c686`. |
| Fecha y proyección | `SECCION/SECCION.shp.xml`, dentro del ZIP | Creación/proyección `2024-05-09`; Lambert Conforme Cónica, WGS84, unidad metro. |
| Significado del producto | [INE, productos especializados](https://www.ine.mx/voto-y-elecciones/especializados/) | El MGS nacional contiene polígonos de entidad, distrito, municipio y sección y usa Lambert Conforme Cónica. |
| Universo modelado | CCPC 2024, ya auditado en el proyecto | 70,751 llaves únicas `entidad:sección`; todas tienen geometría. |
| Definición topológica | [OGC Simple Features](https://www.ogc.org/standards/sfa/) y [PySAL Rook](https://pysal.org/libpysal/stable/generated/libpysal.weights.Rook.html) | Rook considera vecinas a dos áreas cuando comparten una arista, no sólo un vértice. |

El manifiesto máquina-legible está en
`data/manifests/spatial_graph_source_manifest.csv`; la configuración congelada, incluidos URL,
hash, fechas y umbrales, está en `configs/spatial_graph.yaml`.

### Por qué se usa este archivo

La edición contiene 70,753 polígonos y fue actualizada el 9 de mayo de 2024. Coincide con las
70,751 secciones CCPC 2024 salvo dos polígonos oficiales (`07:2049` y `20:2562`) que no aparecen
en el universo estadístico. Esas dos filas se excluyen y quedan registradas. No se usa la capa
publicada para 2026 porque introduciría cambios posteriores al corte de observación 2024.

## Regla de vecindad

1. La llave canónica es `ENTIDAD:SECCION`, con relleno a 2 y 4 dígitos.
2. Se rechazan llaves duplicadas, geometrías nulas, vacías o inválidas. La fuente pasó todos los
   controles: 70,753 geometrías válidas y 70,753 llaves únicas.
3. Las coordenadas se normalizan en una malla de **0.1 m** sin sobrescribir la fuente. Esto absorbe
   diferencias numéricas submétricas entre vértices nominalmente comunes.
4. Dos secciones son vecinas Rook cuando, después de esa normalización, comparten al menos **1 m**
   de frontera. El límite elimina artefactos minúsculos y conserva la relación física.
5. Un contacto sólo por punto se registra en la tabla de contactos, pero no genera arista GNN.
6. No se restringe por entidad: 4,045 aristas Rook cruzan límites estatales y una
   GNN espacial debe poder propagar información a través de ellos cuando existe frontera común.
7. Los nodos sin ninguna frontera compartida reciben una sola arista al polígono más cercano de su
   misma entidad. La arista lleva `is_synthetic=true`, distancia métrica y tipo
   `island_nearest_same_entity`; nunca se confunde con contigüidad observada.
8. Las autoaristas no se exportan. Deben añadirse en la capa GNN si la arquitectura las requiere.

## Controles observados

| Control | Resultado |
|---|---:|
| Cobertura CCPC 2024 | 70,751 / 70,751 (100%) |
| Aristas Rook | 201,286 |
| Contactos sólo por punto excluidos | 14,417 |
| Contactos lineales menores de 1 m excluidos | 1 |
| Aristas sintéticas para nodos aislados | 2 |
| Nodos aislados después del respaldo | 0 |
| Componentes conexos | 5 |
| Grado mínimo / mediano / máximo | 1 / 5 / 50 |
| Simetría | exacta |
| Autoaristas | 0 |

Los cinco componentes no son un error: la cartografía nacional contiene masas terrestres e islas
separadas. Sólo se corrigen nodos de grado cero; no se inventan puentes entre componentes que ya
tienen estructura interna.

## Archivos para la GNN

- `section_graph_2024_nodes.parquet`: `node_id` contiguo, llave seccional, atributos geográficos,
  centroides, área, grado y componente.
- `section_graph_2024_edges.parquet`: una fila por arista no dirigida y tipo de evidencia.
- `section_graph_2024_contacts.parquet`: auditoría de todos los contactos de punto o línea.
- `section_graph_2024_adjacency.npz`: matriz CSR binaria simétrica, sin diagonal.
- `section_graph_2024_edge_index.npz`: `edge_index` dirigido en ambos sentidos, pesos unitarios,
  llaves ordenadas y número de nodos; puede cargarse directamente para PyTorch Geometric o DGL.
- `section_graph_2024_metadata.json`: procedencia, reglas, conteos y controles de cierre.

Los artefactos se regeneran con:

```bash
uv run python scripts/build_section_graph.py --download
```

Si el ZIP ya existe y coincide con tamaño y SHA-256, basta omitir `--download`.

## Límites de uso

- Éste es un snapshot 2024, no una certificación de la geografía 2027.
- Para backtests anteriores debe construirse un snapshot contemporáneo a cada elección o usar el
  grafo sólo como sensibilidad; aplicar retrospectivamente la topología 2024 puede filtrar cambios
  territoriales posteriores.
- La distancia de las dos aristas sintéticas no prueba colindancia. El modelo puede excluirlas con
  `is_synthetic` para una prueba de robustez.
- El peso exportado es 1. La longitud compartida se conserva para experimentar con pesos, pero no
  se impone una transformación arbitraria en el artefacto base.
