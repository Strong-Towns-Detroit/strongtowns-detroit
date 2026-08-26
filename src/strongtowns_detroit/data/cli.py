"""CLI for reproducible Strong Towns data pipelines."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dotenv import load_dotenv

from .engine import DataBuildSystem
from .archive import DataArchive


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="strongtowns-data")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("list")
    commands.add_parser("status")
    graph = commands.add_parser("graph")
    graph.add_argument("--json", action="store_true")
    build = commands.add_parser("build")
    build.add_argument("pipeline", nargs="*")
    build.add_argument("--no-promote", action="store_true")
    fetch = commands.add_parser("fetch")
    fetch.add_argument("pipeline")
    fetch.add_argument("--apply", action="store_true")
    fetch.add_argument("--allow-paid", action="store_true")
    fetch.add_argument("--no-promote", action="store_true")
    verify = commands.add_parser("verify")
    verify.add_argument("asset", nargs="*")
    legacy = commands.add_parser("legacy-import")
    legacy.add_argument("asset", nargs="*")
    archive = commands.add_parser("archive")
    archive_commands = archive.add_subparsers(dest="archive_command", required=True)
    for name in ("status", "push", "pull"):
        command = archive_commands.add_parser(name)
        command.add_argument(
            "--tier", action="append",
            choices=["critical", "source", "deliverable"],
        )
        if name in {"push", "pull"}:
            command.add_argument("--apply", action="store_true")
    review = commands.add_parser("review")
    review_commands = review.add_subparsers(dest="review_command", required=True)
    review_commands.add_parser("export")
    review_import = review_commands.add_parser("import")
    review_import.add_argument("--no-promote", action="store_true")
    catalog = commands.add_parser("catalog")
    catalog_commands = catalog.add_subparsers(dest="catalog_command", required=True)
    catalog_inspect = catalog_commands.add_parser("inspect")
    catalog_inspect.add_argument("asset")
    catalog_query = catalog_commands.add_parser("query")
    catalog_query.add_argument("asset")
    catalog_query.add_argument("--sql", required=True)
    catalog_query.add_argument(
        "--format", choices=["table", "csv", "json"], default="table"
    )
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        system = DataBuildSystem.find()
        load_dotenv(system.root / ".env")
        if args.command == "list":
            for pipeline in system.pipelines or ():
                print(pipeline.name)
            return 0
        if args.command == "status":
            for record in system.status():
                states = ", ".join(
                    f"{item['id']}={item['state']}" for item in record["outputs"]
                )
                print(f"{record['pipeline']}: {states}")
            return 0
        if args.command == "graph":
            graph = {
                pipeline.name: {
                    "inputs": list(pipeline.inputs),
                    "outputs": [item.id for item in pipeline.outputs],
                }
                for pipeline in system.pipelines or ()
            }
            if args.json:
                print(json.dumps(graph, indent=2, sort_keys=True))
            else:
                for name, item in graph.items():
                    print(f"{name}: {', '.join(item['inputs']) or '-'} -> {', '.join(item['outputs'])}")
            return 0
        if args.command == "build":
            records = system.build(args.pipeline or None, promote=not args.no_promote)
            for record in records:
                state = "promoted" if record["promoted"] else "staged"
                print(f"{record['pipeline']}: {record['asset']} {state} at {record['path']}")
            return 0
        if args.command == "fetch":
            records = system.fetch(
                args.pipeline,
                apply=args.apply,
                allow_paid=args.allow_paid,
                promote=not args.no_promote,
            )
            for record in records:
                if not record["applied"]:
                    print(
                        f"would fetch {record['pipeline']} ({record['policy']}) -> "
                        + ", ".join(record["outputs"])
                    )
                else:
                    state = "promoted" if record["promoted"] else "staged"
                    print(f"fetched {record['asset']} {state} at {record['path']}")
            return 0
        if args.command == "verify":
            records = system.verify(args.asset or None)
            invalid = [item for item in records if item["state"] != "promoted"]
            if invalid:
                for item in invalid:
                    print(f"invalid or missing: {item['asset']}: {item['error']}")
                return 1
            print(f"verified {len(records)} promoted dataset(s)")
            return 0
        if args.command == "legacy-import":
            for record in system.import_legacy(args.asset or None):
                print(f"imported {record['asset']} -> {record['path']}")
            return 0
        if args.command == "archive":
            archive = DataArchive(system.root, tuple(system.assets.values()))
            if args.archive_command == "status":
                for item in archive.status(args.tier):
                    print(
                        f"{item['tier']:<11} {item['asset']:<42} "
                        f"{item['archived']}/{item['files']} archived ({item['bytes']} bytes)"
                    )
                return 0
            operation = getattr(archive, args.archive_command)
            result = operation(args.tier, apply=args.apply)
            action = "transferred" if result["applied"] else "would transfer"
            print(f"{action} {result['files']} files ({result['bytes']} bytes)")
            return 0
        if args.command == "review":
            if args.review_command == "export":
                for path in system.review_export():
                    print(f"wrote {path}")
                return 0
            record = system.review_import(promote=not args.no_promote)
            state = "promoted" if record["promoted"] else "staged"
            print(f"imported {record['asset']} {state} at {record['path']}")
            return 0
        if args.command == "catalog":
            if args.catalog_command == "inspect":
                print(json.dumps(system.catalog_inspect(args.asset), indent=2, sort_keys=True))
                return 0
            frame = system.catalog_query(args.asset, args.sql)
            if args.format == "csv":
                print(frame.write_csv(), end="")
            elif args.format == "json":
                print(frame.write_json())
            else:
                print(frame)
            return 0
    except (FileNotFoundError, ImportError, TypeError, ValueError) as error:
        parser().error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
