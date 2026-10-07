from __future__ import annotations

from pathlib import Path

from radar27.modeling.entity_cycle_adaptation import run_entity_cycle_adaptation


def main() -> None:
    _, _, decision = run_entity_cycle_adaptation(Path.cwd())
    print(decision)


if __name__ == "__main__":
    main()
