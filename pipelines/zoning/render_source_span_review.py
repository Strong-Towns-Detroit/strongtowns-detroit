#!/usr/bin/env python3
"""Render a standalone Article I legal-IR source-span review page."""

from __future__ import annotations

import argparse
from pathlib import Path

from strongtowns_detroit.zoning.legal_ir import ReviewedProvisionLedger
from strongtowns_detroit.zoning.municode_source_model import (
    compile_municode_source_corpus,
    latest_snapshot,
)
from strongtowns_detroit.zoning.source_span_review import render_review_page


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument(
        "--document", default="ARTICLE_I.municode.json",
        help="Canonical Municode document name containing the reviewed spans.",
    )
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / "artifacts/zoning/article-i-source-span-review.html",
    )
    parser.add_argument("--selected", default="0", help="Zero-based index, provision ID, or atom key")
    args = parser.parse_args()

    snapshot = args.snapshot or latest_snapshot(ROOT / "resources/municode")
    corpus = compile_municode_source_corpus(snapshot)
    ledger = ReviewedProvisionLedger.load(args.ledger)
    selected: int | str = int(args.selected) if args.selected.isdigit() else args.selected
    html = render_review_page(corpus, ledger, document=args.document, selected=selected)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print(f"wrote {len(ledger.provisions)} provisions to {args.output}")


if __name__ == "__main__":
    main()
