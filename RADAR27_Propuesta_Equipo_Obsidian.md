---
title: "RADAR 27 — Propuesta para el equipo"
aliases:
  - RADAR 27
tags:
  - hackathon
  - INE
  - ciencia-de-datos
  - grafos
  - prediccion
---

# RADAR 27
## Propuesta para el Reto 2 — Predicción y escenarios de riesgo de abstención

**Nombre provisional:** RADAR 27 — Sistema geoespacial de alerta temprana de riesgo de abstención  
**Hackathon:** *Hackea la participación: Datos que construyen democracia*  
**Eje:** Reto 2 — Predicción y escenarios de riesgo de abstención  
**Objetivo del documento:** explicar al equipo qué queremos construir, por qué cada decisión metodológica es defendible y qué distingue esta propuesta de un proyecto estándar de predicción.

---

# 1. La propuesta en una frase

> **RADAR 27 no busca simplemente mapear dónde hubo baja participación; busca anticipar qué territorios presentan mayor riesgo de deterioro de la participación, cuantificar la incertidumbre, explicar los factores asociados al riesgo y simular cómo podría cambiar la priorización territorial bajo distintos escenarios de intervención.**

El producto final sería un sistema reproducible y auditable que combine:

1. datos históricos de participación del INE;
2. información sociodemográfica agregada;
3. estructura espacial entre secciones electorales;
4. modelos predictivos comparados contra baselines simples;
5. representaciones latentes o *embeddings* cuando aporten valor;
6. cuantificación de incertidumbre;
7. explicación de predicciones;
8. un simulador de escenarios;
9. un esquema transparente de priorización de recursos;
10. un mapa/dashboard interactivo.

La idea no es usar técnicas avanzadas por apariencia. Cada componente debe justificar su existencia mediante una mejora medible, una interpretación clara o una utilidad institucional concreta.

---

# 2. Por qué elegir el Reto 2

La convocatoria plantea tres retos. El Reto 2 pregunta qué zonas podrían presentar mayor abstención en el futuro si no se interviene y solicita explícitamente un modelo de riesgo, al menos dos escenarios —sin intervención y con intervención—, un esquema territorial fácil de interpretar y recomendaciones preventivas.

Esto hace que el reto permita construir un producto de ciencia de datos de punta a punta:

$$
\text{Datos}
\rightarrow \text{Predicción}
\rightarrow \text{Estructura espacial}
\rightarrow \text{Incertidumbre}
\rightarrow \text{Explicación}
\rightarrow \text{Escenarios}
\rightarrow \text{Priorización}
\rightarrow \text{Decisión}
$$

El Reto 1 también permite hacer un proyecto sólido, pero tiene mayor riesgo de terminar pareciéndose a una segmentación estándar con K-means y fichas de perfiles. El Reto 2 ofrece más espacio para demostrar simultáneamente capacidad de predicción, análisis espacial, visualización, simulación y diseño de una herramienta institucional.

## Por qué esto es especialmente pertinente para 2027

El INE informa que el Proceso Electoral Federal 2026–2027 inició el 10 de septiembre de 2026 y que la jornada electoral federal será el 6 de junio de 2027, cuando se renovarán las 500 diputaciones federales.

Por ello, RADAR 27 puede plantearse como una herramienta prospectiva para el siguiente proceso federal, sin afirmar que el hackathon exija explícitamente pronosticar 2027.

---

# 3. Qué exige el reto y cómo lo convertimos en un producto mejor

| Requisito del Reto 2 | Respuesta mínima posible | Propuesta RADAR 27 |
|---|---|---|
| Modelo de riesgo | Regresión o árbol | Baselines + boosting + estructura espacial + modelo de grafo como challenger |
| Tendencias históricas | Promedios y variaciones | Trayectorias, pendientes, volatilidad, diferencias por tipo de elección |
| Variables sociodemográficas | Meter columnas al modelo | Features documentadas, agregadas y sin datos personales |
| Escenario sin intervención | Forecast | Baseline predictivo con intervalo de incertidumbre |
| Escenario con intervención | Sumar una cantidad arbitraria | Simulador explícito de supuestos, sin disfrazarlo de causalidad |
| Semáforo territorial | Rojo/amarillo/verde | Riesgo + tendencia + incertidumbre + tipo de alerta |
| Recomendaciones | Lista general | Priorización territorial bajo restricciones transparentes |
| Mapa | Choropleth estático | Dashboard comparativo, exploración por sección y territorios análogos |
| Viabilidad institucional | Conceptual | Pipeline reproducible + archivos geográficos + datos procesados + documentación |

---

# 4. Decisión central: predecir riesgo, no sólo abstención observada

La baja participación histórica y el deterioro futuro no son lo mismo.

==Una zona puede tener una participación históricamente baja pero estable. Otra puede haber tenido una participación relativamente alta y estar mostrando una caída sostenida. Para planeación preventiva, ambos casos contienen información distinta.

Por eso RADAR 27 propone separar dos dimensiones:

## 4.1 ==Riesgo estructural

Captura territorios con ==niveles persistentemente bajos de participación respecto de unidades comparables.

$$
R_i^{estructural}
=
f(\text{nivel histórico}, \text{persistencia}, \text{posición relativa})
$$

## 4.2 ==Riesgo emergente

Captura territorios cuya ==trayectoria reciente apunta a deterioro.

$$
R_i^{emergente}
=
f(\text{pendiente}, \text{cambio reciente}, \text{vecindario}, \text{volatilidad})
$$

La matriz conceptual sería:

|                                  | Tendencia estable  | Tendencia negativa   |
| -------------------------------- | ------------------ | -------------------- |
| Participación relativamente alta | Estable            | **Alerta emergente** |
| Participación relativamente baja | Rezago persistente | **Riesgo crítico**   |

### Por qué esta decisión es mejor

- distingue niveles de cambio;
- ==evita que el modelo simplemente redescubra dónde siempre ha habido más abstención;
- hace que el mapa sea accionable;
- permite diseñar mensajes institucionales distintos para rezago persistente y deterioro reciente;
- es más interpretable que un score único sin contexto.

---

# 5. Unidad territorial: sección electoral como objetivo, con una regla de factibilidad

La plataforma CCPC permite trabajar a distintos niveles geográficos, incluido el nivel sección. ==El nivel sección ofrece la mayor granularidad territorial disponible para detectar patrones locales.

Por ello:

> **Unidad preferida: sección electoral × elección.**

Sin embargo, no se debe sacrificar validez por granularidad.

## Regla de decisión

1. intentar construir un panel consistente a nivel sección;
2. auditar cobertura, llaves y compatibilidad entre años;
3. si la armonización a nivel sección presenta problemas materiales, subir a municipio o distrito;
4. documentar el costo de granularidad y la razón del cambio.

### Por qué no fijamos la sección pase lo que pase

Porque una buena metodología debe poder decir “estos datos no soportan esta granularidad” si la evidencia lo exige. La convocatoria valora solidez y viabilidad, no complejidad por sí misma.

---

# 6. No mezclar indiscriminadamente elecciones presidenciales e intermedias

La plataforma reúne procesos federales de:

- 2009
- 2012
- 2015
- 2018
- 2021
- 2024

El propio manual del INE separa las comparaciones de elecciones federales intermedias —2009, 2015 y 2021— de las elecciones presidenciales —2012, 2018 y 2024—.

Por ello, para un ejercicio prospectivo hacia 2027, la señal principal de mismo tipo de elección debe ser:

$$
2009 \rightarrow 2015 \rightarrow 2021 \rightarrow 2027
$$

Las elecciones presidenciales:

$$
2012 \rightarrow 2018 \rightarrow 2024
$$

no se tiran. Sirven como información contextual sobre la propensión participativa del territorio y sobre la brecha entre tipos de proceso.

## Feature importante: brecha presidencial–intermedia

Ejemplo:

$$
Gap_i =
\bar{p}^{presidencial}_i
-
\bar{p}^{intermedia}_i
$$

==Una sección que aumenta mucho su participación en años presidenciales y cae fuertemente en intermedias tiene un patrón distinto a una sección estable.

### Por qué esta decisión es mejor

Evita pedirle al algoritmo que aprenda como equivalentes procesos con incentivos y niveles nacionales de participación distintos.

---

# 7. Representar cada territorio mediante una “huella participativa”

La idea central es que cada sección no se describa sólo por su última tasa de participación.

Construiremos una representación rica:

$$
x_i =
[
\text{niveles históricos},
\text{cambios},
\text{tendencia},
\text{volatilidad},
\text{brecha por sexo},
\text{perfil de edad},
\text{tipo de sección},
\text{contexto espacial},
\dots
]
$$

Entre las features candidatas:

### Históricas

- participación en cada elección;
- abstención;
- diferencia respecto de elección anterior comparable;
- pendiente de participación;
- media móvil;
- desviación estándar;
- máximo descenso;
- recuperación posterior a una caída;
- persistencia de bajo desempeño.

### Tipo de elección

- promedio en presidenciales;
- promedio en intermedias;
- gap presidencial–intermedia;
- tendencia dentro de cada familia.

### Sociodemográficas agregadas

Cuando estén efectivamente disponibles en los archivos:

- sexo;
- edad;
- grupo quinquenal;
- etapa de vida;
- tipo de sección;
- referente indígena;
- referente afromexicano;
- composición de lista nominal.

### Relativas

Muchas variables serán más útiles como diferencia respecto de un benchmark:

$$
p_i - p_{estado}
$$

$$
p_i - p_{municipio}
$$

$$
p_i - p_{vecinos}
$$

Esto reduce el riesgo de confundir shocks nacionales de participación con cambios locales.

---

# 8. El grafo: por qué sí tiene sentido aquí

El territorio tiene estructura.

==Una tabla tradicional considera que las observaciones son independientes. Pero las secciones electorales están insertas en un espacio geográfico y pueden compartir contextos territoriales.

Construiremos al menos un grafo principal:

## ==Grafo geográfico

- nodo = sección electoral;
- arista = contigüidad territorial;
- peso opcional = frontera compartida o distancia.

$$
G_{geo}=(V,E)
$$

Dos secciones están conectadas si son vecinas según la cartografía.

Esto permite construir features como:

$$
\bar p_{N(i)}
=
\frac{1}{|N(i)|}
\sum_{j \in N(i)} p_j
$$

y:

$$
SpatialGap_i
=
p_i-\bar p_{N(i)}
$$

## Qué nos permite detectar

### Isla de abstención

Sección con baja participación rodeada de secciones con mayor participación.

### Clúster de deterioro

Conjunto contiguo de secciones cuya participación está descendiendo.

### Outlier positivo

Sección con participación anormalmente alta respecto de su entorno.

### Contagio o correlación espacial

No afirmaremos causalidad, pero sí podremos medir si existe autocorrelación espacial.

## Grafo de similitud — opcional

==Como extensión, se puede construir un segundo grafo en el que se conecten territorios con huellas participativas similares, aunque estén lejos físicamente.

Esto permitiría encontrar “análogos” nacionales:

> “Esta sección de Puebla se parece históricamente a estas secciones de Guanajuato, Hidalgo y Veracruz.”

==El grafo de similitud sólo se conservará si añade interpretación o mejora predictiva.

---

# 9. Embeddings: herramienta, no argumento

Queremos usar embeddings, pero sólo si resuelven algo que las features tradicionales no resuelven.

Tres candidatos:

## 9.1 Embedding temporal

Comprimir la trayectoria de participación y composición mediante un autoencoder o encoder pequeño:

$$
X_i^{histórico}
\rightarrow
z_i^{temporal}
$$

El objetivo sería capturar patrones no lineales de trayectoria.

## 9.2 ==Embedding de grafo

Node2Vec, GraphSAGE no supervisado o un Graph Autoencoder pueden representar la posición de una sección dentro de la red territorial:

$$
G
\rightarrow
z_i^{graph}
$$

## 9.3 Embedding combinado

$$
z_i=
[
z_i^{temporal},
z_i^{graph},
X_i^{tabular}
]
$$

El embedding se puede alimentar a un modelo tabular posterior.

## Regla de oro

Un embedding entra al producto únicamente si:

1. mejora predicción fuera de muestra;
2. mejora la recuperación de territorios análogos;
3. o produce una representación visual/interpretable claramente útil.

Si no ocurre ninguna de las tres, se elimina.

---

# 10. Jerarquía de modelos: baseline first

Una propuesta sólida no empieza con la GNN. Empieza preguntando cuánto valor añadido aporta cada capa de complejidad.

La secuencia será:

### M0 — Baseline ingenuo

- último valor comparable;
- media histórica;
- tendencia lineal simple.

### M1 — Modelo lineal regularizado

Elastic Net o similar.

Sirve como benchmark interpretable.

### M2 — Gradient boosting

LightGBM o XGBoost sobre features tabulares.

Probablemente será uno de los modelos más fuertes en datos tabulares.

### M3 — Boosting + features espaciales

Agregar:

- media de vecinos;
- dispersión de vecinos;
- Local Moran/LISA;
- centralidad o embedding geográfico.

### M4 — Embeddings como features

Boosting + embedding temporal + embedding de grafo.

### M5 — GNN, únicamente como challenger

GraphSAGE, GAT o arquitectura semejante.

Se adopta como modelo final sólo si supera consistentemente al mejor modelo más simple.

## Por qué esta estrategia es mejor

Nos permite decir:

> “No usamos una GNN porque sonaba sofisticada. La comparamos contra XGBoost y medimos si realmente aportaba.”

Eso es una señal fuerte de madurez técnica.

---

# 11. Validación: nunca random split puro

Un random train/test split permitiría que el modelo vea patrones de una misma elección tanto en entrenamiento como en prueba. Eso puede producir métricas artificialmente optimistas.

==La evaluación principal debe respetar el tiempo.

## ==Backtesting

La lógica general es:

> entrenar únicamente con información que habría estado disponible antes de una elección y predecir una elección posterior.

Debido a que sólo existen seis cortes electorales y sólo tres elecciones intermedias en el periodo, la cantidad de folds temporales verdaderamente comparables es limitada. Esto debe declararse desde el inicio.

Podemos complementar con:

- folds por elección;
- holdout geográfico;
- evaluación específica en elecciones intermedias;
- pruebas de robustez usando elecciones presidenciales como tarea auxiliar, no como sustituto del backtest principal.

## Métricas

Si predecimos participación continua:

- MAE;
- RMSE;
- error absoluto mediano;
- error por decil de riesgo;
- calibración de intervalos.

Si construimos un clasificador de deterioro:

- PR-AUC;
- ROC-AUC;
- recall en el decil de mayor riesgo;
- precision@K;
- calibración.

Para la finalidad institucional, **precision@K y recall@K** pueden ser especialmente relevantes porque simulan recursos limitados.

---

# 12. Incertidumbre: no fingir precisión

No queremos un mapa que diga:

> “Participación 2027 = 51.37%”

sin expresar incertidumbre.

El producto debe mostrar:

$$
\hat{y}_i
$$

junto con un intervalo:

$$
[\hat L_i,\hat U_i]
$$

La primera opción será **conformal prediction**, porque permite construir intervalos predictivos con supuestos relativamente débiles y medir empíricamente su cobertura.

Esto permite distinguir:

- alto riesgo + alta confianza;
- alto riesgo + baja confianza.

### Utilidad institucional

La incertidumbre no sólo comunica prudencia. También identifica dónde conviene obtener más información antes de asignar recursos.

---

# 13. Explicabilidad: tres niveles

## Nivel 1 — Drivers globales

¿Qué variables usa más el modelo en general?

Ejemplo:

- última participación intermedia;
- tendencia;
- brecha respecto de vecinos;
- volatilidad;
- composición por edad.

## Nivel 2 — Explicación local

Para una sección específica:

> “El riesgo aumenta principalmente por una tendencia descendente, un rezago frente a secciones vecinas y una caída fuerte en la última elección comparable.”

Se pueden usar SHAP values para modelos de árboles.

## Nivel 3 — Territorios análogos

Mostrar secciones históricamente similares.

Esto complementa SHAP con una explicación basada en ejemplos:

> “El modelo encuentra que esta zona sigue una trayectoria parecida a estas otras.”

---

# 14. Detección de anomalías

El forecast responde:

> “¿Qué esperamos?”

La detección de anomalías responde:

> “¿Qué está ocurriendo de forma inusual?”

Construiremos un módulo challenger con:

- Isolation Forest;
- Local Outlier Factor;
- o anomalía basada en residuales espaciales.

Ejemplo de señal:

$$
A_i =
f(
\Delta p_i,
\Delta p_{N(i)},
\sigma_i
)
$$

Esto puede identificar:

- deterioros abruptos;
- secciones que se separan de sus vecinos;
- cambios inusuales respecto de su propia historia.

No se interpretará automáticamente como problema causal o irregularidad electoral; sólo como una observación estadísticamente atípica que merece contexto.

---

# 15. ==Escenarios de intervención: simulación, no causalidad inventada

==La convocatoria exige comparar al menos un escenario sin intervención y uno con intervención.

Los CCPC por sí solos no permiten identificar el efecto causal de una campaña institucional hipotética.

Por ello, el simulador será explícitamente contrafactual bajo supuestos.

## Escenario base

$$
Y_i(0)=\hat{Y}_i
$$

## Escenario hipotético

El usuario define un uplift:

$$
\delta \in \{0.5,1,2,3\}\text{ pp}
$$

y el sistema calcula:

$$
Y_i(1)=Y_i(0)+\delta_i
$$

para las zonas seleccionadas.

La interfaz debe decir con claridad:

> “Este cambio es un supuesto de simulación, no una estimación causal del efecto de una intervención.”

Si posteriormente se incorpora evidencia causal externa pertinente, se podrá usar para definir rangos plausibles, documentando su transferibilidad y limitaciones.

### Por qué esto es mejor

Es preferible un escenario honesto que una cifra causal sin identificación.

---

# 16. Priorización de recursos

El reto menciona explícitamente la priorización estratégica de recursos.

No debemos asumir que las zonas con mayor abstención observada son necesariamente las mejores candidatas para una intervención.

El dashboard puede calcular un índice transparente como:

$$
Priority_i
=
Risk_i
\times
Exposure_i
\times
Confidence_i
$$

donde:

- $Risk_i$ = riesgo predictivo;
- $Exposure_i$ = población/lista nominal potencialmente cubierta;
- $Confidence_i$ = penalización por incertidumbre.

Como extensión, si existe una restricción de capacidad:

$$
\sum_i c_i a_i \le B
$$

se puede resolver:

$$
\max_{a_i}
\sum_i
ExpectedBenefit_i a_i
$$

El objetivo no será afirmar cuál intervención debe realizar el INE, sino mostrar cómo cambia una priorización técnica bajo reglas y supuestos definidos por el usuario.

---

# 17. Diseño del dashboard

La experiencia debe poder entenderse en menos de un minuto.

## Pantalla principal

Mapa nacional por sección/territorio.

Selector:

- riesgo estructural;
- riesgo emergente;
- riesgo total;
- incertidumbre;
- cambio histórico;
- anomalía espacial.

## Al hacer clic en una zona

Mostrar:

### Riesgo
`Alto / Medio / Bajo`

### Estimación
Participación o score esperado.

### Intervalo de incertidumbre
Ejemplo:
`48.1% – 54.0%`

### Trayectoria
Gráfica 2009–2024.

### Comparables
Promedio nacional, estatal, municipal y vecinos.

### Drivers
Top variables asociadas al pronóstico.

### Territorios análogos
Cinco secciones similares según representación histórica.

## Modo escenarios

Dos mapas lado a lado:

**Sin intervención** | **Con escenario hipotético**

Controles:

- capacidad/presupuesto relativo;
- uplift supuesto;
- criterio de priorización;
- nivel de confianza mínimo.

Salida:

- territorios seleccionados;
- lista nominal cubierta;
- cambio agregado bajo el supuesto;
- distribución regional;
- sensibilidad a distintos parámetros.

---

# 18. Qué hace que RADAR 27 sea distinto

No es una sola técnica. Es el diseño integrado.

### Proyecto estándar

$$
CSV
\rightarrow
XGBoost
\rightarrow
Mapa
$$

### RADAR 27

$$
\begin{aligned}
&\text{CCPC + cartografía}\\
&\downarrow\\
&\text{panel temporal auditado}\\
&\downarrow\\
&\text{features históricas + espaciales}\\
&\downarrow\\
&\text{baselines + boosting + challengers de embeddings/grafo}\\
&\downarrow\\
&\text{backtesting temporal}\\
&\downarrow\\
&\text{incertidumbre + explicabilidad}\\
&\downarrow\\
&\text{riesgo estructural + emergente}\\
&\downarrow\\
&\text{simulador de escenarios}\\
&\downarrow\\
&\text{priorización bajo restricciones}\\
&\downarrow\\
&\text{dashboard institucional}
\end{aligned}
$$

---

# 19. Principio metodológico: cada sofisticación debe ganar su lugar

No vamos a defender una técnica porque sea compleja.

| Componente | Benchmark | Se conserva si… |
|---|---|---|
| Gradient boosting | Regresión/naive | mejora fuera de muestra |
| Features espaciales | boosting tabular | mejoran backtest o interpretación |
| Node2Vec | features espaciales simples | mejora modelo o analogías |
| Autoencoder | features temporales manuales | añade señal fuera de muestra |
| GNN | mejor modelo tabular | mejora consistentemente y no sacrifica trazabilidad |
| Anomaly detector | reglas de cambio | encuentra señales robustas útiles |
| Optimización | ranking simple | cambia decisiones bajo restricciones reales |

Esto protege al proyecto de la crítica:

> “Metieron embeddings y grafos sólo para impresionar.”

---

# 20. Riesgos metodológicos y cómo los enfrentamos

## Riesgo 1 — Sólo hay seis elecciones

No venderemos el proyecto como una serie de tiempo larga.

La fuerza estadística viene de muchas unidades territoriales observadas en pocos cortes temporales.

**Mitigación:** backtesting estricto, regularización, modelos sencillos como benchmark y declaración explícita de límites.

## Riesgo 2 — Sólo tres elecciones intermedias históricas

2027 es comparable principalmente con 2009, 2015 y 2021.

**Mitigación:** usar las presidenciales como contexto/feature, no asumir que pertenecen al mismo régimen.

## Riesgo 3 — Leakage espacial

Si un feature de vecinos usa información de la elección objetivo, estaríamos filtrando el futuro.

**Mitigación:** toda feature para un año $t$ debe calcularse únicamente con información disponible antes de $t$.

## Riesgo 4 — Cambios de geografía

Aunque la plataforma 2009–2024 toma como referencia cartografía con corte a mayo de 2023, debemos verificar que las llaves descargadas sean consistentes.

**Mitigación:** auditoría de IDs, cobertura y geometrías antes de modelar.

## Riesgo 5 — Falacia ecológica

Los datos son agregados.

**Mitigación:** nunca inferir comportamiento individual a partir de patrones territoriales.

## Riesgo 6 — Confundir correlación con causalidad

Una feature predictiva no es una causa.

**Mitigación:** separar rigurosamente predicción, explicación del modelo y escenarios hipotéticos.

## Riesgo 7 — Sesgos territoriales

El error puede concentrarse en estados, secciones rurales o ciertos tamaños de población.

**Mitigación:** reportar métricas por entidad, tipo de sección, tamaño y grupos relevantes.

---

# 21. MVP y extensiones

## MVP obligatorio

1. descarga y panel limpio CCPC;
2. EDA;
3. target de riesgo;
4. baselines;
5. LightGBM/XGBoost;
6. features espaciales;
7. backtesting;
8. intervalos de incertidumbre;
9. SHAP;
10. mapa de riesgo;
11. escenarios con/sin intervención;
12. semáforo territorial;
13. reporte y 10 slides.

## Stretch 1

Node2Vec / embedding de grafo.

## Stretch 2

Embedding temporal.

## Stretch 3

GNN.

## Stretch 4

Detector de anomalías.

## Stretch 5

Optimización de recursos.

## Regla

El MVP debe quedar terminado antes de dedicar tiempo a los *stretch goals*.

---

# 22. Qué NO vamos a hacer

- No usaremos datos personales.
- No intentaremos inferir preferencias partidistas.
- No construiremos perfiles ideológicos.
- No afirmaremos causalidad sin identificación.
- No haremos random split como evaluación principal.
- No meteremos una GNN si un modelo más simple funciona igual o mejor.
- No reportaremos una predicción puntual sin incertidumbre.
- No ocultaremos años, territorios o filas eliminadas.
- No modificaremos archivos crudos.
- No construiremos un score cuya fórmula o entrenamiento no pueda auditarse.

---

# 23. Criterios de éxito del proyecto

El proyecto debe demostrar simultáneamente:

### Validez
El modelo funciona mejor que baselines simples en evaluación fuera de muestra.

### Utilidad
Permite identificar y explorar zonas de riesgo.

### Honestidad
Distingue claramente predicción, correlación, incertidumbre y simulación.

### Originalidad
Integra dinámica temporal, espacio, grafos, embeddings y escenarios sólo cuando añaden valor.

### Interpretabilidad
Cada alerta puede explicarse.

### Viabilidad
El pipeline corre de principio a fin y produce archivos utilizables por terceros.

### Reproducibilidad
Una persona externa puede reconstruir los resultados desde los datos públicos mediante instrucciones documentadas.

---

# 24. Pitch en 10 diapositivas

## Slide 1 — Problema
“Ver dónde hubo abstención es retrospectivo. La planeación necesita saber dónde podría deteriorarse.”

## Slide 2 — Datos
CCPC 2009–2024 + geografía + variables agregadas.

## Slide 3 — Nueva definición
Riesgo estructural vs. riesgo emergente.

## Slide 4 — Huella participativa
Trayectoria histórica + sociodemografía + contexto espacial.

## Slide 5 — Grafo
Secciones conectadas con sus vecinos; ilustrar una isla de abstención y un clúster.

## Slide 6 — Modelos y validación
Baseline → boosting → spatial → embeddings/GNN. Backtesting temporal.

## Slide 7 — Resultados
Métricas, calibración e importancia de variables.

## Slide 8 — Incertidumbre y explicabilidad
Intervalos + SHAP + territorios análogos.

## Slide 9 — Escenarios
Mapa sin intervención vs. escenario hipotético; simulador de recursos.

## Slide 10 — Valor institucional
De datos históricos a un sistema reproducible de alerta y priorización.

---

# 25. Respuestas rápidas a objeciones del equipo

### “¿Por qué no sólo hacemos XGBoost?”
Porque XGBoost puede ser el mejor predictor, pero por sí solo no explota explícitamente la geografía ni convierte la predicción en una herramienta de escenarios y priorización.

### “¿Por qué grafos?”
Porque las secciones tienen vecinos reales y queremos medir contexto territorial. El grafo representa una relación que existe en los datos, no una abstracción decorativa.

### “¿Por qué embeddings?”
Porque pueden comprimir trayectorias y representar posición en la red. Pero sólo se conservan si aportan valor medible.

### “¿Por qué no una GNN desde el principio?”
Porque no sabemos si la complejidad adicional mejora el problema. Primero debe ganarle a un baseline fuerte.

### “¿Por qué separar presidenciales e intermedias?”
Porque el propio marco comparativo del INE las separa y porque 2027 es una elección federal legislativa, por lo que el patrón 2009–2015–2021 es el análogo histórico más directo.

### “¿Por qué intervalos?”
Porque una predicción sin incertidumbre puede dar una falsa sensación de precisión y conducir a una priorización frágil.

### “¿Por qué no estimamos el efecto de una campaña?”
Porque los CCPC no identifican causalmente ese efecto. Es mejor simular supuestos transparentes que inventar causalidad.

### “¿Esto sigue siendo viable para un hackathon?”
Sí, si se trabaja por capas. El producto mínimo no depende de embeddings ni de GNN. Esos componentes son challengers una vez que el pipeline base funciona.

---

# 26. Frase de cierre para presentar al equipo

> **La ventaja de RADAR 27 no es que use más algoritmos; es que convierte datos históricos del INE en un sistema auditable que anticipa riesgo, reconoce la estructura territorial, comunica incertidumbre, explica sus predicciones y permite explorar decisiones bajo escenarios transparentes.**

---

# 27. Fuentes oficiales de referencia

- Convocatoria oficial *Hackea la participación: Datos que construyen democracia*.
- INE, Plataforma de Conteos Censales de Participación Ciudadana 2009–2024:  
  https://www.ine.mx/transparencia/datos-abiertos/visualizacion-datos/conteos-censales-participacion/
- INE, Manual de uso de la Plataforma CCPC 2009–2024:  
  https://www.ine.mx/wp-content/uploads/2025/06/Manual-Conteos-Censales-2009-2024.pdf
- INE, Proceso Electoral Federal 2026–2027:  
  https://portal.ine.mx/voto-y-elecciones/elecciones-2027/
- INE, productos de geografía electoral:  
  https://www.ine.mx/productos-geografia-electoral-descargables/

---

# 28. Nota metodológica final

Este documento describe una arquitectura propuesta. Algunas decisiones —en particular la granularidad final, las variables efectivamente disponibles en los ZIP, la construcción exacta del grafo y la conveniencia de embeddings/GNN— quedan condicionadas a la auditoría inicial de los datos. Esa condicionalidad no es una debilidad: es parte del diseño científico del proyecto.
