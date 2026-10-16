# Metodología técnica municipal

La tasa electoral es `SV/(SV+NV)` y todas las agregaciones son razones de sumas. Las unidades A son secciones estables; B son componentes oficiales de linaje. Las tasas municipales se construyen sobre el universo A/B armonizado del fold y el residual usa una referencia municipal que excluye la unidad evaluada.

Para B: `P_hat = P_previa + Delta_m_local + 0.25 r_hat`. Para C: `Delta*_m = w_m Delta_m + (1-w_m) Delta_estado`, con `w_m = cobertura electoral × (n-1)/n`, donde `n` es el número de unidades comparables. Es una regla de cobertura y precisión leave-one-out, no un hiperparámetro optimizado. Si no existen ambas transiciones intermedias para 2027, B y C usan la referencia estatal y lo etiquetan como fallback.

El target es `(P_target-P_previa)-Delta_m_realizado`. Tanto target como predicción residual se centran por municipio con pesos preelectorales; por ello el residual sólo redistribuye heterogeneidad intramunicipal y no duplica el componente municipal. No se añade después otro componente nacional, estatal o municipal.

Las features vecinales son participación histórica de vecinos, diferencia sección-entorno, cambio histórico vecinal y trayectoria relativa. En backtests proceden de los artefactos Rook contemporáneos de cada fold; para 2027 usan el grafo 2024 y datos hasta 2024. Las aristas sintéticas se excluyen de indicadores descriptivos.

Los perfiles P1–P6 mantienen exactamente las reglas y precedencia del handoff anterior; sólo se recalculan las señales dependientes de la predicción central.
