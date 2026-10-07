from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
import torch
from scipy import sparse
from scipy.sparse.csgraph import connected_components
from sklearn.neighbors import NearestNeighbors

from radar27.modeling.feature_enrichment import _resolve_feature_group
from radar27.modeling.feature_models import _load_yaml
from radar27.modeling.graph_embedding_challenger import (
    _fit_encoder,
    _normalized_adjacency,
    _sha256,
)
from radar27.modeling.spatial_feature_challenger import _neighbor_statistics
from radar27.modeling.tabular_challengers import _predict_residual_correction


def _model_frame(mart: pd.DataFrame, year: int) -> pd.DataFrame:
    frame = mart[mart["target_year"].eq(year)].copy()
    if frame["evaluation_unit_id"].duplicated().any():
        raise ValueError(f"Unidades duplicadas en el mart {year}")
    return frame.sort_values("evaluation_unit_id").reset_index(drop=True)


def _fit_scaler(
    frames: dict[int, pd.DataFrame],
    train_years: list[int],
    columns: list[str],
    validation_entities: set[str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    parts = []
    for year in train_years:
        frame = frames[year]
        fit = ~frame["entity_id"].astype(str).isin(validation_entities)
        parts.append(frame.loc[fit, columns].to_numpy(dtype=float))
    values = np.vstack(parts)
    median = np.nanmedian(values, axis=0)
    filled = np.where(np.isfinite(values), values, median)
    mean = filled.mean(axis=0)
    scale = filled.std(axis=0)
    scale[scale < 1e-8] = 1.0
    return median, mean, scale, len(values)


def _standardized(
    frame: pd.DataFrame,
    columns: list[str],
    scaler: tuple[np.ndarray, np.ndarray, np.ndarray, int],
) -> np.ndarray:
    median, mean, scale, _ = scaler
    raw = frame[columns].to_numpy(dtype=float)
    filled = np.where(np.isfinite(raw), raw, median)
    return np.clip((filled - mean) / scale, -10.0, 10.0).astype(np.float32)


def _mutual_knn_graph(
    values: np.ndarray, k: int
) -> tuple[sparse.csr_matrix, sparse.csr_matrix, set[tuple[int, int]]]:
    if k < 1 or k >= len(values):
        raise ValueError("k debe ser positivo y menor que el número de nodos")
    neighbors = NearestNeighbors(n_neighbors=k + 1, algorithm="auto", n_jobs=4)
    neighbors.fit(values)
    distances, indices = neighbors.kneighbors(values)
    rows: list[int] = []
    columns: list[int] = []
    distance_values: list[float] = []
    nearest_nonself: dict[int, tuple[int, float]] = {}
    for node, (node_distances, node_indices) in enumerate(
        zip(distances, indices, strict=True)
    ):
        candidates = [
            (int(peer), float(distance))
            for peer, distance in zip(node_indices, node_distances, strict=True)
            if int(peer) != node
        ][:k]
        if len(candidates) != k:
            raise ValueError("No se encontraron suficientes pares sociodemográficos")
        nearest_nonself[node] = candidates[0]
        rows.extend([node] * k)
        columns.extend(peer for peer, _ in candidates)
        distance_values.extend(distance for _, distance in candidates)
    directed = sparse.csr_matrix(
        (np.ones(len(rows), dtype=np.float32), (rows, columns)),
        shape=(len(values), len(values)),
    )
    mutual = directed.multiply(directed.T).tocsr()
    mutual.data[:] = 1.0
    distance_directed = sparse.csr_matrix(
        (distance_values, (rows, columns)), shape=(len(values), len(values))
    )
    distance_matrix = distance_directed.maximum(distance_directed.T).multiply(mutual)
    fallback_pairs: set[tuple[int, int]] = set()
    degree = np.asarray(mutual.sum(axis=1)).ravel()
    if np.any(degree == 0):
        mutual = mutual.tolil()
        distance_matrix = distance_matrix.tolil()
        for node in np.flatnonzero(degree == 0):
            peer, distance = nearest_nonself[int(node)]
            mutual[node, peer] = 1.0
            mutual[peer, node] = 1.0
            distance_matrix[node, peer] = distance
            distance_matrix[peer, node] = distance
            fallback_pairs.add(tuple(sorted((int(node), peer))))
        mutual = mutual.tocsr()
        distance_matrix = distance_matrix.tocsr()
    mutual.setdiag(0)
    mutual.eliminate_zeros()
    distance_matrix.setdiag(0)
    distance_matrix.eliminate_zeros()
    if (mutual != mutual.T).nnz:
        raise ValueError("El grafo de similitud no es simétrico")
    if np.any(np.asarray(mutual.sum(axis=1)).ravel() == 0):
        raise ValueError("El grafo de similitud contiene nodos aislados")
    return mutual, distance_matrix, fallback_pairs


def _edge_index(adjacency: sparse.csr_matrix) -> np.ndarray:
    rows, columns = adjacency.nonzero()
    return np.vstack([rows, columns]).astype(np.int64)


def _peer_feature_frame(
    frame: pd.DataFrame,
    adjacency: sparse.csr_matrix,
    distance_matrix: sparse.csr_matrix,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, list[str]]:
    peers = pd.DataFrame({"evaluation_unit_id": frame["evaluation_unit_id"]})
    feature_names: list[str] = []
    for source in config["peer_source_features"]:
        statistics = _neighbor_statistics(
            adjacency,
            frame[source].to_numpy(dtype=float),
            f"peer_{source}",
            float(config["zscore_clip"]),
        )
        for name, values in statistics.items():
            peers[name] = values
            feature_names.append(name)
    degree = np.asarray(adjacency.sum(axis=1)).ravel()
    distance_total = np.asarray(distance_matrix.sum(axis=1)).ravel()
    mean_distance = np.divide(
        distance_total,
        degree,
        out=np.zeros(len(frame), dtype=float),
        where=degree > 0,
    )
    rows, columns = adjacency.nonzero()
    entity = frame["entity_id"].astype(str).to_numpy()
    cross_entity_count = np.bincount(
        rows,
        weights=(entity[rows] != entity[columns]).astype(float),
        minlength=len(frame),
    )
    cross_entity_share = np.divide(
        cross_entity_count,
        degree,
        out=np.zeros(len(frame), dtype=float),
        where=degree > 0,
    )
    structural = {
        "sociodemographic_peer_degree": degree,
        "sociodemographic_peer_mean_distance": mean_distance,
        "sociodemographic_cross_entity_peer_share": cross_entity_share,
    }
    for name, values in structural.items():
        peers[name] = values
        feature_names.append(name)
    return peers, feature_names


def _write_graph_artifacts(
    output: Path,
    frame: pd.DataFrame,
    adjacency: sparse.csr_matrix,
    distance_matrix: sparse.csr_matrix,
    fallback_pairs: set[tuple[int, int]],
    peer_features: pd.DataFrame,
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    degree = np.asarray(adjacency.sum(axis=1)).ravel().astype(int)
    nodes = frame[
        [
            "evaluation_unit_id",
            "entity_id",
            "geography_confidence_class",
            "target_year",
            "max_electoral_feature_year",
            "context_source_max_year",
        ]
    ].copy()
    nodes.insert(0, "node_id", np.arange(len(nodes), dtype=np.int64))
    nodes["degree"] = degree
    nodes.to_parquet(output / "nodes.parquet", index=False)
    upper = sparse.triu(adjacency, k=1).tocoo()
    source = upper.row.astype(int)
    target = upper.col.astype(int)
    distances = np.asarray(distance_matrix[source, target]).ravel()
    entity = frame["entity_id"].astype(str).to_numpy()
    edges = pd.DataFrame(
        {
            "source_node_id": source,
            "target_node_id": target,
            "source_evaluation_unit_id": frame.iloc[source][
                "evaluation_unit_id"
            ].to_numpy(),
            "target_evaluation_unit_id": frame.iloc[target][
                "evaluation_unit_id"
            ].to_numpy(),
            "distance": distances,
            "cross_entity": entity[source] != entity[target],
            "is_isolated_fallback": [
                (int(left), int(right)) in fallback_pairs
                for left, right in zip(source, target, strict=True)
            ],
        }
    )
    edges.to_parquet(output / "edges.parquet", index=False)
    peer_features.to_parquet(output / "peer_features.parquet", index=False)
    components, _ = connected_components(adjacency, directed=False)
    return {
        "nodes": len(frame),
        "undirected_edges": len(edges),
        "minimum_degree": int(degree.min()),
        "maximum_degree": int(degree.max()),
        "mean_degree": float(degree.mean()),
        "connected_components": int(components),
        "fallback_edges": len(fallback_pairs),
        "cross_entity_edge_share": float(edges["cross_entity"].mean()),
    }


def _encoder_values(
    frame: pd.DataFrame,
    numeric: list[str],
    scaler: tuple[np.ndarray, np.ndarray, np.ndarray, int],
) -> np.ndarray:
    raw = frame[numeric].to_numpy(dtype=float)
    missing = ~np.isfinite(raw)
    standardized = _standardized(frame, numeric, scaler)
    return np.concatenate([standardized, missing.astype(np.float32)], axis=1).astype(
        np.float32
    )


def _prediction_frame(
    test: pd.DataFrame,
    model_id: str,
    candidate_kind: str,
    topology: str,
    before_shift: np.ndarray,
    residual_prediction: np.ndarray,
    national_shift: float,
    entity_cycle_shrinkage: float,
) -> pd.DataFrame:
    predicted = test[
        [
            "target_year",
            "evaluation_unit_id",
            "entity_id",
            "geography_confidence_class",
            "target_sections_represented",
            "target_identified_records",
            "actual",
            "participation_same_type",
            "entity_same_family_change_minus_national",
        ]
    ].copy()
    predicted["model_id"] = model_id
    predicted["candidate_kind"] = candidate_kind
    predicted["topology"] = topology
    predicted["model_prediction_before_national_shift"] = before_shift
    predicted["predicted_residual_unshrunk"] = residual_prediction
    predicted["national_shift_correction"] = national_shift
    predicted["entity_cycle_shrinkage"] = entity_cycle_shrinkage
    predicted["entity_cycle_correction"] = (
        entity_cycle_shrinkage
        * predicted["entity_same_family_change_minus_national"]
    )
    predicted["prediction"] = (
        predicted["model_prediction_before_national_shift"]
        + predicted["national_shift_correction"]
        + predicted["entity_cycle_correction"]
    ).clip(0.0, 1.0)
    return predicted


def _metric_row(
    predicted: pd.DataFrame,
    baseline_mae: float,
    reference_mae: float | None,
) -> dict[str, Any]:
    valid = predicted.dropna(subset=["actual", "prediction"]).copy()
    weights = valid["target_identified_records"].astype(float)
    error = valid["prediction"] - valid["actual"]
    weighted_mae = float(np.average(error.abs(), weights=weights))
    return {
        "target_year": int(valid["target_year"].iloc[0]),
        "model_id": str(valid["model_id"].iloc[0]),
        "candidate_kind": str(valid["candidate_kind"].iloc[0]),
        "topology": str(valid["topology"].iloc[0]),
        "evaluation_units": len(valid),
        "baseline_weighted_mae": baseline_mae,
        "identified_weighted_mae": weighted_mae,
        "mae_change_vs_baseline": weighted_mae - baseline_mae,
        "reference_weighted_mae": reference_mae,
        "mae_change_vs_reference": (
            weighted_mae - reference_mae if reference_mae is not None else 0.0
        ),
        "weighted_bias": float(np.average(error, weights=weights)),
        "mae": float(error.abs().mean()),
        "share_within_5pp": float(error.abs().le(0.05).mean()),
    }


def _candidate_feature_names(
    kind: str, peer_features: list[str], embedding_features: list[str]
) -> list[str]:
    if kind == "explicit":
        return peer_features
    if kind == "embedding":
        return embedding_features
    if kind == "combined":
        return [*peer_features, *embedding_features]
    raise ValueError(f"Tipo de candidato no soportado: {kind}")


def run_sociodemographic_similarity_challenger(
    project_root: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    config = _load_yaml(
        project_root / "configs/sociodemographic_similarity_challenger.yaml"
    )
    feature_config = _load_yaml(project_root / str(config["feature_config"]))
    model_config = _load_yaml(project_root / str(config["reference_model_config"]))
    numeric, categorical = _resolve_feature_group(
        feature_config, str(config["feature_group"])
    )
    mart = pd.read_parquet(
        project_root / "artifacts/tables/feature_ablation_mart.parquet"
    )
    years = sorted({2015, *map(int, config["evaluation_targets"])})
    frames = {year: _model_frame(mart, year) for year in years}
    required = set(
        numeric
        + categorical
        + list(config["similarity_features"])
        + list(config["peer_source_features"])
        + ["entity_same_family_change_minus_national"]
    )
    missing = required - set(mart.columns)
    if missing:
        raise ValueError(f"Variables ausentes para el grafo de similitud: {sorted(missing)}")
    similarity_features = list(config["similarity_features"])
    forbidden = {"actual", "participation", "turnout", "voted", "did_not_vote"}
    if any(any(token in feature for token in forbidden) for feature in similarity_features):
        raise ValueError("La topología sociodemográfica contiene una señal de participación")
    entity_decision = json.loads(
        (project_root / str(config["entity_cycle_decision"])).read_text(encoding="utf-8")
    )
    entity_shrinkage = float(entity_decision["applied_shrinkage"])
    if not np.isclose(
        entity_shrinkage,
        float(config["expected_entity_cycle_shrinkage"]),
        atol=1e-12,
    ):
        raise ValueError("La corrección estatal no coincide con el contrato")
    shift = pd.read_csv(
        project_root / "artifacts/tables/national_shift_estimates.csv"
    ).set_index("target_year")["national_shift_correction"]
    baseline = pd.read_csv(project_root / "artifacts/tables/backtest_metrics.csv")
    baseline = baseline[baseline["scenario"].eq("stable_plus_lineage")].set_index(
        "target_year"
    )["identified_weighted_mae"]
    reference_spec = model_config["models"]["hist_gradient_boosting"]
    validation_entities = set(map(str, config["validation_entity_ids"]))
    seed = int(config["random_seed"])
    residual_shrinkage = float(config["residual_shrinkage"])
    graph_root = project_root / str(config["outputs"]["graph_directory"])
    model_root = project_root / str(config["outputs"]["model_directory"])
    graph_root.mkdir(parents=True, exist_ok=True)
    model_root.mkdir(parents=True, exist_ok=True)
    prediction_rows: list[pd.DataFrame] = []
    metric_rows: list[dict[str, Any]] = []
    registry_rows: list[dict[str, Any]] = []
    graph_registry_rows: list[dict[str, Any]] = []

    for evaluation_year in map(int, config["evaluation_targets"]):
        train_years = [year for year in years if year < evaluation_year]
        train_reference = pd.concat(
            [frames[year] for year in train_years], ignore_index=True
        )
        train_reference = train_reference[train_reference["actual"].notna()].copy()
        test_reference = frames[evaluation_year].copy()
        national_shift = float(shift.get(evaluation_year, 0.0))
        before_shift, residual_prediction, fit_seconds = _predict_residual_correction(
            train_reference,
            test_reference,
            numeric,
            categorical,
            reference_spec,
            seed,
            residual_shrinkage,
        )
        reference_prediction = _prediction_frame(
            test_reference,
            str(config["reference_model"]),
            "reference",
            "none",
            before_shift,
            residual_prediction,
            national_shift,
            entity_shrinkage,
        )
        reference_metric = _metric_row(
            reference_prediction, float(baseline.loc[evaluation_year]), None
        )
        reference_mae = float(reference_metric["identified_weighted_mae"])
        prediction_rows.append(reference_prediction)
        metric_rows.append(reference_metric)
        registry_rows.append(
            {
                "target_year": evaluation_year,
                "model_id": config["reference_model"],
                "candidate_kind": "reference",
                "topology": "none",
                "training_target_years": "|".join(map(str, train_years)),
                "training_units": len(train_reference),
                "base_numeric_features": len(numeric),
                "additional_features": 0,
                "encoder_dimensions": 0,
                "encoder_uses_target_labels": False,
                "fit_seconds": fit_seconds,
            }
        )

        similarity_scaler = _fit_scaler(
            frames,
            train_years,
            similarity_features,
            validation_entities,
        )
        encoder_scaler = _fit_scaler(
            frames, train_years, numeric, validation_entities
        )
        for topology, k_value in config["topologies"].items():
            k = int(k_value)
            enriched: dict[int, pd.DataFrame] = {}
            graphs: dict[int, dict[str, Any]] = {}
            peer_feature_names: list[str] = []
            for graph_year in [*train_years, evaluation_year]:
                frame = frames[graph_year]
                similarity_values = _standardized(
                    frame, similarity_features, similarity_scaler
                )
                adjacency, distances, fallback_pairs = _mutual_knn_graph(
                    similarity_values, k
                )
                peer_frame, peer_feature_names = _peer_feature_frame(
                    frame, adjacency, distances, config
                )
                enriched[graph_year] = frame.merge(
                    peer_frame,
                    on="evaluation_unit_id",
                    validate="one_to_one",
                )
                values = _encoder_values(frame, numeric, encoder_scaler)
                validation = frame["entity_id"].astype(str).isin(validation_entities).to_numpy()
                graphs[graph_year] = {
                    "values": torch.from_numpy(values),
                    "adjacency": _normalized_adjacency(
                        _edge_index(adjacency), len(frame)
                    ),
                    "fit_mask": torch.from_numpy(~validation),
                    "validation_mask": torch.from_numpy(validation),
                    "unit_ids": frame["evaluation_unit_id"].astype(str).to_numpy(),
                }
                artifact_directory = (
                    graph_root
                    / f"fold_{evaluation_year}"
                    / f"year_{graph_year}"
                    / topology
                )
                graph_summary = _write_graph_artifacts(
                    artifact_directory,
                    frame,
                    adjacency,
                    distances,
                    fallback_pairs,
                    peer_frame,
                )
                graph_registry_rows.append(
                    {
                        "evaluation_year": evaluation_year,
                        "graph_year": graph_year,
                        "topology": topology,
                        "k": k,
                        "similarity_features": "|".join(similarity_features),
                        "scaler_training_years": "|".join(map(str, train_years)),
                        "scaler_fit_nodes": similarity_scaler[3],
                        **graph_summary,
                    }
                )

            encoder_started = time.perf_counter()
            encoder, diagnostics = _fit_encoder(
                graphs, train_years, config["encoder"], seed
            )
            encoder_seconds = time.perf_counter() - encoder_started
            state_path = model_root / (
                f"neighbor_only_fold_{evaluation_year}_{topology}.pt"
            )
            torch.save(encoder.state_dict(), state_path)
            embedding_columns = [
                f"sociodemographic_embedding_{index:02d}"
                for index in range(int(config["encoder"]["embedding_dim"]))
            ]
            encoder.eval()
            with torch.no_grad():
                for graph_year, graph in graphs.items():
                    embedding = encoder.encode(
                        graph["values"], graph["adjacency"]
                    ).numpy()
                    embedding_frame = pd.DataFrame(
                        embedding, columns=embedding_columns
                    )
                    embedding_frame.insert(
                        0, "evaluation_unit_id", graph["unit_ids"]
                    )
                    enriched[graph_year] = enriched[graph_year].merge(
                        embedding_frame,
                        on="evaluation_unit_id",
                        validate="one_to_one",
                    )
                    artifact_directory = (
                        graph_root
                        / f"fold_{evaluation_year}"
                        / f"year_{graph_year}"
                        / topology
                    )
                    embedding_frame.to_parquet(
                        artifact_directory / "embeddings.parquet", index=False
                    )

            for kind in config["candidate_feature_sets"]:
                additional = _candidate_feature_names(
                    str(kind), peer_feature_names, embedding_columns
                )
                train = pd.concat(
                    [enriched[year] for year in train_years], ignore_index=True
                )
                train = train[train["actual"].notna()].copy()
                test = enriched[evaluation_year]
                before_shift, residual_prediction, candidate_seconds = (
                    _predict_residual_correction(
                        train,
                        test,
                        [*numeric, *additional],
                        categorical,
                        reference_spec,
                        seed,
                        residual_shrinkage,
                    )
                )
                model_id = f"{config['candidate_model_prefix']}_{kind}_{topology}"
                predicted = _prediction_frame(
                    test,
                    model_id,
                    str(kind),
                    topology,
                    before_shift,
                    residual_prediction,
                    national_shift,
                    entity_shrinkage,
                )
                prediction_rows.append(predicted)
                metric_rows.append(
                    _metric_row(
                        predicted,
                        float(baseline.loc[evaluation_year]),
                        reference_mae,
                    )
                )
                registry_rows.append(
                    {
                        "target_year": evaluation_year,
                        "model_id": model_id,
                        "candidate_kind": kind,
                        "topology": topology,
                        "k": k,
                        "training_target_years": "|".join(map(str, train_years)),
                        "training_units": len(train),
                        "base_numeric_features": len(numeric),
                        "additional_features": len(additional),
                        "additional_feature_names": "|".join(additional),
                        "encoder_dimensions": len(embedding_columns),
                        "encoder_uses_target_labels": False,
                        "encoder_uses_own_node_features": False,
                        "encoder_best_epoch": diagnostics["best_epoch"],
                        "encoder_validation_loss": diagnostics[
                            "best_validation_reconstruction_loss"
                        ],
                        "encoder_fit_seconds": encoder_seconds,
                        "tabular_fit_seconds": candidate_seconds,
                        "encoder_model_sha256": _sha256(state_path),
                        "torch_version": torch.__version__,
                        "sklearn_version": sklearn.__version__,
                    }
                )

    predictions = pd.concat(prediction_rows, ignore_index=True)
    metrics = pd.DataFrame(metric_rows).sort_values(
        ["target_year", "identified_weighted_mae"]
    )
    registry = pd.DataFrame(registry_rows)
    graph_registry = pd.DataFrame(graph_registry_rows)
    outputs = config["outputs"]
    predictions.to_parquet(project_root / str(outputs["predictions"]), index=False)
    metrics.to_csv(project_root / str(outputs["metrics"]), index=False)
    registry.to_csv(project_root / str(outputs["registry"]), index=False)
    graph_registry.to_csv(project_root / str(outputs["graph_registry"]), index=False)
    decision = write_sociodemographic_similarity_decision(project_root, metrics)
    return predictions, metrics, registry, graph_registry, decision


def _candidate_gate(
    metrics: pd.DataFrame,
    candidate_id: str,
    reference_id: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    primary_year = int(config["primary_target_year"])
    primary = metrics[metrics["target_year"].eq(primary_year)]
    reference = primary[primary["model_id"].eq(reference_id)].iloc[0]
    candidate = primary[primary["model_id"].eq(candidate_id)].iloc[0]
    improvement = float(
        reference["identified_weighted_mae"] - candidate["identified_weighted_mae"]
    )
    robustness = []
    for year in map(int, config["evaluation_targets"]):
        if year == primary_year:
            continue
        row = metrics[
            metrics["target_year"].eq(year) & metrics["model_id"].eq(candidate_id)
        ].iloc[0]
        change = float(row["mae_change_vs_reference"])
        robustness.append(
            {
                "target_year": year,
                "mae_change_vs_reference": change,
                "passes": change
                <= float(config["maximum_other_fold_weighted_mae_deterioration"]),
            }
        )
    return {
        "model_id": candidate_id,
        "primary_improvement": improvement,
        "robustness": robustness,
        "passes": improvement > 0 and all(row["passes"] for row in robustness),
    }


def write_sociodemographic_similarity_decision(
    project_root: Path, metrics: pd.DataFrame
) -> dict[str, Any]:
    config = _load_yaml(
        project_root / "configs/sociodemographic_similarity_challenger.yaml"
    )
    reference_id = str(config["reference_model"])
    primary_year = int(config["primary_target_year"])
    primary_candidates = metrics[
        metrics["target_year"].eq(primary_year)
        & ~metrics["model_id"].eq(reference_id)
    ].sort_values("identified_weighted_mae")
    best_id = str(primary_candidates.iloc[0]["model_id"])
    best_gate = _candidate_gate(metrics, best_id, reference_id, config)
    explicit = primary_candidates[primary_candidates["candidate_kind"].eq("explicit")].iloc[0]
    embedding_candidates = primary_candidates[
        primary_candidates["candidate_kind"].isin(["embedding", "combined"])
    ]
    embedding = embedding_candidates.iloc[0]
    explicit_id = str(explicit["model_id"])
    embedding_id = str(embedding["model_id"])
    explicit_gate = _candidate_gate(metrics, explicit_id, reference_id, config)
    embedding_gate = _candidate_gate(metrics, embedding_id, reference_id, config)
    embedding_incremental_improvement = float(
        explicit["identified_weighted_mae"] - embedding["identified_weighted_mae"]
    )
    embedding_promoted = bool(
        embedding_gate["passes"] and embedding_incremental_improvement > 0
    )
    selected = best_id if best_gate["passes"] else reference_id
    decision = {
        "objective": config["objective"],
        "reference_model": reference_id,
        "feature_group_held_constant": config["feature_group"],
        "entity_cycle_shrinkage_held_constant": float(
            config["expected_entity_cycle_shrinkage"]
        ),
        "topology_uses_outcome": False,
        "similarity_features": config["similarity_features"],
        "best_candidate": best_id,
        "best_candidate_gate": best_gate,
        "best_explicit_candidate": explicit_id,
        "explicit_gate": explicit_gate,
        "best_embedding_candidate": embedding_id,
        "embedding_gate": embedding_gate,
        "embedding_incremental_improvement_vs_best_explicit": (
            embedding_incremental_improvement
        ),
        "embedding_promoted": embedding_promoted,
        "selected_model_for_next_iteration": selected,
        "candidate_promoted": bool(best_gate["passes"]),
        "limitations": [
            "Only three strict out-of-time target elections are available.",
            "The topology uses lagged CCPC sex-age composition, not ECEG, so all folds remain valid.",
            "Edges represent statistical similarity and must not be interpreted as geographic adjacency.",
            "The encoder is label-free and its embedding is evaluated only as an additional tabular signal.",
        ],
    }
    (project_root / str(config["outputs"]["decision"])).write_text(
        json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return decision
