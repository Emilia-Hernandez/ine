# Cambios respecto a la versión auditada

## Predicción

- Se reemplazó la media del panel +5.21497 pp por un componente nacional definido como razón de sumas disponible antes de cada target.
- El target ahora descuenta el componente nacional y se centra por fold con lista nominal preelectoral.
- La predicción residual también se centra antes de combinarse con baseline y componente nacional.
- Se eliminó la corrección estatal adicional para evitar solapamiento territorial.
- Modelo y baseline se comparan sobre las mismas unidades.
- Se publican todos los candidatos de contracción 0–1.
- La persistencia quedó como predicción operativa; el residual centrado 0.25 quedó exploratorio.
- Se retiraron afirmaciones de cobertura de intervalos.

## Riesgo

- No se invirtieron probabilidades ni etiquetas.
- El score sólo se exporta para A/B y se identifica como experimental.
- El p80 se recalcula sobre 65,095 secciones elegibles: 14,821 altas (22.77%), con 3,867 empates.
- El antiguo “volumen alto” se sustituye por `volumen_exploratorio_caida_positiva`.
- No se produce score operativo presidencial ni predicción 2030.

## Perfiles y geografía

- Los perfiles P1–P3 sólo se asignan a A/B con conteos locales.
- C/D queda sin perfil en vez de recibir uno por referencia estatal.
- Los nombres se neutralizaron y todos se marcan exploratorios.
- Sólo la brecha desfavorable a hombres se conserva como patrón históricamente consistente.
- Las 38 A/B con fallback ECEG mantienen su clase A/B y su perfil electoral local.
- Las fuentes electoral, ECEG y de arquetipo permanecen en columnas separadas.

## Ingeniería

- Se creó un pipeline reproducible de handoff y una configuración versionada.
- Las nuevas salidas se escriben fuera de `artifacts/`.
- Se añadió un manifiesto SHA-256 de resultados anteriores.
- Se añadieron pruebas de centrado, muestras pareadas, llaves, perfiles, empates, diccionario y agregación territorial.

