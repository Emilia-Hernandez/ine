# Guía para el análisis político y territorial

## 1. Objetivo del proyecto

Este material ayuda a estudiar diferencias territoriales de participación electoral y a formular preguntas sobre posibles barreras de participación ciudadana. La unidad principal es la sección electoral.

La base no identifica personas, preferencias partidistas ni motivaciones individuales. Tampoco demuestra que una acción institucional causará un cambio de participación.

## 2. Información utilizada

El análisis utiliza conteos censales de participación del INE para 2009, 2012, 2015, 2018, 2021 y 2024, además de características agregadas ECEG 2020 del INEGI. La participación se calcula como votos registrados entre votos registrados más personas identificadas que no votaron.

La base contiene 70,751 secciones del snapshot geográfico 2024. La geografía de 2027 todavía no está certificada. Por esa razón, las claves deben actualizarse antes de un uso operativo en campo.

## 3. Qué hicimos

1. Reconstruimos la participación histórica y la elección previa comparable de cada sección o unidad territorial.
2. Separamos explícitamente el cambio nacional del patrón territorial. El cambio nacional 2015–2021 es 4.7644 puntos porcentuales, calculado como razón de sumas.
3. Comparamos persistencia histórica, árboles de cambio completo, residuales centrados y la especificación anterior usando exactamente las mismas observaciones.
4. Conservamos la persistencia histórica como predicción operativa porque no existe una elección intacta que valide externamente el modelo avanzado.
5. Incluimos un escenario exploratorio centrado con contracción 0.25. Este escenario sirve para investigación, no para asignar recursos como si fuera una predicción confirmada.
6. Limitamos los perfiles a las 65,095 secciones A/B con evidencia electoral local comparable.
7. Conservamos el score de riesgo sólo para A/B y lo etiquetamos como experimental.

## 4. Qué significa cada perfil

Los perfiles son patrones descriptivos, no tipos estables de ciudadanía. Su estabilidad algorítmica es alta, pero la separación entre grupos es baja.

### P1. Base alta y brechas por edad y sexo

Secciones con participación histórica relativamente alta y diferencias apreciables entre grupos de edad y sexo. Permite investigar si una participación agregada alta oculta grupos con menor participación.

Limitación: no explica por qué existen las brechas ni identifica comportamientos individuales.

### P2. Base media y brechas por edad y sexo

Secciones con participación histórica intermedia y brechas demográficas observadas. Permite comparar territorios que no presentan extremos agregados, pero sí diferencias internas.

Limitación: las diferencias son asociaciones ecológicas y pueden variar entre elecciones.

### P3. Base baja y mayor variabilidad histórica

Secciones con referencia histórica menor y cambios más débiles o variables entre ciclos. Permite explorar condiciones territoriales asociadas con persistencia o deterioro.

Limitación: no debe interpretarse como una población homogénea o permanentemente abstencionista.

Las 5,656 secciones C/D no reciben perfil. Usan referencias jerárquicas o estatales y no tienen evidencia local comparable suficiente.

De los seis arquetipos previos, sólo la brecha desfavorable a hombres mostró consistencia histórica suficiente para conservarse como indicador. Los demás permanecen únicamente como descripciones exploratorias y no aparecen como categorías estables.

## 5. Qué significa cada categoría de riesgo

### Score experimental de caída de 2 pp

El score ordena secciones A/B según un clasificador desarrollado para una elección intermedia. No es una probabilidad externamente validada.

La categoría alta usa el percentil 80 inclusivo. El umbral es 0.4457185. Selecciona 14,821 de 65,095 secciones elegibles, equivalentes a 22.77%, porque 3,867 secciones están empatadas en el umbral.

Una categoría elevada significa “score relativamente alto dentro del universo A/B”. No significa que la sección tenga una probabilidad demostrada de caída, ni que una intervención vaya a funcionar.

### Caída exploratoria positiva

El indicador compara el escenario exploratorio 2027 con la referencia histórica 2021. Sólo 68 secciones presentan una caída puntual positiva. El volumen asociado es una magnitud de escenario, no un conteo esperado validado.

No se utiliza la expresión “quintil superior de volumen”. El antiguo p80 era cero y en realidad identificaba valores positivos.

## 6. Cómo interpretar una fila

Ejemplo real: la sección `07:1209`, en Simojovel, Chiapas, es clase A. Tiene información electoral local y perfil P1. Su referencia intermedia 2021 es aproximadamente 79.28%.

- `prediccion_operativa_2027` conserva 79.28% porque el baseline de persistencia es la única opción operativa defendible.
- `prediccion_exploratoria_centrada_2027` añade el componente nacional y una corrección territorial centrada. Debe usarse para explorar escenarios, no como resultado confirmado.
- `score_riesgo_experimental_caida_2pp` aparece en el grupo alto por empate en el umbral. Esto no contradice el escenario de participación: el score y el escenario son herramientas distintas y ninguna es una observación futura.
- `fuente_caracteristicas_eceg` muestra si las características son locales, una coincidencia de clave no validada o una referencia estatal.

## 7. Qué se puede hacer con los resultados

- Comparar perfiles territoriales y su cobertura de datos.
- Formular preguntas sobre brechas por edad y sexo.
- Identificar secciones que requieren investigación cualitativa adicional.
- Contrastar score experimental, historia electoral y características agregadas.
- Diseñar escenarios institucionales hipotéticos no partidistas.
- Seleccionar casos para entrevistas, revisión de contexto o análisis geográfico actualizado.

No deben utilizarse para persuasión individualizada, inferir preferencias partidistas o afirmar causalidad.

## 8. Limitaciones

- Sólo 2021 muestra una mejora clara del modelo avanzado frente a persistencia.
- 2018 y 2024 no confirman una ventaja estable.
- El score de 2024 obtiene AUC 0.423 y no se usa para contextos presidenciales.
- No se produce predicción puntual presidencial 2030.
- La geografía es un snapshot 2024 y debe certificarse para 2027.
- Treinta y ocho secciones A/B usan referencia ECEG estatal; 3,630 C/D tienen coincidencia de código cuya continuidad territorial no está demostrada.
- Los perfiles describen agregados territoriales. No describen individuos.
- Los intervalos anteriores no validaban la especificación final. Esta entrega usa etiquetas cualitativas de incertidumbre y no afirma cobertura.

## 9. Recomendaciones para el siguiente equipo

Decisiones cerradas:

- Fórmula de participación y universo de 70,751 secciones.
- Cambio nacional calculado como razón de sumas.
- Residual territorial centrado y sin corrección estatal duplicada.
- Comparaciones modelo-baseline sobre muestras idénticas.
- Persistencia como predicción operativa.
- Score, perfiles y escenario avanzado etiquetados como exploratorios.

Trabajo pendiente:

- Actualizar el crosswalk geográfico 2027.
- Revisar sustantivamente los nombres y usos de los perfiles.
- Investigar causas plausibles con fuentes cualitativas o administrativas adicionales.
- Congelar la especificación antes de una elección futura y validarla sin ajustes posteriores.

## 10. Glosario

**Participación:** votos registrados divididos entre votos registrados más personas identificadas que no votaron.

**Baseline o persistencia:** supone que la participación de la próxima elección será igual a la elección anterior de la misma familia o a una referencia jerárquica cuando falta historia local.

**Componente nacional:** cambio agregado entre las dos elecciones anteriores de la misma familia, calculado como razón de sumas.

**Residual territorial centrado:** corrección del modelo cuya media ponderada se fuerza a cero para no duplicar el cambio nacional.

**Contracción:** reducción de la corrección territorial para evitar cambios extremos.

**Score experimental:** número útil para ordenar casos dentro de un universo definido. No equivale a una probabilidad validada.

**Clase A/B/C/D:** nivel de comparabilidad geográfica e historia disponible. A/B tienen la evidencia más fuerte para el modelo local.

**Fallback:** referencia de un nivel territorial más amplio utilizada cuando falta información local.

**Perfil exploratorio:** agrupación descriptiva de secciones con características semejantes. No implica causalidad ni estabilidad permanente.

