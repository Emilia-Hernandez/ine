# Perfiles de riesgo de participación 2027

## Alcance

Este módulo implementa los pasos 1–6 del paquete de evidencia para el equipo de
ciencia política. Su propósito es identificar secciones donde podría bajar la
participación, cuantificar la magnitud y el electorado expuesto, y describir los
patrones de edad y sexo que comparten. No diseña intervenciones, no estima efectos
causales y no sustituye el paso 7 de evaluación de la política cuando ésta exista.

Se ejecuta con:

```bash
uv run python scripts/run_turnout_risk_profiles.py
# o
make turnout-risk-profiles
```

## 1. Panel histórico y descomposición

La unidad principal conserva el contrato territorial del proyecto:

- A: sección estable;
- B: componente de linaje oficial agregado por suma de conteos;
- C/D: no se fuerzan a una unidad longitudinal local.

Para cada transición de misma familia (2009→2015, 2012→2018, 2015→2021 y
2018→2024), los conteos directos de `voted` y `did_not_vote` se agregan por sexo y
por cuatro grupos de edad. Las tasas pequeñas se suavizan hacia la media
entidad–año–grupo con 100 registros identificados de fuerza previa. El archivo de
sensibilidad repite los resúmenes con fuerzas 0, 50, 100 y 200.

La descomposición simétrica de Kitagawa separa, dentro de cada partición, el cambio
atribuible a tasas del cambio atribuible a composición. La suma de ambos términos
reproduce exactamente el cambio de la tasa suavizada de la partición. Es una
identidad descriptiva, no una atribución causal.

## 2. Riesgo de una caída

Se entrenan clasificadores `HistGradientBoostingClassifier` para tres resultados:

- cualquier caída;
- caída de al menos 2 puntos porcentuales, umbral principal;
- caída de al menos 5 puntos porcentuales.

El outcome es la diferencia entre la participación de la elección anterior de la
misma familia y la participación observada. Se comparan dos grupos de variables:
`competition_concurrency` y `entity_cycle_context`. Cada fold usa únicamente años
target anteriores. La calibración histórica también es expansiva: 2018 se reporta
sin calibración, 2021 sólo puede aprender de 2018 y 2024 sólo de 2018/2021.

`competition_concurrency` queda seleccionado. Para el umbral de 2 pp:

| Target | Tasa positiva ponderada | Brier ponderado | ROC AUC | Precisión en el 20% del electorado | Casos positivos capturados |
|---|---:|---:|---:|---:|---:|
| 2018 | 28.87% | 0.205 | 0.615 | 52.88% | 36.63% |
| 2021 | 26.63% | 0.170 | 0.747 | 55.40% | 41.61% |
| 2024 | 50.66% | 0.327 | 0.423 | 33.56% | 13.25% |

El resultado 2024 muestra que el orden de riesgo no transfiere bien entre el
régimen intermedio y el presidencial. Como 2027 es una elección intermedia, las
probabilidades finales se recalibran exclusivamente con las predicciones fuera de
tiempo de 2021. Los resultados 2018/2024 permanecen en la entrega como pruebas de
sensibilidad y se activa `cross_cycle_transfer_warning=true`. Por esta razón las
probabilidades deben comunicarse como riesgo del análogo intermedio, no como
certezas frecuentistas universales.

## 3. Ranking operativo para análisis

Cada sección contiene tres ejes separados:

1. `risk_probability_02pp`: probabilidad calibrada de una caída ≥2 pp;
2. `predicted_decline_pp`: magnitud puntual del modelo 2027 ya promovido;
3. `predicted_additional_nonvoters`: magnitud positiva multiplicada por lista
   nominal.

La prioridad cruza los percentiles 80 de probabilidad y volumen. Es una forma
transparente de ordenar el archivo, no una recomendación de política. El resultado
cubre 70,751 secciones; 5,656 C/D reciben una referencia estatal explícitamente
marcada en lugar de un perfil local inventado.

El volumen puntual agregado es 246,870 no votantes adicionales respecto del
baseline de misma familia. Su intervalo superior es amplio y debe consultarse en
la columna correspondiente; no es un conteo observado ni un efecto causal.

## 4. Arquetipos continuos y superpuestos

Los clusters dejan de ser la salida principal. Cada sección recibe puntajes de
0–100, calculados contra la distribución nacional A/B ponderada por lista nominal,
en seis dimensiones:

- participación juvenil baja;
- brecha desfavorable a hombres;
- brecha desfavorable a mujeres;
- deterioro histórico 2015→2021;
- participación general baja;
- volatilidad histórica alta.

Una sección activa todos los arquetipos que superan p80. La robustez de la etiqueta
se mide variando el corte entre p75 y p85; se conservan puntaje, estado para los
tres cortes, margen y lista multilabel. Esto evita forzar grupos mutuamente
excluyentes.

Los tres clusters anteriores se conservan sólo como segmentos exploratorios
secundarios. Su ARI es 0.932, pero el silhouette de 0.170 confirma que no son
taxonomías naturales.

## 5. Backtest completo de arquetipos

Para 2018, 2021 y 2024 se reconstruye cada arquetipo usando exclusivamente
variables disponibles antes del target. Se reportan tasa observada de caída ≥2 pp
en el quintil activo, tasa en el resto, lift, volumen positivo capturado y AUC.

Sólo la **brecha desfavorable a hombres** presenta lift positivo y AUC mayor a 0.5
en los tres folds. Los demás arquetipos siguen siendo descriptores útiles, pero no
deben presentarse como predictores históricamente consistentes. En particular,
participación general baja y volatilidad muestran reversión a la media en algunos
ciclos.

## 6. Incertidumbre del ranking

Se ajustan 20 réplicas con pesos bootstrap bayesianos exponenciales por entidad.
Para cada sección se entregan:

- media, desviación y percentiles 10/90 de probabilidad;
- percentiles 10/90 de posición en el ranking;
- frecuencia de pertenecer al 20% superior;
- frecuencia de combinar alto riesgo y alto volumen.

Resultan 9,875 secciones de alto riesgo robusto, 53,202 robustamente fuera del
quintil superior y 7,674 sensibles al remuestreo. Esta incertidumbre mide
estabilidad del modelo y de la composición territorial; no incorpora el posible
cambio de régimen electoral, que permanece como una limitación separada.

## 7. ECEG como descriptor, nunca como predictor

Se añaden nueve variables ECEG 2020: sexo, población adulta y mayor, analfabetismo,
actividad económica, discapacidad, lengua indígena, internet y escolaridad. A/B se
agregan a la unidad longitudinal; C/D usan coincidencia directa de clave 2020 cuando
existe y referencia estatal etiquetada en caso contrario.

ECEG está excluido del clasificador de riesgo. Su función es permitir que el equipo
de política interprete los arquetipos con contexto sociodemográfico sin convertir
una fotografía de 2020 en una explicación causal.

## 8. Entrega

Los artefactos principales son:

- `artifacts/tables/section_risk_profiles_2027.parquet` y `.csv`: sección;
- `artifacts/tables/municipality_risk_summary_2027.csv`: municipio;
- `artifacts/tables/entity_risk_summary_2027.csv`: entidad;
- `artifacts/tables/historical_subgroup_decomposition.parquet`: evidencia histórica;
- `artifacts/tables/historical_subgroup_decomposition_sensitivity.csv`: robustez al
  suavizado;
- `artifacts/tables/turnout_decline_risk_metrics.csv`: backtests completos;
- `artifacts/tables/turnout_decline_calibration.csv`: confiabilidad por deciles;
- `artifacts/tables/turnout_profile_summary.csv`: centroides interpretables;
- `artifacts/tables/turnout_archetype_summary_2027.csv`: arquetipos multilabel;
- `artifacts/tables/turnout_archetype_backtest.csv`: validación por target;
- `artifacts/tables/turnout_archetype_backtest_summary.csv`: consistencia histórica;
- `artifacts/tables/turnout_risk_bootstrap_uncertainty_2027.parquet`: incertidumbre;
- `artifacts/tables/turnout_archetype_eceg_summary.csv`: contexto ECEG;
- `artifacts/tables/turnout_profile_eceg_coverage.csv`: procedencia y cobertura ECEG;
- `artifacts/tables/turnout_risk_data_dictionary.csv`: diccionario de entrega;
- `artifacts/reports/turnout_risk_profiles_2027.html`: mapa y ficha navegable;
- `artifacts/turnout_risk_profile_decision.json`: contrato y advertencias legibles
  por máquina.

## Límites para la entrega a politólogos

- Las asociaciones por edad y sexo provienen de conteos directos, pero siguen sin
  identificar efectos de una intervención.
- A/B son comparables mediante estabilidad o linaje oficial; C/D son referencias
  estatales de menor confianza.
- La geografía 2027 aún no está certificada; se usa el snapshot auditado 2024.
- La transferencia 2024 es una advertencia material contra sobreinterpretar el
  ranking fuera de elecciones intermedias.
- El bootstrap por entidad no mide incertidumbre por cambio de régimen electoral.
- Sólo un arquetipo muestra consistencia predictiva en los tres folds; el resto es
  estrictamente descriptivo.
- El paso 7 sólo debe comenzar cuando exista una intervención definida, con
  población elegible, tratamiento, outcome y mecanismo de asignación documentados.
