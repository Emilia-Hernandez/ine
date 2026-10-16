from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, f1_score, precision_score, recall_score

YEARS = (2009, 2015, 2021)
DECLINE_THRESHOLD = -0.01
SECTION_WEIGHT = 0.50


@dataclass(frozen=True)
class ExperimentPaths:
    totals: Path
    confidence: Path
    backtest_a: Path
    master_2027: Path
    output_dir: Path


def _clip_rate(values: pd.Series) -> pd.Series:
    return values.clip(lower=0.0, upper=1.0)


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator.div(denominator.where(denominator.gt(0)))


def _wide_history(totals: pd.DataFrame) -> pd.DataFrame:
    history = totals.loc[totals["election_year"].isin(YEARS)].copy()
    if history.duplicated(["section_key_observed", "election_year"]).any():
        raise ValueError("La tabla de totales no es unica por seccion y eleccion")

    pieces: list[pd.DataFrame] = []
    for column, stem in (
        ("participation", "participacion"),
        ("voted", "votos_identificados_participaron"),
        ("identified_records", "registros_identificados"),
    ):
        piece = history.pivot(
            index="section_key_observed", columns="election_year", values=column
        )
        piece.columns = [f"{stem}_{int(year)}" for year in piece.columns]
        pieces.append(piece)
    return pd.concat(pieces, axis=1).reset_index()


def _add_leave_one_out_references(
    frame: pd.DataFrame,
    municipality_col: str,
    entity_col: str,
) -> pd.DataFrame:
    result = frame.copy()
    municipality_valid = pd.Series(True, index=result.index)
    entity_valid = pd.Series(True, index=result.index)

    for year in YEARS:
        voted = f"votos_identificados_participaron_{year}"
        records = f"registros_identificados_{year}"
        municipal_voted = result.groupby(municipality_col, dropna=False)[voted].transform("sum")
        municipal_records = result.groupby(municipality_col, dropna=False)[records].transform("sum")
        municipal_loo = _safe_ratio(municipal_voted - result[voted], municipal_records - result[records])

        entity_voted = result.groupby(entity_col, dropna=False)[voted].transform("sum")
        entity_records = result.groupby(entity_col, dropna=False)[records].transform("sum")
        entity_loo = _safe_ratio(entity_voted - result[voted], entity_records - result[records])

        result[f"referencia_municipal_loo_{year}"] = municipal_loo
        result[f"referencia_entidad_loo_{year}"] = entity_loo
        municipality_valid &= municipal_loo.notna()
        entity_valid &= entity_loo.notna()

    result["fuente_regularizacion"] = np.select(
        [municipality_valid, entity_valid],
        ["municipio_sin_seccion", "entidad_sin_seccion"],
        default="sin_referencia",
    )
    for year in YEARS:
        result[f"referencia_regularizacion_{year}"] = np.where(
            municipality_valid,
            result[f"referencia_municipal_loo_{year}"],
            result[f"referencia_entidad_loo_{year}"],
        )
    return result


def _confusion_labels(actual: pd.Series, projected: pd.Series) -> pd.Series:
    return pd.Series(
        np.select(
            [actual & projected, ~actual & projected, actual & ~projected],
            ["VP", "FP", "FN"],
            default="VN",
        ),
        index=actual.index,
    )


def decline_metrics(
    actual: pd.Series,
    previous: pd.Series,
    prediction: pd.Series,
    model: str,
    eligible_universe: int,
) -> dict[str, float | int | str]:
    actual_decline = actual.sub(previous).le(DECLINE_THRESHOLD)
    projected_decline = prediction.sub(previous).le(DECLINE_THRESHOLD)
    error = prediction.sub(actual)
    tp = int((actual_decline & projected_decline).sum())
    fp = int((~actual_decline & projected_decline).sum())
    fn = int((actual_decline & ~projected_decline).sum())
    tn = int((~actual_decline & ~projected_decline).sum())
    return {
        "modelo": model,
        "unidades_evaluacion": len(actual),
        "universo_objetivo": int(eligible_universe),
        "cobertura": float(len(actual) / eligible_universe),
        "precision": float(precision_score(actual_decline, projected_decline, zero_division=0)),
        "recall": float(recall_score(actual_decline, projected_decline, zero_division=0)),
        "f1": float(f1_score(actual_decline, projected_decline, zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(actual_decline, projected_decline)),
        "verdaderos_positivos": tp,
        "falsos_positivos": fp,
        "falsos_negativos": fn,
        "verdaderos_negativos": tn,
        "mae": float(error.abs().mean()),
        "rmse": float(np.sqrt(error.pow(2).mean())),
        "bias": float(error.mean()),
        "caidas_proyectadas": int(projected_decline.sum()),
        "caidas_observadas": int(actual_decline.sum()),
    }


def build_backtest(
    totals: pd.DataFrame,
    confidence: pd.DataFrame,
    backtest_a: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    target = confidence.loc[
        confidence["target_year"].eq(2021)
        & confidence["geography_confidence_class"].eq("A"),
        [
            "entity_id",
            "entity_name",
            "municipality_key_observed",
            "municipality_name",
            "section_key_observed",
            "section_number",
            "geography_confidence_class",
        ],
    ].drop_duplicates("section_key_observed")

    advanced = backtest_a.loc[
        backtest_a["target_year"].eq(2021)
        & backtest_a["evaluation_unit_id"].str.startswith("S:"),
        ["evaluation_unit_id", "D_centered_shrink_0.25"],
    ].copy()
    advanced["section_key_observed"] = advanced["evaluation_unit_id"].str.removeprefix("S:")
    advanced = advanced.rename(columns={"D_centered_shrink_0.25": "prediccion_A"})

    paired = target.merge(_wide_history(totals), on="section_key_observed", how="left")
    paired = paired.merge(
        advanced[["section_key_observed", "prediccion_A"]],
        on="section_key_observed",
        how="inner",
        validate="one_to_one",
    )
    required = [
        *(f"participacion_{year}" for year in YEARS),
        *(f"votos_identificados_participaron_{year}" for year in YEARS),
        *(f"registros_identificados_{year}" for year in YEARS),
        "prediccion_A",
    ]
    paired = paired.dropna(subset=required).reset_index(drop=True)
    paired = _add_leave_one_out_references(
        paired, "municipality_key_observed", "entity_id"
    )
    paired = paired.loc[paired["fuente_regularizacion"].ne("sin_referencia")].copy()

    paired["cambio_seccional_2009_2015"] = paired["participacion_2015"].sub(
        paired["participacion_2009"]
    )
    paired["cambio_referencia_2009_2015"] = paired[
        "referencia_regularizacion_2015"
    ].sub(paired["referencia_regularizacion_2009"])
    paired["prediccion_B_sin_recorte"] = paired["participacion_2015"].add(
        paired["cambio_seccional_2009_2015"]
    )
    paired["prediccion_C_sin_recorte"] = paired["participacion_2015"].add(
        SECTION_WEIGHT * paired["cambio_seccional_2009_2015"]
        + (1.0 - SECTION_WEIGHT) * paired["cambio_referencia_2009_2015"]
    )
    paired["prediccion_B"] = _clip_rate(paired["prediccion_B_sin_recorte"])
    paired["prediccion_C"] = _clip_rate(paired["prediccion_C_sin_recorte"])
    paired["recorte_B"] = paired["prediccion_B"].ne(paired["prediccion_B_sin_recorte"])
    paired["recorte_C"] = paired["prediccion_C"].ne(paired["prediccion_C_sin_recorte"])
    paired["prediccion_D"] = paired["participacion_2015"]
    paired["cambio_observado_2015_2021"] = paired["participacion_2021"].sub(
        paired["participacion_2015"]
    )
    paired["caida_observada_1pp"] = paired["cambio_observado_2015_2021"].le(
        DECLINE_THRESHOLD
    )

    models = {
        "A_modelo_avanzado_actual": "prediccion_A",
        "B_tendencia_seccional_simple": "prediccion_B",
        "C_tendencia_seccional_regularizada": "prediccion_C",
        "D_persistencia": "prediccion_D",
    }
    metrics = []
    for model, column in models.items():
        projected = paired[column].sub(paired["participacion_2015"]).le(DECLINE_THRESHOLD)
        paired[f"caida_proyectada_1pp_{model[0]}"] = projected
        paired[f"resultado_{model[0]}"] = _confusion_labels(
            paired["caida_observada_1pp"], projected
        )
        paired[f"error_{model[0]}"] = paired[column].sub(paired["participacion_2021"])
        metrics.append(
            decline_metrics(
                paired["participacion_2021"],
                paired["participacion_2015"],
                paired[column],
                model,
                eligible_universe=len(confidence.loc[confidence["target_year"].eq(2021)]),
            )
        )

    audit = {
        "target_2021_total": int(confidence.loc[confidence["target_year"].eq(2021)].shape[0]),
        "target_2021_clase_A": int(target.shape[0]),
        "modelo_A_secciones": int(advanced.shape[0]),
        "muestra_pareada": int(paired.shape[0]),
    }
    return paired.sort_values("section_key_observed"), pd.DataFrame(metrics), audit


def _ineligibility_reason(frame: pd.DataFrame) -> pd.Series:
    history_ok = frame[[f"participacion_{year}" for year in YEARS]].notna().all(axis=1)
    counts_ok = frame[
        [
            *(f"votos_identificados_participaron_{year}" for year in YEARS),
            *(f"registros_identificados_{year}" for year in YEARS),
        ]
    ].notna().all(axis=1)
    return pd.Series(
        np.select(
            [
                frame["clase_confianza_geografica"].ne("A"),
                ~history_ok,
                ~counts_ok,
            ],
            [
                "comparabilidad_geografica_inferior_a_A",
                "historia_2009_2015_2021_incompleta",
                "denominadores_historicos_incompletos",
            ],
            default="elegible",
        ),
        index=frame.index,
    )


def build_scenarios_2027(
    totals: pd.DataFrame,
    master: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, float | int]]:
    master = master.copy()
    master["clave_entidad"] = master["clave_entidad"].astype("string").str.zfill(2)
    master = master.merge(
        _wide_history(totals).drop(columns=[f"participacion_{year}" for year in YEARS]),
        left_on="clave_seccion",
        right_on="section_key_observed",
        how="left",
        validate="one_to_one",
    )
    master["motivo_elegibilidad_tendencia"] = _ineligibility_reason(master)
    master["elegible_tendencia_seccional"] = master[
        "motivo_elegibilidad_tendencia"
    ].eq("elegible")

    eligible = master.loc[master["elegible_tendencia_seccional"]].copy()
    eligible = _add_leave_one_out_references(eligible, "clave_municipio", "clave_entidad")
    eligible = eligible.loc[eligible["fuente_regularizacion"].ne("sin_referencia")].copy()
    eligible["cambio_1"] = eligible["participacion_2015"].sub(eligible["participacion_2009"])
    eligible["cambio_2"] = eligible["participacion_2021"].sub(eligible["participacion_2015"])
    eligible["tendencia_seccional_media"] = eligible[["cambio_1", "cambio_2"]].mean(axis=1)
    eligible["cambio_referencia_1"] = eligible["referencia_regularizacion_2015"].sub(
        eligible["referencia_regularizacion_2009"]
    )
    eligible["cambio_referencia_2"] = eligible["referencia_regularizacion_2021"].sub(
        eligible["referencia_regularizacion_2015"]
    )
    eligible["tendencia_referencia_media"] = eligible[
        ["cambio_referencia_1", "cambio_referencia_2"]
    ].mean(axis=1)
    eligible["prediccion_B_2027_sin_recorte"] = eligible["participacion_2021"].add(
        eligible["tendencia_seccional_media"]
    )
    eligible["prediccion_C_2027_sin_recorte"] = eligible["participacion_2021"].add(
        SECTION_WEIGHT * eligible["tendencia_seccional_media"]
        + (1.0 - SECTION_WEIGHT) * eligible["tendencia_referencia_media"]
    )
    eligible["prediccion_B_2027"] = _clip_rate(eligible["prediccion_B_2027_sin_recorte"])
    eligible["prediccion_C_2027"] = _clip_rate(eligible["prediccion_C_2027_sin_recorte"])
    eligible["recorte_B"] = eligible["prediccion_B_2027"].ne(
        eligible["prediccion_B_2027_sin_recorte"]
    )
    eligible["recorte_C"] = eligible["prediccion_C_2027"].ne(
        eligible["prediccion_C_2027_sin_recorte"]
    )
    eligible["diferencia_absoluta_cambios"] = eligible["cambio_2"].sub(
        eligible["cambio_1"]
    ).abs()
    eligible["cambio_signo"] = (
        np.sign(eligible["cambio_1"]) != np.sign(eligible["cambio_2"])
    ) & eligible["cambio_1"].ne(0) & eligible["cambio_2"].ne(0)
    eligible["dos_cambios_negativos"] = eligible["cambio_1"].lt(0) & eligible["cambio_2"].lt(0)
    eligible["dos_cambios_positivos"] = eligible["cambio_1"].gt(0) & eligible["cambio_2"].gt(0)
    eligible["extrapolacion_extrema_20pp"] = eligible["tendencia_seccional_media"].abs().ge(0.20)
    eligible["ajuste_regularizacion_pp"] = eligible["prediccion_C_2027"].sub(
        eligible["prediccion_B_2027"]
    ).mul(100)

    scenario_columns = [
        "clave_seccion",
        "fuente_regularizacion",
        *(f"referencia_regularizacion_{year}" for year in YEARS),
        "cambio_1",
        "cambio_2",
        "tendencia_seccional_media",
        "cambio_referencia_1",
        "cambio_referencia_2",
        "tendencia_referencia_media",
        "prediccion_B_2027_sin_recorte",
        "prediccion_C_2027_sin_recorte",
        "prediccion_B_2027",
        "prediccion_C_2027",
        "recorte_B",
        "recorte_C",
        "diferencia_absoluta_cambios",
        "cambio_signo",
        "dos_cambios_negativos",
        "dos_cambios_positivos",
        "extrapolacion_extrema_20pp",
        "ajuste_regularizacion_pp",
    ]
    scenarios = master.merge(
        eligible[scenario_columns], on="clave_seccion", how="left", validate="one_to_one"
    )
    scenarios["prediccion_A_2027"] = scenarios["prediccion_modelo_A_nacional_2027"]
    scenarios["prediccion_D_2027"] = scenarios["participacion_2021"]

    common = scenarios.loc[scenarios["elegible_tendencia_seccional"]].copy()
    counts = {
        "universo_total": len(scenarios),
        "universo_comun": len(common),
        "sin_historia_comparable": int((~scenarios["elegible_tendencia_seccional"]).sum()),
        "proporcion_sin_historia_comparable": float(
            (~scenarios["elegible_tendencia_seccional"]).mean()
        ),
    }
    for letter in "ABCD":
        prediction = common[f"prediccion_{letter}_2027"]
        counts[f"caidas_2027_{letter}"] = int(
            prediction.sub(common["participacion_2021"]).le(DECLINE_THRESHOLD).sum()
        )
    return scenarios, counts


def _fmt_pct(value: float) -> str:
    return f"{value:.2%}"


def _fmt_metrics_table(metrics: pd.DataFrame) -> str:
    rows = [
        "| Modelo | Precision | Recall | F1 | Bal. acc. | MAE | RMSE | Bias | VP | FP | FN | VN | Caídas pred. |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in metrics.itertuples(index=False):
        rows.append(
            f"| {row.modelo} | {row.precision:.4f} | {row.recall:.4f} | {row.f1:.4f} | "
            f"{row.balanced_accuracy:.4f} | {_fmt_pct(row.mae)} | {_fmt_pct(row.rmse)} | "
            f"{_fmt_pct(row.bias)} | {row.verdaderos_positivos:,} | {row.falsos_positivos:,} | "
            f"{row.falsos_negativos:,} | {row.verdaderos_negativos:,} | {row.caidas_proyectadas:,} |"
        )
    return "\n".join(rows)


def _diagnostics(scenarios: pd.DataFrame) -> dict[str, float | int]:
    eligible = scenarios.loc[scenarios["elegible_tendencia_seccional"]].copy()
    diff = eligible["diferencia_absoluta_cambios"]
    adjustment = eligible["ajuste_regularizacion_pp"].abs()
    return {
        "eligible": len(eligible),
        "both_negative": int(eligible["dos_cambios_negativos"].sum()),
        "both_positive": int(eligible["dos_cambios_positivos"].sum()),
        "sign_change": int(eligible["cambio_signo"].sum()),
        "zero_involved": int(
            len(eligible)
            - eligible["dos_cambios_negativos"].sum()
            - eligible["dos_cambios_positivos"].sum()
            - eligible["cambio_signo"].sum()
        ),
        "diff_mean": float(diff.mean()),
        "diff_median": float(diff.median()),
        "diff_p90": float(diff.quantile(0.90)),
        "diff_p95": float(diff.quantile(0.95)),
        "diff_max": float(diff.max()),
        "raw_outside_B": int(eligible["recorte_B"].sum()),
        "raw_outside_C": int(eligible["recorte_C"].sum()),
        "extreme_20pp": int(eligible["extrapolacion_extrema_20pp"].sum()),
        "adjust_mean_pp": float(adjustment.mean()),
        "adjust_median_pp": float(adjustment.median()),
        "adjust_p90_pp": float(adjustment.quantile(0.90)),
        "adjust_max_pp": float(adjustment.max()),
    }


def write_reports(
    paired: pd.DataFrame,
    metrics: pd.DataFrame,
    audit: dict[str, int],
    scenarios: pd.DataFrame,
    scenario_counts: dict[str, float | int],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    paired.to_csv(output_dir / "PREDICTIONS_COMPARISON.csv", index=False)

    keep = [
        "clave_entidad",
        "nombre_entidad",
        "clave_municipio",
        "nombre_municipio",
        "clave_seccion",
        "clase_confianza_geografica",
        "participacion_2009",
        "participacion_2015",
        "participacion_2021",
        "elegible_tendencia_seccional",
        "motivo_elegibilidad_tendencia",
        "fuente_regularizacion",
        "cambio_1",
        "cambio_2",
        "tendencia_seccional_media",
        "tendencia_referencia_media",
        "prediccion_A_2027",
        "prediccion_B_2027_sin_recorte",
        "prediccion_B_2027",
        "prediccion_C_2027_sin_recorte",
        "prediccion_C_2027",
        "prediccion_D_2027",
        "recorte_B",
        "recorte_C",
        "diferencia_absoluta_cambios",
        "cambio_signo",
        "dos_cambios_negativos",
        "dos_cambios_positivos",
        "extrapolacion_extrema_20pp",
        "ajuste_regularizacion_pp",
    ]
    scenarios[keep].to_csv(output_dir / "SCENARIOS_2027.csv", index=False)

    diagnostics = _diagnostics(scenarios)
    metric_table = _fmt_metrics_table(metrics)
    metric_index = metrics.set_index("modelo")
    persistence = metric_index.loc["D_persistencia"]
    advanced = metric_index.loc["A_modelo_avanzado_actual"]
    simple = metric_index.loc["B_tendencia_seccional_simple"]
    regularized = metric_index.loc["C_tendencia_seccional_regularizada"]

    model_comparison = f"""# Comparación de modelos — tendencia seccional 2027

## Diseño fijado antes de observar resultados

- Backtest único: predicción de 2021 usando solamente 2009 y 2015.
- Evento de caída: cambio menor o igual a -1 punto porcentual, sin optimizar el umbral.
- A: modelo nacional corregido vigente, residual centrado y contracción 0.25; se reutilizó su predicción guardada, sin reentrenamiento.
- B: `P2015 + (P2015 - P2009)`.
- C: 50% del cambio seccional y 50% del cambio municipal histórico calculado sin la propia sección. El peso 0.50 es fijo, no fue seleccionado por desempeño. Si un municipio no tiene otra sección comparable se usa la entidad sin la propia sección.
- D: persistencia (`P2015`).
- B y C se recortan al dominio [0, 1] para evaluar tasas válidas; los valores sin recorte y la bandera de recorte se conservan en el CSV.

## Muestra estrictamente pareada

El universo objetivo 2021 contiene {audit['target_2021_total']:,} secciones observadas; {audit['target_2021_clase_A']:,} son clase A. El modelo A dispone de {audit['modelo_A_secciones']:,} predicciones seccionales. La intersección con historia completa y referencias válidas produce **{audit['muestra_pareada']:,} secciones** ({metrics.iloc[0]['cobertura']:.2%} del universo objetivo). Todos los modelos se evalúan sobre esas mismas filas. Se observaron {int(metrics.iloc[0]['caidas_observadas']):,} caídas materiales.

## Resultados 2021

{metric_table}

Las métricas continuas están expresadas como proporciones; por ejemplo, MAE {_fmt_pct(simple['mae'])} equivale a {simple['mae'] * 100:.2f} puntos porcentuales.

## Diferencias clave

- B frente a persistencia: Δ precision {simple['precision'] - persistence['precision']:+.4f}, Δ recall {simple['recall'] - persistence['recall']:+.4f}, Δ F1 {simple['f1'] - persistence['f1']:+.4f}, Δ MAE {(simple['mae'] - persistence['mae']) * 100:+.2f} pp.
- C frente a persistencia: Δ precision {regularized['precision'] - persistence['precision']:+.4f}, Δ recall {regularized['recall'] - persistence['recall']:+.4f}, Δ F1 {regularized['f1'] - persistence['f1']:+.4f}, Δ MAE {(regularized['mae'] - persistence['mae']) * 100:+.2f} pp.
- B frente a A: Δ precision {simple['precision'] - advanced['precision']:+.4f}, Δ recall {simple['recall'] - advanced['recall']:+.4f}, Δ F1 {simple['f1'] - advanced['f1']:+.4f}, Δ MAE {(simple['mae'] - advanced['mae']) * 100:+.2f} pp.
- C frente a A: Δ precision {regularized['precision'] - advanced['precision']:+.4f}, Δ recall {regularized['recall'] - advanced['recall']:+.4f}, Δ F1 {regularized['f1'] - advanced['f1']:+.4f}, Δ MAE {(regularized['mae'] - advanced['mae']) * 100:+.2f} pp.

## Alcance de la evidencia

Este backtest valida una extrapolación basada en **una** transición (2009→2015); no valida exactamente la regla 2027, que promedia dos transiciones. No se usó ningún valor 2021 como feature de B, C o D. La predicción A se toma del artefacto canónico previo.
"""
    (output_dir / "MODEL_COMPARISON.md").write_text(model_comparison, encoding="utf-8")

    trend_diagnostics = f"""# Diagnóstico de estabilidad de tendencia

## Universo 2027

El maestro conserva {scenario_counts['universo_total']:,} secciones. Son elegibles {scenario_counts['universo_comun']:,} secciones clase A con historia y denominadores completos; {scenario_counts['sin_historia_comparable']:,} ({scenario_counts['proporcion_sin_historia_comparable']:.2%}) no tienen comparabilidad suficiente para B/C. No se imputan tendencias a esas filas.

## Dirección de las dos transiciones

Sobre {diagnostics['eligible']:,} secciones elegibles:

- Dos cambios negativos: {diagnostics['both_negative']:,} ({diagnostics['both_negative'] / diagnostics['eligible']:.2%}).
- Dos cambios positivos: {diagnostics['both_positive']:,} ({diagnostics['both_positive'] / diagnostics['eligible']:.2%}).
- Cambio de signo: {diagnostics['sign_change']:,} ({diagnostics['sign_change'] / diagnostics['eligible']:.2%}).
- Algún cambio exactamente cero u otro caso límite: {diagnostics['zero_involved']:,}.

## Magnitud de la inestabilidad

La diferencia absoluta entre los cambios 2009–2015 y 2015–2021 tiene media {_fmt_pct(diagnostics['diff_mean'])}, mediana {_fmt_pct(diagnostics['diff_median'])}, percentil 90 {_fmt_pct(diagnostics['diff_p90'])}, percentil 95 {_fmt_pct(diagnostics['diff_p95'])} y máximo {_fmt_pct(diagnostics['diff_max'])}.

## Extremos y regularización

- B produce {diagnostics['raw_outside_B']:,} tasas crudas fuera de [0,1]; C produce {diagnostics['raw_outside_C']:,}. Se conservan los valores crudos y se aplica recorte solamente a la predicción operacional del experimento.
- {diagnostics['extreme_20pp']:,} secciones tienen una tendencia media absoluta de al menos 20 pp; este umbral es diagnóstico, no un filtro.
- La diferencia absoluta C–B tiene media {diagnostics['adjust_mean_pp']:.2f} pp, mediana {diagnostics['adjust_median_pp']:.2f} pp, percentil 90 {diagnostics['adjust_p90_pp']:.2f} pp y máximo {diagnostics['adjust_max_pp']:.2f} pp.

La frecuencia de cambios de signo y la dispersión entre transiciones muestran que la trayectoria propia no es estable para una fracción sustantiva del universo. La regularización reduce extremos, pero no convierte dos observaciones históricas en una tendencia estructural demostrada.
"""
    (output_dir / "TREND_DIAGNOSTICS.md").write_text(trend_diagnostics, encoding="utf-8")

    b_beats_persistence = simple["mae"] < persistence["mae"] and simple["f1"] > persistence["f1"]
    c_beats_advanced = regularized["mae"] < advanced["mae"] and regularized["f1"] > advanced["f1"]
    recommendation = f"""# Recomendación

## Respuestas ejecutivas

1. **¿La tendencia propia mejora respecto a persistencia?** {'Sí en MAE y F1 simultáneamente.' if b_beats_persistence else 'No de forma conjunta: cualquier ganancia de detección debe leerse junto con el error continuo y los falsos positivos.'}
2. **¿Mejora respecto al modelo avanzado actual?** {'C supera simultáneamente a A en MAE y F1.' if c_beats_advanced else 'No: la tendencia regularizada no supera simultáneamente a A en MAE y F1.'}
3. **¿Detecta más caídas reales?** B registra {int(simple['verdaderos_positivos']):,} VP y C {int(regularized['verdaderos_positivos']):,}, frente a {int(advanced['verdaderos_positivos']):,} de A y {int(persistence['verdaderos_positivos']):,} de persistencia.
4. **¿Costo en falsos positivos?** B genera {int(simple['falsos_positivos']):,} FP y C {int(regularized['falsos_positivos']):,}, frente a {int(advanced['falsos_positivos']):,} de A.
5. **¿La regularización mejora estabilidad?** Reduce tasas crudas fuera de rango de {diagnostics['raw_outside_B']:,} a {diagnostics['raw_outside_C']:,} y modera la proyección en {diagnostics['adjust_mean_pp']:.2f} pp absolutos en promedio. Su efecto predictivo se observa en la tabla; estabilidad numérica no equivale por sí sola a mayor validez.
6. **¿Modelo central defendible para 2027?** Se recomienda **mantener A como proyección central de trabajo**. B y C quedan como escenarios diagnósticos: amplían la detección, pero deben justificar su costo en FP y error continuo antes de sustituir el modelo vigente. El handoff canónico no se modificó.
7. **¿Residual ML sin leakage?** No es viable validarlo con la historia intermedia disponible. Para el backtest 2021 solo existe una transición anterior (2009→2015), de modo que no hay un ciclo previo adicional para entrenar targets residuales y luego evaluar temporalmente en 2021. No se fabricaron folds, no se reentrenó ML y el experimento se detiene aquí.

## Escenarios 2027 en universo común

| Modelo | Caídas proyectadas (≤ -1 pp) |
|---|---:|
| A avanzado actual | {scenario_counts['caidas_2027_A']:,} |
| B tendencia simple | {scenario_counts['caidas_2027_B']:,} |
| C tendencia regularizada | {scenario_counts['caidas_2027_C']:,} |
| D persistencia | {scenario_counts['caidas_2027_D']:,} |

Los conteos anteriores se calculan sobre las mismas {scenario_counts['universo_comun']:,} secciones elegibles. A y D también tienen mayor cobertura en el maestro, pero mezclar universos haría injusta la comparación.

## Evidencia frente a supuestos

**Evidencia observada:** métricas pareadas de 2021, conteos de confusión, error continuo, cobertura y diagnósticos históricos calculados en los CSV. **Supuestos de modelación:** continuidad de la trayectoria hasta 2027, peso fijo 50/50 de C, validez del municipio como ancla y recorte de tasas al dominio posible. La recomendación no trata esos supuestos como hechos.
"""
    (output_dir / "RECOMMENDATION.md").write_text(recommendation, encoding="utf-8")


def run_experiment(paths: ExperimentPaths) -> tuple[pd.DataFrame, dict[str, float | int]]:
    totals = pd.read_parquet(paths.totals)
    confidence = pd.read_parquet(paths.confidence)
    backtest_a = pd.read_parquet(paths.backtest_a)
    master = pd.read_csv(
        paths.master_2027,
        dtype={"clave_entidad": "string", "clave_municipio": "string", "clave_seccion": "string"},
    )
    paired, metrics, audit = build_backtest(totals, confidence, backtest_a)
    scenarios, scenario_counts = build_scenarios_2027(totals, master)
    write_reports(paired, metrics, audit, scenarios, scenario_counts, paths.output_dir)
    return metrics, scenario_counts
