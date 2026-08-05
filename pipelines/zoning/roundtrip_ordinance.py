#!/usr/bin/env python3
"""Pack, exactly restore, and verify Detroit ordinance DOCX files via JSON."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from strongtowns_detroit.zoning.roundtrip import restore_document, verify_document
from strongtowns_detroit.zoning.source_model import compile_source_corpus

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PACKAGE = ROOT / "data/zoning-ordinance/source-corpus.lossless.json"


def write_package(path: Path) -> dict:
    corpus = compile_source_corpus(ROOT / "resources", include_archives=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(corpus, separators=(",", ":")), encoding="utf-8")
    return corpus


def read_package(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def restore_corpus(corpus: dict, output_dir: Path, *, verify: bool = True) -> None:
    for document in corpus["documents"]:
        target = restore_document(document, output_dir)
        if verify:
            verify_document(document, target)
        print(f"{document['document']}: exact + semantic OK")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("pack", "verify", "restore", "loop"))
    parser.add_argument("--package", type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    corpus = write_package(args.package) if args.command == "pack" else read_package(args.package)
    if args.command == "pack":
        print(f"packed {len(corpus['documents'])} documents -> {args.package}")
    elif args.command == "restore":
        if args.output_dir is None:
            raise SystemExit("restore requires --output-dir")
        restore_corpus(corpus, args.output_dir)
    elif args.command == "verify":
        for document in corpus["documents"]:
            source = ROOT / "resources" / document["document"]
            verify_document(document, source)
            print(f"{document['document']}: source + semantic OK")
    else:
        with tempfile.TemporaryDirectory(prefix="ordinance-roundtrip-") as temp:
            restore_corpus(corpus, Path(temp))
        print(f"closed loop passed for {len(corpus['documents'])} documents")


if __name__ == "__main__":
    main()
