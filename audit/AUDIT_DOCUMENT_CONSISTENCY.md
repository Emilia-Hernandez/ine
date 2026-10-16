# Consistencia entre código, artefactos y documentos

## Resultado

Se inventariaron 42 afirmaciones cuantitativas o metodológicas centrales. Se recalcularon 38 (90.5%): 35 coinciden con artefactos/código y tres quedan refutadas de forma reproducible. Cuatro no se validaron de manera limpia. “Recalculada” incluye una falsificación; no equivale a “correcta”.

| # | Documento | Página/sección | Afirmación o cifra | Código/dato fuente | Resultado recalculado | Estado / corrección |
|---:|---|---|---|---|---|---|
| 1 | README | Inicio | El proyecto atiende el Reto 2 | README y convocatoria | Reto 2 declarado | Verificada |
| 2 | Reportes Predicción/Perfiles | Fuentes | Hay seis elecciones 2009–2024 | `source_manifest.csv` | Seis elecciones | Verificada |
| 3 | Reporte Predicción | Datos | Se procesan 54,872,712 filas | archivos CCPC | 54,872,712 | Verificada |
| 4 | Manual y documentos | Indicadores | Participación=`SV/(SV+NV)` | agregación + manual pp. 17–18 | Coincide | Verificada |
| 5 | Manual y documentos | Indicadores | `NS` no es abstención | código de agregación | Excluido del denominador | Verificada |
| 6 | Docs modelado | Mart | Mart con 243,108 filas | `feature_ablation_mart.parquet` | 243,108 | Verificada |
| 7 | Docs modelado | Mart | Llave año/unidad única | mismo artefacto | 0 duplicados | Verificada |
| 8 | Docs modelado | Temporalidad | Features electorales previas | `max_electoral_feature_year` | 0 violaciones | Verificada |
| 9 | Reporte Perfiles | Universo | Salida con 70,751 secciones | `section_risk_profiles_2027.parquet` | 70,751 | Verificada |
| 10 | Reporte Perfiles | Universo | Llaves finales únicas | mismo artefacto | 70,751 únicas | Verificada |
| 11 | Reporte Predicción | Geografía | 58,534 A | clase final | 58,534 | Verificada |
| 12 | Reporte Predicción | Geografía | 6,561 B | clase final | 6,561 | Verificada |
| 13 | Reporte Predicción | Geografía | 1,865 C | clase final | 1,865 | Verificada |
| 14 | Reporte Predicción | Geografía | 3,791 D | clase final | 3,791 | Verificada |
| 15 | Reporte Perfiles | §§8–9 | 65,095 A/B | A+B | 65,095 | Verificada |
| 16 | Reporte Perfiles | §§8–9 | 65,057 A/B con ECEG local | `eceg_profile_source` | 65,057 | Verificada |
| 17 | Reporte Perfiles | §§8–9 | Diferencia de 38 | conciliación independiente | 38 claves exactas | Verificada |
| 18 | Reporte Perfiles | §§8–9 | Las 38 son A | tabla de conciliación | 38 A; 0 B | Verificada |
| 19 | Reporte Perfiles | §§8–9 | Las 38 usan ECEG estatal | fuente efectiva | 38 fallback | Verificada |
| 20 | Reporte Perfiles | §9 | Total fallback ECEG=2,064 | fuente efectiva | 2,026 C/D + 38 A | Verificada |
| 21 | Reporte Perfiles | §9 | 36/38 con arquetipo local | fuente arquetipo | 36 | Verificada |
| 22 | Reporte Perfiles | §9 | Dos además con fallback demográfico | fuente arquetipo | `05:0153`, `25:1994` | Verificada |
| 23 | Reporte Predicción | pp. 4–5 | Ajuste=+5.21497 pp | `national_shift_estimates.csv` | +5.21497 pp de panel | Verificada como cálculo |
| 24 | Reporte Predicción | pp. 4–5 | +5.21 es cambio nacional | totales 2015/2021 | +4.76442 pp razón de sumas | **Refutada; renombrar o recalcular** |
| 25 | Reporte Predicción | pp. 4–5 | Se separan efectos local/nacional | target y fórmula final | residual contraído medio +0.3433 pp | **Refutada; centrar target** |
| 26 | Reporte Predicción | Forecast | Nacional 2027=57.3067% | forecast seccional | 57.3067% | Verificada |
| 27 | Auditoría | Sensibilidad | Con razón de sumas=56.8565% | contrafactual con fórmula final | 56.8565%; Δ−0.4501 pp | Verificada |
| 28 | Reporte Predicción | p. 10 | Modelo/baseline mismo universo | tablas de predicción | +71/+1,513/+1,970 unidades | **Refutada; parear muestra** |
| 29 | Reporte Predicción | p. 10 | Mejora amplia en 2021 | comparación pareada | Δ MAE=−2.0555 pp | Verificada |
| 30 | Reporte Predicción | p. 10 | Mejora presidencial | comparación pareada + bootstrap | IC incluyen cero | No respaldada; matizar |
| 31 | Reporte Perfiles | p. 5 | Positivo=caída ≥2 pp | target de riesgo | Coincide | Verificada |
| 32 | Reporte Perfiles | p. 5 | Probabilidad de clase caída | clases del estimador | `predict_proba[:,1]` correcto | Verificada |
| 33 | Reporte Perfiles | p. 5 | AUC 2024≈0.423 | predicciones de backtest | 0.422706 | Verificada |
| 34 | Reporte Perfiles | p. 5 | Utilidad del score 2024 | benchmarks independientes | Peor que baseline histórico | Verificada como limitación |
| 35 | Reporte Perfiles | p. 5 | Alto riesgo=15,631 | percentiles y score | 15,631; 22.09% | Verificada; explicar empate |
| 36 | Reporte Perfiles | p. 5 | Alto volumen=9,891 | percentiles y magnitud | 9,891; 13.98% | Verificada; renombrar |
| 37 | Reporte Perfiles | p. 5 | Ambos son top 20% | reglas de ranking | 22.09% y 13.98% | No respaldada; corregir etiqueta |
| 38 | Reporte Perfiles | Salida | Probabilidades en [0,1] | perfil final | min=0; max=1 | Verificada |
| 39 | README/docs calibración | Resultados | 90.41%/87.08% cubren modelo final | resultados de etapa | No hay backtest final equivalente | **No verificada** |
| 40 | Docs fuentes | Fuentes | Fuentes coinciden hoy con servidor | manifiesto local | Sólo hash local | **No verificada** |
| 41 | README | Reproducción | Pipeline limpio end-to-end | scripts con rutas fijas | No ejecutado para preservar evidencia | **No verificada** |
| 42 | Reporte Predicción | Geografía futura | Geografía 2027/2030 certificada | snapshot y AMGE | snapshot 2024; evidencia hasta 2022 | **No verificada** |

## Contradicciones documentales relevantes

- README indica 93 pruebas; la suite actual ejecuta 100.
- El ajuste se denomina “nacional” aunque se estima en el panel comparable A/B.
- Las tablas dicen “mismo universo” y usan conteos diferentes.
- El texto largo trata la solución como final; otros documentos reconocen que intervalos y riesgo siguen siendo experimentales.
- La cobertura de una etapa anterior aparece cerca del forecast final sin una frontera suficientemente clara.
- La versión larga de predicción tiene 27 páginas, fuera del requisito de 10–15; la corta tiene 10, pero ambas son DOCX y ninguna está identificada como PDF canónico.
- La numeración de la versión larga salta la sección 11.

## Revisión visual

Se renderizaron las 79 páginas de los cuatro DOCX. No se observaron cortes graves, texto desbordado o páginas ilegibles. La limitación no es de maquetación sino de canonicidad, formato, extensión y consistencia de contenido.

## Cumplimiento de convocatoria

Para el Reto 2 faltan entregables materiales: mapa ejecutable, base anonimizada de entrega y dos escenarios —incluido uno con intervención hipotética— acompañados de recomendaciones preventivas. El repositorio declara diferida la intervención. La omisión de entregables mínimos representa riesgo de descalificación, independientemente de la calidad del modelo.
