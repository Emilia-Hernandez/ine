# Guía para politólogos

Usamos participación federal observada, cambios municipales calculados con votos y denominadores, historia seccional armonizada y vecinos geográficos Rook. La tendencia municipal permite que territorios distintos suban o bajen de forma diferente; el árbol aporta sólo una desviación moderada dentro del municipio.

En la evaluación, los modelos municipales detectaron más caídas, pero generaron demasiados falsos positivos y empeoraron sustancialmente el MAE y la balanced accuracy de 2021. Por eso la columna central conserva el Modelo A; C queda como alternativa municipal preferida para investigación, no como resultado operativo.

Una caída material significa una proyección al menos 1 punto porcentual menor que la elección intermedia 2021. No es una probabilidad. Una sección puede aumentar en términos absolutos y aun así deteriorarse relativamente si crece menos que su municipio.

Los perfiles conservan la precedencia P1 deterioro persistente, P2 deterioro proyectado, P3 rezago persistente, P4 recuperación, P5 favorable/estable y P6 variable/no diferenciada. Evidencia insuficiente queda fuera de los seis perfiles.

Para leer una fila: revise primero `modelo_central`, baseline, componente municipal, residual, cambio total y señal de caída; después perfil, cobertura, calidad, fallback y clase A/B/C/D. Por ejemplo, la sección 07:0038 pasa de 84.7% a 83.2%; su etiqueta P2 expresa una caída proyectada, no una observación ni una causa.

La geografía corresponde a 2024, 2021 no es validación externa, algunos municipios cambian composición y los datos agregados no revelan motivaciones individuales. Antes de conclusiones causales deben investigarse accesibilidad, movilidad, organización electoral, condiciones sociales y mecanismos locales con diseños específicos.
