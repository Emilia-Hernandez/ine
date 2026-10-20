"""Perfila RADAR 27 con el patrón de un worker y dos hilos de Render.

Este script es de auditoría; no forma parte del arranque web ni modifica datos.
"""

from __future__ import annotations

import argparse
import json
import resource
import threading
import time
from typing import Any

import psutil


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full-export",
        action="store_true",
        help="consume un CSV de 70,751 filas y dos solicitudes concurrentes",
    )
    args = parser.parse_args()
    process = psutil.Process()

    def mark(stage: str, started: float | None = None, **extra: Any) -> None:
        print(
            json.dumps(
                {
                    "stage": stage,
                    "rss_mib": round(process.memory_info().rss / 2**20, 2),
                    "maxrss_mib": round(
                        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20, 2
                    ),
                    "elapsed_s": round(time.perf_counter() - started, 3)
                    if started
                    else None,
                    **extra,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    mark("python_start")
    started = time.perf_counter()
    from dashboard.app import (
        ALL_PROFILES,
        ORANGE,
        WINE,
        build_payload,
        distribution_figure,
        load_sections,
        socio_figure,
        timeline_figure,
    )
    from dashboard.data_layer import export_selection_csv_stream

    frame = load_sections()
    mark(
        "app_import_and_data",
        started,
        rows=len(frame),
        columns=len(frame.columns),
        dataframe_mib=round(frame.memory_usage(deep=True).sum() / 2**20, 2),
    )
    for percent in (10, 25, 50, 66, 100):
        started = time.perf_counter()
        payload = build_payload(ALL_PROFILES, None, "internet", percent, percent)
        mark(f"filters_{percent}", started, sections=payload["section_count"])

    started = time.perf_counter()
    payload = build_payload(ALL_PROFILES, str(frame.index[0]), "internet", 100, 100)
    distribution_figure(payload["age"], WINE)
    distribution_figure(payload["sex"], ORANGE)
    socio_figure(payload["socio"])
    timeline_figure(payload)
    mark("section_and_figures", started)

    if not args.full_export:
        return

    def consume(result: list[int], position: int) -> None:
        chunks, count = export_selection_csv_stream(ALL_PROFILES, 100, 100)
        result[position] = sum(len(chunk.encode("utf-8")) for chunk in chunks)
        if count != 70_751:
            raise RuntimeError(f"Conteo de exportación inesperado: {count}")

    started = time.perf_counter()
    sizes = [0]
    consume(sizes, 0)
    mark("full_export", started, bytes=sizes[0])

    started = time.perf_counter()
    sizes = [0, 0]
    threads = [threading.Thread(target=consume, args=(sizes, position)) for position in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    mark("two_export_requests", started, bytes=sum(sizes))


if __name__ == "__main__":
    main()
