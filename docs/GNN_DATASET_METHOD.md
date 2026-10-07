# Dataset temporal para el challenger GNN

Actualizado: 2026-10-06.

## Resultado

Se construyeron cuatro grafos contemporáneos a las elecciones federales de 2015,
2018, 2021 y 2024. Cada ejemplo del GNN es una sección estable de clase A, con
variables conocidas antes de la elección, su target observado y la topología que
estaba publicada antes de ese proceso electoral. No se rellena ningún año histórico
con geometría futura.

## Fuentes cartográficas congeladas

| Elección | ZIP oficial INE | Creación de geometría | SHA-256 | Cobertura de llaves CCPC |
|---:|---|---:|---|---:|
| 2015 | [SECCION.zip](https://pautas.ine.mx/transparencia/mapas/cob_2015/SECCION.zip) | 2014-12-09 | `c8aa6f6d9b8821121e39799ffcb1fa3d1f4ad0d1ef049257e189fe7013b96751` | 68,362 / 68,362 |
| 2018 | [SECCION.zip](https://pautas.ine.mx/transparencia/mapas/cob_2018/SECCION.zip) | 2017-10-02 | `08c75206239b263204eabd13b1c4dfb6eb8c138e2181b15f71eb779e619c6d13` | 68,361 / 68,408 |
| 2021 | [SECCION.zip](https://pautas.ine.mx/transparencia/mapas/cob_2020/SECCION.zip) | 2020-06-11 | `4f39a2b87d66876cf551b3cfdad4fbf864f19330d6b7b823c2d25f22a40343b1` | 67,633 / 68,812 |
| 2024 | [SECCION.zip](https://pautas.ine.mx/transparencia/mapas/cob_2024/SECCION.zip) | 2024-05-09 | `7098010b3c58d708afc8c0f166552fc3713699c4f39508f6fe42be5f9069c686` | 70,751 / 70,751 |

La fecha se valida tanto contra `CreaDate` del XML de metadatos como contra la
fecha del encabezado DBF. Se validan además bytes, SHA-256, miembros obligatorios
del Shapefile y número de objetos. El manifiesto completo está en
`data/manifests/temporal_graph_source_manifest.csv`.

Las capas antiguas contienen defectos de origen que se corrigen de forma explícita:
3 anillos no cerrados en 2015; 10 anillos y una autointersección en 2018 y 2021;
ninguna reparación en 2024. Los conteos están congelados como pruebas para detectar
cambios silenciosos de librería o de fuente.

## Definición de vecindad

La regla es idéntica en los cuatro cortes:

- precisión geométrica normalizada a 0.1 m;
- arista Rook si dos polígonos comparten al menos 1 m de frontera;
- un contacto sólo por vértice se conserva en auditoría, pero no forma arista;
- un nodo sin vecino Rook recibe una sola arista sintética al polígono más cercano
  de su misma entidad; nunca cruza un estado;
- sin diagonal y con las dos direcciones de cada arista en `edge_index`.

Las aristas sintéticas están marcadas para hacer la ablación Rook estricto frente a
Rook más respaldo. Los grafos completos, contactos y exclusiones quedan en
`artifacts/graphs/temporal/<año>/`.

## Nodos, variables y folds

El dataset inducido usa exclusivamente unidades `S:` de clase geográfica A del
feature mart y el grupo de ablación `territorial_context`: 22 variables numéricas,
32 indicadores de entidad, dos de familia electoral y cuatro de tipo geográfico.
Los faltantes numéricos se guardan por separado; no se imputa al construir el
artefacto.

Cinco entidades completas (`04`, `14`, `20`, `26`, `31`) forman la validación
espacial fija. El resto de nodos etiquetados forma `fit_mask`. Para cada evaluación,
la mediana y la estandarización se ajustan sólo con `fit_mask` de elecciones
anteriores:

| Test | Años permitidos para entrenamiento/preprocesamiento |
|---:|---|
| 2018 | 2015 |
| 2021 | 2015, 2018 |
| 2024 | 2015, 2018, 2021 |

Esta separación evita que la validación espacial o el año evaluado influyan en la
imputación y el escalado.

## Bundles producidos

| Año | Nodos estables A | Nodos con target | Aristas Rook dirigidas | Aristas aumentadas dirigidas |
|---:|---:|---:|---:|---:|
| 2015 | 60,983 | 59,440 | 330,716 | 330,718 |
| 2018 | 60,430 | 58,275 | 324,972 | 324,974 |
| 2021 | 59,963 | 58,561 | 320,826 | 320,830 |
| 2024 | 58,534 | 56,780 | 306,060 | 306,062 |

Cada `graph_<año>.npz` contiene features, máscara de faltantes, target, peso,
`fit_mask`, `validation_mask`, las dos variantes de `edge_index` y las llaves en el
mismo orden. `gnn_fold_preprocessing.npz` congela los parámetros de cada fold. Los
Parquet asociados permiten auditar cada fila.

## Reproducción

```bash
uv run python scripts/build_gnn_dataset.py --download
uv run pytest -q tests/test_gnn_dataset.py
```

Configuraciones: `configs/temporal_graphs.yaml` y `configs/gnn_dataset.yaml`.
El siguiente experimento debe comparar, sin cambiar estos folds, el boosting
vigente, un MLP sin aristas, GCN y GraphSAGE; también debe retirar las aristas
sintéticas como ablación.
