from __future__ import annotations

from pathlib import Path

from radar27.modeling.sociodemographic_similarity_challenger import (
    run_sociodemographic_similarity_challenger,
)


def main() -> None:
    _, metrics, _, graph_registry, decision = (
        run_sociodemographic_similarity_challenger(Path.cwd())
    )
    print(metrics.to_string(index=False))
    print(graph_registry.to_string(index=False))
    print(decision)


if __name__ == "__main__":
    main()
