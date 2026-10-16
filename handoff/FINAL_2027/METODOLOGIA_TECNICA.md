# Metodología técnica 2027

## Universo y fórmula

El maestro conserva las 70,751 secciones del snapshot CCPC 2024. Participación = SV/(SV+NV); toda tasa agregada es razón de sumas, nunca promedio simple de porcentajes.

## Modelo

Para cada fold temporal se usa únicamente información anterior al target. El target residual es `participación_target - participación_intermedia_previa - componente_nacional`. Se centra con lista nominal preelectoral dentro del fold. La predicción es `clip(persistencia + componente_nacional + 0.25 × residual_centrado, 0, 1)`. Esto evita doble conteo nacional/estatal.

## Componente nacional

Para 2027 se usa la media aritmética de los cambios nacionales 2009→2015 y 2015→2021, ambos calculados como razón de sumas. Cero y el último cambio se conservan como sensibilidad. Para 2021 sólo se usa el cambio 2009→2015.

## Caída material

`caida_material = 1` cuando `participación_target - participación_previa <= -0.01`. El umbral es exactamente un punto porcentual. Se comparan persistencia, modelo corregido 0.25 y el mismo modelo con peso doble de entrenamiento para caídas. La alternativa ponderada sólo se promueve si reduce falsos negativos de 2021 sin reducir F1 ni balanced accuracy.

## Municipio y vecinos

Las referencias municipales históricas suman SV y SV+NV y excluyen la propia sección. Sólo se publican cuando el municipio observado coincide temporalmente. La referencia 2027 agrega votos proyectados y lista nominal y también excluye la sección. El contraste vecinal usa aristas Rook con frontera compartida del grafo oficial 2024; se excluyen las dos aristas sintéticas de islas.

## Perfiles y precedencia

- P1: ambos cambios intermedios <= -1 pp.
- P2: cambio central 2021→2027 <= -1 pp, sin P1.
- P3: brecha municipal <= -1 pp en al menos dos intermedias, sin P1/P2.
- P4: mejora de brecha municipal >=1 pp en ambos tramos, sin P1-P3.
- P5: brecha municipal >=1 pp en al menos dos períodos y ningún cambio histórico/proyectado <= -1 pp, sin P1-P4.
- P6: tres observaciones intermedias y proyección, pero ninguna regla anterior.
- EI: clase C/D o historia insuficiente; no es un séptimo perfil sustantivo.

Las señales se conservan por separado. La demografía no interviene.
