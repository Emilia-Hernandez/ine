from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import nbformat
import yaml
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError
from nbconvert import HTMLExporter

ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_value(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ejecuta notebooks RADAR 27 con kernels separados")
    parser.add_argument("--only", action="append", default=[], help="ID de notebook a ejecutar")
    parser.add_argument("--timeout", type=int, default=1800, help="Timeout por celda, segundos")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with (ROOT / "configs/notebook_pipeline.yaml").open(encoding="utf-8") as stream:
        pipeline = yaml.safe_load(stream)
    entries = sorted(pipeline["notebooks"], key=lambda item: item["order"])
    if args.only:
        requested = set(args.only)
        entries = [item for item in entries if item["id"] in requested]
        unknown = requested - {item["id"] for item in entries}
        if unknown:
            raise SystemExit(f"IDs no encontrados: {sorted(unknown)}")

    profile = str(pipeline.get("profile", "notebooks")).replace("_", "-")
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + f"-{profile}"
    run_root = ROOT / "artifacts/runs" / run_id
    executed_dir = run_root / "notebooks"
    html_dir = run_root / "html"
    log_dir = run_root / "logs"
    for directory in (executed_dir, html_dir, log_dir):
        directory.mkdir(parents=True, exist_ok=False)

    run_metadata = {
        "run_id": run_id,
        "started_at_utc": datetime.now(UTC).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "git_commit": git_value("rev-parse", "HEAD"),
        "git_status": git_value("status", "--short"),
        "uv_lock_sha256": sha256_file(ROOT / "uv.lock"),
        "pipeline_sha256": sha256_file(ROOT / "configs/notebook_pipeline.yaml"),
        "notebooks": [],
    }
    artifact_rows = []
    status = "success"
    try:
        for entry in entries:
            source = ROOT / entry["path"]
            started = time.perf_counter()
            source_hash = sha256_file(source)
            notebook = nbformat.read(source, as_version=4)
            client = NotebookClient(
                notebook,
                timeout=args.timeout,
                kernel_name="python3",
                allow_errors=False,
                resources={"metadata": {"path": str(ROOT)}},
            )
            executed_path = executed_dir / source.name
            try:
                client.execute(cwd=str(ROOT))
            except Exception:
                status = "failed"
                nbformat.write(notebook, executed_path)
                raise
            nbformat.write(notebook, executed_path)
            exporter = HTMLExporter()
            exporter.exclude_input = False
            body, _ = exporter.from_notebook_node(notebook)
            html_path = html_dir / source.with_suffix(".html").name
            html_path.write_text(body, encoding="utf-8")
            record = {
                "id": entry["id"],
                "source": entry["path"],
                "source_sha256": source_hash,
                "executed_path": executed_path.relative_to(ROOT).as_posix(),
                "executed_sha256": sha256_file(executed_path),
                "html_path": html_path.relative_to(ROOT).as_posix(),
                "html_sha256": sha256_file(html_path),
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "status": "success",
            }
            run_metadata["notebooks"].append(record)
            for artifact in entry.get("artifacts", []):
                artifact_path = ROOT / artifact["path"]
                if not artifact_path.is_file():
                    raise FileNotFoundError(f"Artefacto declarado no encontrado: {artifact_path}")
                artifact_rows.append(
                    {
                        "artifact_id": f"{entry['id']}::{artifact_path.name}",
                        "artifact_path": artifact["path"],
                        "artifact_sha256": sha256_file(artifact_path),
                        "artifact_type": artifact["type"],
                        "notebook_path": entry["path"],
                        "notebook_source_sha256": source_hash,
                        "cell_id": artifact["cell_id"],
                        "cell_tag": artifact["cell_tag"],
                        "input_manifest_path": "data/manifests/source_manifest.csv",
                        "config_sha256": run_metadata["pipeline_sha256"],
                        "git_commit": run_metadata["git_commit"],
                        "run_id": run_id,
                        "model_id": "",
                        "fold_id": "",
                        "seed": "",
                        "generated_at": datetime.now(UTC).isoformat(),
                    }
                )
            (log_dir / f"{entry['id']}.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
            )
    except CellExecutionError as exc:
        print(str(exc), file=sys.stderr)
        status = "failed"
        return_code = 1
    except Exception as exc:  # noqa: BLE001 - el runner debe conservar evidencia ante cualquier fallo
        print(f"Fallo de ejecución: {exc}", file=sys.stderr)
        status = "failed"
        return_code = 1
    else:
        return_code = 0
    finally:
        run_metadata["finished_at_utc"] = datetime.now(UTC).isoformat()
        run_metadata["status"] = status
        (run_root / "run_manifest.json").write_text(
            json.dumps(run_metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if artifact_rows:
            with (run_root / "artifact_registry.csv").open(
                "w", newline="", encoding="utf-8"
            ) as stream:
                writer = csv.DictWriter(stream, fieldnames=list(artifact_rows[0]))
                writer.writeheader()
                writer.writerows(artifact_rows)
        print(run_root.relative_to(ROOT).as_posix())
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
