# Método de la proyección experimental 2027 actualizada

Actualizado: 2026-10-06.

## Objetivo

Construir la primera proyección de participación 2027 completamente trazable, usando únicamente elecciones hasta 2024. La salida debe mostrar por separado:

1. baseline histórico;
2. corrección aprendida por el modelo;
3. corrección nacional por familia electoral;
4. intervalo empírico;
5. procedencia y confianza territorial.

No existe todavía resultado, lista nominal ni marco seccional 2027. Por eso la proyección usa las 70,751 secciones del snapshot 2024 y se etiqueta experimental.

## Baseline contra el que se compara el MAE

El baseline congelado es `lag_same_type_stable_plus_official_lineage`:

- para una sección estable A, usa su participación de 2021;
- para una sección modificada B, agrega su componente territorial oficial y usa la participación 2021 del componente;
- para C/D, el producto operacional busca sección, componente, municipio, entidad y finalmente el promedio nacional.

Es una regla simple: “la próxima elección intermedia se parecerá a la intermedia anterior”. No es una regresión ni un árbol.

En backtest, su MAE ponderado fue 9.38 pp en 2021 y 4.42 pp en 2024. No puede calcularse MAE 2027 hasta conocer el resultado real.

## Modelo challenger

El modelo es `HistGradientBoostingRegressor` de scikit-learn: un ensamble de árboles de decisión entrenados secuencialmente. Cada árbol divide las observaciones según umbrales de variables y los árboles posteriores intentan corregir los errores de los anteriores.

No predice siempre desde cero. Aprende el residual:

```text
residual = participación real - baseline de la elección anterior del mismo tipo
```

La predicción del candidato es:

```text
model_prediction = baseline + 0.25 × residual_estimado_por_los_árboles
```

El factor 0.25 limita sobreajuste. Si falta baseline, se usa la predicción directa de otro boosting con la misma especificación.

Hiperparámetros congelados:

- 250 iteraciones;
- learning rate 0.05;
- máximo 15 hojas por árbol;
- mínimo 40 observaciones por hoja;
- regularización L2 de 1.0;
- semilla 27.

El grupo seleccionado es `territorial_context`. Incluye participaciones rezagadas, cambios y tendencia histórica, volatilidad, tamaño de lista nominal, cobertura de registros y clase territorial. Además incorpora promedios y dispersiones rezagados por entidad y nación, la diferencia de cada unidad frente a esos referentes y el tipo de unidad geográfica. No usa sexo/edad ni ECEG en el predictor puntual porque la ablación no mostró una mejora consistente.

Los faltantes numéricos usan mediana aprendida en entrenamiento; entidad, familia y tipo geográfico se codifican como categorías. El algoritmo fue retenido después de compararlo con XGBoost, LightGBM y Extra Trees bajo los mismos folds y variables.

## Entrenamiento y corrección 2027

Se entrena con targets 2015, 2018, 2021 y 2024. Todas sus variables provienen de elecciones anteriores a cada target. Para 2027, las variables terminan en 2024 y el baseline de misma familia corresponde a 2021.

Después del boosting se suma +5.21 pp, el cambio nacional intermedio observado entre 2015 y 2021. Este ajuste queda en una columna separada y se recorta el resultado final a `[0,1]`.

## Territorio e incertidumbre

- A/B: boosting residual más corrección nacional;
- C/D: respaldo jerárquico más corrección nacional;
- intervalos A/B: errores fuera de tiempo 2021 del HistGradientBoosting con contexto territorial, por clase;
- intervalos C/D: errores del respaldo jerárquico 2021; C usa el pool C+D porque sólo tiene 46 casos calibrables.

La geografía es la observada en 2024 y los linajes públicos terminan en 2022. Los intervalos se recalculan porque cambiar las features también cambia los errores del modelo. Son intervalos seccionales; promediar sus límites no crea un intervalo estadístico para el total nacional.
