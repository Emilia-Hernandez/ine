"""Perfila por separado los dos procesos web de RADAR 27.

No modifica datos ni inicia un servidor. Debe ejecutarse una vez por aplicación
para que las mediciones de RSS no compartan imports ni cachés entre procesos.
"""

from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from pathlib import Path
from typing import Any

import psutil

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _maxrss_mib() -> float:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS reporta bytes; Linux reporta KiB.
    return value / 2**20 if value > 10_000_000 else value / 2**10


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("application", choices=("explorer", "simulator"))
    parser.add_argument("--exports", action="store_true")
    args = parser.parse_args()
    process = psutil.Process()

    def mark(stage: str, started: float | None = None, **extra: Any) -> None:
        print(
            json.dumps(
                {
                    "application": args.application,
                    "stage": stage,
                    "rss_mib": round(process.memory_info().rss / 2**20, 2),
                    "maxrss_mib": round(_maxrss_mib(), 2),
                    "elapsed_s": (
                        round(time.perf_counter() - started, 3)
                        if started is not None
                        else None
                    ),
                    **extra,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    mark("python_start")
    started = time.perf_counter()
    if args.application == "explorer":
        from dashboard.explorer_app import app
        from dashboard.app import ALL_PROFILES, ORANGE, WINE
        from dashboard.app import build_payload, distribution_figure
        from dashboard.app import load_sections, socio_figure, timeline_figure

        frame = load_sections()
        mark(
            "import_layout_and_data",
            started,
            callbacks=len(app.callback_map),
            rows=len(frame),
        )
        started = time.perf_counter()
        payload = build_payload(ALL_PROFILES, None, "internet", 100, 100)
        distribution_figure(payload["age"], WINE)
        distribution_figure(payload["sex"], ORANGE)
        socio_figure(payload["socio"])
        timeline_figure(payload)
        mark("aggregate_and_figures", started, sections=payload["section_count"])
        return

    from dashboard.data_layer import ALL_PROFILES
    from dashboard.simulator import coverage_count, eligible_sections, simulate
    from dashboard.simulator_app import app
    from dashboard.simulator_ui import simulation_aggregate_csv, simulation_csv_chunks

    frame = eligible_sections(ALL_PROFILES, include_insufficient=True)
    mark(
        "import_layout_and_data",
        started,
        callbacks=len(app.callback_map),
        rows=len(frame),
    )
    if args.exports:
        started = time.perf_counter()
        chunks, selected = simulation_csv_chunks(
            ALL_PROFILES,
            ["include"],
            100,
            100,
            "cumulative",
            63,
            len(frame),
            42,
        )
        byte_count = sum(len(chunk.encode("utf-8")) for chunk in chunks)
        mark(
            "sections_csv_100",
            started,
            rows=len(frame),
            selected=selected,
            bytes=byte_count,
        )
        started = time.perf_counter()
        aggregate_csv = simulation_aggregate_csv(
            ALL_PROFILES,
            ["include"],
            100,
            100,
            "cumulative",
            63,
            len(frame),
            42,
        )
        mark(
            "aggregate_csv_100",
            started,
            bytes=len(aggregate_csv.encode("utf-8")),
        )
        return
    for percent in (0, 25, 100):
        started = time.perf_counter()
        result = simulate(frame, coverage_count(len(frame), percent), seed=42)
        mark(
            f"coverage_{percent}",
            started,
            eligible=result["eligible_count"],
            selected=result["selected_count"],
        )


if __name__ == "__main__":
    main()
