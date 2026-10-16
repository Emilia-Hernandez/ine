import numpy as np
import pandas as pd

from radar27.modeling.section_trend_2027 import (
    DECLINE_THRESHOLD,
    SECTION_WEIGHT,
    _add_leave_one_out_references,
    decline_metrics,
)


def test_regularization_rule_is_fixed_and_leave_one_out() -> None:
    frame = pd.DataFrame(
        {
            "municipality": ["m", "m"],
            "entity": ["e", "e"],
            "votos_identificados_participaron_2009": [40.0, 60.0],
            "registros_identificados_2009": [100.0, 100.0],
            "votos_identificados_participaron_2015": [50.0, 70.0],
            "registros_identificados_2015": [100.0, 100.0],
            "votos_identificados_participaron_2021": [60.0, 80.0],
            "registros_identificados_2021": [100.0, 100.0],
        }
    )
    result = _add_leave_one_out_references(frame, "municipality", "entity")
    assert SECTION_WEIGHT == 0.50
    assert np.isclose(result.loc[0, "referencia_regularizacion_2009"], 0.60)
    assert np.isclose(result.loc[1, "referencia_regularizacion_2021"], 0.60)
    assert result["fuente_regularizacion"].eq("municipio_sin_seccion").all()


def test_decline_metrics_uses_exact_one_point_threshold() -> None:
    previous = pd.Series([0.50, 0.50, 0.50, 0.50])
    actual = pd.Series([0.49, 0.4899, 0.50, 0.52])
    prediction = pd.Series([0.49, 0.50, 0.48, 0.52])
    metrics = decline_metrics(actual, previous, prediction, "test", 4)
    assert DECLINE_THRESHOLD == -0.01
    assert metrics["caidas_observadas"] == 2
    assert metrics["caidas_proyectadas"] == 2
    assert metrics["verdaderos_positivos"] == 1
    assert metrics["falsos_positivos"] == 1
    assert metrics["falsos_negativos"] == 1
    assert metrics["verdaderos_negativos"] == 1


def test_confusion_counts_cover_sample() -> None:
    previous = pd.Series([0.5, 0.5, 0.5])
    actual = pd.Series([0.4, 0.5, 0.6])
    prediction = pd.Series([0.45, 0.45, 0.6])
    metrics = decline_metrics(actual, previous, prediction, "test", 10)
    confusion = sum(
        metrics[key]
        for key in (
            "verdaderos_positivos",
            "falsos_positivos",
            "falsos_negativos",
            "verdaderos_negativos",
        )
    )
    assert confusion == metrics["unidades_evaluacion"]
    assert np.isclose(metrics["cobertura"], 0.3)
