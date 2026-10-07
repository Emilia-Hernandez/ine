from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from radar27.modeling.feature_enrichment import _resolve_feature_group


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def _direct_stable_rows(mart: pd.DataFrame, year: int) -> pd.DataFrame:
    rows = mart[
        mart["target_year"].eq(year)
        & mart["geography_confidence_class"].eq("A")
        & mart["evaluation_unit_id"].str.startswith("S:")
    ].copy()
    rows["section_key"] = rows["evaluation_unit_id"].str.removeprefix("S:")
    if rows["section_key"].duplicated().any():
        raise ValueError(f"Llaves estables duplicadas en el mart {year}")
    return rows


def _categorical_matrix(
    frame: pd.DataFrame,
    categorical: list[str],
    levels: dict[str, list[str]],
) -> tuple[np.ndarray, list[str]]:
    arrays = []
    names = []
    for column in categorical:
        configured = [str(value) for value in levels[column]]
        values = frame[column].fillna("unknown").astype(str)
        unknown = sorted(set(values) - set(configured))
        if unknown:
            raise ValueError(f"Categorias no configuradas para {column}: {unknown}")
        for level in configured:
            arrays.append(values.eq(level).to_numpy(dtype=np.float32))
            names.append(f"{column}={level}")
    return np.column_stack(arrays).astype(np.float32), names


def _induced_edges(edges: pd.DataFrame, node_map: dict[str, int], include_synthetic: bool) -> np.ndarray:
    selected = edges[
        edges["source_section_key"].isin(node_map)
        & edges["target_section_key"].isin(node_map)
    ].copy()
    if not include_synthetic:
        selected = selected[~selected["is_synthetic"]]
    source = selected["source_section_key"].map(node_map).to_numpy(dtype=np.int64)
    target = selected["target_section_key"].map(node_map).to_numpy(dtype=np.int64)
    return np.vstack([np.concatenate([source, target]), np.concatenate([target, source])])


def _build_year_bundle(
    project_root: Path,
    config: dict[str, Any],
    mart: pd.DataFrame,
    year: int,
    numeric: list[str],
    categorical: list[str],
) -> dict[str, Any]:
    graph_root = project_root / config["inputs"]["temporal_graph_directory"] / str(year)
    graph_nodes = pd.read_parquet(graph_root / "nodes.parquet")
    graph_edges = pd.read_parquet(graph_root / "edges.parquet")
    features = _direct_stable_rows(mart, year)
    features = features.merge(
        graph_nodes[["node_id", "section_key", "degree", "component_id"]],
        on="section_key",
        how="inner",
        validate="one_to_one",
    ).sort_values("section_key").reset_index(drop=True)
    expected = len(_direct_stable_rows(mart, year))
    if len(features) != expected:
        raise ValueError(f"El grafo {year} no cubre todas las secciones estables A")
    features["dataset_node_id"] = np.arange(len(features), dtype=np.int64)
    node_map = dict(zip(features["section_key"], features["dataset_node_id"], strict=True))
    numeric_values = features[numeric].to_numpy(dtype=np.float32)
    numeric_missing = ~np.isfinite(numeric_values)
    categorical_values, categorical_names = _categorical_matrix(
        features, categorical, config["categorical_levels"]
    )
    labels = features["actual"].to_numpy(dtype=np.float32)
    weights = features["target_identified_records"].to_numpy(dtype=np.float32)
    labeled = np.isfinite(labels) & np.isfinite(weights) & (weights > 0)
    validation_entities = set(config["validation_entity_ids"])
    validation = labeled & features["entity_id"].isin(validation_entities).to_numpy()
    fit = labeled & ~validation
    rook_edges = _induced_edges(graph_edges, node_map, include_synthetic=False)
    augmented_edges = _induced_edges(graph_edges, node_map, include_synthetic=True)
    output = project_root / config["outputs"]["directory"]
    output.mkdir(parents=True, exist_ok=True)
    node_columns = [
        "dataset_node_id",
        "node_id",
        "section_key",
        "entity_id",
        "geography_confidence_class",
        "geography_unit_type",
        "target_year",
        "actual",
        "target_identified_records",
        "max_electoral_feature_year",
        "context_source_max_year",
        "degree",
        "component_id",
    ]
    node_table = features[node_columns].copy()
    node_table["labeled_mask"] = labeled
    node_table["fit_mask"] = fit
    node_table["validation_mask"] = validation
    node_table.to_parquet(output / f"nodes_{year}.parquet", index=False)
    feature_table = features[["section_key", *numeric, *categorical]].copy()
    feature_table.to_parquet(output / f"features_{year}.parquet", index=False)
    np.savez_compressed(
        output / f"graph_{year}.npz",
        x_numeric=numeric_values,
        x_numeric_missing=numeric_missing.astype(np.uint8),
        x_categorical=categorical_values,
        y=labels,
        sample_weight=weights,
        labeled_mask=labeled,
        fit_mask=fit,
        validation_mask=validation,
        edge_index_rook=rook_edges,
        edge_index_augmented=augmented_edges,
        section_keys=features["section_key"].to_numpy(dtype=str),
        numeric_feature_names=np.asarray(numeric, dtype=str),
        categorical_feature_names=np.asarray(categorical_names, dtype=str),
        target_year=np.asarray([year], dtype=np.int64),
    )
    return {
        "target_year": year,
        "nodes": len(features),
        "labeled_nodes": int(labeled.sum()),
        "fit_nodes": int(fit.sum()),
        "validation_nodes": int(validation.sum()),
        "rook_directed_edges": int(rook_edges.shape[1]),
        "augmented_directed_edges": int(augmented_edges.shape[1]),
        "max_electoral_feature_year": int(features["max_electoral_feature_year"].max()),
        "context_source_max_year": int(features["context_source_max_year"].max()),
    }


def _fold_preprocessing(
    project_root: Path,
    config: dict[str, Any],
    numeric: list[str],
) -> dict[str, Any]:
    output = project_root / config["outputs"]["directory"]
    arrays: dict[str, np.ndarray] = {}
    summary = {}
    for evaluation_year in config["evaluation_years"]:
        train_years = [year for year in config["target_years"] if year < evaluation_year]
        matrices = []
        for year in train_years:
            bundle = np.load(output / f"graph_{year}.npz")
            matrices.append(bundle["x_numeric"][bundle["fit_mask"]])
        train = np.vstack(matrices).astype(np.float64)
        median = np.nanmedian(train, axis=0)
        filled = np.where(np.isfinite(train), train, median)
        mean = filled.mean(axis=0)
        scale = filled.std(axis=0)
        scale[scale < 1e-8] = 1.0
        prefix = f"fold_{evaluation_year}"
        arrays[f"{prefix}_median"] = median.astype(np.float32)
        arrays[f"{prefix}_mean"] = mean.astype(np.float32)
        arrays[f"{prefix}_scale"] = scale.astype(np.float32)
        arrays[f"{prefix}_train_years"] = np.asarray(train_years, dtype=np.int64)
        summary[str(evaluation_year)] = {
            "train_years": train_years,
            "preprocessing_fit_nodes": len(train),
            "numeric_features": len(numeric),
        }
    arrays["numeric_feature_names"] = np.asarray(numeric, dtype=str)
    np.savez_compressed(output / config["outputs"]["fold_preprocessing"], **arrays)
    return summary


def build_gnn_dataset(project_root: Path) -> dict[str, Any]:
    config = _load_yaml(project_root / "configs/gnn_dataset.yaml")
    feature_config = _load_yaml(project_root / "configs/feature_ablation.yaml")
    numeric, categorical = _resolve_feature_group(feature_config, config["feature_group"])
    mart = pd.read_parquet(project_root / config["inputs"]["feature_mart"])
    missing = set(numeric + categorical) - set(mart.columns)
    if missing:
        raise ValueError(f"Faltan variables del mart: {sorted(missing)}")
    years = {
        str(year): _build_year_bundle(
            project_root, config, mart, int(year), numeric, categorical
        )
        for year in config["target_years"]
    }
    for year, result in years.items():
        if result["max_electoral_feature_year"] >= int(year):
            raise ValueError(f"Fuga electoral detectada en {year}")
        if result["context_source_max_year"] >= int(year):
            raise ValueError(f"Fuga de contexto detectada en {year}")
    folds = _fold_preprocessing(project_root, config, numeric)
    metadata = {
        "feature_group": config["feature_group"],
        "geography_scope": config["geography_scope"],
        "target": "voted / (voted + did_not_vote)",
        "numeric_features": numeric,
        "categorical_features": categorical,
        "validation_entity_ids": config["validation_entity_ids"],
        "year_bundles": years,
        "evaluation_folds": folds,
        "preprocessing_rule": (
            "Median imputation and standardization are fit only on fit_mask nodes from "
            "target years strictly earlier than the evaluation year."
        ),
        "topology_rule": (
            "Each target uses its own pre-election INE snapshot; class A stable sections form "
            "an induced graph. No future geometry is backfilled."
        ),
    }
    output = project_root / config["outputs"]["directory"]
    with (output / config["outputs"]["metadata"]).open("w", encoding="utf-8") as stream:
        json.dump(metadata, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    return metadata
