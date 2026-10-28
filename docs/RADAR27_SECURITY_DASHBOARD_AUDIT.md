# Auditoría de baseline · RADAR 27 seguridad y exportación

Fecha: 2026-10-20.

El dashboard real es una aplicación Dash/Flask con `dash-leaflet`; entra por `dashboard/app.py`, carga un Parquet seccional en memoria mediante `dashboard/data_layer.py` y sirve dos capas FlatGeobuf (900 m y 75 m) según el zoom. Los filtros se aplican en cliente al mapa y en servidor a los agregados. La navegación del mapa no define el universo estadístico.

El handoff vigente comprobado es `handoff/FINAL_2027_MUNICIPAL`, versión `radar27-final-2027-municipal.1`. Su manifest declara que reemplaza `FINAL_2027` como proyección de trabajo. El modelo central continúa siendo `A_nacional_actual`; `A_persistence` es solamente el baseline. El universo tiene 70,751 secciones y los conteos sustantivos verificados son P1 2,718; P2 58; P3 20,698; P4 7,028; P5 9,955; P6 20,932; EI 9,362.

Los generadores relevantes son `src/radar27/modeling/final_2027.py`, `src/radar27/modeling/final_2027_municipal.py`, `dashboard/prepare_data.py` y sus configuraciones. La historia directa procede de `provisional_section_year_totals.parquet`; confianza y linaje de `section_confidence_by_election.parquet` y `lineage_components_by_election.parquet`; predicción de `forecast_2027_section_predictions.parquet`; evaluación tabular de `feature_ablation_mart.parquet`.

Baseline previo a esta ampliación: 47 pruebas seleccionadas pasaron. Se detectaron cambios locales previos del filtro de densidad y se conservaron. La regla de elegibilidad de `_assign_profiles()` no fue modificada.

La separación visual de EI produce 3,706 EI-A/B y 5,656 EI-C/D. `EI` identifica evidencia insuficiente y no es un séptimo perfil sustantivo; `perfil_visual_id` es sólo una categoría de presentación.
