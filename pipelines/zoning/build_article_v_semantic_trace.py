#!/usr/bin/env python3
"""Build Article V's proposition and DSL-projection trace."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from strongtowns_detroit.zoning.article_v_semantics import build_article_v_semantic_trace
from strongtowns_detroit.zoning.legal_ir import ReviewedProvisionLedger
from strongtowns_detroit.zoning.municode_source_model import compile_municode_source_corpus


ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "resources/municode/2025-10-09_job-429936"
LEDGER = ROOT / "data/zoning-ordinance/reviewed-provisions/article-v.json"
OUTPUT = ROOT / "data/zoning-ordinance/reviewed-provisions/article-v-semantic-trace.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    corpus = compile_municode_source_corpus(args.snapshot)
    trace = build_article_v_semantic_trace(corpus, ReviewedProvisionLedger.load(args.ledger))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(trace["coverage"], sort_keys=True))


if __name__ == "__main__":
    main()
