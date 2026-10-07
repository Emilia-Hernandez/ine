from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from radar27.modeling.entity_cycle_adaptation import corrected_prediction

ROOT = Path(__file__).resolve().parents[1]


def test_entity_cycle_correction_is_bounded_and_directional() -> None:
    prediction = pd.Series([0.01, 0.50, 0.99])
    signal = pd.Series([0.10, 0.10, -0.10])
    corrected = corrected_prediction(prediction, signal, -0.5)
    assert np.allclose(corrected, [0.0, 0.45, 1.0])


def test_zero_shrinkage_reproduces_uncorrected_ablation() -> None:
    metrics = pd.read_csv(ROOT / "artifacts/tables/entity_cycle_adaptation_metrics.csv")
    zero = metrics[metrics["entity_cycle_shrinkage"].eq(0.0)].set_index("target_year")
    ablation = pd.read_csv(ROOT / "artifacts/tables/feature_ablation_metrics.csv")
    ablation = ablation[
        ablation["feature_group"].eq("competition_concurrency")
    ].set_index("target_year")
    assert np.allclose(
        zero.loc[[2018, 2021, 2024], "identified_weighted_mae"],
        ablation.loc[[2018, 2021, 2024], "identified_weighted_mae"],
    )


def test_entity_cycle_decision_passes_prespecified_gate() -> None:
    decision = json.loads(
        (ROOT / "artifacts/entity_cycle_adaptation_decision.json").read_text(
            encoding="utf-8"
        )
    )
    assert decision["base_feature_group"] == "competition_concurrency"
    assert decision["selected_shrinkage"] == -0.5
    assert decision["applied_shrinkage"] == -0.5
    assert decision["primary_mae_improvement"] >= 0.001
    assert all(row["passes"] for row in decision["robustness"])
    assert decision["promoted_for_2027"] is True
