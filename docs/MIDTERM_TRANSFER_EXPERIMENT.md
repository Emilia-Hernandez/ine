# Experimento de transferencia hacia elecciones intermedias

## Pregunta

Para pronosticar la participación de 2027, ¿conviene entrenar sólo con elecciones
intermedias o conservar las presidenciales como información auxiliar?

## Diseño congelado

El target fuera de tiempo es 2021, la única elección intermedia plenamente comparable
con el contrato actual. Todas las variantes usan el mismo universo A+B, pesos por
registros identificados, baseline de la intermedia anterior, corrección nacional y
`HistGradientBoostingRegressor`.

Se comparan tres variantes:

1. `shared_all_elections`: modelo actual entrenado con todos los targets anteriores.
2. `midterm_only`: misma especificación, entrenada sólo con targets intermedios.
3. `midterm_transfer_two_head`: una cabeza compartida usa todas las elecciones y una
   cabeza especialista usa sólo intermedias; su salida se combina 50/50. Ambas reciben
   variables familiares construidas exclusivamente con elecciones anteriores.

Las variables nuevas separan niveles históricos presidenciales e intermedios,
cambios dentro de cada familia, la última transición presidencial→intermedia, la
transición inversa y sus contextos estatal y nacional. `cycle_source_max_year` debe
ser siempre menor al target.

## Inferencia

Se reporta MAE ponderado y una comparación pareada mediante bootstrap por entidad.
El intervalo geográfico indica si la mejora está distribuida territorialmente; no
equivale a incertidumbre entre ciclos electorales porque sólo existe un target
intermedio fuera de tiempo.

Por esa razón ninguna variante se promueve automáticamente al pronóstico 2027, aunque
resulte mejor en 2021. El resultado sirve para escoger el siguiente challenger y debe
combinarse después con el bloque espacial explícito ya promovido.

## Resultado

| Variante | MAE ponderado 2021 | Cambio frente al modelo actual |
|---|---:|---:|
| Compartido, todas las elecciones | 8.098 pp | referencia |
| Transferencia, dos cabezas 50/50 | 8.174 pp | +0.077 pp |
| Sólo intermedias | 8.494 pp | +0.397 pp |

El modelo que descarta presidenciales empeora 4.90% en términos relativos y sólo
mejora al referente en 8 de 32 entidades. El intervalo bootstrap por entidad para su
cambio de MAE es `[+0.121, +0.716]` pp: dentro de este único ciclo, el deterioro es
territorialmente consistente.

La variante de transferencia empeora 0.95% relativo y mejora en 12 de 32 entidades.
Su intervalo `[-0.103, +0.247]` pp cruza cero, por lo que no puede distinguirse con
claridad de la referencia mediante remuestreo geográfico. La cabeza compartida con
las variables de ciclo, considerada aisladamente, obtiene 8.101 pp: prácticamente el
mismo error que el modelo actual. La pérdida de la mezcla proviene de dar 50% de peso
a una cabeza especialista que sólo pudo aprender del target 2015.

La decisión es conservar todas las elecciones en el aprendizaje principal. Para 2027
el baseline y la fila a predecir siguen siendo de familia intermedia; las presidenciales
no se descartan porque aportan diversidad temporal. Las variables de ciclo quedan
disponibles, pero no se promueven con esta única validación.

## Reproducción

```bash
make midterm-transfer
```

Salidas:

- `artifacts/tables/midterm_cycle_mart.parquet`
- `artifacts/tables/midterm_transfer_predictions.parquet`
- `artifacts/tables/midterm_transfer_metrics.csv`
- `artifacts/tables/midterm_transfer_registry.csv`
- `artifacts/midterm_transfer_decision.json`
