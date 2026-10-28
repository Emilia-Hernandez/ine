# Changelog · radar27-dashboard-security.5

- Se preservaron P1–P6. EI no es un perfil sustantivo: indica evidencia insuficiente; `EI_AB` y `EI_CD` son categorías exclusivamente visuales de ese estado.
- Se documentan años de historia disponibles/faltantes y la limitación territorial en fichas EI.
- El panel izquierdo ahora tiene scroll interno, accesos 10/25/50/66/100, sliders 1–100 y descarga fija.
- Densidad conserva el extremo superior del ranking nacional y es neutra a 100%.
- Se incorporó SESNSP 2015–2025 + CONAPO municipal, sin mezclar RNID 2026 ni imputar faltantes.
- Seguridad conserva el extremo inferior y respeta bloques municipales empatados.
- Mapa, conteos, agregados y CSV usan la misma intersección de filtros.
- Se añadió una ablación M0–M4 separada del modelo central.
- Se añadió publicación versionada, aprobación explícita, cambio atómico de puntero y rollback.
- Se publicó `radar27-dashboard-security.5` con el modelo vigente `radar27-final-2027-municipal.1/A_nacional_actual`; ningún modelo experimental fue promovido. Los releases anteriores se conservan para rollback.

## radar27-security-ablation.2 — auditoría correctiva

- Se preservó intacto `radar27-security-ablation.1` y se generó una versión nueva no promovida.
- Se corrigió la propagación de un denominador municipal nulo a la referencia estatal completa.
- Se separó la muestra máxima de M2–M4 de la intersección común y se activó el manejo nativo de densidad faltante que ya declaraba M4.
- Se sustituyó el Precision@K dependiente del orden en empates por una convención fraccional estable; M0 queda marcado como ranking no informativo.
- Se añadieron `COVERAGE_AUDIT.csv`, `SELECTION_BIAS.csv`, `ranking_metrics.csv` y `TEMPORAL_AUDIT.csv`.
- Se corrigió la afirmación de disponibilidad ex ante de CONAPO: el producto usado se publicó el 9 de mayo de 2024.
- No se modificó ningún archivo consumido por `radar27-dashboard-security.5` ni se promovió un candidato.
