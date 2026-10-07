# Adaptación estatal por ciclo de la misma familia

Actualizado: 2026-10-07.

## Señal

Para cada entidad se calcula el cambio de participación entre las dos elecciones federales previas de la misma familia y se resta el cambio nacional equivalente. Las fuentes son agregados territoriales definitivos SICEE; se excluye voto en el extranjero y nunca se usa la elección objetivo.

La corrección se aplica después del boosting y de la corrección nacional:

```text
predicción corregida = clip(predicción + λ × (cambio estatal − cambio nacional), 0, 1)
```

Se comparó una rejilla simétrica `[-0.75, -0.50, -0.25, 0, 0.25, 0.50, 0.75]`. El valor se elige sólo por MAE ponderado en el fold principal 2021; 2018 y 2024 actúan como controles de robustez. El gate exige al menos 0.1 pp de mejora en 2021 y no permite deterioros mayores a 0.5 pp en otro fold.

## Resultado

Se selecciona `λ = −0.50`. El signo negativo indica reversión parcial a la media: una entidad cuyo aumento previo superó al nacional recibe una corrección descendente, y viceversa.

| Target | Sin corrección estatal | Con corrección | Cambio |
|---:|---:|---:|---:|
| 2018 | 4.206 pp | 4.478 pp | +0.271 pp |
| 2021 | 7.807 pp | 7.351 pp | −0.456 pp |
| 2024 | 4.651 pp | 4.516 pp | −0.135 pp |

La corrección supera el gate: mejora claramente el target principal y también el holdout posterior 2024; el deterioro 2018 permanece bajo el máximo permitido. Se incorpora a la proyección experimental 2027 como una capa separada, no como una nueva feature promovida del árbol.

## Límites

- Sólo existen tres folds estrictos para validar el coeficiente.
- La mejora no es uniforme: 2018 empeora y el modelo corregido sigue ligeramente por encima del baseline simple en 2018 y 2024.
- La señal usa resultados estatales agregados; no identifica causalidad ni sustituye información local.
- La promoción es experimental y reversible. Configuración, métricas, predicciones y decisión se conservan en artefactos separados.
