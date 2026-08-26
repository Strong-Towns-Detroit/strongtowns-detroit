"""Command-line interface for the library-owned graphics build system."""

from __future__ import annotations

import argparse
from pathlib import Path
from collections.abc import Sequence

from strongtowns_detroit.graphics.builder import GraphicBuildSystem
from strongtowns_detroit.graphics.model import GraphicFormat


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="strongtowns-graphics",
        description="Discover and build semantic graphics into publishing targets.",
    )
    parser.add_argument(
        "--project",
        type=Path,
        help="graphics project root (automatically discovered by default)",
    )
    commands = parser.add_subparsers(dest="command")

    build = commands.add_parser("build", help="build all or selected graphics")
    build.add_argument("source", nargs="*", help="graphic source names")
    build.add_argument(
        "--target",
        action="append",
        choices=[item.value for item in GraphicFormat],
        help="publishing target; may be repeated",
    )

    commands.add_parser("list", help="list automatically discovered definitions")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        system = (
            GraphicBuildSystem(args.project)
            if args.project is not None
            else GraphicBuildSystem.find()
        )
        if args.command == "list":
            for definition in system.definitions():
                print(definition.name)
            return 0

        if args.command in (None, "build"):
            sources = args.source or None if args.command == "build" else None
            targets = args.target if args.command == "build" else None
            records = system.build(formats=targets, sources=sources)
            for record in records:
                kinds = ", ".join(sorted(record.files))
                print(
                    f"built {record.source}/{record.name} -> "
                    f"{record.target} ({kinds})"
                )
            return 0
    except (FileNotFoundError, ImportError, TypeError, ValueError) as error:
        _parser().error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
