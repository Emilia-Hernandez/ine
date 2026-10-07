from __future__ import annotations

import copy
import hashlib
import json
import random
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
import torch
from torch import nn

from radar27.modeling.feature_enrichment import _resolve_feature_group
from radar27.modeling.feature_models import _load_yaml
from radar27.modeling.tabular_challengers import _predict_residual_correction


class GraphSAGELayer(nn.Module):
    def __init__(self, input_dim: int, output_dim: int) -> None:
        super().__init__()
        self.self_linear = nn.Linear(input_dim, output_dim)
        self.neighbor_linear = nn.Linear(input_dim, output_dim, bias=False)

    def forward(self, values: torch.Tensor, adjacency: torch.Tensor) -> torch.Tensor:
        neighbors = torch.sparse.mm(adjacency, values)
        return self.self_linear(values) + self.neighbor_linear(neighbors)


class GraphSAGEDenoisingAutoencoder(nn.Module):
    def __init__(
        self,
        input_dim: int,
        hidden_dim: int,
        embedding_dim: int,
        input_dropout: float,
        hidden_dropout: float,
    ) -> None:
        super().__init__()
        self.input_dropout = nn.Dropout(input_dropout)
        self.hidden_dropout = nn.Dropout(hidden_dropout)
        self.layer_one = GraphSAGELayer(input_dim, hidden_dim)
        self.layer_two = GraphSAGELayer(hidden_dim, embedding_dim)
        self.decoder = nn.Sequential(
            nn.Linear(embedding_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, input_dim),
        )

    def encode(self, values: torch.Tensor, adjacency: torch.Tensor) -> torch.Tensor:
        hidden = torch.relu(self.layer_one(self.input_dropout(values), adjacency))
        hidden = self.hidden_dropout(hidden)
        return self.layer_two(hidden, adjacency)

    def forward(
        self, values: torch.Tensor, adjacency: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        embedding = self.encode(values, adjacency)
        return embedding, self.decoder(embedding)


class NeighborOnlyDenoisingAutoencoder(nn.Module):
    """Encode one-hop neighbor means without any path from a node to itself."""

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int,
        embedding_dim: int,
        input_dropout: float,
        hidden_dropout: float,
    ) -> None:
        super().__init__()
        self.input_dropout = nn.Dropout(input_dropout)
        self.hidden_dropout = nn.Dropout(hidden_dropout)
        self.neighbor_projection = nn.Linear(input_dim, hidden_dim, bias=False)
        self.embedding_projection = nn.Linear(hidden_dim, embedding_dim, bias=False)
        self.decoder = nn.Sequential(
            nn.Linear(embedding_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, input_dim),
        )

    def encode(self, values: torch.Tensor, adjacency: torch.Tensor) -> torch.Tensor:
        neighbor_mean = torch.sparse.mm(adjacency, self.input_dropout(values))
        hidden = torch.relu(self.neighbor_projection(neighbor_mean))
        return self.embedding_projection(self.hidden_dropout(hidden))

    def forward(
        self, values: torch.Tensor, adjacency: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        embedding = self.encode(values, adjacency)
        return embedding, self.decoder(embedding)


EmbeddingAutoencoder = GraphSAGEDenoisingAutoencoder | NeighborOnlyDenoisingAutoencoder


def _seed_everything(seed: int, threads: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(threads)


def _normalized_adjacency(edge_index: np.ndarray, nodes: int) -> torch.Tensor:
    source = edge_index[0].astype(np.int64, copy=False)
    degree = np.bincount(source, minlength=nodes).astype(np.float32)
    weights = (1.0 / degree[source]).astype(np.float32)
    indices = torch.from_numpy(edge_index.astype(np.int64, copy=False))
    adjacency = torch.sparse_coo_tensor(
        indices,
        torch.from_numpy(weights),
        size=(nodes, nodes),
        dtype=torch.float32,
        check_invariants=False,
    )
    return adjacency.coalesce()


def _fold_input(
    bundle: np.lib.npyio.NpzFile,
    preprocessing: np.lib.npyio.NpzFile,
    evaluation_year: int,
) -> np.ndarray:
    prefix = f"fold_{evaluation_year}"
    raw = bundle["x_numeric"].astype(np.float32)
    missing = bundle["x_numeric_missing"].astype(np.float32)
    median = preprocessing[f"{prefix}_median"].astype(np.float32)
    mean = preprocessing[f"{prefix}_mean"].astype(np.float32)
    scale = preprocessing[f"{prefix}_scale"].astype(np.float32)
    filled = np.where(np.isfinite(raw), raw, median)
    standardized = np.clip((filled - mean) / scale, -10.0, 10.0)
    categorical = bundle["x_categorical"].astype(np.float32)
    return np.concatenate([standardized, missing, categorical], axis=1).astype(np.float32)


def _load_fold_graphs(
    project_root: Path,
    evaluation_year: int,
    train_years: list[int],
    topology_key: str,
) -> dict[int, dict[str, Any]]:
    dataset_root = project_root / "artifacts/gnn_dataset"
    preprocessing = np.load(dataset_root / "gnn_fold_preprocessing.npz")
    dataset_config = _load_yaml(project_root / "configs/gnn_dataset.yaml")
    validation_entities = set(map(str, dataset_config["validation_entity_ids"]))
    graphs: dict[int, dict[str, Any]] = {}
    for year in [*train_years, evaluation_year]:
        bundle = np.load(dataset_root / f"graph_{year}.npz")
        values = _fold_input(bundle, preprocessing, evaluation_year)
        node_table = pd.read_parquet(
            dataset_root / f"nodes_{year}.parquet",
            columns=["section_key", "entity_id"],
        )
        if not np.array_equal(
            bundle["section_keys"].astype(str), node_table["section_key"].to_numpy(dtype=str)
        ):
            raise ValueError("El orden de nodos no coincide entre NPZ y Parquet")
        validation = node_table["entity_id"].astype(str).isin(validation_entities).to_numpy()
        graphs[year] = {
            "values": torch.from_numpy(values),
            "adjacency": _normalized_adjacency(bundle[topology_key], len(values)),
            "fit_mask": torch.from_numpy(~validation),
            "validation_mask": torch.from_numpy(validation),
            "section_keys": bundle["section_keys"].astype(str),
        }
    return graphs


def _masked_reconstruction_loss(
    reconstructed: torch.Tensor, target: torch.Tensor, mask: torch.Tensor
) -> torch.Tensor:
    return torch.nn.functional.smooth_l1_loss(
        reconstructed[mask], target[mask], reduction="mean", beta=0.5
    )


def _validation_loss(
    model: EmbeddingAutoencoder,
    graphs: dict[int, dict[str, Any]],
    train_years: list[int],
) -> float:
    model.eval()
    losses = []
    with torch.no_grad():
        for year in train_years:
            graph = graphs[year]
            _, reconstructed = model(graph["values"], graph["adjacency"])
            mask = graph["validation_mask"]
            losses.append(float(_masked_reconstruction_loss(reconstructed, graph["values"], mask)))
    return float(np.mean(losses))


def _fit_encoder(
    graphs: dict[int, dict[str, Any]],
    train_years: list[int],
    encoder_config: dict[str, Any],
    seed: int,
) -> tuple[EmbeddingAutoencoder, dict[str, float | int]]:
    _seed_everything(seed, int(encoder_config["torch_threads"]))
    input_dim = int(graphs[train_years[0]]["values"].shape[1])
    model_class: type[EmbeddingAutoencoder]
    if encoder_config["family"] == "graphsage_denoising_autoencoder":
        model_class = GraphSAGEDenoisingAutoencoder
    elif encoder_config["family"] == "neighbor_only_denoising_autoencoder":
        model_class = NeighborOnlyDenoisingAutoencoder
    else:
        raise ValueError(f"Familia de encoder no soportada: {encoder_config['family']}")
    model = model_class(
        input_dim=input_dim,
        hidden_dim=int(encoder_config["hidden_dim"]),
        embedding_dim=int(encoder_config["embedding_dim"]),
        input_dropout=float(encoder_config["input_dropout"]),
        hidden_dropout=float(encoder_config["hidden_dropout"]),
    )
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(encoder_config["learning_rate"]),
        weight_decay=float(encoder_config["weight_decay"]),
    )
    best_state: dict[str, torch.Tensor] | None = None
    best_loss = float("inf")
    best_epoch = 0
    stale_epochs = 0
    started = time.perf_counter()
    maximum_epochs = int(encoder_config["maximum_epochs"])
    for epoch in range(1, maximum_epochs + 1):
        model.train()
        for year in train_years:
            graph = graphs[year]
            optimizer.zero_grad(set_to_none=True)
            _, reconstructed = model(graph["values"], graph["adjacency"])
            loss = _masked_reconstruction_loss(
                reconstructed, graph["values"], graph["fit_mask"]
            )
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                model.parameters(), float(encoder_config["gradient_clip_norm"])
            )
            optimizer.step()
        validation_loss = _validation_loss(model, graphs, train_years)
        if validation_loss < best_loss - float(encoder_config["minimum_delta"]):
            best_loss = validation_loss
            best_epoch = epoch
            best_state = copy.deepcopy(model.state_dict())
            stale_epochs = 0
        else:
            stale_epochs += 1
            if stale_epochs >= int(encoder_config["patience"]):
                break
    if best_state is None:
        raise RuntimeError("El encoder no produjo un estado valido")
    model.load_state_dict(best_state)
    return model, {
        "best_epoch": best_epoch,
        "epochs_run": epoch,
        "best_validation_reconstruction_loss": best_loss,
        "encoder_fit_seconds": time.perf_counter() - started,
        "input_dim": input_dim,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _export_embeddings(
    project_root: Path,
    evaluation_year: int,
    topology: str,
    model: EmbeddingAutoencoder,
    graphs: dict[int, dict[str, Any]],
    config: dict[str, Any],
) -> tuple[dict[int, pd.DataFrame], Path]:
    output = project_root / config["outputs"]["embedding_directory"]
    output.mkdir(parents=True, exist_ok=True)
    frames: dict[int, pd.DataFrame] = {}
    model.eval()
    with torch.no_grad():
        for graph_year, graph in graphs.items():
            embedding = model.encode(graph["values"], graph["adjacency"]).numpy()
            columns = [f"graph_embedding_{index:02d}" for index in range(embedding.shape[1])]
            frame = pd.DataFrame(embedding, columns=columns)
            frame.insert(0, "section_key", graph["section_keys"])
            frame.insert(0, "graph_year", graph_year)
            frame.insert(0, "evaluation_year", evaluation_year)
            frame.insert(0, "topology", topology)
            frames[graph_year] = frame
        combined = pd.concat(frames.values(), ignore_index=True)
        path = output / f"embeddings_fold_{evaluation_year}_{topology}.parquet"
        combined.to_parquet(path, index=False)
    return frames, path


def _load_model_frame(project_root: Path, year: int) -> pd.DataFrame:
    root = project_root / "artifacts/gnn_dataset"
    nodes = pd.read_parquet(root / f"nodes_{year}.parquet")[
        [
            "section_key",
            "target_year",
            "actual",
            "target_identified_records",
            "geography_confidence_class",
        ]
    ]
    features = pd.read_parquet(root / f"features_{year}.parquet")
    frame = nodes.merge(features, on="section_key", how="inner", validate="one_to_one")
    frame["evaluation_unit_id"] = "S:" + frame["section_key"]
    frame["target_sections_represented"] = 1
    return frame


def _metric_row(
    predicted: pd.DataFrame,
    model_id: str,
    baseline_mae: float,
    reference_mae: float | None,
) -> dict[str, Any]:
    valid = predicted.dropna(subset=["actual", "prediction"]).copy()
    weights = valid["target_identified_records"].astype(float)
    error = valid["prediction"] - valid["actual"]
    weighted_mae = float(np.average(error.abs(), weights=weights))
    return {
        "target_year": int(valid["target_year"].iloc[0]),
        "model_id": model_id,
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


def _prediction_frame(
    test: pd.DataFrame,
    model_id: str,
    before_shift: np.ndarray,
    residual_prediction: np.ndarray,
    correction: float,
) -> pd.DataFrame:
    predicted = test[
        [
            "target_year",
            "evaluation_unit_id",
            "section_key",
            "entity_id",
            "geography_confidence_class",
            "target_sections_represented",
            "target_identified_records",
            "actual",
            "participation_same_type",
        ]
    ].copy()
    predicted["model_id"] = model_id
    predicted["model_prediction_before_national_shift"] = before_shift
    predicted["predicted_residual_unshrunk"] = residual_prediction
    predicted["national_shift_correction"] = correction
    predicted["prediction"] = np.clip(before_shift + correction, 0.0, 1.0)
    return predicted


def run_graph_embedding_challenger(
    project_root: Path,
    config_path: str | Path = "configs/graph_embedding_challenger.yaml",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    config = _load_yaml(project_root / config_path)
    feature_config = _load_yaml(project_root / str(config["feature_config"]))
    reference_config = _load_yaml(project_root / str(config["reference_model_config"]))
    numeric, categorical = _resolve_feature_group(feature_config, config["feature_group"])
    reference_spec = reference_config["models"]["hist_gradient_boosting"]
    preprocessing = np.load(
        project_root / "artifacts/gnn_dataset/gnn_fold_preprocessing.npz"
    )
    shift = pd.read_csv(
        project_root / "artifacts/tables/national_shift_estimates.csv"
    ).set_index("target_year")["national_shift_correction"]
    frames = {
        year: _load_model_frame(project_root, year)
        for year in sorted(
            set(config["evaluation_targets"]) | set(preprocessing["fold_2024_train_years"])
        )
    }
    seed = int(config["random_seed"])
    shrinkage = float(config["residual_shrinkage"])
    prediction_rows: list[pd.DataFrame] = []
    metric_rows: list[dict[str, Any]] = []
    registry_rows: list[dict[str, Any]] = []
    model_directory = project_root / config["outputs"]["model_directory"]
    model_directory.mkdir(parents=True, exist_ok=True)

    for evaluation_year in config["evaluation_targets"]:
        train_years = preprocessing[f"fold_{evaluation_year}_train_years"].astype(int).tolist()
        train_reference = pd.concat([frames[year] for year in train_years], ignore_index=True)
        train_reference = train_reference[train_reference["actual"].notna()].copy()
        test_reference = frames[evaluation_year].copy()
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
            reference_prediction,
            config["reference_model"],
            baseline_mae,
            None,
        )
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
                "numeric_feature_count": len(numeric),
                "embedding_dimensions": 0,
                "embedding_uses_target_labels": False,
                "encoder_best_epoch": np.nan,
                "encoder_validation_loss": np.nan,
                "encoder_fit_seconds": 0.0,
                "tabular_fit_seconds": fit_seconds,
                "encoder_model_sha256": "",
            }
        )

        for topology, topology_key in config["topologies"].items():
            graphs = _load_fold_graphs(
                project_root, evaluation_year, train_years, topology_key
            )
            model, diagnostics = _fit_encoder(
                graphs,
                train_years,
                config["encoder"],
                seed,
            )
            embedding_frames, embedding_path = _export_embeddings(
                project_root, evaluation_year, topology, model, graphs, config
            )
            state_path = model_directory / (
                f"{config['encoder']['family']}_fold_{evaluation_year}_{topology}.pt"
            )
            torch.save(model.state_dict(), state_path)
            embedding_columns = [
                f"graph_embedding_{index:02d}"
                for index in range(int(config["encoder"]["embedding_dim"]))
            ]
            train_parts = []
            for year in train_years:
                train_parts.append(
                    frames[year].merge(
                        embedding_frames[year][["section_key", *embedding_columns]],
                        on="section_key",
                        validate="one_to_one",
                    )
                )
            train = pd.concat(train_parts, ignore_index=True)
            train = train[train["actual"].notna()].copy()
            test = frames[evaluation_year].merge(
                embedding_frames[evaluation_year][["section_key", *embedding_columns]],
                on="section_key",
                validate="one_to_one",
            )
            before_shift, residual_prediction, tabular_seconds = _predict_residual_correction(
                train,
                test,
                [*numeric, *embedding_columns],
                categorical,
                reference_spec,
                seed,
                shrinkage,
            )
            model_id = f"{config['candidate_model_prefix']}_{topology}"
            predicted = _prediction_frame(
                test,
                model_id,
                before_shift,
                residual_prediction,
                correction,
            )
            prediction_rows.append(predicted)
            metric_rows.append(
                _metric_row(predicted, model_id, baseline_mae, reference_mae)
            )
            registry_rows.append(
                {
                    "target_year": evaluation_year,
                    "model_id": model_id,
                    "topology": topology,
                    "training_target_years": "|".join(map(str, train_years)),
                    "training_units": len(train),
                    "numeric_feature_count": len(numeric) + len(embedding_columns),
                    "embedding_dimensions": len(embedding_columns),
                    "embedding_uses_target_labels": False,
                    "encoder_uses_own_node_features": bool(
                        config["encoder"]["uses_own_node_features"]
                    ),
                    "encoder_best_epoch": diagnostics["best_epoch"],
                    "encoder_validation_loss": diagnostics[
                        "best_validation_reconstruction_loss"
                    ],
                    "encoder_fit_seconds": diagnostics["encoder_fit_seconds"],
                    "tabular_fit_seconds": tabular_seconds,
                    "encoder_model_sha256": _sha256(state_path),
                    "embedding_artifact": str(embedding_path.relative_to(project_root)),
                    "torch_version": torch.__version__,
                    "sklearn_version": sklearn.__version__,
                }
            )

    predictions = pd.concat(prediction_rows, ignore_index=True)
    metrics = pd.DataFrame(metric_rows).sort_values(["target_year", "identified_weighted_mae"])
    registry = pd.DataFrame(registry_rows)
    outputs = config["outputs"]
    predictions.to_parquet(project_root / outputs["predictions"], index=False)
    metrics.to_csv(project_root / outputs["metrics"], index=False)
    registry.to_csv(project_root / outputs["registry"], index=False)
    decision = write_graph_embedding_decision(project_root, metrics, config_path)
    return predictions, metrics, registry, decision


def write_graph_embedding_decision(
    project_root: Path,
    metrics: pd.DataFrame,
    config_path: str | Path = "configs/graph_embedding_challenger.yaml",
) -> dict[str, Any]:
    config = _load_yaml(project_root / config_path)
    primary_year = int(config["primary_target_year"])
    reference_id = str(config["reference_model"])
    primary = metrics[metrics["target_year"].eq(primary_year)]
    reference_primary = primary[primary["model_id"].eq(reference_id)].iloc[0]
    candidate = primary[~primary["model_id"].eq(reference_id)].sort_values(
        "identified_weighted_mae"
    ).iloc[0]
    candidate_id = str(candidate["model_id"])
    improvement = float(
        reference_primary["identified_weighted_mae"] - candidate["identified_weighted_mae"]
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
    promoted = bool(improvement > 0 and all(item["passes"] for item in robustness))
    decision = {
        "objective": config["objective"],
        "embedding_role": "additional_features_for_hist_gradient_boosting",
        "embedding_is_standalone_predictor": False,
        "embedding_uses_outcome_labels": False,
        "encoder_uses_own_node_features": bool(
            config["encoder"]["uses_own_node_features"]
        ),
        "reference_model": reference_id,
        "best_embedding_candidate": candidate_id,
        "primary_target_year": primary_year,
        "reference_primary_weighted_mae": float(
            reference_primary["identified_weighted_mae"]
        ),
        "candidate_primary_weighted_mae": float(candidate["identified_weighted_mae"]),
        "primary_improvement": improvement,
        "robustness": robustness,
        "embedding_promoted": promoted,
        "selected_model_for_next_iteration": candidate_id if promoted else reference_id,
        "encoder": config["encoder"],
        "limitations": [
            "Only three strict out-of-time target elections are available.",
            "The encoder is label-free and reconstructs known inputs; it does not optimize turnout directly.",
            "Historical coverage is incomplete for a small share of 2018 and 2021 sections.",
        ],
    }
    (project_root / config["outputs"]["decision"]).write_text(
        json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return decision
