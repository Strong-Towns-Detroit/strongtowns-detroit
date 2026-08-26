#!/usr/bin/env python3
"""Compatibility shim for the library-owned graphics build system."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from strongtowns_detroit.graphics import GraphicBuildSystem  # noqa: E402
from strongtowns_detroit.graphics.cli import main as cli_main  # noqa: E402

SOURCE_ROOT = HERE / "src"
OUTPUT_ROOT = HERE / "output"
SYSTEM = GraphicBuildSystem(HERE)
PROJECT = SYSTEM.project


def run(*, targets: list[str] | None = None, sources: list[str] | None = None) -> None:
    records = SYSTEM.build(formats=targets, sources=sources)
    for record in records:
        print(f"built {record.source}/{record.name} -> {record.target}")


def main() -> None:
    # Preserve the old ``build.py --target ... --source ...`` interface while
    # delegating all behavior to the installed library command.
    arguments = sys.argv[1:]
    sources: list[str] = []
    normalized: list[str] = ["--project", str(HERE), "build"]
    index = 0
    while index < len(arguments):
        if arguments[index] == "--source":
            index += 1
            if index >= len(arguments):
                raise SystemExit("--source requires a value")
            sources.append(arguments[index])
        else:
            normalized.append(arguments[index])
        index += 1
    normalized.extend(sources)
    raise SystemExit(cli_main(normalized))


if __name__ == "__main__":
    main()
