# Resumen de implementación

## Operación

```bash
PYTHONPATH=src .venv/bin/python scripts/run_security_municipal.py
LOKY_MAX_CPU_COUNT=4 PYTHONPATH=src .venv/bin/python scripts/run_security_ablation.py  # crea .2 una sola vez
PYTHONPATH=src .venv/bin/python dashboard/prepare_data.py
.venv/bin/python -m dashboard.app
```

El dashboard publicado es `radar27-dashboard-security.5`, consume `radar27-final-2027-municipal.1/A_nacional_actual` y requiere reinicio para leer un cambio de release.

## Publicación y rollback

Un experimento nunca cambia el puntero. Tras aprobación humana y generación completa:

```bash
PYTHONPATH=src .venv/bin/python scripts/publish_dashboard.py --version VERSION --model-version MODELO --approve
PYTHONPATH=src .venv/bin/python scripts/publish_dashboard.py --version VERSION_ANTERIOR --rollback --approve
```

El comando verifica universo, unicidad, perfiles y una sola versión de modelo; empaqueta datos y geometrías sin sobrescribir releases previos y cambia `dashboard/data/current_release.json` con `os.replace`. Si falla el staging, el puntero anterior permanece.

## Auditoría correctiva 2026-10-20

`radar27-security-ablation.1` se conserva intacto como resultado histórico y queda reemplazado para interpretación por `radar27-security-ablation.2`.

La pérdida anterior a 39,241 unidades en 2021 y 38,408 en 2024 no representaba la cobertura de M2. Dos errores la producían: (a) un denominador CONAPO nulo contaminaba la referencia estatal de una entidad completa y (b) la muestra común exigía densidad observada aun cuando M4 ya declaraba `density_missing` y el estimador admite nulos nativamente. La corrección recupera legítimamente 18,765 unidades en 2021 y 17,536 en 2024. Permanecen fuera 63 unidades en cada fold, correspondientes a tres municipios sin historial SESNSP aplicable.

En la muestra común corregida, M2 reduce el MAE 2021 en 0.000318, pero su intervalo bootstrap municipal cruza cero. M4 reduce 0.000353 y su intervalo queda apenas por debajo de cero; esta señal de una sola elección intermedia no se sostiene en 2024. En 2024 M2, M3 y M4 empeoran el MAE en 0.001801, 0.002735 y 0.002758, respectivamente, con intervalos completamente positivos.

Para priorización 2024, la prevalencia es 0.5918. M4 obtiene Precision@5% de 0.6033 (lift 1.019) y Precision@10% de 0.5861 (lift 0.990). La ventaja a 5% es pequeña y desaparece al 10%; no constituye evidencia robusta. M0 asigna score cero a todas las unidades y ahora reporta Precision/Recall/Lift top-K como no definidos, con la expectativa bajo desempate aleatorio en columnas separadas.

Conclusión: la incidencia delictiva municipal registrada merece investigación adicional, especialmente con snapshots históricos *as-of* y más elecciones intermedias, pero la evidencia corregida no justifica promover M2, M3 ni M4. El central permanece sin cambios.

## Limitaciones reales

- 301 secciones no tienen indicador municipal 2025 confiable.
- Los archivos SESNSP usados contienen revisiones posteriores; no son snapshots *as-of*.
- La serie municipal CONAPO usada se publicó el 9 de mayo de 2024 y tampoco era *as-of* en los cortes de abril.
- La seguridad varía a nivel municipal, no entre secciones del mismo municipio.
- Las 63 unidades excluidas por fold difieren del resto en tamaño de lista, participación previa y densidad; no se afirma representatividad.
- Para 2018 no existe un fold anterior compatible para entrenar M2–M4; se reportan M0/M1 y 2018 se usa como entrenamiento de 2021.
- La cartografía sigue siendo el snapshot INE 2024, no geometría certificada para 2027.
