# Recomendación

## Respuestas ejecutivas

1. **¿La tendencia propia mejora respecto a persistencia?** No de forma conjunta: cualquier ganancia de detección debe leerse junto con el error continuo y los falsos positivos.
2. **¿Mejora respecto al modelo avanzado actual?** No: la tendencia regularizada no supera simultáneamente a A en MAE y F1.
3. **¿Detecta más caídas reales?** B registra 2,414 VP y C 2,239, frente a 60 de A y 0 de persistencia.
4. **¿Costo en falsos positivos?** B genera 14,070 FP y C 13,915, frente a 7 de A.
5. **¿La regularización mejora estabilidad?** Reduce tasas crudas fuera de rango de 612 a 502 y modera la proyección en 1.24 pp absolutos en promedio. Su efecto predictivo se observa en la tabla; estabilidad numérica no equivale por sí sola a mayor validez.
6. **¿Modelo central defendible para 2027?** Se recomienda **mantener A como proyección central de trabajo**. B y C quedan como escenarios diagnósticos: amplían la detección, pero deben justificar su costo en FP y error continuo antes de sustituir el modelo vigente. El handoff canónico no se modificó.
7. **¿Residual ML sin leakage?** No es viable validarlo con la historia intermedia disponible. Para el backtest 2021 solo existe una transición anterior (2009→2015), de modo que no hay un ciclo previo adicional para entrenar targets residuales y luego evaluar temporalmente en 2021. No se fabricaron folds, no se reentrenó ML y el experimento se detiene aquí.

## Escenarios 2027 en universo común

| Modelo | Caídas proyectadas (≤ -1 pp) |
|---|---:|
| A avanzado actual | 58 |
| B tendencia simple | 8,288 |
| C tendencia regularizada | 7,213 |
| D persistencia | 0 |

Los conteos anteriores se calculan sobre las mismas 54,968 secciones elegibles. A y D también tienen mayor cobertura en el maestro, pero mezclar universos haría injusta la comparación.

## Evidencia frente a supuestos

**Evidencia observada:** métricas pareadas de 2021, conteos de confusión, error continuo, cobertura y diagnósticos históricos calculados en los CSV. **Supuestos de modelación:** continuidad de la trayectoria hasta 2027, peso fijo 50/50 de C, validez del municipio como ancla y recorte de tasas al dominio posible. La recomendación no trata esos supuestos como hechos.
