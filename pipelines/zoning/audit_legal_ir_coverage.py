#!/usr/bin/env python3
"""Audit reviewed article ledgers against the canonical Municode corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from strongtowns_detroit.zoning.legal_ir_coverage import aggregate_coverage  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/zoning-ordinance/source-corpus.json")
    parser.add_argument("--ledgers", type=Path, default=ROOT / "data/zoning-ordinance/reviewed-provisions")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    report = aggregate_coverage(corpus, args.ledgers)
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
