from __future__ import annotations

from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]


def md(text: str, cell_id: str, tags: list[str] | None = None):
    cell = nbf.v4.new_markdown_cell(text)
    cell["id"] = cell_id
    if tags:
        cell["metadata"]["tags"] = tags
    return cell


def code(text: str, cell_id: str, tags: list[str] | None = None):
    cell = nbf.v4.new_code_cell(text)
    cell["id"] = cell_id
    if tags:
        cell["metadata"]["tags"] = tags
    return cell


def notebook_00() -> nbf.NotebookNode:
    cells = [
        md(
            """# 00 · Configuración, fuentes y descarga oficial

**Pregunta.** ¿Las seis bases federales 2009–2024 y el manual oficial pueden obtenerse, validarse e inventariarse de forma reproducible?

**Entradas.** `configs/sources.yaml`, página oficial del INE y documentos locales de referencia. Las unidades de esta fase son archivos y miembros de archivo, no personas ni territorios.

**Método.** Se usa HTTP con *streaming*, archivo temporal, SHA-256, validación de firma/contenido, CRC y rutas seguras. Los ZIP crudos quedan inmutables en `data/raw/`; su extracción separada queda en `data/interim/extracted/`.

**Criterios.** Deben existir seis ZIP federales válidos, un PDF oficial, un manifiesto con URL solicitada/final y un inventario de miembros. Voto anticipado, voto en prisión preventiva y Poder Judicial se registran como universos separados.

**Salidas.** `data/manifests/source_manifest.csv`, `data/manifests/zip_member_inventory.csv` y carpetas extraídas. Tiempo esperado: varios minutos; descarga aproximada: 292 MB comprimidos más el manual.""",
            "intro-scope",
            ["scope"],
        ),
        md(
            """## Entorno y raíz del proyecto

Se localiza la raíz mediante archivos versionados y se muestran versiones efectivas. No se usa una ruta personal absoluta ni estado de otro notebook.""",
            "environment-question",
        ),
        code(
            """from pathlib import Path
import hashlib
import platform
import sys
import time

import pandas as pd
import yaml
from IPython.display import Markdown, display


def find_project_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "pyproject.toml").exists() and (candidate / "configs/sources.yaml").exists():
            return candidate
    raise FileNotFoundError("No se encontró la raíz del proyecto")


PROJECT_ROOT = find_project_root(Path.cwd().resolve())
RUN_STARTED = time.perf_counter()
environment = {
    "project_root_detected": PROJECT_ROOT.name,
    "python": sys.version.split()[0],
    "implementation": platform.python_implementation(),
    "platform": platform.platform(),
    "pandas": pd.__version__,
}
pd.Series(environment, name="valor").to_frame()""",
            "setup-environment",
            ["setup", "output-environment"],
        ),
        code(
            """display(Markdown(
    f"**Interpretación.** La ejecución usa Python `{environment['python']}` y detectó la raíz "
    f"`{environment['project_root_detected']}` sin depender de una ruta absoluta escrita en el notebook."
))""",
            "environment-interpretation",
        ),
        md(
            """## Registro de alcance y fuentes

Antes de transferir bytes se inspecciona la configuración. El universo principal incluye sólo elecciones federales comparables del portal; los procesos especiales se documentan y se excluyen de esta descarga principal.""",
            "sources-question",
        ),
        code(
            """with (PROJECT_ROOT / "configs/sources.yaml").open(encoding="utf-8") as stream:
    sources = yaml.safe_load(stream)

source_rows = []
for year, item in sorted(sources["elections"].items(), key=lambda pair: int(pair[0])):
    source_rows.append({"source_id": f"ccpc_federal_{year}", "year": int(year), **item})
configured_sources = pd.DataFrame(source_rows)
display(configured_sources[["source_id", "year", "kind", "filename", "url"]])
display(pd.Series(sources["scope"], name="definición"))""",
            "show-source-contract",
            ["source-contract"],
        ),
        code(
            """excluded = sources["scope"]["excluded_from_main_panel"]
display(Markdown(
    f"**Interpretación.** Se configuraron `{len(configured_sources)}` elecciones federales. "
    f"Permanecen fuera del panel principal `{len(excluded)}` universos: " + "; ".join(excluded) + "."
))""",
            "sources-interpretation",
        ),
        md(
            """## Trazabilidad de documentos locales

Se calculan hashes de la convocatoria, el manual y los dos documentos metodológicos existentes. Esto conserva la procedencia de las versiones realmente leídas; no modifica sus originales.""",
            "documents-question",
        ),
        code(
            """def sha256_local(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


document_paths = [
    PROJECT_ROOT / "Convocatoria_Hackaton-1.pdf",
    PROJECT_ROOT / "Manual-Conteos-Censales-2009-2024.pdf",
    PROJECT_ROOT / "RADAR27_Plan_Maestro_Agente.md",
    PROJECT_ROOT / "RADAR27_Propuesta_Equipo_Obsidian.md",
]
document_registry = pd.DataFrame(
    {
        "path": [path.relative_to(PROJECT_ROOT).as_posix() for path in document_paths],
        "bytes": [path.stat().st_size for path in document_paths],
        "sha256": [sha256_local(path) for path in document_paths],
    }
)
display(document_registry)""",
            "hash-local-documents",
            ["document-provenance"],
        ),
        code(
            """display(Markdown(
    f"**Interpretación.** Se registraron `{len(document_registry)}` documentos locales. "
    "Sus hashes identifican exactamente las versiones consultadas en esta fase."
))""",
            "documents-interpretation",
        ),
        md(
            """## Descarga, validación y extracción segura

La llamada siguiente muestra explícitamente el archivo de configuración, el destino y los controles aplicados por la utilidad versionada `src/radar27/ingest/download_ccpc.py`: HTTP con redirecciones registradas, escritura `.part`, SHA-256, rechazo de HTML, prueba CRC, prohibición de `..`, rutas absolutas y enlaces simbólicos, y extracción separada. Si una instantánea existente tiene contenido distinto, la ejecución se detiene.""",
            "download-question",
        ),
        code(
            """from radar27.ingest.download_ccpc import download_configured_sources

download_started = time.perf_counter()
manifest_rows, member_rows = download_configured_sources(
    PROJECT_ROOT,
    notebook="notebooks/00_setup_sources_download.ipynb",
    cell_id="download-official-sources",
    extract=True,
)
download_seconds = time.perf_counter() - download_started
manifest = pd.DataFrame(manifest_rows)
members = pd.DataFrame(member_rows)
display(manifest[[
    "source_id", "year", "http_status", "content_type", "bytes", "sha256",
    "requested_url", "final_url", "validation_status"
]])""",
            "download-official-sources",
            ["download", "artifact-source-manifest"],
        ),
        code(
            """zip_rows = manifest[manifest["kind"].eq("zip")]
valid_zip_count = int(zip_rows["validation_status"].eq("zip_signature_crc_paths_verified").sum())
requested_equals_final = int((manifest["requested_url"] == manifest["final_url"]).sum())
display(Markdown(
    f"**Resultado.** Se validaron `{valid_zip_count}` de `{len(zip_rows)}` ZIP mediante firma, CRC y rutas "
    f"seguras. La descarga tardó `{download_seconds:.1f}` s. En `{requested_equals_final}` de "
    f"`{len(manifest)}` fuentes la URL final coincidió exactamente con la solicitada; cualquier "
    "redirección restante quedó en el manifiesto."
))""",
            "download-interpretation",
        ),
        md(
            """## Inventario interno y tamaño expandido

Se resume cada archivo comprimido antes de interpretar tablas. El conteo incluye miembros documentales y de datos; todavía no se impone una unidad de observación.""",
            "inventory-question",
        ),
        code(
            """member_summary = (
    members.groupby("year", as_index=False)
    .agg(
        members=("member_name", "count"),
        files=("is_dir", lambda values: int((~values.astype(bool)).sum())),
        compressed_bytes=("compressed_bytes", "sum"),
        uncompressed_bytes=("uncompressed_bytes", "sum"),
    )
)
member_summary["expansion_ratio"] = (
    member_summary["uncompressed_bytes"] / member_summary["compressed_bytes"].replace(0, pd.NA)
)
display(member_summary)
display(members[["year", "member_name", "uncompressed_bytes", "crc32"]])""",
            "summarize-zip-members",
            ["artifact-zip-inventory"],
        ),
        code(
            """display(Markdown(
    f"**Resultado.** Los seis ZIP contienen `{len(members)}` miembros registrados y "
    f"`{int(member_summary['uncompressed_bytes'].sum()):,}` bytes declarados al expandirse. "
    "La granularidad y compatibilidad de cada tabla se auditan en el notebook 01; este inventario "
    "no supone que nombres parecidos tengan el mismo significado."
))""",
            "inventory-interpretation",
        ),
        md(
            """## Cierre de la fase de descarga

Se comprueban los artefactos mínimos y se informa duración y límites. Tener ZIP íntegros no implica que sus esquemas sean comparables ni que la cartografía histórica esté armonizada.""",
            "download-close-question",
        ),
        code(
            """required_outputs = [
    PROJECT_ROOT / "data/manifests/source_manifest.csv",
    PROJECT_ROOT / "data/manifests/zip_member_inventory.csv",
]
checks = {
    "six_election_zips": len(zip_rows) == 6,
    "all_http_200": bool(manifest["http_status"].eq(200).all()),
    "all_outputs_exist": all(path.exists() for path in required_outputs),
    "all_years_extracted": all(
        (PROJECT_ROOT / "data/interim/extracted" / str(year)).exists()
        for year in configured_sources["year"]
    ),
}
elapsed = time.perf_counter() - RUN_STARTED
display(pd.Series(checks, name="aprobado").to_frame())
display(Markdown(
    f"**Cierre.** `{sum(checks.values())}/{len(checks)}` comprobaciones pasaron en `{elapsed:.1f}` s. "
    "Siguiente paso: determinar formatos, esquemas, categorías y granularidad reales sin unir años. "
    "La cartografía oficial de mayo de 2023 está identificada, pero su compatibilidad con cada ZIP "
    "permanece pendiente y por ello no se supera todavía el Gate 1 completo del plan maestro."
))""",
            "download-final-checks",
            ["gate", "summary"],
        ),
    ]
    notebook = nbf.v4.new_notebook(cells=cells)
    notebook["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.12"},
    }
    return notebook


def notebook_01() -> nbf.NotebookNode:
    cells = [
        md(
            """# 01 · Auditoría física, de esquema, categorías y granularidad

**Pregunta.** ¿Qué contienen realmente los 192 CSV oficiales y bajo qué condiciones pueden compararse los seis años?

**Entradas.** Manifiestos del notebook 00, seis diccionarios TXT y CSV extraídos. La unidad candidata se comprueba, no se presupone.

**Método.** Lectura completa y conservadora como texto mediante DuckDB; auditoría por archivo y año de formato, esquema, nulos, rangos, categorías, duplicados, claves, conciliación `LN = SV + NV + NS` y cobertura territorial. Los identificadores se mantienen como texto.

**Supuestos.** Un mismo código de sección entre años no prueba identidad territorial. `SEXO`, `EDAD` y las filas no se recodifican. Ausencia de categoría, valor faltante y conteo cero se reportan por separado.

**Salidas.** Inventario Parquet, matrices CSV, reporte HTML y evidencia para los documentos de definiciones y auditoría. No se construye panel ni target.

**Recursos esperados.** Lectura aproximada de 3.6 GB; varios minutos, memoria acotada por ejecución columnar.""",
            "audit-intro",
            ["scope"],
        ),
        md(
            """## Entorno y entradas

Se detecta la raíz, se comprueba que el notebook 00 produjo los manifiestos y se mide tiempo/memoria del proceso actual.""",
            "audit-setup-question",
        ),
        code(
            """from pathlib import Path
import hashlib
import json
import resource
import time

import pandas as pd
from IPython.display import HTML, Markdown, display


def find_project_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "pyproject.toml").exists() and (candidate / "configs/sources.yaml").exists():
            return candidate
    raise FileNotFoundError("No se encontró la raíz del proyecto")


PROJECT_ROOT = find_project_root(Path.cwd().resolve())
RUN_STARTED = time.perf_counter()
required_inputs = [
    PROJECT_ROOT / "data/manifests/source_manifest.csv",
    PROJECT_ROOT / "data/manifests/zip_member_inventory.csv",
    PROJECT_ROOT / "data/interim/extracted",
]
input_checks = {path.relative_to(PROJECT_ROOT).as_posix(): path.exists() for path in required_inputs}
display(pd.Series(input_checks, name="existe").to_frame())
assert all(input_checks.values()), "Faltan entradas del notebook 00"
""",
            "audit-setup",
            ["setup"],
        ),
        code(
            """display(Markdown(
    f"**Interpretación.** Las `{len(required_inputs)}` entradas declaradas existen. "
    "La auditoría comienza desde archivos persistidos, no desde variables de otro notebook."
))""",
            "audit-setup-interpretation",
        ),
        md(
            """## Documentación incluida en los ZIP

Se leen y hashean los seis diccionarios. Se comparan sus textos para detectar cambios documentales antes de interpretar columnas.""",
            "dictionary-question",
        ),
        code(
            """def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


dictionary_rows = []
dictionary_texts = {}
for year in [2009, 2012, 2015, 2018, 2021, 2024]:
    matches = list((PROJECT_ROOT / "data/interim/extracted" / str(year)).rglob("01_descripcioncampos*.txt"))
    assert len(matches) == 1, (year, matches)
    path = matches[0]
    text = path.read_text(encoding="utf-8-sig")
    dictionary_texts[year] = text
    dictionary_rows.append({
        "year": year,
        "path": path.relative_to(PROJECT_ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "mentions_derfe_2021": "DERFE 2021" in text,
        "mentions_derfe_2023": "DERFE 2023" in text,
        "mentions_non_binary": "No binario" in text,
    })
dictionary_inventory = pd.DataFrame(dictionary_rows)
display(dictionary_inventory)""",
            "read-zip-dictionaries",
            ["dictionary-provenance"],
        ),
        code(
            """old_hashes = dictionary_inventory.loc[dictionary_inventory.year < 2024, "sha256"].nunique()
display(Markdown(
    f"**Hallazgo.** Los diccionarios 2009–2021 tienen `{old_hashes}` hash distinto(s): son "
    "binariamente idénticos y documentan distritos en el marco DERFE 2021. El diccionario 2024 "
    "cambia al marco DERFE 2023, agrega `SEXO=2` (No binario) y omite de la lista de NS el caso "
    "de cuadernillo solicitado por autoridad jurisdiccional. La sección se describe en todos los "
    "años como la del año correspondiente."
))""",
            "dictionary-interpretation",
        ),
        md(
            """## Lectura completa e inventario físico

Se recorren los 192 CSV. Para preservar ceros y códigos, todas las columnas se leen inicialmente como texto; los rangos numéricos se calculan con conversiones explícitas que cuentan valores inválidos. El inventario por archivo incluye hash, formato, filas, columnas, nulos y muestra.""",
            "physical-audit-question",
        ),
        code(
            """from radar27.audit.raw_schema import audit_all

audit_started = time.perf_counter()
inventory, year_summary, categories, section_frames = audit_all(PROJECT_ROOT)
audit_seconds = time.perf_counter() - audit_started
peak_rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024

display(inventory[[
    "year", "path", "bytes", "encoding", "has_utf8_bom", "separator",
    "line_ending", "rows", "column_count", "null_pct_max"
]].head(12))
display(pd.DataFrame({
    "files": [len(inventory)],
    "bytes": [int(inventory.bytes.sum())],
    "rows": [int(inventory.rows.sum())],
    "elapsed_seconds": [round(audit_seconds, 2)],
    "peak_rss_mb_process": [round(peak_rss_mb, 1)],
}))""",
            "run-physical-audit",
            ["artifact-raw-file-inventory"],
        ),
        code(
            """display(Markdown(
    f"**Resultado.** Se leyeron completamente `{len(inventory)}` CSV con "
    f"`{int(inventory.rows.sum()):,}` filas y `{int(inventory.bytes.sum()):,}` bytes en "
    f"`{audit_seconds:.1f}` s. El máximo RSS observado por el proceso fue `{peak_rss_mb:.1f}` MB. "
    "El inventario se guardó en `artifacts/tables/raw_file_inventory.parquet`."
))""",
            "physical-audit-interpretation",
        ),
        md(
            """## Esquema, nulos y granularidad

Se compara el esquema por año y se audita la clave candidata `AELEC × EDOCVE × SECCION × SEXO × EDAD`. Esta clave expresa sección por sexo por edad, no casilla ni una fila agregada territorial. Los duplicados exactos se calculan por separado.""",
            "schema-question",
        ),
        code(
            """summary_view = year_summary[[
    "year", "files", "rows", "schema_matches_expected", "sections", "municipalities",
    "duplicate_key_groups", "duplicate_key_extra_rows", "exact_duplicate_groups",
    "exact_duplicate_extra_rows", "ln_zero_rows", "identified_zero_rows"
]].copy()
display(summary_view)

null_matrix = pd.DataFrame(
    {int(row.year): row.null_counts for row in year_summary.itertuples(index=False)}
).fillna(0).astype("int64")
display(null_matrix)""",
            "audit-schema-granularity",
            ["schema", "duplicates", "nulls"],
        ),
        code(
            """schema_ok = bool(year_summary.schema_matches_expected.all())
key_duplicates = int(year_summary.duplicate_key_extra_rows.sum())
exact_duplicates = int(year_summary.exact_duplicate_extra_rows.sum())
display(Markdown(
    f"**Hallazgo.** Los seis años comparten las 16 columnas esperadas: `{schema_ok}`. La clave "
    f"candidata sección × sexo × edad tiene `{key_duplicates:,}` filas adicionales en grupos "
    f"duplicados y existen `{exact_duplicates:,}` duplicados exactos. Las repeticiones territoriales "
    "entre sexo y edad son dimensiones sustantivas, no duplicados. Los nulos se concentran en los "
    "campos mostrados y no se imputan en esta fase."
))""",
            "schema-interpretation",
        ),
        md(
            """## Categorías de sexo, edad y tipo de sección

Se muestran las categorías observadas. La ausencia de `SEXO=2` antes de 2024 se interpreta como categoría no disponible según la documentación, no como conteo cero. Los códigos de edad se conservan sin asignar todavía grupos abiertos.""",
            "categories-question",
        ),
        code(
            """sex_categories = categories[categories.column.eq("SEXO")].copy()
section_type_categories = categories[categories.column.eq("TIPOSEC")].copy()
age_categories = categories[categories.column.eq("EDAD")].copy()
age_summary = (
    age_categories.assign(age_numeric=pd.to_numeric(age_categories.value, errors="coerce"))
    .groupby("year", as_index=False)
    .agg(
        category_count=("value", "nunique"),
        min_age=("age_numeric", "min"),
        max_age=("age_numeric", "max"),
        nonnumeric_categories=("age_numeric", lambda values: int(values.isna().sum())),
    )
)
age_outliers = (
    age_categories.assign(age_numeric=pd.to_numeric(age_categories.value, errors="coerce"))
    .loc[lambda frame: frame.age_numeric.gt(100)]
    .groupby("year", as_index=False)
    .agg(rows_over_100=("rows", "sum"), nominal_list_over_100=("nominal_list", "sum"), max_age=("age_numeric", "max"))
)
display(sex_categories)
display(section_type_categories)
display(age_summary)
display(age_outliers)""",
            "audit-categories",
            ["categories"],
        ),
        code(
            """non_binary_2024 = sex_categories[
    sex_categories.year.eq(2024) & sex_categories.value.astype(str).eq("2")
]
display(Markdown(
    f"**Hallazgo.** `SEXO=2` aparece en 2024 con `{int(non_binary_2024.rows.sum()):,}` filas y "
    f"lista nominal agregada `{int(non_binary_2024.nominal_list.sum()):,}`; no aparece en años "
    "anteriores. Los códigos de tipo de sección observados se reportan arriba. La edad llega al "
    f"rango `{int(age_summary.min_age.min())}`–`{int(age_summary.max_age.max())}`; el manual del "
    "tablero agrupa 100+, pero los TXT sólo describen años cumplidos, por lo que la semántica de "
    "edades mayores a 100 queda pendiente antes de agrupar o validar."
))""",
            "categories-interpretation",
        ),
        md(
            """## Conciliación contable e indicadores

Se verifica fila por fila `LN = SV + NV + NS`. Después se agregan numeradores y denominadores antes de dividir. La participación oficial del tablero es `SV/(SV+NV)`; `SV/LN` se etiqueta sólo como sensibilidad. Si un denominador fuera cero, el resultado queda no definido (`NA`).""",
            "indicators-question",
        ),
        code(
            """counts = year_summary[[
    "year", "rows", "accounting_mismatch_rows", "accounting_max_abs_difference",
    "sum_ln", "sum_sv", "sum_nv", "sum_ns"
]].copy()
identified = counts.sum_sv + counts.sum_nv
counts["official_participation"] = counts.sum_sv.div(identified.where(identified.ne(0)))
counts["official_abstention"] = counts.sum_nv.div(identified.where(identified.ne(0)))
counts["unspecified_share_ln"] = counts.sum_ns.div(counts.sum_ln.where(counts.sum_ln.ne(0)))
counts["identified_coverage_ln"] = identified.div(counts.sum_ln.where(counts.sum_ln.ne(0)))
counts["sensitivity_voted_over_ln"] = counts.sum_sv.div(counts.sum_ln.where(counts.sum_ln.ne(0)))
display(counts)""",
            "audit-indicators",
            ["accounting", "indicator-definitions"],
        ),
        code(
            """mismatch_total = int(counts.accounting_mismatch_rows.sum())
display(Markdown(
    f"**Resultado.** La identidad contable presenta `{mismatch_total:,}` filas discrepantes. "
    "Los porcentajes nacionales mostrados se calcularon como razones de sumas, no como promedio "
    "simple entre secciones. NS permanece fuera de abstención y se informa por separado sobre LN."
))""",
            "indicators-interpretation",
        ),
        md(
            """## Equivalencia de campos y ausencias del archivo descargable

Se construye una matriz conceptual. También se registran dimensiones del tablero que no aparecen como columnas en los CSV; su presencia en la plataforma no autoriza a fabricarlas ni a atribuirlas a personas.""",
            "equivalence-question",
        ),
        code(
            """concepts = [
    ("año electoral", "AELEC"), ("fecha electoral", "FELECCION"),
    ("entidad", "EDOCVE / EDONOM"), ("municipio", "MPIOCVE / MPIONOM"),
    ("sección", "SECCION"), ("tipo de sección", "TIPOSEC"),
    ("distrito federal", "DEF"), ("distrito local", "DEL"),
    ("sexo", "SEXO"), ("edad", "EDAD"), ("lista nominal", "LN"),
    ("sí votaron", "SV"), ("no votaron", "NV"),
    ("registros no especificados", "NS"),
    ("porcentaje de participación publicado", None),
    ("referente indígena", None), ("referente afromexicano", None),
]
equivalence_rows = []
for concept, source_field in concepts:
    row = {"campo_conceptual": concept}
    for year in [2009, 2012, 2015, 2018, 2021, 2024]:
        row[str(year)] = source_field if source_field else "NO PRESENTE EN CSV"
    if concept == "sexo":
        row["discrepancia"] = "SEXO=2 sólo está documentado y observado en 2024"
    elif concept in {"distrito federal", "distrito local"}:
        row["discrepancia"] = "Marco DERFE 2021 en 2009–2021; marco DERFE 2023 en 2024"
    elif source_field is None:
        row["discrepancia"] = "Disponible o derivado en tablero, no como campo del ZIP general"
    else:
        row["discrepancia"] = "Nombre común; definición sujeta al diccionario de cada versión"
    equivalence_rows.append(row)
equivalence = pd.DataFrame(equivalence_rows)
equivalence_path = PROJECT_ROOT / "artifacts/tables/field_equivalence_matrix.csv"
equivalence.to_csv(equivalence_path, index=False)
display(equivalence)""",
            "build-field-equivalence",
            ["artifact-field-equivalence"],
        ),
        code(
            """missing_dashboard_fields = equivalence[
    equivalence["2009"].eq("NO PRESENTE EN CSV")
].campo_conceptual.tolist()
display(Markdown(
    "**Hallazgo.** Los conteos LN/SV/NV/NS y las dimensiones básicas sí mantienen nombres de "
    "campo comunes. No aparecen columnas de " + ", ".join(missing_dashboard_fields) +
    ". Por tanto, los referentes indígena/afromexicano se tratan provisionalmente como atributos "
    "territoriales o enriquecimientos externos del tablero, nunca como identidad individual."
))""",
            "equivalence-interpretation",
        ),
        md(
            """## Comparabilidad territorial

Se comparan identificadores de sección tal como vienen (`EDOCVE:SECCION`) y cambios de metadatos. La superposición de códigos mide coincidencia nominal, no equivalencia geométrica.""",
            "territory-question",
        ),
        code(
            """section_frames = section_frames.assign(
    section_code=section_frames.EDOCVE.astype(str).str.zfill(2) + ":" + section_frames.SECCION.astype(str)
)
years = [2009, 2012, 2015, 2018, 2021, 2024]
section_sets = {
    year: set(section_frames.loc[section_frames.year.eq(year), "section_code"])
    for year in years
}
overlap_rows = []
for previous, current in zip(years[:-1], years[1:]):
    intersection = section_sets[previous] & section_sets[current]
    overlap_rows.append({
        "previous": previous,
        "current": current,
        "previous_sections": len(section_sets[previous]),
        "current_sections": len(section_sets[current]),
        "shared_codes": len(intersection),
        "only_previous": len(section_sets[previous] - section_sets[current]),
        "only_current": len(section_sets[current] - section_sets[previous]),
    })
overlap = pd.DataFrame(overlap_rows)

left = section_frames[section_frames.year.eq(2021)].set_index("section_code")
right = section_frames[section_frames.year.eq(2024)].set_index("section_code")
shared = left.join(right, how="inner", lsuffix="_2021", rsuffix="_2024")
metadata_changes = pd.DataFrame({
    "field": ["MPIOCVE", "DEF", "DEL", "TIPOSEC"],
    "changed_shared_codes": [
        int((shared[f"{field}_2021"].fillna("<NA>") != shared[f"{field}_2024"].fillna("<NA>")).sum())
        for field in ["MPIOCVE", "DEF", "DEL", "TIPOSEC"]
    ],
    "shared_codes": len(shared),
})
display(overlap)
display(metadata_changes)""",
            "audit-territorial-comparability",
            ["territory", "comparability"],
        ),
        code(
            """display(Markdown(
    f"**Interpretación.** Entre 2021 y 2024 coinciden nominalmente `{len(shared):,}` códigos de "
    "sección, pero existen altas/bajas y cambios de municipio, distrito o tipo de sección según la "
    "tabla. Esto confirma que repetir ID no basta para afirmar territorio idéntico. Hace falta "
    "cartografía oficial, catálogos y, si existe, un crosswalk autorizado antes de construir el panel."
))""",
            "territory-interpretation",
        ),
        md(
            """## Reporte HTML y comprobaciones de cierre

El HTML de auditoría reúne las tablas obtenidas. Se verifican los artefactos mínimos; no se declara armonización, target ni reproducibilidad completa.""",
            "audit-close-question",
        ),
        code(
            """report_path = PROJECT_ROOT / "artifacts/reports/raw_audit.html"
report_path.parent.mkdir(parents=True, exist_ok=True)
html_parts = [
    "<h1>RADAR 27 · Auditoría inicial de archivos crudos</h1>",
    "<p>Generado por notebooks/01_raw_schema_audit.ipynb. Código y contexto completo en la copia ejecutada.</p>",
    "<h2>Resumen por año</h2>", summary_view.to_html(index=False),
    "<h2>Conciliación e indicadores</h2>", counts.to_html(index=False),
    "<h2>Categorías de sexo</h2>", sex_categories.to_html(index=False),
    "<h2>Tipos de sección</h2>", section_type_categories.to_html(index=False),
    "<h2>Edades</h2>", age_summary.to_html(index=False),
    "<h2>Edades mayores a 100</h2>", age_outliers.to_html(index=False),
    "<h2>Equivalencia de campos</h2>", equivalence.to_html(index=False),
    "<h2>Superposición territorial nominal</h2>", overlap.to_html(index=False),
    "<h2>Cambios de metadatos 2021–2024</h2>", metadata_changes.to_html(index=False),
]
report_path.write_text("\\n".join(html_parts), encoding="utf-8")

required_outputs = [
    PROJECT_ROOT / "artifacts/tables/raw_file_inventory.parquet",
    PROJECT_ROOT / "artifacts/tables/field_equivalence_matrix.csv",
    PROJECT_ROOT / "artifacts/tables/category_inventory.csv",
    report_path,
]
checks = {
    "all_192_csv_audited": len(inventory) == 192,
    "six_years_audited": len(year_summary) == 6,
    "all_outputs_exist": all(path.exists() for path in required_outputs),
    "accounting_identity_holds": int(counts.accounting_mismatch_rows.sum()) == 0,
    "no_exact_duplicates": int(year_summary.exact_duplicate_extra_rows.sum()) == 0,
    "cartography_compatibility_resolved": False,
}
display(pd.Series(checks, name="aprobado").to_frame())
elapsed = time.perf_counter() - RUN_STARTED
display(Markdown(
    f"**Cierre.** Pasaron `{sum(checks.values())}/{len(checks)}` comprobaciones en `{elapsed:.1f}` s. "
    "La comprobación territorial falla deliberadamente porque aún no hay geometría/crosswalk validado. "
    "Siguiente paso concreto: definir reglas de limpieza sin recodificar categorías, obtener catálogos "
    "cartográficos oficiales y probar reconciliación territorial antes del panel."
))""",
            "audit-final-checks",
            ["gate", "summary"],
        ),
    ]
    notebook = nbf.v4.new_notebook(cells=cells)
    notebook["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.12"},
    }
    return notebook


def notebook_02() -> nbf.NotebookNode:
    cells = [
        md(
            """# 02 · Limpieza tipada y contratos de identificadores

**Pregunta.** ¿Es posible producir una capa limpia, reproducible y sin pérdidas, dejando explícito qué identificadores son sólo observados y qué armonización territorial sigue pendiente?

**Entradas.** Los 192 CSV auditados, `configs/harmonization.yaml`, el resumen crudo y la evidencia cartográfica registrada.

**Método.** Validación exacta de año/fecha, tipado explícito, serialización canónica de IDs, conservación de categorías, indicadores con denominador documentado y conciliación después de agregar. Cada año se escribe en Parquet de forma atómica.

**Política de retención.** No se excluye ninguna fila. Edades mayores de 100, distritos vacíos y denominadores identificados en cero se conservan con bandera o nulo semántico. `SEXO=2` permanece como categoría fuente de 2024.

**Límite.** `section_key_observed` evita colisiones dentro de una elección, pero no demuestra equivalencia geométrica entre elecciones. El agregado sección–año de este notebook es provisional y no es un panel longitudinal armonizado.

**Salidas.** Parquet limpios por año, resumen, bitácora de retención, agregado provisional, conciliación y transiciones nominales de códigos.""",
            "clean-intro",
            ["scope"],
        ),
        md(
            """## Entorno y precondiciones

Se detecta la raíz y se comprueba que la auditoría previa existe. El notebook no depende del estado de memoria de los notebooks 00 o 01.""",
            "clean-setup-question",
        ),
        code(
            """from pathlib import Path
import resource
import time

import pandas as pd
import yaml
from IPython.display import Markdown, display


def find_project_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "pyproject.toml").exists() and (candidate / "configs/harmonization.yaml").exists():
            return candidate
    raise FileNotFoundError("No se encontró la raíz del proyecto")


PROJECT_ROOT = find_project_root(Path.cwd().resolve())
RUN_STARTED = time.perf_counter()
required_inputs = [
    PROJECT_ROOT / "artifacts/tables/raw_year_summary.json",
    PROJECT_ROOT / "artifacts/tables/raw_section_frame_inventory.parquet",
    PROJECT_ROOT / "configs/harmonization.yaml",
    PROJECT_ROOT / "configs/geography_sources.yaml",
]
input_checks = {path.relative_to(PROJECT_ROOT).as_posix(): path.exists() for path in required_inputs}
display(pd.Series(input_checks, name="existe").to_frame())
assert all(input_checks.values()), "Faltan entradas auditadas del notebook 01"
""",
            "clean-setup",
            ["setup"],
        ),
        code(
            """display(Markdown(
    f"**Interpretación.** Las `{len(required_inputs)}` precondiciones existen. "
    "La transformación parte de artefactos persistidos y configuraciones versionadas."
))""",
            "clean-setup-interpretation",
        ),
        md(
            """## Contrato temporal, categórico y de IDs

Las fechas se mapean por valor fuente exacto porque 2009–2021 usan día/mes/año y 2024 usa mes/día/año. Los anchos son reglas de serialización, no afirmaciones sobre una clave maestra oficial.""",
            "contract-question",
        ),
        code(
            """with (PROJECT_ROOT / "configs/harmonization.yaml").open(encoding="utf-8") as stream:
    harmonization_config = yaml.safe_load(stream)

year_contract = pd.DataFrame([
    {"year": int(year), **values}
    for year, values in harmonization_config["years"].items()
])
display(year_contract)
display(pd.Series(harmonization_config["id_serialization"], name="regla").to_frame())
display(pd.Series(harmonization_config["retention_policy"], name="regla").to_frame())""",
            "show-clean-contract",
            ["contract"],
        ),
        code(
            """display(Markdown(
    "**Interpretación.** El contrato fija seis fechas inequívocas y conserva ceros a la izquierda. "
    "La llave `section_key_observed = entidad:sección` se limita al marco declarado por cada fuente; "
    "no recibe el nombre de ID armonizado."
))""",
            "contract-interpretation",
        ),
        md(
            """## Evidencia y estado de la cartografía

Se muestra el registro de fuentes cartográficas. La ausencia de descarga oficial directa se trata como un bloqueo verificable, no como permiso para inferir polígonos por coincidencia de códigos.""",
            "geography-question",
        ),
        code(
            """with (PROJECT_ROOT / "configs/geography_sources.yaml").open(encoding="utf-8") as stream:
    geography_config = yaml.safe_load(stream)

geography_sources = pd.DataFrame(geography_config["sources"])
display(geography_sources)
display(pd.Series({
    "status": geography_config["status"],
    "crosswalk_downloaded": geography_config["crosswalk_downloaded"],
    "geometry_downloaded": geography_config["geometry_downloaded"],
    "decision": geography_config["decision"],
}, name="valor").to_frame())""",
            "show-geography-evidence",
            ["geography", "source-contract"],
        ),
        code(
            """display(Markdown(
    "**Hallazgo.** El catálogo especializado requiere solicitud de información. El informe DERFE "
    "registra 69,548 secciones para mayo de 2023, mientras la fuente CCPC 2024 contiene 70,751 "
    "códigos observados. La discrepancia impide declarar que la base 2024 ya está en un marco "
    "seccional 2023 único y validado."
))""",
            "geography-interpretation",
        ),
        md(
            """## Transformación limpia por año

La función versionada lee cada columna como texto, valida año y literal de fecha, convierte tipos y escribe seis archivos Parquet. Después vuelve a leer cada salida para validar unicidad, formatos, categorías, no negatividad y la identidad `LN = SV + NV + NS`.""",
            "harmonize-question",
        ),
        code(
            """from radar27.clean.harmonize import harmonize_all

clean_started = time.perf_counter()
summary, exclusions, reconciliation, transitions = harmonize_all(PROJECT_ROOT)
clean_seconds = time.perf_counter() - clean_started
peak_rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024

display(summary[[
    "year", "election_family", "election_date", "raw_rows", "clean_rows", "excluded_rows",
    "unique_record_ids", "accounting_mismatches", "age_review_rows",
    "missing_federal_district_rows", "missing_local_district_rows", "zero_identified_rows",
    "non_binary_rows",
]])
display(pd.DataFrame({
    "elapsed_seconds": [round(clean_seconds, 2)],
    "peak_rss_mb_process": [round(peak_rss_mb, 1)],
    "clean_rows": [int(summary.clean_rows.sum())],
    "excluded_rows": [int(summary.excluded_rows.sum())],
}))""",
            "run-harmonization",
            ["artifact-harmonization-summary", "transform"],
        ),
        code(
            """display(Markdown(
    f"**Resultado.** Se tiparon y validaron `{int(summary.clean_rows.sum()):,}` filas en "
    f"`{clean_seconds:.1f}` s, con `{int(summary.excluded_rows.sum()):,}` exclusiones. "
    "Cada `record_id` es único y todos los totales concilian con la auditoría cruda."
))""",
            "harmonization-interpretation",
        ),
        md(
            """## Retención, banderas y nulos semánticos

La tabla siguiente distingue exclusión de revisión. Las banderas pueden traslaparse; sus conteos no se suman para obtener filas únicas.""",
            "retention-question",
        ),
        code(
            """display(exclusions)
assert exclusions["excluded_rows"].sum() == 0
assert summary["excluded_rows"].sum() == 0""",
            "show-exclusion-log",
            ["artifact-exclusion-log", "retention"],
        ),
        code(
            """display(Markdown(
    "**Interpretación.** Ninguna observación fue descartada. Los distritos vacíos permanecen como "
    "nulos, las edades mayores a 100 quedan marcadas para revisión y los cocientes con denominador "
    "cero se conservan como nulos en vez de convertirse artificialmente en cero."
))""",
            "retention-interpretation",
        ),
        md(
            """## Conciliación del agregado provisional

Los conteos se suman primero por elección y código observado de sección; los porcentajes se calculan después como razón de sumas. El nombre y estado del artefacto impiden confundirlo con un panel armonizado.""",
            "aggregation-question",
        ),
        code(
            """display(reconciliation)
raw_summary = pd.read_json(PROJECT_ROOT / "artifacts/tables/raw_year_summary.json")
comparison = reconciliation.merge(
    raw_summary[["year", "rows", "sum_ln", "sum_sv", "sum_nv", "sum_ns"]],
    left_on="election_year", right_on="year", validate="one_to_one",
)
comparison["rows_match"] = comparison["demographic_rows"].eq(comparison["rows"])
comparison["ln_match"] = comparison["sum_nominal_list"].eq(comparison["sum_ln"])
comparison["sv_match"] = comparison["sum_voted"].eq(comparison["sum_sv"])
comparison["nv_match"] = comparison["sum_did_not_vote"].eq(comparison["sum_nv"])
comparison["ns_match"] = comparison["sum_unspecified"].eq(comparison["sum_ns"])
display(comparison[["election_year", "rows_match", "ln_match", "sv_match", "nv_match", "ns_match"]])
assert comparison[["rows_match", "ln_match", "sv_match", "nv_match", "ns_match"]].all().all()""",
            "validate-provisional-aggregation",
            ["artifact-aggregation-reconciliation", "accounting"],
        ),
        code(
            """display(Markdown(
    f"**Resultado.** Las `{len(reconciliation)}` elecciones conservan exactamente filas y cuatro "
    "totales contables después de agregar. Esto valida la transformación aritmética, no la "
    "equivalencia territorial entre años."
))""",
            "aggregation-interpretation",
        ),
        md(
            """## Transiciones nominales y bloqueo longitudinal

Se comparan altas, bajas y cambios de metadatos entre elecciones consecutivas. Coincidencia nominal significa sólo que se repite `entidad:sección`.""",
            "transitions-question",
        ),
        code(
            """display(transitions)""",
            "show-section-transitions",
            ["artifact-section-transitions", "territory"],
        ),
        code(
            """latest = transitions.iloc[-1]
display(Markdown(
    f"**Hallazgo.** En 2021–2024 hay `{int(latest.shared_observed_codes):,}` códigos nominales "
    f"compartidos, `{int(latest.only_previous):,}` sólo previos y `{int(latest.only_current):,}` "
    "sólo actuales, además de cambios de metadatos. No se genera una llave longitudinal."
))""",
            "transitions-interpretation",
        ),
        md(
            """## Cierre y compuertas

Se comprueba la capa limpia y se mantiene fallida, de forma deliberada, la compuerta que requeriría cartografía/crosswalk oficial.""",
            "clean-close-question",
        ),
        code(
            """required_outputs = [
    PROJECT_ROOT / "artifacts/tables/harmonization_year_summary.csv",
    PROJECT_ROOT / "artifacts/tables/cleaning_exclusion_log.csv",
    PROJECT_ROOT / "artifacts/tables/provisional_section_year_totals.parquet",
    PROJECT_ROOT / "artifacts/tables/aggregation_reconciliation.csv",
    PROJECT_ROOT / "artifacts/tables/section_code_transition_summary.csv",
]
checks = {
    "all_54m_rows_retained": int(summary.clean_rows.sum()) == 54_872_712,
    "zero_excluded_rows": int(summary.excluded_rows.sum()) == 0,
    "record_ids_unique": bool((summary.clean_rows == summary.unique_record_ids).all()),
    "accounting_holds": bool(summary.accounting_mismatches.eq(0).all()),
    "all_outputs_exist": all(path.exists() for path in required_outputs),
    "official_crosswalk_available": bool(geography_config["crosswalk_downloaded"]),
    "longitudinal_panel_built": False,
}
display(pd.Series(checks, name="aprobado").to_frame())
elapsed = time.perf_counter() - RUN_STARTED
display(Markdown(
    f"**Cierre.** Pasaron `{sum(checks.values())}/{len(checks)}` comprobaciones en `{elapsed:.1f}` s. "
    "Las dos negativas son restricciones metodológicas intencionales: no existe crosswalk oficial "
    "validado y, por ello, no se construyó el panel longitudinal. Siguiente paso: solicitar los "
    "productos cartográficos especializados y validar una estrategia de correspondencia."
))""",
            "clean-final-checks",
            ["gate", "summary"],
        ),
    ]
    notebook = nbf.v4.new_notebook(cells=cells)
    notebook["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.12"},
    }
    return notebook


def notebook_03() -> nbf.NotebookNode:
    cells = [
        md(
            """# 03 · Fuentes públicas y linajes del Marco Geográfico Electoral

**Pregunta.** ¿Qué continuidad territorial puede defenderse usando sólo información pública y cómo debe clasificarse cada sección antes de modelar?

**Entradas.** El libro público AMGE 2005–2022 publicado por DERFE mediante una resolución de transparencia existente, el agregado limpio sección–elección y configuraciones versionadas.

**Método.** Se valida el SHA-256 del libro, se interpretan por separado secciones origen y destino, se expanden rangos únicamente cuando existe guion y se crean aristas sólo para divisiones o fusiones completas uno-a-muchos o muchos-a-uno. Otros cambios se conservan como ambiguos.

**Disponibilidad temporal.** Para evaluar un target en el año `t` sólo se permiten eventos con `effective_year < t`. Esto evita incorporar retrospectivamente modificaciones del mismo año cuya fecha exacta no esté disponible.

**Límite.** El archivo termina en 2022. La clasificación 2024 es útil pero parcial; no se declara completa la evidencia de cambios 2023. No se construye contigüidad espacial ni se distribuyen conteos históricos entre descendientes.

**Salidas.** Manifiesto público, eventos, secciones afectadas, aristas de linaje, componentes y clases A/B/C/D por elección.""",
            "public-geo-intro",
            ["scope"],
        ),
        md(
            """## Entorno y contratos

Se comprueban configuraciones, libro y panel previo. La fuente, reglas de elegibilidad y categorías se muestran antes de ejecutar transformaciones.""",
            "public-geo-setup-question",
        ),
        code(
            """import time
from pathlib import Path

import pandas as pd
import yaml
from IPython.display import Markdown, display


def find_project_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "configs/public_geography.yaml").exists():
            return candidate
    raise FileNotFoundError("No se encontró la raíz del proyecto")


PROJECT_ROOT = find_project_root(Path.cwd().resolve())
RUN_STARTED = time.perf_counter()
required = [
    PROJECT_ROOT / "configs/public_geography.yaml",
    PROJECT_ROOT / "configs/evaluation.yaml",
    PROJECT_ROOT / "data/interim/public_ine/amge_2005_2022.xlsx",
    PROJECT_ROOT / "artifacts/tables/provisional_section_year_totals.parquet",
]
checks = {path.relative_to(PROJECT_ROOT).as_posix(): path.exists() for path in required}
display(pd.Series(checks, name="existe").to_frame())
assert all(checks.values())""",
            "public-geo-setup",
            ["setup"],
        ),
        code(
            """with (PROJECT_ROOT / "configs/public_geography.yaml").open(encoding="utf-8") as stream:
    public_geo_config = yaml.safe_load(stream)
with (PROJECT_ROOT / "configs/evaluation.yaml").open(encoding="utf-8") as stream:
    evaluation_config = yaml.safe_load(stream)

display(pd.DataFrame([
    {"source_id": source_id, **source}
    for source_id, source in public_geo_config["sources"].items()
]))
display(pd.DataFrame([
    {"class": class_id, **definition}
    for class_id, definition in evaluation_config["confidence_classes"].items()
]))""",
            "show-public-contracts",
            ["source-contract", "classification-contract"],
        ),
        code(
            """display(Markdown(
    "**Interpretación.** AMGE es la única fuente usada para construir aristas. El MGS 2022, "
    "Tableau y ECEG 2020 están registrados, pero no se convierten silenciosamente en crosswalks: "
    "sirven como referencia cartográfica o futuras covariables."
))""",
            "public-contracts-interpretation",
        ),
        md(
            """## Procedencia y validación del libro AMGE

El manifiesto registra autoridad, resolución oficial, enlace público, ruta local, bytes y hash. La transformación falla si el hash difiere del valor congelado.""",
            "public-manifest-question",
        ),
        code(
            """from radar27.geography.amge import write_public_source_manifest

public_manifest = write_public_source_manifest(PROJECT_ROOT)
display(public_manifest)""",
            "write-public-manifest",
            ["artifact-public-source-manifest"],
        ),
        code(
            """amge_source = public_manifest[public_manifest.source_id.eq("amge_history")].iloc[0]
display(Markdown(
    f"**Resultado.** El libro AMGE tiene `{int(amge_source.bytes):,}` bytes y SHA-256 "
    f"`{amge_source.sha256}`. Fue obtenido de una carpeta pública enlazada por la resolución "
    "oficial, sin autenticación ni nueva solicitud de información."
))""",
            "public-manifest-interpretation",
        ),
        md(
            """## Eventos, afectados y aristas elegibles

Un guion representa rango inclusivo; coma o la conjunción “Y” representan códigos discretos. Se crean aristas sólo si el caso normalizado es división/fusión, existen ambos lados, hay año efectivo y la forma es uno-a-muchos o muchos-a-uno.""",
            "amge-parse-question",
        ),
        code(
            """from radar27.geography.amge import parse_amge_workbook

events, edges, affected = parse_amge_workbook(PROJECT_ROOT)
event_summary = (
    events.groupby(["effective_year", "lineage_eligible"], dropna=False, as_index=False)
    .agg(event_rows=("event_id", "count"), origins=("origin_count", "sum"), destinations=("destination_count", "sum"))
)
display(event_summary)
display(events[[
    "event_id", "source_excel_row", "entity_id", "program", "case_label", "effective_year",
    "origin_count", "destination_count", "mapping_shape", "lineage_eligible",
]].head(20))""",
            "parse-amge-events",
            ["artifact-amge-events", "transform"],
        ),
        code(
            """display(Markdown(
    f"**Resultado.** Se preservaron `{len(events):,}` filas-evento, `{len(affected):,}` "
    f"registros de sección afectada y `{len(edges):,}` aristas elegibles. "
    f"`{int(events.lineage_eligible.sum()):,}` filas-evento permiten linaje; las restantes "
    "quedan como evidencia ambigua y nunca generan una asignación ponderada."
))""",
            "amge-parse-interpretation",
        ),
        md(
            """## Componentes y clases de confianza

Las aristas elegibles forman componentes conexos no dirigidos. Una sección pasa a D si ella o cualquier miembro de su componente tiene un evento ambiguo previo. La clasificación se recalcula para cada corte temporal.""",
            "confidence-question",
        ),
        code(
            """from radar27.modeling.lineage_evaluation import build_confidence_classes

classes, components = build_confidence_classes(PROJECT_ROOT, affected, edges)
class_summary = (
    classes.groupby(["target_year", "geography_confidence_class"], as_index=False)
    .agg(sections=("section_key_observed", "nunique"), nominal_list=("nominal_list", "sum"))
)
year_totals = class_summary.groupby("target_year").agg(
    total_sections=("sections", "sum"), total_nominal_list=("nominal_list", "sum")
)
class_summary = class_summary.join(year_totals, on="target_year")
class_summary["section_share"] = class_summary.sections / class_summary.total_sections
class_summary["nominal_list_share"] = class_summary.nominal_list / class_summary.total_nominal_list
display(class_summary)""",
            "build-confidence-classes",
            ["artifact-confidence-classes", "classification"],
        ),
        code(
            """current = class_summary[class_summary.target_year.eq(2024)]
display(Markdown(
    "**Resultado 2024.** " + "; ".join(
        f"clase {row.geography_confidence_class}: {int(row.sections):,} secciones "
        f"({row.section_share:.1%})"
        for row in current.itertuples(index=False)
    ) + ". La cobertura AMGE termina en 2022, por lo que estas clases no absorben todavía "
    "las relaciones aprobadas durante 2023."
))""",
            "confidence-interpretation",
        ),
        md(
            """## Comprobaciones de cierre

Se exige unicidad de eventos/aristas, años dentro de cobertura, componentes deterministas y clasificación exhaustiva.""",
            "public-geo-close-question",
        ),
        code(
            """expected_classes = {"A", "B", "C", "D"}
close_checks = {
    "amge_hash_verified": bool(amge_source.local_exists),
    "event_ids_unique": events.event_id.is_unique,
    "edges_unique": not edges.duplicated().any(),
    "eligible_edges_have_two_sides": bool(edges.origin_section_key.notna().all() and edges.destination_section_key.notna().all()),
    "classification_exhaustive": set(classes.geography_confidence_class) == expected_classes,
    "one_class_per_target_section": not classes.duplicated(["target_year", "section_key_observed"]).any(),
    "amge_2024_coverage_complete": False,
    "fractional_allocation_used": False,
}
display(pd.Series(close_checks, name="valor").to_frame())
display(Markdown(
    f"**Cierre.** Se procesaron `{len(events):,}` eventos en `{time.perf_counter()-RUN_STARTED:.1f}` s. "
    "La cobertura 2024 permanece deliberadamente incompleta y la asignación fraccionaria permanece "
    "falsa. El notebook 04 evalúa las tres estrategias con estas restricciones visibles."
))""",
            "public-geo-final-checks",
            ["gate", "summary"],
        ),
    ]
    notebook = nbf.v4.new_notebook(cells=cells)
    notebook["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.12"},
    }
    return notebook


def notebook_04() -> nbf.NotebookNode:
    cells = [
        md(
            """# 04 · Paneles conservadores y evaluación de estrategias geográficas

**Pregunta.** ¿Cuánta cobertura y qué error fuera de tiempo produce cada estrategia de continuidad territorial?

**Target.** Participación oficial en la elección objetivo: `SV/(SV+NV)`. Una sección con `SV+NV=0` no tiene target evaluable, aunque sí puede recibir predicción.

**Predictor común.** Participación de la elección anterior de la misma familia. Se evalúan 2009→2015, 2012→2018, 2015→2021 y 2018→2024. El fold 2021 es el análogo principal para 2027.

**Escenarios.** (1) sólo clase A; (2) A más componentes B agregados sin repartir conteos; (3) todas las secciones mediante prioridad sección→linaje→municipio→entidad→nacional.

**Interpretación.** Esta evaluación compara estrategias geográficas bajo el mismo predictor transparente. No selecciona todavía el modelo final de 2027 ni estima desempeño futuro garantizado.

**Salidas.** Predicciones fuera de tiempo, métricas, errores por clase, fuentes de fallback, linaje de variables y reporte HTML.""",
            "backtest-intro",
            ["scope", "model-contract"],
        ),
        md(
            """## Contratos y entradas

Se muestran folds, escenarios y recetas de variables antes de calcular predicciones.""",
            "backtest-setup-question",
        ),
        code(
            """import time
from pathlib import Path

import pandas as pd
import yaml
from IPython.display import Markdown, display


def find_project_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "configs/evaluation.yaml").exists():
            return candidate
    raise FileNotFoundError("No se encontró la raíz del proyecto")


PROJECT_ROOT = find_project_root(Path.cwd().resolve())
RUN_STARTED = time.perf_counter()
required = [
    PROJECT_ROOT / "configs/evaluation.yaml",
    PROJECT_ROOT / "configs/features.yaml",
    PROJECT_ROOT / "artifacts/tables/section_confidence_by_election.parquet",
    PROJECT_ROOT / "artifacts/tables/lineage_components_by_election.parquet",
]
checks = {path.relative_to(PROJECT_ROOT).as_posix(): path.exists() for path in required}
display(pd.Series(checks, name="existe").to_frame())
assert all(checks.values())""",
            "backtest-setup",
            ["setup"],
        ),
        code(
            """with (PROJECT_ROOT / "configs/evaluation.yaml").open(encoding="utf-8") as stream:
    evaluation_config = yaml.safe_load(stream)
with (PROJECT_ROOT / "configs/features.yaml").open(encoding="utf-8") as stream:
    feature_config = yaml.safe_load(stream)

display(pd.DataFrame(evaluation_config["folds"]))
display(pd.DataFrame([
    {"scenario": name, **values}
    for name, values in evaluation_config["scenarios"].items()
]))
display(pd.DataFrame([
    {"variable": name, **values}
    for name, values in feature_config["features"].items()
]))""",
            "show-backtest-contract",
            ["fold-contract", "feature-contract"],
        ),
        code(
            """display(Markdown(
    "**Interpretación.** Todos los predictores proceden del `feature_year`; el target procede del "
    "`target_year`. La clase geográfica sólo usa metadatos territoriales y eventos AMGE con año "
    "efectivo estrictamente anterior al target."
))""",
            "backtest-contract-interpretation",
        ),
        md(
            """## Ejecución de los tres escenarios

Cada fold se calcula desde conteos persistidos. Los componentes agregan numeradores y denominadores antes de dividir; nunca distribuyen el valor de una sección origen entre descendientes.""",
            "evaluation-question",
        ),
        code(
            """from radar27.modeling.lineage_evaluation import evaluate_scenarios

classes = pd.read_parquet(PROJECT_ROOT / "artifacts/tables/section_confidence_by_election.parquet")
components = pd.read_parquet(PROJECT_ROOT / "artifacts/tables/lineage_components_by_election.parquet")
metrics, predictions, errors_by_class, source_counts = evaluate_scenarios(
    PROJECT_ROOT, classes, components
)
display(metrics[[
    "target_year", "feature_year", "scenario", "target_sections_represented",
    "section_coverage", "nominal_list_coverage", "mae", "rmse", "bias",
    "identified_weighted_mae", "identified_weighted_rmse", "share_within_5pp",
    "evidence_status",
]])""",
            "run-geography-backtests",
            ["artifact-backtest-metrics", "evaluation"],
        ),
        code(
            """primary = metrics[metrics.target_year.eq(2021)].set_index("scenario")
stable = primary.loc["stable_only"]
lineage = primary.loc["stable_plus_lineage"]
fallback = primary.loc["hierarchical_fallback"]
display(Markdown(
    f"**Resultado principal 2015→2021.** Sólo A cubre `{stable.section_coverage:.1%}` y logra MAE "
    f"ponderado `{stable.identified_weighted_mae:.3f}`. A+B cubre `{lineage.section_coverage:.1%}` "
    f"con MAE `{lineage.identified_weighted_mae:.3f}`. El respaldo jerárquico cubre "
    f"`{fallback.section_coverage:.1%}` con MAE `{fallback.identified_weighted_mae:.3f}`. "
    "La participación de una elección intermedia no es estacionaria: el sesgo negativo cuantifica "
    "cuánto sobrepredice el rezago de 2015 a 2021."
))""",
            "primary-backtest-interpretation",
        ),
        md(
            """## Cobertura y procedencia de cada predicción

Se cuenta cuántas secciones utilizaron el rezago propio, un componente oficial o un respaldo municipal/estatal. La fuente es un campo por predicción, no una inferencia posterior.""",
            "fallback-question",
        ),
        code(
            """display(source_counts)
source_totals = source_counts.groupby("target_year", as_index=False).agg(
    total_sections=("sections", "sum"), total_nominal_list=("nominal_list", "sum")
)
source_shares = source_counts.merge(source_totals, on="target_year")
source_shares["section_share"] = source_shares.sections / source_shares.total_sections
source_shares["nominal_list_share"] = source_shares.nominal_list / source_shares.total_nominal_list
display(source_shares)""",
            "show-fallback-provenance",
            ["artifact-fallback-sources", "provenance"],
        ),
        code(
            """primary_sources = source_shares[source_shares.target_year.eq(2021)]
display(Markdown(
    "**Resultado.** En 2021, " + "; ".join(
        f"{row.prediction_source}: {int(row.sections):,} secciones ({row.section_share:.1%})"
        for row in primary_sources.itertuples(index=False)
    ) + ". No fue necesario usar el promedio nacional en ningún fold."
))""",
            "fallback-interpretation",
        ),
        md(
            """## Error por clase territorial

La desagregación detecta si la cobertura adicional se compra a costa de errores concentrados en secciones nuevas o ambiguas.""",
            "class-error-question",
        ),
        code(
            """display(errors_by_class)""",
            "show-errors-by-class",
            ["artifact-errors-by-class", "robustness"],
        ),
        code(
            """primary_errors = errors_by_class[errors_by_class.target_year.eq(2021)]
display(Markdown(
    "**Interpretación 2021.** " + "; ".join(
        f"clase {row.geography_confidence_class}: MAE {row.mae:.3f} en {int(row.sections):,} secciones"
        for row in primary_errors.itertuples(index=False)
    ) + ". Estas diferencias justifican conservar la clase como indicador de incertidumbre y "
    "reportar desempeño estratificado."
))""",
            "class-error-interpretation",
        ),
        md(
            """## Linaje de variables y prevención de fuga

El registro siguiente vincula variable, columnas fuente, transformación, disponibilidad, riesgo, política de faltantes e implementación.""",
            "variable-lineage-question",
        ),
        code(
            """variable_lineage = pd.read_csv(PROJECT_ROOT / "artifacts/tables/variable_lineage.csv")
display(variable_lineage)

leakage_checks = {
    "all_prediction_folds_are_temporal": bool((predictions.feature_year < predictions.target_year).all()),
    "no_missing_predictions": bool(predictions.prediction.notna().all()),
    "predictions_are_probabilities": bool(predictions.prediction.between(0, 1).all()),
    "targets_are_probabilities_when_defined": bool(predictions.actual.dropna().between(0, 1).all()),
}
display(pd.Series(leakage_checks, name="aprobado").to_frame())""",
            "audit-variable-lineage",
            ["artifact-variable-lineage", "leakage"],
        ),
        code(
            """display(Markdown(
    "**Resultado.** Cada predicción conserva `feature_year`, `target_year` y `prediction_source`. "
    "La prueba temporal exige `feature_year < target_year`; ningún promedio se calcula con el "
    "target para producir su propia predicción."
))""",
            "variable-lineage-interpretation",
        ),
        md(
            """## Reporte y decisión

El reporte HTML resume métricas, fuentes y error por clase. La decisión se basa en cobertura, error y auditabilidad, no sólo en la menor cifra.""",
            "decision-question",
        ),
        code(
            """report_path = PROJECT_ROOT / "artifacts/reports/public_lineage_evaluation.html"
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text("\\n".join([
    "<h1>RADAR 27 · Evaluación de continuidad territorial pública</h1>",
    "<p>Generado por notebooks/04_panel_build_audit.ipynb. El código y outputs completos están en la copia ejecutada.</p>",
    "<h2>Contrato</h2><p>Target SV/(SV+NV); predictor: participación previa de la misma familia.</p>",
    "<h2>Métricas</h2>", metrics.to_html(index=False),
    "<h2>Procedencia de fallback</h2>", source_shares.to_html(index=False),
    "<h2>Error por clase</h2>", errors_by_class.to_html(index=False),
    "<h2>Linaje de variables</h2>", variable_lineage.to_html(index=False),
]), encoding="utf-8")

required_outputs = [
    PROJECT_ROOT / "artifacts/tables/backtest_predictions.parquet",
    PROJECT_ROOT / "artifacts/tables/backtest_metrics.csv",
    PROJECT_ROOT / "artifacts/tables/backtest_errors_by_class.csv",
    PROJECT_ROOT / "artifacts/tables/fallback_source_counts.csv",
    PROJECT_ROOT / "artifacts/tables/variable_lineage.csv",
    report_path,
]
final_checks = {
    "all_outputs_exist": all(path.exists() for path in required_outputs),
    "four_folds_three_scenarios": len(metrics) == 12,
    "hierarchical_defined_target_coverage_is_complete": bool(
        metrics[metrics.scenario.eq("hierarchical_fallback")].section_coverage.eq(1).all()
    ),
    "lineage_improves_2021_coverage": lineage.section_coverage > stable.section_coverage,
    "lineage_does_not_worsen_2021_weighted_mae": (
        lineage.identified_weighted_mae <= stable.identified_weighted_mae
    ),
    "2024_geography_evidence_complete": False,
    **leakage_checks,
}
display(pd.Series(final_checks, name="valor").to_frame())""",
            "write-evaluation-report",
            ["artifact-evaluation-report", "gate"],
        ),
        code(
            """display(Markdown(
    f"**Decisión.** Adoptar A+B como muestra principal: aumenta cobertura con error ponderado "
    f"ligeramente menor en el análogo 2021. Usar el escenario jerárquico para cobertura nacional, "
    f"con clase y fuente visibles como incertidumbre. No usar 2024 para validar por sí solo el "
    f"crosswalk porque AMGE termina en 2022. Tiempo total: `{time.perf_counter()-RUN_STARTED:.1f}` s."
))""",
            "evaluation-final-interpretation",
            ["summary"],
        ),
    ]
    notebook = nbf.v4.new_notebook(cells=cells)
    notebook["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.12"},
    }
    return notebook


def notebook_05() -> nbf.NotebookNode:
    cells = [
        md(
            """# 05 · Feature mart temporal y evaluación de modelos

**Pregunta.** ¿Las variables electorales históricas auditadas mejoran el baseline A+B sin fuga temporal ni deterioro fuerte en otros folds? ¿Qué valor incremental ofrece ECEG 2020 cuando realmente estaba disponible?

**Entradas.** Conteos CCPC armonizados por sexo y edad, clases A/B, componentes AMGE, baseline congelado y ZIP público ECEG 2020 de INEGI.

**Diseño.** Se agregan conteos antes de calcular tasas. Cada fold entrena sólo con elecciones objetivo anteriores. El modelo principal usa variables electorales; ECEG, publicado/modificado el 18 de agosto de 2021, queda prohibido en los backtests estrictos 2015/2018/2021 y se evalúa sólo como evidencia secundaria para 2024.

**Gate.** Mejorar el MAE ponderado 2021 de 9.38 pp, igualar su cobertura A+B y no empeorar ningún otro fold más de 0.5 pp absolutos.

**Salidas.** Feature mart, linaje de variables, predicciones, métricas, errores por entidad/clase, importancia, registro de modelos, decisión y reporte HTML.""",
            "feature-model-scope",
            ["scope"],
        ),
        code(
            """from pathlib import Path
import json
import time

import pandas as pd
from IPython.display import Markdown, display

from radar27.ingest.eceg import prepare_eceg
from radar27.modeling.feature_models import (
    build_feature_mart,
    build_section_year_behavioral_features,
    evaluate_models,
)


def find_project_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "pyproject.toml").exists() and (candidate / "configs/modeling.yaml").exists():
            return candidate
    raise FileNotFoundError("No se encontró la raíz del proyecto")


PROJECT_ROOT = find_project_root(Path.cwd().resolve())
RUN_STARTED = time.perf_counter()
display(pd.Series({"project_root": PROJECT_ROOT.name, "phase": "feature_model_evaluation"}))""",
            "feature-model-setup",
            ["setup"],
        ),
        md(
            """## Fuente sociodemográfica pública

Se verifica tamaño, SHA-256, firma ZIP, CRC y rutas internas antes de extraer sólo la tabla seccional, el diccionario y los metadatos. La fecha de disponibilidad se conserva como una restricción de modelado, no como una nota informal.""",
            "eceg-source-question",
        ),
        code(
            """eceg_manifest, eceg_dictionary, eceg = prepare_eceg(PROJECT_ROOT)
display(eceg_manifest.T)
display(eceg_dictionary[["topic", "indicator", "mnemonic", "unit", "output_variable"]])
display(pd.Series({
    "eceg_sections": len(eceg),
    "unique_section_keys": eceg.section_key_observed.nunique(),
    "selected_source_variables": len(eceg_dictionary),
}))""",
            "prepare-eceg-source",
            ["artifact-eceg-manifest", "artifact-eceg-dictionary"],
        ),
        code(
            """display(Markdown(
    "**Interpretación.** ECEG representa una fotografía censal 2020 por sección. Su fecha oficial "
    "de modificación es posterior a la elección 2021; por contrato sólo puede entrar a la prueba "
    "secundaria 2024 y a un futuro modelo 2027. No se usa como crosswalk territorial."
))""",
            "eceg-source-interpretation",
        ),
        md(
            """## Variables electorales por sección–año

Los 54.9 millones de registros sexo–edad se reducen a numeradores y denominadores auditables. Las tasas por sexo y edad se calcularán después de agregar cada sección o componente AMGE.""",
            "behavioral-features-question",
        ),
        code(
            """section_year = build_section_year_behavioral_features(PROJECT_ROOT)
behavioral_summary = (
    section_year.groupby("election_year", as_index=False)
    .agg(
        sections=("section_key_observed", "nunique"),
        nominal_list=("nominal_list", "sum"),
        voted=("voted", "sum"),
        did_not_vote=("did_not_vote", "sum"),
    )
)
display(behavioral_summary)""",
            "build-section-year-features",
            ["artifact-section-year-features"],
        ),
        code(
            """display(Markdown(
    f"**Resultado.** Se construyeron `{len(section_year):,}` filas sección–año. "
    "Cada componente posterior suma conteos; no promedia porcentajes seccionales."
))""",
            "behavioral-features-interpretation",
        ),
        md(
            """## Feature mart A+B

Las unidades A conservan su sección. Las B usan el componente oficial AMGE. Cada fila contiene outcome sólo para evaluar; la matriz predictora usa exclusivamente elecciones anteriores. ECEG conserva una bandera explícita de elegibilidad temporal.""",
            "feature-mart-question",
        ),
        code(
            """feature_mart, feature_coverage = build_feature_mart(PROJECT_ROOT)
display(feature_coverage)
display(pd.read_csv(PROJECT_ROOT / "artifacts/tables/model_feature_lineage.csv"))""",
            "build-feature-mart",
            ["artifact-feature-mart", "artifact-feature-lineage"],
        ),
        code(
            """mart_checks = {
    "unit_target_unique": not feature_mart.duplicated(["target_year", "evaluation_unit_id"]).any(),
    "electoral_features_strictly_prior": bool(
        (feature_mart.max_electoral_feature_year < feature_mart.target_year).all()
    ),
    "eceg_forbidden_in_2021_strict_backtest": bool(
        (~feature_mart.loc[feature_mart.target_year.eq(2021), "eceg_strict_backtest_allowed"]).all()
    ),
    "targets_defined_only_from_target_counts": bool(
        feature_mart.actual.dropna().between(0, 1).all()
    ),
}
display(pd.Series(mart_checks, name="aprobado").to_frame())
assert all(mart_checks.values())""",
            "audit-feature-mart",
            ["leakage"],
        ),
        md(
            """## Backtest de modelos

Ridge sirve como referencia interpretable. El boosting principal aprende una corrección residual conservadora de 25% sobre el rezago de la misma familia; si falta ese rezago usa una predicción directa. El factor se fijó usando el fold 2018, anterior al gate principal 2021. Imputación, escalamiento y categorías se ajustan sólo con targets anteriores.""",
            "model-evaluation-question",
        ),
        code(
            """model_metrics, model_predictions, feature_importance, model_decision = evaluate_models(
    PROJECT_ROOT, feature_mart
)
display(model_metrics)
display(pd.Series(model_decision).to_frame("valor"))""",
            "run-feature-model-backtests",
            ["artifact-model-metrics", "artifact-model-predictions", "artifact-model-decision"],
        ),
        code(
            """primary = model_metrics[model_metrics.target_year.eq(2021)].copy()
primary["weighted_mae_pp"] = 100 * primary["identified_weighted_mae"]
primary["coverage_pct"] = 100 * primary["section_coverage"]
display(primary[["model_id", "weighted_mae_pp", "coverage_pct", "bias", "share_within_5pp"]])

selected = model_decision["selected_for_next_phase"]
status = "APROBADO" if model_decision["candidate_approved"] else "NO APROBADO"
display(Markdown(
    f"**Gate principal: {status}.** Selección: `{selected}`. "
    f"Baseline congelado: `{100*model_decision['frozen_baseline_identified_weighted_mae']:.2f}` pp; "
    f"mejor candidato: `{100*model_decision['best_candidate_identified_weighted_mae']:.2f}` pp."
))""",
            "primary-gate-interpretation",
            ["gate"],
        ),
        md(
            """## Robustez, procedencia e interpretación

Se muestran los controles de deterioro y las variables más influyentes. La importancia por permutación es descriptiva sobre una muestra determinista y no implica causalidad.""",
            "model-interpretation-question",
        ),
        code(
            """display(pd.DataFrame(model_decision["robustness_checks"]))
top_importance = (
    feature_importance[
        feature_importance.model_id.eq("hist_gradient_boosting_electoral")
        & feature_importance.target_year.eq(2021)
    ]
    .sort_values("importance", ascending=False)
    .head(15)
)
display(top_importance)
display(pd.read_csv(PROJECT_ROOT / "artifacts/tables/model_run_registry.csv"))""",
            "show-model-provenance",
            ["artifact-model-importance", "artifact-model-registry"],
        ),
        code(
            """prediction_checks = {
    "emitted_predictions_are_probabilities": bool(
        model_predictions.prediction.dropna().between(0, 1).all()
    ),
    "eceg_models_only_evaluate_2024": set(
        model_metrics.loc[model_metrics.model_id.str.endswith("_eceg"), "target_year"]
    ) <= {2024},
    "training_years_are_strictly_prior": all(
        all(int(year) < int(row.target_year) for year in str(row.training_target_years).split("|"))
        for row in model_metrics.itertuples(index=False)
        if str(row.training_target_years)
    ),
}
display(pd.Series(prediction_checks, name="aprobado").to_frame())
assert all(prediction_checks.values())""",
            "audit-model-predictions",
            ["leakage", "validation"],
        ),
        md(
            """## Reporte final

El reporte reúne fuente, cobertura, métricas, decisión, robustez, importancia y registro de ejecución. Las tablas detalladas permanecen como artefactos máquina-legibles.""",
            "feature-report-question",
        ),
        code(
            """report_path = PROJECT_ROOT / "artifacts/reports/feature_model_evaluation.html"
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text("\\n".join([
    "<h1>RADAR 27 · Feature mart y evaluación temporal</h1>",
    "<p>Generado por notebooks/05_feature_model_evaluation.ipynb.</p>",
    "<h2>Fuente ECEG</h2>", eceg_manifest.to_html(index=False),
    "<h2>Cobertura del feature mart</h2>", feature_coverage.to_html(index=False),
    "<h2>Métricas</h2>", model_metrics.to_html(index=False),
    "<h2>Decisión</h2><pre>" + json.dumps(model_decision, ensure_ascii=False, indent=2) + "</pre>",
    "<h2>Robustez</h2>", pd.DataFrame(model_decision["robustness_checks"]).to_html(index=False),
    "<h2>Importancia principal 2021</h2>", top_importance.to_html(index=False),
]), encoding="utf-8")

required_outputs = [
    PROJECT_ROOT / "data/manifests/eceg_source_manifest.csv",
    PROJECT_ROOT / "artifacts/tables/eceg_2020_section_features.parquet",
    PROJECT_ROOT / "artifacts/tables/section_year_behavioral_features.parquet",
    PROJECT_ROOT / "artifacts/tables/feature_mart_ab.parquet",
    PROJECT_ROOT / "artifacts/tables/model_feature_lineage.csv",
    PROJECT_ROOT / "artifacts/tables/model_backtest_predictions.parquet",
    PROJECT_ROOT / "artifacts/tables/model_backtest_metrics.csv",
    PROJECT_ROOT / "artifacts/tables/model_errors_by_entity_class.csv",
    PROJECT_ROOT / "artifacts/tables/model_feature_importance.csv",
    PROJECT_ROOT / "artifacts/tables/model_run_registry.csv",
    PROJECT_ROOT / "artifacts/model_decision.json",
    report_path,
]
final_checks = {
    "all_outputs_exist": all(path.exists() for path in required_outputs),
    "source_hash_verified": eceg_manifest.validation_status.eq(
        "zip_signature_crc_paths_hash_verified"
    ).all(),
    "decision_is_explicit": selected in {
        "hist_gradient_boosting_electoral", "stable_plus_lineage_baseline"
    },
    **mart_checks,
    **prediction_checks,
}
display(pd.Series(final_checks, name="aprobado").to_frame())
assert all(final_checks.values())""",
            "write-feature-model-report",
            ["artifact-feature-model-report", "summary"],
        ),
        code(
            """display(Markdown(
    f"**Cierre.** `{sum(final_checks.values())}/{len(final_checks)}` controles pasaron. "
    f"La decisión quedó congelada en `artifacts/model_decision.json`. "
    f"Tiempo total: `{time.perf_counter()-RUN_STARTED:.1f}` s."
))""",
            "feature-model-final-interpretation",
            ["summary"],
        ),
    ]
    notebook = nbf.v4.new_notebook(cells=cells)
    notebook["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.12"},
    }
    return notebook


def notebook_06() -> nbf.NotebookNode:
    cells = [
        md(
            """# 06 · Incertidumbre conformal y robustez espacial

**Pregunta.** ¿El candidato aprobado produce intervalos temporalmente válidos y conserva su desempeño cuando se retienen entidades completas?

**Entradas.** Predicciones fuera de tiempo, feature mart A+B, decisión de modelo y `configs/uncertainty.yaml`.

**Método.** Intervalos conformales de residuo absoluto con calibración móvil estrictamente anterior al target y cuantiles por clase A/B cuando hay muestra suficiente. Como prueba espacial separada, cinco grupos deterministas retienen entidades completas tanto del entrenamiento histórico como de la evaluación.

**Criterio de honestidad.** El resultado 2021 sólo puede usar residuos 2018; el resultado 2024 puede usar 2018–2021. No se recalibra con el target que se evalúa. La prueba espacial es diagnóstico de transferencia, no el esquema de entrenamiento productivo.

**Salidas.** Intervalos, cobertura global y por subgrupo, predicciones espaciales, métricas de transferencia, decisión máquina-legible y reporte HTML.""",
            "uncertainty-intro",
            ["scope"],
        ),
        md(
            """## Entorno, configuración y entradas

Se comprueban las salidas congeladas del notebook 05 y se muestra el contrato antes de calcular resultados.""",
            "uncertainty-setup-question",
        ),
        code(
            """from pathlib import Path
import json
import time

import pandas as pd
import yaml
from IPython.display import Markdown, display

from radar27.modeling.uncertainty import (
    build_conformal_intervals,
    run_spatial_entity_holdout,
    write_uncertainty_decision,
)


def find_project_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "pyproject.toml").exists() and (candidate / "configs/uncertainty.yaml").exists():
            return candidate
    raise FileNotFoundError("No se encontró la raíz del proyecto")


PROJECT_ROOT = find_project_root(Path.cwd().resolve())
RUN_STARTED = time.perf_counter()
with (PROJECT_ROOT / "configs/uncertainty.yaml").open(encoding="utf-8") as stream:
    uncertainty_config = yaml.safe_load(stream)
required_inputs = [
    PROJECT_ROOT / "artifacts/model_decision.json",
    PROJECT_ROOT / "artifacts/tables/feature_mart_ab.parquet",
    PROJECT_ROOT / "artifacts/tables/model_backtest_predictions.parquet",
]
input_checks = {path.relative_to(PROJECT_ROOT).as_posix(): path.exists() for path in required_inputs}
display(pd.Series(input_checks, name="existe").to_frame())
display(pd.Series(uncertainty_config["conformal"], name="valor").to_frame())
assert all(input_checks.values())""",
            "uncertainty-setup",
            ["setup", "config"],
        ),
        md(
            """## Intervalos conformales móviles

El radio es el cuantil conformal finito de los errores absolutos fuera de tiempo. Se estratifica por clase territorial sólo si el estrato de calibración supera el mínimo configurado; de otro modo se usa el cuantil global y se registra el respaldo.""",
            "conformal-question",
        ),
        code(
            """intervals, coverage, calibration = build_conformal_intervals(PROJECT_ROOT)
overall_coverage = coverage[coverage.group_dimension.eq("overall")].copy()
display(calibration)
display(overall_coverage)""",
            "build-conformal-intervals",
            ["artifact-conformal-intervals", "artifact-conformal-coverage"],
        ),
        code(
            """conformal_checks = {
    "calibration_strictly_prior": bool(
        (intervals.max_calibration_target_year < intervals.target_year).all()
    ),
    "bounds_are_probabilities": bool(
        intervals.lower.dropna().between(0, 1).all()
        and intervals.upper.dropna().between(0, 1).all()
    ),
    "ordered_intervals": bool((intervals.lower <= intervals.upper).all()),
    "required_diagnostics_present": {
        "overall", "entity_id", "geography_confidence_class",
        "section_size_band", "predicted_risk_decile",
    } <= set(coverage.group_dimension),
}
display(pd.Series(conformal_checks, name="aprobado").to_frame())
assert all(conformal_checks.values())""",
            "audit-conformal-contract",
            ["leakage", "validation"],
        ),
        code(
            """coverage_2021 = overall_coverage.set_index("target_year").loc[2021]
coverage_2024 = overall_coverage.set_index("target_year").loc[2024]
display(Markdown(
    f"**Resultado temporal.** Con nominal de 90%, la cobertura observada es "
    f"`{100*coverage_2021.empirical_coverage:.2f}%` en 2021 y "
    f"`{100*coverage_2024.empirical_coverage:.2f}%` en 2024. "
    "La diferencia evidencia cambio entre elecciones; no se corrige usando información del target."
))""",
            "conformal-interpretation",
            ["interpretation"],
        ),
        md(
            """## Validación espacial con entidades retenidas

Las 32 entidades se reparten en cinco grupos por orden de ID. Para cada año y grupo, el modelo se reentrena sólo con años anteriores y sin ninguna fila histórica de las entidades evaluadas. Se compara contra el backtest temporal ordinario sobre exactamente las mismas unidades.""",
            "spatial-question",
        ),
        code(
            """spatial_predictions, spatial_metrics = run_spatial_entity_holdout(PROJECT_ROOT)
overall_spatial = spatial_metrics[spatial_metrics.scope.eq("overall")].copy()
display(overall_spatial)
display(
    spatial_metrics[spatial_metrics.scope.eq("entity_id")]
    .sort_values(["target_year", "weighted_mae_deterioration"], ascending=[True, False])
    .groupby("target_year", as_index=False)
    .head(5)
)""",
            "run-spatial-holdout",
            ["artifact-spatial-predictions", "artifact-spatial-metrics"],
        ),
        code(
            """spatial_checks = {
    "training_years_strictly_prior": bool(
        (spatial_predictions.max_training_target_year < spatial_predictions.target_year).all()
    ),
    "each_entity_is_held_out": bool(spatial_predictions.apply(
        lambda row: str(row.entity_id) in str(row.held_out_entities).split("|"), axis=1
    ).all()),
    "one_prediction_per_unit": not spatial_predictions.duplicated(
        ["target_year", "evaluation_unit_id"]
    ).any(),
    "predictions_are_probabilities": bool(
        spatial_predictions.spatial_holdout_prediction.between(0, 1).all()
    ),
}
display(pd.Series(spatial_checks, name="aprobado").to_frame())
assert all(spatial_checks.values())""",
            "audit-spatial-contract",
            ["leakage", "validation"],
        ),
        md(
            """## Decisión y reporte

Los umbrales configurados son diagnósticos de preparación, no una forma de seleccionar de nuevo el modelo. Una cobertura temporal insuficiente impide declarar listos los intervalos 2027 aunque el estrés espacial sea favorable.""",
            "uncertainty-decision-question",
        ),
        code(
            """uncertainty_decision = write_uncertainty_decision(
    PROJECT_ROOT, coverage, spatial_metrics
)
display(pd.Series(uncertainty_decision).to_frame("valor"))""",
            "write-uncertainty-decision",
            ["artifact-uncertainty-decision", "gate"],
        ),
        code(
            """report_path = PROJECT_ROOT / "artifacts/reports/uncertainty_spatial_validation.html"
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text("\\n".join([
    "<h1>RADAR 27 · Incertidumbre y robustez espacial</h1>",
    "<p>Generado por notebooks/06_uncertainty_spatial_validation.ipynb.</p>",
    "<h2>Calibración</h2>", calibration.to_html(index=False),
    "<h2>Cobertura global</h2>", overall_coverage.to_html(index=False),
    "<h2>Cobertura por subgrupo</h2>", coverage.to_html(index=False),
    "<h2>Robustez espacial global</h2>", overall_spatial.to_html(index=False),
    "<h2>Robustez espacial detallada</h2>", spatial_metrics.to_html(index=False),
    "<h2>Decisión</h2><pre>" + json.dumps(
        uncertainty_decision, ensure_ascii=False, indent=2
    ) + "</pre>",
]), encoding="utf-8")

required_outputs = [
    PROJECT_ROOT / "artifacts/tables/conformal_backtest_intervals.parquet",
    PROJECT_ROOT / "artifacts/tables/conformal_coverage_metrics.csv",
    PROJECT_ROOT / "artifacts/tables/conformal_calibration_summary.csv",
    PROJECT_ROOT / "artifacts/tables/spatial_holdout_predictions.parquet",
    PROJECT_ROOT / "artifacts/tables/spatial_robustness_metrics.csv",
    PROJECT_ROOT / "artifacts/uncertainty_decision.json",
    report_path,
]
final_checks = {
    "all_outputs_exist": all(path.exists() for path in required_outputs),
    **conformal_checks,
    **spatial_checks,
}
display(pd.Series(final_checks, name="aprobado").to_frame())
assert all(final_checks.values())""",
            "write-uncertainty-report",
            ["artifact-uncertainty-report", "summary"],
        ),
        code(
            """readiness = "LISTO" if uncertainty_decision["ready_for_first_2027_projection"] else "NO LISTO"
display(Markdown(
    f"**Cierre: {readiness} para proyectar 2027 con intervalos.** "
    f"La validación espacial pasa: `{uncertainty_decision['spatial_deterioration_diagnostic_passes']}`; "
    f"la cobertura conformal pasa: `{uncertainty_decision['global_coverage_diagnostic_passes']}`. "
    f"Tiempo total: `{time.perf_counter()-RUN_STARTED:.1f}` s."
))""",
            "uncertainty-final-interpretation",
            ["summary"],
        ),
    ]
    notebook = nbf.v4.new_notebook(cells=cells)
    notebook["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.12"},
    }
    return notebook


def notebook_07() -> nbf.NotebookNode:
    cells = [
        md(
            """# 07 · Adaptación al cambio nacional y calibración por familia electoral

**Pregunta.** ¿Puede corregirse el fallo de cobertura 2021 usando únicamente señales disponibles antes de cada elección, sin perder robustez en 2024?

**Entradas.** Feature mart A+B, predicciones del candidato aprobado, intervalos del notebook 06 y `configs/calibration_adaptation.yaml`.

**Método.** La predicción suma el cambio nacional observado en el ciclo anterior de la misma familia, separado por seis años. Se comparan el conformal móvil original, el conformal móvil con centro corregido y un intervalo de análogo familiar calibrado con la última elección de la misma familia. Cuando el candidato no tiene predicción fuera de tiempo para el análogo 2015, se usa explícitamente el baseline de mismo tipo como arranque frío.

**Criterios.** Todas las fuentes deben preceder al target; el MAE 2021 debe mejorar; el deterioro 2024 no puede superar 0.5 pp; la cobertura global debe superar 85% en ambos targets. Alcanzar ese piso habilita experimentación 2027, pero sólo 90% en todos los targets permitiría hablar de intervalos publicables.

**Salidas.** Correcciones nacionales, predicciones corregidas, comparación de intervalos, decisión máquina-legible y reporte HTML.""",
            "adaptation-intro",
            ["scope"],
        ),
        md(
            """## Configuración y entradas

Se fija la regla antes de evaluar resultados. No se aprende un factor con 2021 ni 2024: se traslada exactamente el cambio nacional del ciclo comparable anterior.""",
            "adaptation-setup-question",
        ),
        code(
            """from pathlib import Path
import json
import time

import pandas as pd
import yaml
from IPython.display import Markdown, display

from radar27.modeling.calibration_adaptation import (
    build_adaptive_interval_comparison,
    build_shift_corrected_predictions,
    estimate_national_shift,
    write_adaptation_decision,
)


def find_project_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "pyproject.toml").exists() and (
            candidate / "configs/calibration_adaptation.yaml"
        ).exists():
            return candidate
    raise FileNotFoundError("No se encontró la raíz del proyecto")


PROJECT_ROOT = find_project_root(Path.cwd().resolve())
RUN_STARTED = time.perf_counter()
with (PROJECT_ROOT / "configs/calibration_adaptation.yaml").open(encoding="utf-8") as stream:
    adaptation_config = yaml.safe_load(stream)
required_inputs = [
    PROJECT_ROOT / "artifacts/tables/feature_mart_ab.parquet",
    PROJECT_ROOT / "artifacts/tables/model_backtest_predictions.parquet",
    PROJECT_ROOT / "artifacts/tables/conformal_backtest_intervals.parquet",
    PROJECT_ROOT / "artifacts/uncertainty_decision.json",
]
input_checks = {path.relative_to(PROJECT_ROOT).as_posix(): path.exists() for path in required_inputs}
display(pd.Series(input_checks, name="existe").to_frame())
display(pd.Series(adaptation_config["national_shift"], name="valor").to_frame())
assert all(input_checks.values())""",
            "adaptation-setup",
            ["setup", "config"],
        ),
        md(
            """## Corrección nacional fuera de tiempo

Para cada target se calcula la diferencia ponderada `actual - rezago de misma familia` seis años antes. La fila 2027 es sólo un parámetro operacional derivado de 2021; no es una predicción.""",
            "national-shift-question",
        ),
        code(
            """shift_estimates = estimate_national_shift(PROJECT_ROOT)
shift_predictions, shift_metrics = build_shift_corrected_predictions(
    PROJECT_ROOT, shift_estimates
)
display(shift_estimates)
display(shift_metrics)""",
            "estimate-national-shift",
            ["artifact-shift-estimates", "artifact-shift-predictions", "artifact-shift-metrics"],
        ),
        code(
            """shift_checks = {
    "all_sources_strictly_prior": bool(shift_estimates.source_strictly_prior.all()),
    "evaluated_families_match": bool(
        shift_estimates.loc[
            shift_estimates.target_year.isin([2021, 2024, 2027]), "family_match"
        ].all()
    ),
    "probability_bounds": bool(
        shift_predictions.prediction_shift_corrected.dropna().between(0, 1).all()
    ),
    "primary_mae_improves": bool(
        shift_metrics.set_index("target_year").loc[2021, "weighted_mae_change"] < 0
    ),
    "secondary_deterioration_within_05pp": bool(
        shift_metrics.set_index("target_year").loc[2024, "weighted_mae_change"] <= 0.005
    ),
}
display(pd.Series(shift_checks, name="aprobado").to_frame())
assert all(shift_checks.values())""",
            "audit-national-shift",
            ["leakage", "validation"],
        ),
        code(
            """primary = shift_metrics.set_index("target_year").loc[2021]
display(Markdown(
    f"**Resultado puntual 2021.** El MAE ponderado cambia de "
    f"`{100*primary.original_weighted_mae:.2f}` a `{100*primary.corrected_weighted_mae:.2f}` pp "
    f"y el sesgo de `{100*primary.original_weighted_bias:.2f}` a "
    f"`{100*primary.corrected_weighted_bias:.2f}` pp."
))""",
            "national-shift-interpretation",
            ["interpretation"],
        ),
        md(
            """## Comparación de intervalos adaptativos

El método de análogo familiar cambia la distribución de calibración, no sólo el centro. Para 2021 usa errores del baseline 2015 porque el candidato aún no tenía historia entrenable; para 2024 usa los errores fuera de tiempo del candidato 2018. Esta adaptación es empírica y no se presenta como garantía conformal bajo intercambiabilidad.""",
            "adaptive-interval-question",
        ),
        code(
            """adaptive_intervals, adaptive_coverage, adaptive_calibration = (
    build_adaptive_interval_comparison(PROJECT_ROOT, shift_predictions)
)
overall_coverage = adaptive_coverage[
    adaptive_coverage.group_dimension.eq("overall")
].copy()
display(overall_coverage[[
    "interval_method", "target_year", "empirical_coverage",
    "identified_weighted_coverage", "mean_interval_width",
]])
display(adaptive_calibration)""",
            "compare-adaptive-intervals",
            ["artifact-adaptive-intervals", "artifact-adaptive-coverage", "artifact-adaptive-calibration"],
        ),
        code(
            """interval_checks = {
    "calibration_strictly_prior": bool(
        (adaptive_intervals.max_calibration_target_year < adaptive_intervals.target_year).all()
    ),
    "one_interval_per_method_unit": not adaptive_intervals.duplicated(
        ["interval_method", "target_year", "evaluation_unit_id"]
    ).any(),
    "ordered_bounds": bool((adaptive_intervals.lower <= adaptive_intervals.upper).all()),
    "bounds_are_probabilities": bool(
        adaptive_intervals.lower.dropna().between(0, 1).all()
        and adaptive_intervals.upper.dropna().between(0, 1).all()
    ),
}
display(pd.Series(interval_checks, name="aprobado").to_frame())
assert all(interval_checks.values())""",
            "audit-adaptive-intervals",
            ["leakage", "validation"],
        ),
        md(
            """## Decisión

Se distingue entre habilitar una primera canalización experimental 2027 y afirmar que los intervalos son publicables. El segundo estándar exige cobertura nominal en todos los targets y es deliberadamente más estricto.""",
            "adaptation-decision-question",
        ),
        code(
            """adaptation_decision = write_adaptation_decision(
    PROJECT_ROOT, shift_metrics, adaptive_coverage
)
display(pd.Series(adaptation_decision).to_frame("valor"))""",
            "write-adaptation-decision",
            ["artifact-adaptation-decision", "gate"],
        ),
        code(
            """report_path = PROJECT_ROOT / "artifacts/reports/calibration_adaptation.html"
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text("\\n".join([
    "<h1>RADAR 27 · Adaptación de calibración</h1>",
    "<p>Generado por notebooks/07_calibration_adaptation.ipynb.</p>",
    "<h2>Correcciones nacionales</h2>", shift_estimates.to_html(index=False),
    "<h2>Métricas puntuales</h2>", shift_metrics.to_html(index=False),
    "<h2>Comparación de cobertura</h2>", overall_coverage.to_html(index=False),
    "<h2>Calibración</h2>", adaptive_calibration.to_html(index=False),
    "<h2>Decisión</h2><pre>" + json.dumps(
        adaptation_decision, ensure_ascii=False, indent=2
    ) + "</pre>",
]), encoding="utf-8")

required_outputs = [
    PROJECT_ROOT / "artifacts/tables/national_shift_estimates.csv",
    PROJECT_ROOT / "artifacts/tables/shift_corrected_predictions.parquet",
    PROJECT_ROOT / "artifacts/tables/shift_correction_metrics.csv",
    PROJECT_ROOT / "artifacts/tables/adaptive_interval_predictions.parquet",
    PROJECT_ROOT / "artifacts/tables/adaptive_interval_coverage.csv",
    PROJECT_ROOT / "artifacts/tables/adaptive_interval_calibration.csv",
    PROJECT_ROOT / "artifacts/calibration_adaptation_decision.json",
    report_path,
]
final_checks = {
    "all_outputs_exist": all(path.exists() for path in required_outputs),
    **shift_checks,
    **interval_checks,
}
display(pd.Series(final_checks, name="aprobado").to_frame())
assert all(final_checks.values())""",
            "write-adaptation-report",
            ["artifact-adaptation-report", "summary"],
        ),
        code(
            """display(Markdown(
    f"**Cierre.** Experimental 2027: "
    f"`{adaptation_decision['approved_for_experimental_2027_pipeline']}`. "
    f"Intervalo publicable: `{adaptation_decision['public_interval_ready']}`. "
    f"Tiempo total: `{time.perf_counter()-RUN_STARTED:.1f}` s."
))""",
            "adaptation-final-interpretation",
            ["summary"],
        ),
    ]
    notebook = nbf.v4.new_notebook(cells=cells)
    notebook["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.12"},
    }
    return notebook


def notebook_08() -> nbf.NotebookNode:
    cells = [
        md(
            """# 08 · Proyección experimental 2027 actualizada

**Objetivo.** Construir una proyección seccional auditable para 2027 usando sólo información electoral hasta 2024, manteniendo separados el baseline, la corrección aprendida por árboles, el ajuste nacional y la incertidumbre.

**Baseline.** Participación 2021 de la misma sección o componente territorial oficial. Para C/D se usa la jerarquía sección→componente→municipio→entidad→nacional. En los backtests este baseline A+B tuvo MAE ponderado de 9.38 pp en 2021 y 4.42 pp en 2024.

**Modelo seleccionado.** `HistGradientBoostingRegressor` con `territorial_context`, ganador de la comparación controlada contra XGBoost, LightGBM y Extra Trees. Predice el residual sobre el baseline; sólo se aplica 25% de esa corrección. Después se suma, por separado, el desplazamiento nacional de +5.21 pp estimado con el ciclo intermedio 2015→2021.

**Corte.** Elecciones hasta 2024; geografía observada en el snapshot 2024; linajes públicos AMGE disponibles hasta 2022. No existe todavía marco seccional ni resultado 2027.

**Salidas.** Feature mart 2027, predicciones A/B por unidad, expansión a 70,751 secciones del snapshot, intervalos por clase, resumen, registro del modelo y decisión experimental.""",
            "forecast-2027-intro",
            ["scope"],
        ),
        md(
            """## Configuración y corte informativo

Se valida que ninguna elección posterior a 2024 entre al entrenamiento o a las variables. El target 2027 no aparece como outcome en ningún artefacto.""",
            "forecast-setup-question",
        ),
        code(
            """from pathlib import Path
import json
import time

import pandas as pd
import yaml
from IPython.display import Markdown, display

from radar27.modeling.forecast_2027 import (
    build_forecast_feature_mart,
    expand_to_section_forecast,
    train_and_predict_2027,
    write_forecast_decision,
)


def find_project_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "pyproject.toml").exists() and (
            candidate / "configs/forecast_2027.yaml"
        ).exists():
            return candidate
    raise FileNotFoundError("No se encontró la raíz del proyecto")


PROJECT_ROOT = find_project_root(Path.cwd().resolve())
RUN_STARTED = time.perf_counter()
with (PROJECT_ROOT / "configs/forecast_2027.yaml").open(encoding="utf-8") as stream:
    forecast_config = yaml.safe_load(stream)
required_inputs = [
    PROJECT_ROOT / "artifacts/tables/feature_ablation_mart.parquet",
    PROJECT_ROOT / "artifacts/tables/national_shift_estimates.csv",
    PROJECT_ROOT / "artifacts/tables/tabular_challenger_predictions.parquet",
    PROJECT_ROOT / "artifacts/tables/tabular_challenger_metrics.csv",
    PROJECT_ROOT / "artifacts/tabular_challenger_decision.json",
]
input_checks = {path.relative_to(PROJECT_ROOT).as_posix(): path.exists() for path in required_inputs}
display(pd.Series(input_checks, name="existe").to_frame())
display(pd.Series(forecast_config, name="valor").to_frame())
assert all(input_checks.values())""",
            "forecast-2027-setup",
            ["setup", "config"],
        ),
        md(
            """## Feature mart operacional enriquecido

Las unidades A son secciones estables; las B son componentes de linaje oficial. Las variables terminan en 2024 y el rezago de misma familia es 2021. Se añaden promedios y diferencias relativas frente a la entidad y al país, calculados sólo con rezagos.""",
            "forecast-feature-question",
        ),
        code(
            """forecast_features = build_forecast_feature_mart(PROJECT_ROOT)
feature_checks = {
    "unit_id_unique": forecast_features.evaluation_unit_id.is_unique,
    "only_A_B": set(forecast_features.geography_confidence_class) == {"A", "B"},
    "all_features_before_2027": bool(
        (forecast_features.max_electoral_feature_year < 2027).all()
    ),
    "no_target_outcome": "actual" not in forecast_features,
    "territorial_context_available": all(
        column in forecast_features
        for column in [
            "entity_same_type_mean", "same_type_minus_entity_mean",
            "national_same_type_mean", "geography_unit_type",
        ]
    ),
    "context_is_prior": bool(
        (forecast_features.context_source_max_year < 2027).all()
    ),
}
display(pd.Series(feature_checks, name="aprobado").to_frame())
display(forecast_features.groupby("geography_confidence_class").agg(
    units=("evaluation_unit_id", "size"),
    sections=("target_sections_represented", "sum"),
))
assert all(feature_checks.values())""",
            "build-forecast-2027-features",
            ["artifact-forecast-features", "leakage"],
        ),
        md(
            """## Entrenamiento del boosting residual

El modelo no predice desde cero cuando existe baseline. Los árboles estiman `participación real − participación de la elección anterior del mismo tipo`; se aplica 25% de esa corrección para limitar sobreajuste. El ajuste nacional permanece en otra columna.""",
            "forecast-model-question",
        ),
        code(
            """model_units, model_registry = train_and_predict_2027(
    PROJECT_ROOT, forecast_features
)
display(pd.Series({
    "model_id": model_registry["model_id"],
    "family": model_registry["model_family"],
    "feature_group": model_registry["feature_set"],
    "training_years": model_registry["training_target_years"],
    "training_units": model_registry["training_units"],
    "residual_shrinkage": model_registry["residual_shrinkage"],
    "national_shift_pp": 100 * model_registry["national_shift_correction"],
}).to_frame("valor"))
display(pd.Series(model_registry["hyperparameters"]).to_frame("valor"))""",
            "train-forecast-2027-model",
            ["artifact-forecast-model-units", "artifact-forecast-model-registry"],
        ),
        code(
            """model_checks = {
    "training_stops_in_2024": model_registry["maximum_training_target_year"] == 2024,
    "selected_model_id": model_registry["model_id"] == "hist_gradient_boosting",
    "selected_feature_group": model_registry["feature_set"] == "territorial_context",
    "frozen_shrinkage": model_registry["residual_shrinkage"] == 0.25,
    "predictions_are_probabilities": bool(
        model_units.experimental_prediction.between(0, 1).all()
    ),
}
display(pd.Series(model_checks, name="aprobado").to_frame())
assert all(model_checks.values())""",
            "audit-forecast-2027-model",
            ["validation"],
        ),
        md(
            """## Cobertura territorial e incertidumbre

El modelo se aplica a A/B. Sus radios se recalibran con errores fuera de tiempo 2021 del modelo territorial. Las clases C/D reciben el baseline jerárquico más la corrección nacional y radios de errores C/D de 2021. La expansión usa el snapshot 2024 y no afirma conocer cambios territoriales futuros.""",
            "forecast-expansion-question",
        ),
        code(
            """section_forecast, forecast_summary = expand_to_section_forecast(
    PROJECT_ROOT, model_units
)
display(forecast_summary[
    forecast_summary.group_dimension.isin([
        "overall", "geography_confidence_class", "prediction_strategy"
    ])
])
display(pd.read_csv(PROJECT_ROOT / "artifacts/tables/forecast_2027_interval_calibration.csv"))""",
            "expand-forecast-2027-sections",
            ["artifact-forecast-sections", "artifact-forecast-summary", "artifact-forecast-calibration"],
        ),
        code(
            """section_checks = {
    "snapshot_sections_unique": section_forecast.section_key_observed.is_unique,
    "snapshot_section_count": len(section_forecast) == 70_751,
    "all_classes_present": set(section_forecast.geography_confidence_class) == {"A", "B", "C", "D"},
    "all_sections_predicted": bool(section_forecast.experimental_prediction.notna().all()),
    "intervals_ordered": bool(
        (section_forecast.lower <= section_forecast.experimental_prediction).all()
        and (section_forecast.experimental_prediction <= section_forecast.upper).all()
    ),
    "snapshot_not_future_geography": section_forecast.forecast_geography_status.eq(
        "2024_snapshot_not_2027_certified"
    ).all(),
}
display(pd.Series(section_checks, name="aprobado").to_frame())
assert all(section_checks.values())""",
            "audit-forecast-2027-sections",
            ["validation", "geography"],
        ),
        md(
            """## Comparación histórica y decisión

No existe MAE 2027 porque aún no hay resultado real. La referencia disponible son backtests históricos contra el baseline de última elección de la misma familia.""",
            "forecast-decision-question",
        ),
        code(
            """forecast_decision = write_forecast_decision(
    PROJECT_ROOT, model_units, section_forecast, forecast_summary, model_registry
)
historical_comparison = pd.DataFrame(forecast_decision["historical_mae_comparison"])
historical_comparison["baseline_mae_pp"] = 100 * historical_comparison["baseline_weighted_mae"]
historical_comparison["corrected_model_mae_pp"] = 100 * historical_comparison[
    "corrected_boosting_weighted_mae"
]
historical_comparison["change_pp"] = 100 * historical_comparison["mae_change_vs_baseline"]
display(historical_comparison[[
    "target_year", "baseline_model", "baseline_mae_pp",
    "corrected_model_mae_pp", "change_pp",
]])
display(pd.Series(forecast_decision).to_frame("valor"))""",
            "write-forecast-2027-decision",
            ["artifact-forecast-decision", "gate"],
        ),
        code(
            """report_path = PROJECT_ROOT / "artifacts/reports/forecast_2027_experimental.html"
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text("\\n".join([
    "<h1>RADAR 27 · Proyección experimental 2027</h1>",
    "<p>Generado por notebooks/08_forecast_2027_experimental.ipynb.</p>",
    "<h2>Modelo</h2><pre>" + json.dumps(model_registry, ensure_ascii=False, indent=2) + "</pre>",
    "<h2>Comparación histórica</h2>", historical_comparison.to_html(index=False),
    "<h2>Resumen de proyección</h2>", forecast_summary.to_html(index=False),
    "<h2>Decisión</h2><pre>" + json.dumps(
        forecast_decision, ensure_ascii=False, indent=2
    ) + "</pre>",
]), encoding="utf-8")

required_outputs = [
    PROJECT_ROOT / "artifacts/tables/forecast_2027_feature_mart.parquet",
    PROJECT_ROOT / "artifacts/tables/forecast_2027_model_units.parquet",
    PROJECT_ROOT / "artifacts/tables/forecast_2027_section_predictions.parquet",
    PROJECT_ROOT / "artifacts/tables/forecast_2027_interval_calibration.csv",
    PROJECT_ROOT / "artifacts/tables/forecast_2027_summary.csv",
    PROJECT_ROOT / "artifacts/forecast_2027_model_registry.json",
    PROJECT_ROOT / "artifacts/forecast_2027_decision.json",
    report_path,
]
final_checks = {
    "all_outputs_exist": all(path.exists() for path in required_outputs),
    **feature_checks,
    **model_checks,
    **section_checks,
}
display(pd.Series(final_checks, name="aprobado").to_frame())
assert all(final_checks.values())""",
            "write-forecast-2027-report",
            ["artifact-forecast-report", "summary"],
        ),
        code(
            """overall = forecast_summary[
    forecast_summary.group_dimension.eq("overall")
].iloc[0]
display(Markdown(
    f"**Cierre experimental.** Se proyectaron `{len(section_forecast):,}` secciones del snapshot 2024. "
    f"Promedio ponderado por lista nominal actual: "
    f"`{100*overall.weighted_experimental_prediction:.2f}%`. "
    "No es resultado oficial, estimación de votos ni garantía pública. "
    f"Tiempo total: `{time.perf_counter()-RUN_STARTED:.1f}` s."
))""",
            "forecast-2027-final-interpretation",
            ["summary"],
        ),
    ]
    notebook = nbf.v4.new_notebook(cells=cells)
    notebook["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.12"},
    }
    return notebook


def notebook_09() -> nbf.NotebookNode:
    cells = [
        md(
            """# 09 · Ablación de variables sociodemográficas y territoriales

**Objetivo.** Determinar qué grupos de variables agregan señal real manteniendo fijo el algoritmo. Se evita confundir una mejora por features con una mejora por cambiar simultáneamente de modelo.

**Baseline de MAE.** Última participación de la misma familia electoral para sección estable o componente oficial A+B (`lag_same_type_stable_plus_official_lineage`).

**Modelo constante.** `HistGradientBoostingRegressor` residual, con los mismos hiperparámetros, contracción 0.25 y corrección nacional de los notebooks anteriores.

**Grupos.** Historia mínima; demografía electoral por sexo/edad; contexto relativo a entidad/nación; combinación demografía+contexto; ECEG; combinación completa.

**Regla temporal.** Los grupos sin ECEG se prueban en 2018, 2021 y 2024. ECEG 2020 sólo se prueba en el origen 2024 porque su publicación oficial es posterior a la elección 2021.

**Salidas.** Mart enriquecido, predicciones, métricas, registro de variables, decisión de promoción y reporte HTML.""",
            "feature-ablation-intro",
            ["scope"],
        ),
        md(
            """## Configuración y entradas

El algoritmo y sus hiperparámetros permanecen congelados. La única dimensión experimental es el conjunto de variables.""",
            "feature-ablation-setup-question",
        ),
        code(
            """from pathlib import Path
import json
import time

import pandas as pd
import yaml
from IPython.display import Markdown, display

from radar27.modeling.feature_enrichment import (
    build_enriched_feature_mart,
    run_feature_ablation,
    write_feature_ablation_decision,
)
from radar27.modeling.entity_cycle_adaptation import run_entity_cycle_adaptation


def find_project_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "pyproject.toml").exists() and (
            candidate / "configs/feature_ablation.yaml"
        ).exists():
            return candidate
    raise FileNotFoundError("No se encontró la raíz del proyecto")


PROJECT_ROOT = find_project_root(Path.cwd().resolve())
RUN_STARTED = time.perf_counter()
with (PROJECT_ROOT / "configs/feature_ablation.yaml").open(encoding="utf-8") as stream:
    ablation_config = yaml.safe_load(stream)
required_inputs = [
    PROJECT_ROOT / "artifacts/tables/feature_mart_ab.parquet",
    PROJECT_ROOT / "artifacts/tables/eceg_2020_section_features.parquet",
    PROJECT_ROOT / "artifacts/tables/national_shift_estimates.csv",
    PROJECT_ROOT / "artifacts/tables/backtest_metrics.csv",
]
input_checks = {path.relative_to(PROJECT_ROOT).as_posix(): path.exists() for path in required_inputs}
display(pd.Series(input_checks, name="existe").to_frame())
display(pd.DataFrame(ablation_config["feature_groups"]).T)
assert all(input_checks.values())""",
            "feature-ablation-setup",
            ["setup", "config"],
        ),
        md(
            """## Contexto territorial previo al target

Se calculan promedios y dispersiones de la participación rezagada por entidad y nación, así como la diferencia de cada unidad frente a esos referentes. Sólo se usan columnas conocidas antes del target.""",
            "feature-context-question",
        ),
        code(
            """ablation_mart = build_enriched_feature_mart(PROJECT_ROOT)
context_checks = {
    "unit_target_unique": not ablation_mart.duplicated(
        ["target_year", "evaluation_unit_id"]
    ).any(),
    "context_strictly_prior": bool(
        (ablation_mart.context_source_max_year < ablation_mart.target_year).all()
    ),
    "geography_type_available": bool(ablation_mart.geography_unit_type.notna().all()),
}
display(pd.Series(context_checks, name="aprobado").to_frame())
display(ablation_mart[[
    "target_year", "evaluation_unit_id", "entity_same_type_mean",
    "same_type_minus_entity_mean", "national_same_type_mean",
    "geography_unit_type",
]].head())
assert all(context_checks.values())""",
            "build-feature-ablation-mart",
            ["artifact-feature-ablation-mart", "leakage"],
        ),
        md(
            """## Backtests de ablación

Cada fila cambia únicamente el conjunto de variables. Se reporta el MAE ponderado después de aplicar la misma corrección nacional usada por la proyección experimental.""",
            "feature-ablation-question",
        ),
        code(
            """ablation_predictions, ablation_metrics, ablation_registry = run_feature_ablation(
    PROJECT_ROOT, ablation_mart
)
display(ablation_metrics[[
    "target_year", "feature_group", "availability",
    "baseline_weighted_mae", "identified_weighted_mae",
    "mae_change_vs_baseline", "weighted_bias",
]])""",
            "run-feature-ablation",
            ["artifact-feature-ablation-predictions", "artifact-feature-ablation-metrics", "artifact-feature-ablation-registry"],
        ),
        code(
            """temporal_checks = {
    "eceg_only_2024": set(
        ablation_metrics.loc[
            ablation_metrics.availability.str.startswith("eceg_"), "target_year"
        ]
    ) == {2024},
    "strict_groups_all_folds": all(
        set(group.target_year) == {2018, 2021, 2024}
        for _, group in ablation_metrics[
            ablation_metrics.availability.eq("strict_all_targets")
        ].groupby("feature_group")
    ),
    "training_years_prior": all(
        all(int(year) < int(row.target_year) for year in str(row.training_target_years).split("|"))
        for row in ablation_registry.itertuples(index=False)
    ),
}
display(pd.Series(temporal_checks, name="aprobado").to_frame())
assert all(temporal_checks.values())""",
            "audit-feature-ablation-time",
            ["leakage", "validation"],
        ),
        md(
            """## Decisión

La promoción estricta exige mejorar 2021 y no deteriorar los otros folds más de 0.5 pp frente al conjunto actual. ECEG exige al menos 0.1 pp de mejora en 2024 para justificar complejidad y evidencia de un solo fold.""",
            "feature-ablation-decision-question",
        ),
        code(
            """ablation_decision = write_feature_ablation_decision(
    PROJECT_ROOT, ablation_metrics
)
display(pd.Series(ablation_decision).to_frame("valor"))

entity_cycle_predictions, entity_cycle_metrics, entity_cycle_decision = (
    run_entity_cycle_adaptation(PROJECT_ROOT)
)
display(pd.Series(entity_cycle_decision).to_frame("valor"))""",
            "write-feature-ablation-decision",
            ["artifact-feature-ablation-decision", "artifact-entity-cycle-adaptation", "gate"],
        ),
        code(
            """strict_pivot = ablation_metrics[
    ablation_metrics.availability.eq("strict_all_targets")
].pivot(index="feature_group", columns="target_year", values="identified_weighted_mae")
strict_pivot = 100 * strict_pivot
display(strict_pivot.rename(columns=lambda year: f"MAE_{year}_pp"))

eceg_2024 = ablation_metrics[
    ablation_metrics.target_year.eq(2024)
].sort_values("identified_weighted_mae")
display(eceg_2024[["feature_group", "availability", "identified_weighted_mae"]])""",
            "interpret-feature-ablation",
            ["interpretation"],
        ),
        code(
            """report_path = PROJECT_ROOT / "artifacts/reports/feature_ablation.html"
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text("\\n".join([
    "<h1>RADAR 27 · Ablación de variables</h1>",
    "<p>Generado por notebooks/09_feature_ablation.ipynb.</p>",
    "<h2>Métricas</h2>", ablation_metrics.to_html(index=False),
    "<h2>Registro</h2>", ablation_registry.to_html(index=False),
    "<h2>Decisión</h2><pre>" + json.dumps(
        ablation_decision, ensure_ascii=False, indent=2
    ) + "</pre>",
    "<h2>Adaptación estatal</h2>", entity_cycle_metrics.to_html(index=False),
    "<pre>" + json.dumps(entity_cycle_decision, ensure_ascii=False, indent=2) + "</pre>",
]), encoding="utf-8")

required_outputs = [
    PROJECT_ROOT / "artifacts/tables/feature_ablation_mart.parquet",
    PROJECT_ROOT / "artifacts/tables/feature_ablation_predictions.parquet",
    PROJECT_ROOT / "artifacts/tables/feature_ablation_metrics.csv",
    PROJECT_ROOT / "artifacts/tables/feature_ablation_registry.csv",
    PROJECT_ROOT / "artifacts/feature_ablation_decision.json",
    PROJECT_ROOT / "artifacts/tables/entity_cycle_adaptation_predictions.parquet",
    PROJECT_ROOT / "artifacts/tables/entity_cycle_adaptation_metrics.csv",
    PROJECT_ROOT / "artifacts/entity_cycle_adaptation_decision.json",
    report_path,
]
final_checks = {
    "all_outputs_exist": all(path.exists() for path in required_outputs),
    **context_checks,
    **temporal_checks,
}
display(pd.Series(final_checks, name="aprobado").to_frame())
assert all(final_checks.values())""",
            "write-feature-ablation-report",
            ["artifact-feature-ablation-report", "summary"],
        ),
        code(
            """display(Markdown(
    f"**Cierre.** Grupo estricto seleccionado: "
    f"`{ablation_decision['selected_feature_group_for_2027']}`. "
    f"ECEG promovido: `{ablation_decision['eceg_promoted']}`. "
    f"Tiempo total: `{time.perf_counter()-RUN_STARTED:.1f}` s."
))""",
            "feature-ablation-final-interpretation",
            ["summary"],
        ),
    ]
    notebook = nbf.v4.new_notebook(cells=cells)
    notebook["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.12"},
    }
    return notebook


def notebook_10() -> nbf.NotebookNode:
    cells = [
        md(
            """# 10 · Challengers tabulares

**Objetivo.** Saber si XGBoost, LightGBM o Extra Trees predicen mejor que el `HistGradientBoostingRegressor` actual sin cambiar simultáneamente los datos ni la evaluación.

**Baseline del MAE.** Participación anterior de la misma familia electoral para sección estable o componente oficial A+B (`lag_same_type_stable_plus_official_lineage`).

**Control experimental.** Todos usan `territorial_context`, folds 2018/2021/2024, pesos por registros identificados, predicción residual con contracción 0.25 y la misma corrección nacional. Cada familia tiene una especificación moderada congelada; no hay búsqueda masiva con sólo tres targets.

**Gate.** Un challenger debe mejorar el MAE ponderado 2021 frente al boosting actual y no deteriorar 2018 ni 2024 más de 0.5 pp.""",
            "tabular-challengers-intro",
            ["scope"],
        ),
        code(
            """from pathlib import Path
import json
import time

import pandas as pd
import yaml
from IPython.display import Markdown, display

from radar27.modeling.tabular_challengers import (
    run_tabular_challengers,
    write_tabular_challenger_decision,
)


def find_project_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "pyproject.toml").exists() and (
            candidate / "configs/tabular_challengers.yaml"
        ).exists():
            return candidate
    raise FileNotFoundError("No se encontró la raíz del proyecto")


PROJECT_ROOT = find_project_root(Path.cwd().resolve())
RUN_STARTED = time.perf_counter()
with (PROJECT_ROOT / "configs/tabular_challengers.yaml").open(encoding="utf-8") as stream:
    challenger_config = yaml.safe_load(stream)
mart_path = PROJECT_ROOT / "artifacts/tables/feature_ablation_mart.parquet"
assert mart_path.exists()
challenger_mart = pd.read_parquet(mart_path)
display(pd.DataFrame(challenger_config["models"]).T)
display(Markdown(
    f"Se comparan `{len(challenger_config['models'])}` familias sobre "
    f"`{len(challenger_mart):,}` filas del mart y las mismas variables territoriales."
))""",
            "tabular-challengers-setup",
            ["setup", "config"],
        ),
        md(
            """## Backtests fuera de tiempo

Para cada elección, el entrenamiento contiene únicamente elecciones anteriores. Cada algoritmo ajusta un modelo directo de respaldo y otro que estima cuánto corregir el baseline.""",
            "tabular-challengers-question",
        ),
        code(
            """challenger_predictions, challenger_metrics, challenger_registry = (
    run_tabular_challengers(PROJECT_ROOT, challenger_mart)
)
metric_view = challenger_metrics.copy()
for column in [
    "baseline_weighted_mae", "identified_weighted_mae",
    "mae_change_vs_baseline", "mae_change_vs_reference",
]:
    metric_view[column] = 100 * metric_view[column]
display(metric_view[[
    "target_year", "model_id", "baseline_weighted_mae",
    "identified_weighted_mae", "mae_change_vs_reference", "fit_seconds",
]])""",
            "run-tabular-challengers",
            ["artifact-challenger-predictions", "artifact-challenger-metrics", "artifact-challenger-registry"],
        ),
        code(
            """audit_checks = {
    "same_feature_group": set(challenger_metrics.feature_group) == {"territorial_context"},
    "all_models_all_folds": all(
        set(group.target_year) == {2018, 2021, 2024}
        for _, group in challenger_metrics.groupby("model_id")
    ),
    "training_strictly_prior": all(
        all(int(year) < int(row.target_year) for year in str(row.training_target_years).split("|"))
        for row in challenger_registry.itertuples(index=False)
    ),
    "same_numeric_features_per_fold": bool(
        challenger_registry.groupby("target_year").numeric_features.nunique().eq(1).all()
    ),
    "same_categorical_features_per_fold": bool(
        challenger_registry.groupby("target_year").categorical_features.nunique().eq(1).all()
    ),
}
display(pd.Series(audit_checks, name="aprobado").to_frame())
assert all(audit_checks.values())""",
            "audit-tabular-challengers",
            ["leakage", "validation"],
        ),
        md(
            """## Decisión

2021 es el target principal congelado. Los otros dos años protegen contra una mejora accidental de un solo ciclo.""",
            "tabular-challengers-decision-question",
        ),
        code(
            """challenger_decision = write_tabular_challenger_decision(
    PROJECT_ROOT, challenger_metrics
)
display(pd.Series(challenger_decision).to_frame("valor"))""",
            "write-tabular-challenger-decision",
            ["artifact-challenger-decision", "gate"],
        ),
        code(
            """report_path = PROJECT_ROOT / "artifacts/reports/tabular_challengers.html"
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text("\\n".join([
    "<h1>RADAR 27 · Challengers tabulares</h1>",
    "<p>Generado por notebooks/10_tabular_challengers.ipynb.</p>",
    "<h2>Métricas</h2>", challenger_metrics.to_html(index=False),
    "<h2>Registro</h2>", challenger_registry.to_html(index=False),
    "<h2>Decisión</h2><pre>" + json.dumps(
        challenger_decision, ensure_ascii=False, indent=2
    ) + "</pre>",
]), encoding="utf-8")

required_outputs = [
    PROJECT_ROOT / "artifacts/tables/tabular_challenger_predictions.parquet",
    PROJECT_ROOT / "artifacts/tables/tabular_challenger_metrics.csv",
    PROJECT_ROOT / "artifacts/tables/tabular_challenger_registry.csv",
    PROJECT_ROOT / "artifacts/tabular_challenger_decision.json",
    report_path,
]
final_checks = {
    "all_outputs_exist": all(path.exists() for path in required_outputs),
    **audit_checks,
}
display(pd.Series(final_checks, name="aprobado").to_frame())
assert all(final_checks.values())""",
            "write-tabular-challenger-report",
            ["artifact-challenger-report", "summary"],
        ),
        code(
            """display(Markdown(
    f"**Cierre.** Mejor modelo en 2021: `{challenger_decision['best_primary_model']}`; "
    f"challenger promovido: `{challenger_decision['challenger_promoted']}`; "
    f"selección: `{challenger_decision['selected_model_for_next_iteration']}`. "
    f"Tiempo total: `{time.perf_counter()-RUN_STARTED:.1f}` s."
))""",
            "tabular-challengers-final-interpretation",
            ["summary"],
        ),
    ]
    notebook = nbf.v4.new_notebook(cells=cells)
    notebook["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.12"},
    }
    return notebook


def notebook_11() -> nbf.NotebookNode:
    cells = [
        md(
            """# 11 · Red neuronal densa como challenger

**Objetivo.** Comprobar si una red neuronal densa pequeña mejora al HistGradientBoosting seleccionado sin cambiar features, folds ni ajustes posteriores.

**Arquitectura.** `MLPRegressor` con dos capas ocultas de 64 y 32 neuronas ReLU. La entrada y el objetivo se estandarizan con estadísticas del entrenamiento. Adam usa parada temprana sobre una fracción interna que contiene sólo elecciones anteriores al target.

**Control.** Se conservan `territorial_context`, folds 2018/2021/2024, pesos por registros identificados, baseline de misma familia, contracción residual 0.25 y corrección nacional.

**Gate.** Debe mejorar el MAE ponderado 2021 y no deteriorar 2018/2024 más de 0.5 pp.""",
            "dense-neural-intro",
            ["scope"],
        ),
        code(
            """from pathlib import Path
import json
import time

import pandas as pd
import yaml
from IPython.display import Markdown, display

from radar27.modeling.neural_challenger import (
    run_dense_neural_challenger,
    write_dense_neural_decision,
)


def find_project_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "pyproject.toml").exists() and (
            candidate / "configs/dense_neural_challenger.yaml"
        ).exists():
            return candidate
    raise FileNotFoundError("No se encontró la raíz del proyecto")


PROJECT_ROOT = find_project_root(Path.cwd().resolve())
RUN_STARTED = time.perf_counter()
with (PROJECT_ROOT / "configs/dense_neural_challenger.yaml").open(encoding="utf-8") as stream:
    neural_config = yaml.safe_load(stream)
mart_path = PROJECT_ROOT / "artifacts/tables/feature_ablation_mart.parquet"
reference_path = PROJECT_ROOT / "artifacts/tables/tabular_challenger_metrics.csv"
assert mart_path.exists() and reference_path.exists()
neural_mart = pd.read_parquet(mart_path)
display(pd.Series(neural_config["network"], name="valor").to_frame())""",
            "dense-neural-setup",
            ["setup", "config"],
        ),
        md(
            """## Backtests fuera de tiempo

La red estima el mismo residual que los árboles. El objetivo se estandariza dentro de cada fold porque los residuales tienen una escala pequeña; la transformación se invierte antes de medir MAE.""",
            "dense-neural-question",
        ),
        code(
            """neural_predictions, neural_metrics, neural_registry = (
    run_dense_neural_challenger(PROJECT_ROOT, neural_mart)
)
metric_view = neural_metrics.copy()
for column in [
    "baseline_weighted_mae", "identified_weighted_mae",
    "reference_weighted_mae", "mae_change_vs_reference",
]:
    metric_view[column] = 100 * metric_view[column]
display(metric_view[[
    "target_year", "identified_weighted_mae", "reference_weighted_mae",
    "mae_change_vs_reference", "direct_iterations", "residual_iterations",
    "fit_seconds",
]])""",
            "run-dense-neural-challenger",
            ["artifact-neural-predictions", "artifact-neural-metrics", "artifact-neural-registry"],
        ),
        code(
            """audit_checks = {
    "same_feature_group": set(neural_metrics.feature_group) == {"territorial_context"},
    "all_folds": set(neural_metrics.target_year) == {2018, 2021, 2024},
    "training_strictly_prior": all(
        all(int(year) < int(row.target_year) for year in str(row.training_target_years).split("|"))
        for row in neural_registry.itertuples(index=False)
    ),
    "positive_target_scales": bool(
        neural_registry.direct_target_scale.gt(0).all()
        and neural_registry.residual_target_scale.gt(0).all()
    ),
    "finite_predictions": bool(neural_predictions.prediction.notna().all()),
}
display(pd.Series(audit_checks, name="aprobado").to_frame())
assert all(audit_checks.values())""",
            "audit-dense-neural-challenger",
            ["leakage", "validation"],
        ),
        code(
            """neural_decision = write_dense_neural_decision(PROJECT_ROOT, neural_metrics)
display(pd.Series(neural_decision).to_frame("valor"))""",
            "write-dense-neural-decision",
            ["artifact-neural-decision", "gate"],
        ),
        code(
            """report_path = PROJECT_ROOT / "artifacts/reports/dense_neural_challenger.html"
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text("\\n".join([
    "<h1>RADAR 27 · Red neuronal densa</h1>",
    "<p>Generado por notebooks/11_dense_neural_challenger.ipynb.</p>",
    "<h2>Métricas</h2>", neural_metrics.to_html(index=False),
    "<h2>Registro</h2>", neural_registry.to_html(index=False),
    "<h2>Decisión</h2><pre>" + json.dumps(
        neural_decision, ensure_ascii=False, indent=2
    ) + "</pre>",
]), encoding="utf-8")
required_outputs = [
    PROJECT_ROOT / "artifacts/tables/dense_neural_predictions.parquet",
    PROJECT_ROOT / "artifacts/tables/dense_neural_metrics.csv",
    PROJECT_ROOT / "artifacts/tables/dense_neural_registry.csv",
    PROJECT_ROOT / "artifacts/dense_neural_decision.json",
    report_path,
]
final_checks = {"all_outputs_exist": all(path.exists() for path in required_outputs), **audit_checks}
display(pd.Series(final_checks, name="aprobado").to_frame())
assert all(final_checks.values())""",
            "write-dense-neural-report",
            ["artifact-neural-report", "summary"],
        ),
        code(
            """display(Markdown(
    f"**Cierre.** MAE 2021 de la red: "
    f"`{100*neural_decision['challenger_primary_weighted_mae']:.2f} pp`; "
    f"referencia: `{100*neural_decision['reference_primary_weighted_mae']:.2f} pp`; "
    f"promovida: `{neural_decision['challenger_promoted']}`. "
    f"Tiempo total: `{time.perf_counter()-RUN_STARTED:.1f}` s."
))""",
            "dense-neural-final-interpretation",
            ["summary"],
        ),
    ]
    notebook = nbf.v4.new_notebook(cells=cells)
    notebook["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.12"},
    }
    return notebook


def main() -> None:
    output_dir = ROOT / "notebooks"
    output_dir.mkdir(parents=True, exist_ok=True)
    nbf.write(notebook_00(), output_dir / "00_setup_sources_download.ipynb")
    nbf.write(notebook_01(), output_dir / "01_raw_schema_audit.ipynb")
    nbf.write(notebook_02(), output_dir / "02_clean_ids_harmonization.ipynb")
    nbf.write(notebook_03(), output_dir / "03_geography_graph.ipynb")
    nbf.write(notebook_04(), output_dir / "04_panel_build_audit.ipynb")
    nbf.write(notebook_05(), output_dir / "05_feature_model_evaluation.ipynb")
    nbf.write(notebook_06(), output_dir / "06_uncertainty_spatial_validation.ipynb")
    nbf.write(notebook_07(), output_dir / "07_calibration_adaptation.ipynb")
    nbf.write(notebook_08(), output_dir / "08_forecast_2027_experimental.ipynb")
    nbf.write(notebook_09(), output_dir / "09_feature_ablation.ipynb")
    nbf.write(notebook_10(), output_dir / "10_tabular_challengers.ipynb")
    nbf.write(notebook_11(), output_dir / "11_dense_neural_challenger.ipynb")


if __name__ == "__main__":
    main()
