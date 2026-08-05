#!/usr/bin/env python3
"""Build Article VI's complete exact-span source-disposition ledger.

Article VI is reserved.  Its editor's note records repeal history and points
to similar provisions elsewhere; this builder accounts for that source text
without promoting the historical note into executable zoning law.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from strongtowns_detroit.zoning.legal_ir import (
    LegalProvision,
    MunicodeSpan,
    ReviewedProvisionLedger,
)
from strongtowns_detroit.zoning.municode_source_model import (
    compile_municode_source_corpus,
    latest_snapshot,
)


ROOT = Path(__file__).resolve().parents[2]
DOCUMENT = "ARTICLE_VI.municode.json"
DEFAULT_OUTPUT = ROOT / "data/zoning-ordinance/reviewed-provisions/article-vi.json"


def build_article_vi_ledger(corpus: dict) -> ReviewedProvisionLedger:
    snapshot = corpus["canonicalSource"]["snapshot"]
    document = next(item for item in corpus["documents"] if item["document"] == DOCUMENT)
    provisions = []
    for block in document["blocks"]:
        text = block["text"]
        span = MunicodeSpan.cite(
            snapshot=snapshot,
            document=DOCUMENT,
            node_id=block["municodeNodeId"],
            source_index=block["sourceIndex"],
            section=block.get("section"),
            text=text,
            start=0,
            end=len(text),
        )
        effect, disposition, execution_status, notes = classify(block)
        provisions.append(LegalProvision(
            id=f"detroit:article-vi:block:{block['sourceIndex']}",
            subject={"article": "VI", "section": block.get("section"), "type": "source_atom"},
            effect=effect,
            sources=(span,),
            review={
                "status": "verified",
                "method": "complete_source_block_disposition",
                "reviewedOn": "2026-07-31",
                "disposition": disposition,
                "executionStatus": execution_status,
                "notes": notes,
            },
        ))
    return ReviewedProvisionLedger(tuple(provisions))


def classify(block: dict) -> tuple[dict, str, str, str]:
    text = block["text"]
    if text.startswith("Editor's note—"):
        return (
            {
                "type": "history",
                "role": "editor_note_repeal_and_relocation_history",
                "repealedSubject": "signs",
                "relatedCurrentLocationText": "Chapter 4, Articles IV and V",
            },
            "accounted_contextual",
            "source_record_only",
            "The editor's note is fully transcribed. Its historical assertions and "
            "reference to similar Chapter 4 provisions are not executable Chapter 50 rules.",
        )
    if "reserved" in text.lower():
        return (
            {"type": "reserved", "role": "reserved_article_or_section_range"},
            "accounted_nonoperative",
            "source_record_only",
            "Exact reserved source text verified; no operative rule is inferred.",
        )
    return (
        {"type": "source_structure", "role": "heading"},
        "accounted_nonoperative",
        "source_record_only",
        "Exact source structure verified.",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    snapshot = args.snapshot or latest_snapshot(ROOT / "resources/municode")
    ledger = build_article_vi_ledger(compile_municode_source_corpus(snapshot))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(ledger.to_json() + "\n", encoding="utf-8")
    print(f"wrote {len(ledger.provisions)} Article VI source atoms")


if __name__ == "__main__":
    main()
