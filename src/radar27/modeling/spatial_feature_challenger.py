from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import shapely
from scipy import sparse

from radar27.geography.temporal_graphs import (
    _load_snapshot,
    load_temporal_graph_config,
)
from radar27.modeling.feature_enrichment import _resolve_feature_group
from radar27.modeling.feature_models import _load_yaml
from radar27.modeling.graph_embedding_challenger import (
    _load_model_frame,
    _metric_row,
    _prediction_frame,
)
from radar27.modeling.tabular_challengers import _predict_residual_correction


def _adjacency(edge_index: np.ndarray, nodes: int) -> sparse.csr_matrix:
    adjacency = sparse.csr_matrix(
        (
            np.ones(edge_index.shape[1], dtype=np.float32),
            (edge_index[0], edge_index[1]),
        ),
        shape=(nodes, nodes),
    )
    adjacency.sum_duplicates()
    adjacency.data[:] = 1.0
    adjacency.setdiag(0)
    adjacency.eliminate_zeros()
    return adjacency


def _neighbor_statistics(
    adjacency: sparse.csr_matrix,
    values: np.ndarray,
    prefix: str,
    zscore_clip: float,
) -> dict[str, np.ndarray]:
    finite = np.isfinite(values)
    clean = np.where(finite, values, 0.0)
    count = np.asarray(adjacency @ finite.astype(np.float32)).ravel()
    total = np.asarray(adjacency @ clean).ravel()
    squared = np.asarray(adjacency @ (clean**2)).ravel()
    mean = np.divide(total, count, out=np.full(len(values), np.nan), where=count > 0)
    variance = np.divide(
        squared,
        count,
        out=np.full(len(values), np.nan),
        where=count > 0,
    ) - mean**2
    std = np.sqrt(np.maximum(variance, 0.0))
    difference = values - mean
    zscore = np.divide(
        difference,
        std,
        out=np.full(len(values), np.nan),
        where=std > 1e-8,
    )
    zero_variance = np.isfinite(difference) & np.isfinite(std) & (std <= 1e-8)
    zscore[zero_variance] = np.sign(difference[zero_variance]) * zscore_clip
    zscore = np.clip(zscore, -zscore_clip, zscore_clip)
    return {
        f"neighbor_{prefix}_mean": mean,
        f"neighbor_{prefix}_std": std,
        f"{prefix}_minus_neighbor_mean": difference,
        f"{prefix}_neighbor_zscore": zscore,
    }


def _exclusive_two_hop(adjacency: sparse.csr_matrix) -> sparse.csr_matrix:
    two_hop = adjacency @ adjacency
    two_hop.data[:] = 1.0
    two_hop.setdiag(0)
    two_hop.eliminate_zeros()
    two_hop = two_hop - two_hop.multiply(adjacency)
    two_hop.eliminate_zeros()
    two_hop.data[:] = 1.0
    return two_hop.tocsr()


def _two_hop_features(
    adjacency: sparse.csr_matrix, values: np.ndarray
) -> dict[str, np.ndarray]:
    two_hop = _exclusive_two_hop(adjacency)
    finite = np.isfinite(values)
    count = np.asarray(two_hop @ finite.astype(np.float32)).ravel()
    total = np.asarray(two_hop @ np.where(finite, values, 0.0)).ravel()
    mean = np.divide(total, count, out=np.full(len(values), np.nan), where=count > 0)
    return {
        "two_hop_same_type_mean": mean,
        "same_type_minus_two_hop_mean": values - mean,
    }


def _morphology_table(project_root: Path, year: int, output: Path) -> pd.DataFrame:
    path = output / f"morphology_{year}.parquet"
    if path.is_file():
        return pd.read_parquet(path)
    temporal_config = load_temporal_graph_config(project_root)
    source = temporal_config["snapshots"][year]
    sections, _ = _load_snapshot(project_root, source)
    precision = float(temporal_config["geometry_policy"]["precision_grid_m"])
    snapped = shapely.set_precision(sections.geometry.array, precision)
    perimeter = shapely.length(snapped).astype(float)
    area = shapely.area(snapped).astype(float)
    compactness = np.divide(
        4.0 * np.pi * area,
        perimeter**2,
        out=np.full(len(sections), np.nan),
        where=perimeter > 0,
    )
    morphology = pd.DataFrame(
        {
            "section_key": sections["section_key"].astype(str),
            "perimeter_m": perimeter,
            "compactness": compactness,
        }
    )
    output.mkdir(parents=True, exist_ok=True)
    morphology.to_parquet(path, index=False)
    return morphology


def _structural_features(
    project_root: Path,
    year: int,
    frame: pd.DataFrame,
    adjacency: sparse.csr_matrix,
    morphology_directory: Path,
) -> pd.DataFrame:
    graph_nodes = pd.read_parquet(
        project_root / f"artifacts/graphs/temporal/{year}/nodes.parquet"
    )
    metadata = frame[["section_key"]].merge(
        graph_nodes[
            [
                "section_key",
                "entity_id",
                "municipality_code",
                "source_nominal_list",
                "source_electoral_roll",
                "centroid_lon",
                "centroid_lat",
                "area_m2",
            ]
        ],
        on="section_key",
        how="left",
        validate="one_to_one",
    )
    if metadata["entity_id"].isna().any():
        raise ValueError(f"Faltan metadatos cartograficos para {year}")
    morphology = _morphology_table(project_root, year, morphology_directory)
    metadata = metadata.merge(morphology, on="section_key", validate="one_to_one")
    degree = np.asarray(adjacency.sum(axis=1)).ravel()
    rows, columns = adjacency.nonzero()
    entity = metadata["entity_id"].astype(str).to_numpy()
    municipality = metadata["municipality_code"].astype(str).to_numpy()
    cross_entity_count = np.bincount(
        rows,
        weights=(entity[rows] != entity[columns]).astype(float),
        minlength=len(metadata),
    )
    cross_municipality_count = np.bincount(
        rows,
        weights=(
            (entity[rows] != entity[columns])
            | (municipality[rows] != municipality[columns])
        ).astype(float),
        minlength=len(metadata),
    )
    cross_entity_share = np.divide(
        cross_entity_count,
        degree,
        out=np.zeros(len(metadata), dtype=float),
        where=degree > 0,
    )
    cross_municipality_share = np.divide(
        cross_municipality_count,
        degree,
        out=np.zeros(len(metadata), dtype=float),
        where=degree > 0,
    )
    area_km2 = metadata["area_m2"].to_numpy(float) / 1_000_000.0
    nominal = metadata["source_nominal_list"].to_numpy(float)
    roll = metadata["source_electoral_roll"].to_numpy(float)
    lag_nominal = np.expm1(frame["log_nominal_list_lag1"].to_numpy(float))
    return pd.DataFrame(
        {
            "section_key": metadata["section_key"],
            "spatial_degree": degree,
            "spatial_isolated": (degree == 0).astype(np.float32),
            "log_section_area_m2": np.log1p(metadata["area_m2"].to_numpy(float)),
            "log_section_perimeter_m": np.log1p(metadata["perimeter_m"].to_numpy(float)),
            "section_compactness": metadata["compactness"].to_numpy(float),
            "log_snapshot_nominal_list": np.log1p(nominal),
            "snapshot_list_to_roll_ratio": np.divide(
                nominal,
                roll,
                out=np.full(len(metadata), np.nan),
                where=roll > 0,
            ),
            "log_snapshot_list_density_km2": np.log1p(
                np.divide(
                    nominal,
                    area_km2,
                    out=np.full(len(metadata), np.nan),
                    where=area_km2 > 0,
                )
            ),
            "snapshot_nominal_growth_vs_lag1": np.divide(
                nominal,
                lag_nominal,
                out=np.full(len(metadata), np.nan),
                where=lag_nominal > 0,
            )
            - 1.0,
            "cross_municipality_neighbor_share": cross_municipality_share,
            "cross_entity_neighbor_share": cross_entity_share,
            "section_centroid_lon": metadata["centroid_lon"].to_numpy(float),
            "section_centroid_lat": metadata["centroid_lat"].to_numpy(float),
        }
    )


def build_spatial_feature_frame(
    project_root: Path,
    year: int,
    topology_key: str,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, list[str]]:
    frame = _load_model_frame(project_root, year)
    bundle = np.load(project_root / f"artifacts/gnn_dataset/graph_{year}.npz")
    if not np.array_equal(
        frame["section_key"].to_numpy(dtype=str), bundle["section_keys"].astype(str)
    ):
        raise ValueError(f"El orden del frame y el grafo no coincide en {year}")
    adjacency = _adjacency(bundle[topology_key], len(frame))
    spatial = pd.DataFrame({"section_key": frame["section_key"]})
    feature_names: list[str] = []
    for source_feature in config["neighbor_source_features"]:
        statistics = _neighbor_statistics(
            adjacency,
            frame[source_feature].to_numpy(float),
            source_feature,
            float(config["zscore_clip"]),
        )
        for name, values in statistics.items():
            spatial[name] = values
            feature_names.append(name)
    two_hop = _two_hop_features(
        adjacency, frame[config["two_hop_source_feature"]].to_numpy(float)
    )
    for name, values in two_hop.items():
        spatial[name] = values
        feature_names.append(name)
    morphology_directory = project_root / config["outputs"]["morphology_directory"]
    structural = _structural_features(
        project_root, year, frame, adjacency, morphology_directory
    )
    structural_names = [column for column in structural if column != "section_key"]
    feature_names.extend(structural_names)
    spatial = spatial.merge(structural, on="section_key", validate="one_to_one")
    enriched = frame.merge(spatial, on="section_key", validate="one_to_one")
    if len(feature_names) != 35:
        raise ValueError(f"Se esperaban 35 variables espaciales, se obtuvieron {len(feature_names)}")
    return enriched, feature_names


def _spatial_feature_sets(
    config: dict[str, Any], all_features: list[str]
) -> dict[str, list[str]]:
    neighbor = []
    for source in config["neighbor_source_features"]:
        neighbor.extend(
            [
                f"neighbor_{source}_mean",
                f"neighbor_{source}_std",
                f"{source}_minus_neighbor_mean",
                f"{source}_neighbor_zscore",
            ]
        )
    groups = {
        "neighbor_statistics": neighbor,
        "two_hop": ["two_hop_same_type_mean", "same_type_minus_two_hop_mean"],
        "administrative_boundaries": [
            "cross_municipality_neighbor_share",
            "cross_entity_neighbor_share",
        ],
        "all": all_features,
    }
    resolved = {}
    for feature_set, definition in config["feature_sets"].items():
        columns = []
        for group in definition["include_groups"]:
            columns.extend(groups[group])
        resolved[feature_set] = list(dict.fromkeys(columns))
    return resolved


def run_spatial_feature_challenger(
    project_root: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    config = _load_yaml(project_root / "configs/spatial_feature_challenger.yaml")
    feature_config = _load_yaml(project_root / str(config["feature_config"]))
    reference_config = _load_yaml(project_root / str(config["reference_model_config"]))
    numeric, categorical = _resolve_feature_group(feature_config, config["feature_group"])
    reference_spec = reference_config["models"]["hist_gradient_boosting"]
    shift = pd.read_csv(
        project_root / "artifacts/tables/national_shift_estimates.csv"
    ).set_index("target_year")["national_shift_correction"]
    years = [2015, *config["evaluation_targets"]]
    reference_frames = {year: _load_model_frame(project_root, year) for year in years}
    seed = int(config["random_seed"])
    shrinkage = float(config["residual_shrinkage"])
    prediction_rows: list[pd.DataFrame] = []
    metric_rows: list[dict[str, Any]] = []
    registry_rows: list[dict[str, Any]] = []
    enriched_by_topology: dict[str, dict[int, pd.DataFrame]] = {}
    feature_names_by_topology: dict[str, list[str]] = {}
    feature_output = project_root / config["outputs"]["feature_directory"]
    feature_output.mkdir(parents=True, exist_ok=True)

    for topology, topology_key in config["topologies"].items():
        enriched_by_topology[topology] = {}
        for year in years:
            enriched, feature_names = build_spatial_feature_frame(
                project_root, year, topology_key, config
            )
            enriched_by_topology[topology][year] = enriched
            feature_names_by_topology[topology] = feature_names
            enriched[["section_key", *feature_names]].to_parquet(
                feature_output / f"spatial_features_{year}_{topology}.parquet",
                index=False,
            )

    for evaluation_year in config["evaluation_targets"]:
        train_years = [year for year in years if year < evaluation_year]
        train_reference = pd.concat(
            [reference_frames[year] for year in train_years], ignore_index=True
        )
        train_reference = train_reference[train_reference["actual"].notna()].copy()
        test_reference = reference_frames[evaluation_year].copy()
        correction = float(shift.get(evaluation_year, 0.0))
        baseline_valid = test_reference.dropna(
            subset=["actual", "participation_same_type", "target_identified_records"]
        )
        baseline_mae = float(
            np.average(
                (baseline_valid["participation_same_type"] - baseline_valid["actual"]).abs(),
                weights=baseline_valid["target_identified_records"],
            )
        )
        before_shift, residual_prediction, fit_seconds = _predict_residual_correction(
            train_reference,
            test_reference,
            numeric,
            categorical,
            reference_spec,
            seed,
            shrinkage,
        )
        reference_prediction = _prediction_frame(
            test_reference,
            config["reference_model"],
            before_shift,
            residual_prediction,
            correction,
        )
        reference_metric = _metric_row(
            reference_prediction, config["reference_model"], baseline_mae, None
        )
        reference_metric["spatial_feature_set"] = "none"
        reference_metric["spatial_feature_count"] = 0
        reference_mae = float(reference_metric["identified_weighted_mae"])
        prediction_rows.append(reference_prediction)
        metric_rows.append(reference_metric)
        registry_rows.append(
            {
                "target_year": evaluation_year,
                "model_id": config["reference_model"],
                "topology": "none",
                "training_target_years": "|".join(map(str, train_years)),
                "training_units": len(train_reference),
                "base_numeric_features": len(numeric),
                "spatial_features": 0,
                "fit_seconds": fit_seconds,
            }
        )

        for topology in config["topologies"]:
            all_feature_names = feature_names_by_topology[topology]
            train = pd.concat(
                [enriched_by_topology[topology][year] for year in train_years],
                ignore_index=True,
            )
            train = train[train["actual"].notna()].copy()
            test = enriched_by_topology[topology][evaluation_year]
            feature_sets = _spatial_feature_sets(config, all_feature_names)
            for feature_set, feature_names in feature_sets.items():
                started = time.perf_counter()
                before_shift, residual_prediction, fit_seconds = (
                    _predict_residual_correction(
                        train,
                        test,
                        [*numeric, *feature_names],
                        categorical,
                        reference_spec,
                        seed,
                        shrinkage,
                    )
                )
                total_seconds = time.perf_counter() - started
                model_id = (
                    f"{config['candidate_model_prefix']}_{feature_set}_{topology}"
                )
                predicted = _prediction_frame(
                    test, model_id, before_shift, residual_prediction, correction
                )
                prediction_rows.append(predicted)
                metric = _metric_row(predicted, model_id, baseline_mae, reference_mae)
                metric["spatial_feature_set"] = feature_set
                metric["spatial_feature_count"] = len(feature_names)
                metric_rows.append(metric)
                registry_rows.append(
                    {
                        "target_year": evaluation_year,
                        "model_id": model_id,
                        "topology": topology,
                        "training_target_years": "|".join(map(str, train_years)),
                        "training_units": len(train),
                        "base_numeric_features": len(numeric),
                        "spatial_features": len(feature_names),
                        "spatial_feature_set": feature_set,
                        "spatial_feature_names": "|".join(feature_names),
                        "fit_seconds": fit_seconds,
                        "total_candidate_seconds": total_seconds,
                        "uses_target_outcome_features": False,
                    }
                )

    predictions = pd.concat(prediction_rows, ignore_index=True)
    metrics = pd.DataFrame(metric_rows).sort_values(["target_year", "identified_weighted_mae"])
    registry = pd.DataFrame(registry_rows)
    outputs = config["outputs"]
    predictions.to_parquet(project_root / outputs["predictions"], index=False)
    metrics.to_csv(project_root / outputs["metrics"], index=False)
    registry.to_csv(project_root / outputs["registry"], index=False)
    decision = write_spatial_feature_decision(project_root, metrics)
    return predictions, metrics, registry, decision


def write_spatial_feature_decision(
    project_root: Path, metrics: pd.DataFrame
) -> dict[str, Any]:
    config = _load_yaml(project_root / "configs/spatial_feature_challenger.yaml")
    primary_year = int(config["primary_target_year"])
    reference_id = str(config["reference_model"])
    primary = metrics[metrics["target_year"].eq(primary_year)]
    reference = primary[primary["model_id"].eq(reference_id)].iloc[0]
    candidate = primary[~primary["model_id"].eq(reference_id)].sort_values(
        "identified_weighted_mae"
    ).iloc[0]
    candidate_id = str(candidate["model_id"])
    improvement = float(
        reference["identified_weighted_mae"] - candidate["identified_weighted_mae"]
    )
    robustness = []
    for year in config["evaluation_targets"]:
        if int(year) == primary_year:
            continue
        row = metrics[
            metrics["target_year"].eq(year) & metrics["model_id"].eq(candidate_id)
        ].iloc[0]
        change = float(row["mae_change_vs_reference"])
        robustness.append(
            {
                "target_year": int(year),
                "mae_change_vs_reference": change,
                "passes": change
                <= float(config["maximum_other_fold_weighted_mae_deterioration"]),
            }
        )
    promoted = bool(improvement > 0 and all(row["passes"] for row in robustness))
    decision = {
        "objective": config["objective"],
        "reference_model": reference_id,
        "best_spatial_candidate": candidate_id,
        "primary_target_year": primary_year,
        "reference_primary_weighted_mae": float(reference["identified_weighted_mae"]),
        "candidate_primary_weighted_mae": float(candidate["identified_weighted_mae"]),
        "primary_improvement": improvement,
        "robustness": robustness,
        "spatial_features_promoted": promoted,
        "selected_model_for_next_iteration": candidate_id if promoted else reference_id,
        "spatial_feature_set": str(candidate["spatial_feature_set"]),
        "spatial_feature_count": int(candidate["spatial_feature_count"]),
        "limitations": [
            "Only stable class A sections are used in this controlled graph comparison.",
            "Snapshot nominal-list fields must be available at the future prediction cutoff.",
            "Only three strict out-of-time target elections are available.",
        ],
    }
    (project_root / config["outputs"]["decision"]).write_text(
        json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return decision
