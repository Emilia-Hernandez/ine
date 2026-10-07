from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from radar27.modeling.feature_models import _load_yaml

COMPETITION_FEATURES = [
    "prior_competition_margin",
    "prior_winner_vote_share",
    "prior_runner_up_vote_share",
    "prior_competition_hhi",
    "prior_effective_number_options",
    "prior_top_two_vote_share",
    "prior_competitive_option_count",
    "prior_competition_coverage",
]

CONCURRENCY_FEATURES = [
    "local_election_concurrent",
    "local_executive_on_ballot",
    "local_congress_on_ballot",
    "municipal_on_ballot",
    "local_ballot_type_count",
]

ENTITY_CYCLE_FEATURES = [
    "entity_same_family_turnout_recent",
    "entity_same_family_turnout_previous",
    "entity_same_family_turnout_change",
    "national_same_family_turnout_change",
    "entity_same_family_change_minus_national",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _archive_member(archive: zipfile.ZipFile, suffix: str) -> str:
    matches = [name for name in archive.namelist() if name.endswith(suffix)]
    if len(matches) != 1:
        raise ValueError(f"Se esperaba un miembro terminado en {suffix}; encontrados={matches}")
    return matches[0]


def _candidate_columns(raw: pd.DataFrame, source: dict[str, Any]) -> list[str]:
    columns = list(source["vote_columns"])
    for prefix in source.get("candidate_prefixes", []):
        columns.extend(column for column in raw.columns if column.startswith(str(prefix)))
    columns = list(dict.fromkeys(columns))
    missing = set(columns) - set(raw.columns)
    if missing:
        raise ValueError(f"Columnas de voto ausentes: {sorted(missing)}")
    return columns


def consolidate_candidate_votes(
    raw: pd.DataFrame, source: dict[str, Any]
) -> tuple[pd.DataFrame, list[str]]:
    """Consolidate split coalition marks into district-specific candidacies."""
    vote_columns = _candidate_columns(raw, source)
    numeric = raw[vote_columns].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    if numeric.lt(0).any().any():
        raise ValueError("La base de resultados contiene votos negativos")
    result = numeric.copy()
    district = source["district_column"]
    if district not in raw:
        raise ValueError(f"No existe la columna distrital {district}")
    for alliance in source.get("alliances", []):
        members = list(alliance["members"])
        joint = list(alliance["joint_columns"])
        required = members + joint
        missing = set(required) - set(result.columns)
        if missing:
            raise ValueError(
                f"Columnas ausentes para la coalicion {alliance['name']}: {sorted(missing)}"
            )
        district_joint_votes = result[joint].sum(axis=1).groupby(raw[district]).transform("sum")
        active = district_joint_votes.gt(0)
        consolidated = result[required].sum(axis=1).where(active, 0.0)
        result[f"alliance__{alliance['name']}"] = consolidated
        result.loc[active, members + joint] = 0.0
    option_columns = [column for column in result if result[column].gt(0).any()]
    original_total = numeric.sum(axis=1)
    consolidated_total = result[option_columns].sum(axis=1)
    if not np.allclose(original_total, consolidated_total, atol=0.0):
        raise ValueError("La consolidacion de coaliciones no conserva los votos")
    identifiers = raw[["ID_ESTADO", "SECCION"]].copy()
    identifiers["entity_id"] = pd.to_numeric(
        identifiers["ID_ESTADO"], errors="coerce"
    ).astype("Int64")
    identifiers["section_number"] = pd.to_numeric(
        identifiers["SECCION"], errors="coerce"
    ).astype("Int64")
    valid_section = identifiers["entity_id"].between(1, 32) & identifiers[
        "section_number"
    ].gt(0)
    identifiers = identifiers.loc[valid_section].copy()
    identifiers["section_key_observed"] = (
        identifiers["entity_id"].astype(int).astype(str).str.zfill(2)
        + ":"
        + identifiers["section_number"].astype(int).astype(str).str.zfill(4)
    )
    result = pd.concat(
        [identifiers[["section_key_observed"]], result.loc[valid_section, option_columns]],
        axis=1,
    )
    if result["section_key_observed"].duplicated().any():
        raise ValueError("La base SICEE contiene secciones duplicadas")
    return result, option_columns


def load_competition_source(
    project_root: Path, source_year: int, config: dict[str, Any] | None = None
) -> tuple[pd.DataFrame, list[str]]:
    config = config or _load_yaml(project_root / "configs/electoral_context.yaml")
    source = config["competition_sources"][int(source_year)]
    archive_path = project_root / str(source["archive_path"])
    if not archive_path.exists():
        raise FileNotFoundError(
            f"Falta la base oficial SICEE {archive_path}; consulte {source['url']}"
        )
    observed_hash = _sha256(archive_path)
    if observed_hash != str(source["sha256"]):
        raise ValueError(
            f"SHA-256 inesperado para {archive_path.name}: {observed_hash}"
        )
    with zipfile.ZipFile(archive_path) as archive:
        member = _archive_member(archive, str(source["member_suffix"]))
        with archive.open(member) as stream:
            raw = pd.read_csv(stream, low_memory=False)
    return consolidate_candidate_votes(raw, source)


def load_entity_turnout_source(
    project_root: Path, source_year: int, config: dict[str, Any] | None = None
) -> pd.DataFrame:
    """Load territorial entity turnout, excluding overseas-vote aggregates."""
    config = config or _load_yaml(project_root / "configs/electoral_context.yaml")
    source = config["turnout_sources"][int(source_year)]
    archive_path = project_root / str(source["archive_path"])
    if not archive_path.exists():
        raise FileNotFoundError(
            f"Falta la base oficial SICEE {archive_path}; consulte {source['url']}"
        )
    observed_hash = _sha256(archive_path)
    if observed_hash != str(source["sha256"]):
        raise ValueError(
            f"SHA-256 inesperado para {archive_path.name}: {observed_hash}"
        )
    with zipfile.ZipFile(archive_path) as archive:
        member = _archive_member(archive, str(source["member_suffix"]))
        with archive.open(member) as stream:
            raw = pd.read_csv(stream, low_memory=False)
    required = {"ID_ESTADO", "SECCIONES", "TOTAL_VOTOS", "LISTA_NOMINAL"}
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"Columnas de participacion ausentes: {sorted(missing)}")
    result = raw[list(required)].copy()
    result["entity_number"] = pd.to_numeric(result["ID_ESTADO"], errors="coerce")
    result["sections"] = pd.to_numeric(result["SECCIONES"], errors="coerce")
    result["total_votes"] = pd.to_numeric(result["TOTAL_VOTOS"], errors="coerce")
    result["nominal_list"] = pd.to_numeric(result["LISTA_NOMINAL"], errors="coerce")
    result = result[
        result["entity_number"].between(1, 32)
        & result["sections"].gt(0)
        & result["total_votes"].ge(0)
        & result["nominal_list"].gt(0)
    ].copy()
    if len(result) != 32 or result["entity_number"].duplicated().any():
        raise ValueError(
            f"La fuente {source_year} no tiene un agregado territorial unico por entidad"
        )
    result["entity_id"] = result["entity_number"].astype(int).astype(str).str.zfill(2)
    result["turnout"] = result["total_votes"].div(result["nominal_list"])
    if not result["turnout"].between(0, 1).all():
        raise ValueError(f"Participacion estatal fuera de rango en {source_year}")
    return result[["entity_id", "total_votes", "nominal_list", "turnout"]].sort_values(
        "entity_id"
    )


def build_entity_cycle_table(
    project_root: Path,
    config: dict[str, Any],
    target_years: list[int] | None = None,
) -> pd.DataFrame:
    """Build prior same-family entity swings for each forecast origin."""
    target_years = target_years or sorted(
        int(year) for year in config["target_turnout_sources"]
    )
    cache: dict[int, pd.DataFrame] = {}
    rows: list[pd.DataFrame] = []
    for target_year in target_years:
        mapping = config["target_turnout_sources"][int(target_year)]
        recent_year = int(mapping["recent"])
        previous_year = int(mapping["previous"])
        if not previous_year < recent_year < int(target_year):
            raise ValueError(
                f"Fuentes temporales invalidas para el ciclo estatal {target_year}"
            )
        if recent_year not in cache:
            cache[recent_year] = load_entity_turnout_source(
                project_root, recent_year, config
            )
        if previous_year not in cache:
            cache[previous_year] = load_entity_turnout_source(
                project_root, previous_year, config
            )
        recent = cache[recent_year]
        previous = cache[previous_year]
        cycle = recent.merge(
            previous,
            on="entity_id",
            suffixes=("_recent", "_previous"),
            validate="one_to_one",
        )
        national_recent = float(
            cycle["total_votes_recent"].sum() / cycle["nominal_list_recent"].sum()
        )
        national_previous = float(
            cycle["total_votes_previous"].sum() / cycle["nominal_list_previous"].sum()
        )
        national_change = national_recent - national_previous
        cycle["target_year"] = int(target_year)
        cycle["entity_same_family_turnout_recent"] = cycle["turnout_recent"]
        cycle["entity_same_family_turnout_previous"] = cycle["turnout_previous"]
        cycle["entity_same_family_turnout_change"] = (
            cycle["turnout_recent"] - cycle["turnout_previous"]
        )
        cycle["national_same_family_turnout_change"] = national_change
        cycle["entity_same_family_change_minus_national"] = (
            cycle["entity_same_family_turnout_change"] - national_change
        )
        cycle["entity_cycle_recent_source_year"] = recent_year
        cycle["entity_cycle_previous_source_year"] = previous_year
        cycle["entity_cycle_source_max_year"] = recent_year
        rows.append(
            cycle[
                [
                    "target_year",
                    "entity_id",
                    *ENTITY_CYCLE_FEATURES,
                    "entity_cycle_recent_source_year",
                    "entity_cycle_previous_source_year",
                    "entity_cycle_source_max_year",
                ]
            ]
        )
    return pd.concat(rows, ignore_index=True)


def _unit_members(
    units: pd.DataFrame, components: pd.DataFrame, membership_year: int
) -> pd.DataFrame:
    ids = units["evaluation_unit_id"].drop_duplicates().astype(str)
    stable = pd.DataFrame({"evaluation_unit_id": ids[ids.str.startswith("S:")]})
    stable["section_key_observed"] = stable["evaluation_unit_id"].str.removeprefix("S:")
    component_ids = ids[ids.str.startswith("C:")].str.removeprefix("C:")
    lineage = components[
        components["target_year"].eq(membership_year)
        & components["amge_component_id"].isin(set(component_ids))
    ][["amge_component_id", "section_key_observed"]].drop_duplicates()
    lineage["evaluation_unit_id"] = "C:" + lineage["amge_component_id"].astype(str)
    members = pd.concat(
        [
            stable[["evaluation_unit_id", "section_key_observed"]],
            lineage[["evaluation_unit_id", "section_key_observed"]],
        ],
        ignore_index=True,
    ).drop_duplicates()
    missing = set(ids) - set(members["evaluation_unit_id"])
    if missing:
        raise ValueError(f"Unidades sin miembros para competencia: {sorted(missing)[:5]}")
    return members


def _competition_metrics(
    members: pd.DataFrame, votes: pd.DataFrame, option_columns: list[str]
) -> pd.DataFrame:
    merged = members.merge(votes, on="section_key_observed", how="left", indicator=True)
    coverage = (
        merged.assign(matched=merged["_merge"].eq("both"))
        .groupby("evaluation_unit_id", as_index=False)
        .agg(
            competition_member_sections=("section_key_observed", "nunique"),
            competition_matched_sections=("matched", "sum"),
        )
    )
    aggregated = merged.groupby("evaluation_unit_id", as_index=False)[option_columns].sum(
        min_count=1
    )
    values = aggregated[option_columns].fillna(0.0).to_numpy(dtype=float)
    values.sort(axis=1)
    values = values[:, ::-1]
    totals = values.sum(axis=1)
    shares = np.divide(
        values,
        totals[:, None],
        out=np.zeros_like(values),
        where=totals[:, None] > 0,
    )
    winner = shares[:, 0]
    runner_up = shares[:, 1] if shares.shape[1] > 1 else np.zeros(len(shares))
    hhi = np.square(shares).sum(axis=1)
    aggregated["prior_competition_valid_votes"] = totals
    aggregated["prior_winner_vote_share"] = np.where(totals > 0, winner, np.nan)
    aggregated["prior_runner_up_vote_share"] = np.where(totals > 0, runner_up, np.nan)
    aggregated["prior_competition_margin"] = np.where(
        totals > 0, winner - runner_up, np.nan
    )
    aggregated["prior_competition_hhi"] = np.where(totals > 0, hhi, np.nan)
    aggregated["prior_effective_number_options"] = np.divide(
        1.0, hhi, out=np.full(len(hhi), np.nan), where=hhi > 0
    )
    aggregated["prior_top_two_vote_share"] = np.where(
        totals > 0, winner + runner_up, np.nan
    )
    aggregated["prior_competitive_option_count"] = np.where(
        totals > 0, (shares >= 0.05).sum(axis=1), np.nan
    )
    aggregated = aggregated.drop(columns=option_columns)
    result = aggregated.merge(coverage, on="evaluation_unit_id", validate="one_to_one")
    result["prior_competition_coverage"] = result[
        "competition_matched_sections"
    ].div(result["competition_member_sections"])
    return result


def _entity_set(value: Any) -> set[str]:
    all_entities = {str(number).zfill(2) for number in range(1, 33)}
    if value == "all":
        return all_entities
    if isinstance(value, str) and value.startswith("all_except_"):
        excluded = {token.zfill(2) for token in value.removeprefix("all_except_").split("_")}
        return all_entities - excluded
    return {str(entity).zfill(2) for entity in value}


def build_concurrency_table(config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for target_year, schedule in config["concurrency"].items():
        election_date = pd.Timestamp(schedule["election_date"])
        known_by = pd.Timestamp(schedule["known_by"])
        if known_by >= election_date:
            raise ValueError(f"El calendario {target_year} no estaba disponible antes de la jornada")
        local = _entity_set(schedule["local_election_entities"])
        executive = _entity_set(schedule["executive_entities"])
        congress = _entity_set(schedule["congress_entities"])
        municipal = _entity_set(schedule["municipal_entities"])
        if not executive | congress | municipal <= local:
            raise ValueError(f"El calendario {target_year} tiene cargos fuera del universo local")
        for entity_id in sorted({str(number).zfill(2) for number in range(1, 33)}):
            flags = {
                "local_election_concurrent": int(entity_id in local),
                "local_executive_on_ballot": int(entity_id in executive),
                "local_congress_on_ballot": int(entity_id in congress),
                "municipal_on_ballot": int(entity_id in municipal),
            }
            ballot_count = sum(flags[key] for key in CONCURRENCY_FEATURES[1:4])
            rows.append(
                {
                    "target_year": int(target_year),
                    "entity_id": entity_id,
                    **flags,
                    "local_ballot_type_count": ballot_count,
                    "concurrency_profile": "_".join(
                        name
                        for name, active in [
                            ("executive", flags["local_executive_on_ballot"]),
                            ("congress", flags["local_congress_on_ballot"]),
                            ("municipal", flags["municipal_on_ballot"]),
                        ]
                        if active
                    )
                    or "none",
                    "concurrency_known_date": known_by.date().isoformat(),
                    "target_election_date": election_date.date().isoformat(),
                    "concurrency_source_url": schedule["source_url"],
                }
            )
    return pd.DataFrame(rows)


def _write_source_manifest(project_root: Path, config: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for source_year, source in config["turnout_sources"].items():
        path = project_root / str(source["archive_path"])
        rows.append(
            {
                "source_kind": "prior_entity_same_family_turnout",
                "reference_year": int(source_year),
                "url": source["url"],
                "local_path": source["archive_path"],
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
                "ballot": source["ballot"],
                "availability_rule": "official_result_used_only_for_later_targets",
            }
        )
    for source_year, source in config["competition_sources"].items():
        path = project_root / str(source["archive_path"])
        rows.append(
            {
                "source_kind": "prior_federal_election_results",
                "reference_year": int(source_year),
                "url": source["url"],
                "local_path": source["archive_path"],
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
                "ballot": source["ballot"],
                "availability_rule": "official_result_used_only_for_later_targets",
            }
        )
    for target_year, schedule in config["concurrency"].items():
        rows.append(
            {
                "source_kind": "target_local_election_schedule",
                "reference_year": int(target_year),
                "url": schedule["source_url"],
                "local_path": "configs/electoral_context.yaml",
                "bytes": np.nan,
                "sha256": np.nan,
                "ballot": "local_schedule",
                "availability_rule": f"known_by_{schedule['known_by']}",
            }
        )
    manifest = pd.DataFrame(rows)
    manifest.to_csv(
        project_root / "data/manifests/electoral_context_source_manifest.csv", index=False
    )
    return manifest


def add_electoral_context(
    project_root: Path,
    frame: pd.DataFrame,
    membership_year_by_target: dict[int, int] | None = None,
) -> pd.DataFrame:
    """Attach prior competition and target-known local concurrency without leakage."""
    config = _load_yaml(project_root / "configs/electoral_context.yaml")
    components = pd.read_parquet(
        project_root / "artifacts/tables/lineage_components_by_election.parquet"
    )
    membership_year_by_target = membership_year_by_target or {}
    competition_rows = []
    source_cache: dict[int, tuple[pd.DataFrame, list[str]]] = {}
    for target_year in sorted(int(year) for year in frame["target_year"].unique()):
        source_year = int(config["target_competition_source"][target_year])
        if source_year >= target_year:
            raise ValueError("La competencia electoral usa el target o una eleccion posterior")
        if source_year not in source_cache:
            source_cache[source_year] = load_competition_source(
                project_root, source_year, config
            )
        votes, option_columns = source_cache[source_year]
        units = frame[frame["target_year"].eq(target_year)][["evaluation_unit_id"]]
        membership_year = int(membership_year_by_target.get(target_year, target_year))
        members = _unit_members(units, components, membership_year)
        metrics = _competition_metrics(members, votes, option_columns)
        metrics["target_year"] = target_year
        metrics["competition_source_year"] = source_year
        metrics["competition_ballot"] = config["competition_sources"][source_year]["ballot"]
        competition_rows.append(metrics)
    competition = pd.concat(competition_rows, ignore_index=True)
    enriched = frame.merge(
        competition,
        on=["target_year", "evaluation_unit_id"],
        how="left",
        validate="one_to_one",
    )
    concurrency = build_concurrency_table(config)
    enriched["entity_id"] = enriched["entity_id"].astype(str).str.zfill(2)
    enriched = enriched.merge(
        concurrency,
        on=["target_year", "entity_id"],
        how="left",
        validate="many_to_one",
    )
    if enriched[CONCURRENCY_FEATURES].isna().any().any():
        raise ValueError("Hay unidades sin calendario de concurrencia")
    entity_cycle = build_entity_cycle_table(
        project_root,
        config,
        sorted(int(year) for year in frame["target_year"].unique()),
    )
    enriched = enriched.merge(
        entity_cycle,
        on=["target_year", "entity_id"],
        how="left",
        validate="many_to_one",
    )
    if enriched[ENTITY_CYCLE_FEATURES].isna().any().any():
        raise ValueError("Hay unidades sin cambio estatal de la misma familia")
    if not (enriched["competition_source_year"] < enriched["target_year"]).all():
        raise ValueError("Se detecto fuga temporal en competencia electoral")
    known = pd.to_datetime(enriched["concurrency_known_date"])
    election = pd.to_datetime(enriched["target_election_date"])
    if not known.lt(election).all():
        raise ValueError("Se detecto un calendario publicado despues de la jornada")
    if not (enriched["entity_cycle_source_max_year"] < enriched["target_year"]).all():
        raise ValueError("Se detecto fuga temporal en el ciclo estatal")
    enriched["electoral_context_source_max_year"] = enriched[
        [
            "max_electoral_feature_year",
            "competition_source_year",
            "entity_cycle_source_max_year",
        ]
    ].max(axis=1)
    _write_source_manifest(project_root, config)
    return enriched
