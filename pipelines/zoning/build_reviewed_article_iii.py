#!/usr/bin/env python3
"""Build Article III's exact-span source-disposition ledger.

This intentionally does not convert review and approval procedures into
executable law. It accounts for every derived source block, records exact
Municode spans, and identifies procedural prose that still requires
clause-level legal encoding.
"""

from __future__ import annotations

import argparse
import re
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
DOCUMENT = "ARTICLE_III.municode.json"
DEFAULT_OUTPUT = ROOT / "data/zoning-ordinance/reviewed-provisions/article-iii.json"
HISTORY_RE = re.compile(r"^\((?:Code 1984|Ord\.)", re.I)
LABEL_RE = re.compile(r"^(?:\([a-z0-9]+\)|[a-z]\.|\d+\.)$", re.I)
RESERVED_RE = re.compile(r"reserved", re.I)


def build_article_iii_ledger(corpus: dict) -> ReviewedProvisionLedger:
    snapshot = corpus["canonicalSource"]["snapshot"]
    document = next(item for item in corpus["documents"] if item["document"] == DOCUMENT)
    provisions: list[LegalProvision] = []
    for block in document["blocks"]:
        if block["type"] == "paragraph":
            text = block["text"]
            effect, execution_status, disposition = classify_paragraph(block)
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
            provisions.append(_provision(
                id=f"detroit:article-iii:block:{block['sourceIndex']}",
                span=span,
                effect=effect,
                execution_status=execution_status,
                disposition=disposition,
            ))
        else:
            for row_index, row in enumerate(block["rows"]):
                for column_index, cell in enumerate(row):
                    if not cell:
                        continue
                    span = MunicodeSpan.cite_table_cell(
                        snapshot=snapshot,
                        document=DOCUMENT,
                        node_id=block["municodeNodeId"],
                        source_index=block["sourceIndex"],
                        section=block.get("section"),
                        cell_text=cell,
                        row=row_index,
                        column=column_index,
                    )
                    provisions.append(_provision(
                        id=(f"detroit:article-iii:block:{block['sourceIndex']}:"
                            f"row:{row_index}:column:{column_index}"),
                        span=span,
                        effect={
                            "type": "procedure_summary_table_cell",
                            "table": "50-3-1",
                            "row": row_index,
                            "column": column_index,
                            "role": "general_summary_not_controlling_detail",
                        },
                        execution_status="non_executable_summary",
                        disposition="accounted_contextual",
                    ))
    return ReviewedProvisionLedger(tuple(provisions))


def classify_paragraph(block: dict) -> tuple[dict, str, str]:
    text = block["text"].strip()
    style = block.get("style")
    if RESERVED_RE.search(text) and len(text) < 100:
        return (
            {"type": "reserved", "role": "reserved_source_text"},
            "source_record_only",
            "accounted_nonoperative",
        )
    if style == "MunicodeTitle":
        return (
            {"type": "source_structure", "role": "heading"},
            "source_record_only",
            "accounted_nonoperative",
        )
    if HISTORY_RE.match(text):
        return (
            {"type": "history", "role": "codification_and_amendment_history"},
            "source_record_only",
            "accounted_nonoperative",
        )
    if LABEL_RE.fullmatch(text) or text in {"Notes:", "Table 50-3-1"}:
        return (
            {"type": "source_structure", "role": "subdivision_or_table_label"},
            "source_record_only",
            "accounted_contextual",
        )
    if block.get("section") == "50-3-1":
        return (
            {"type": "procedure_summary_context", "role": "table_note_or_qualification"},
            "non_executable_summary",
            "accounted_contextual",
        )
    return (
        {"type": "procedure_source", "role": "unparsed_procedural_clause"},
        "non_executable_pending_clause_review",
        "pending_clause_review",
    )


def _provision(
    *, id: str, span: MunicodeSpan, effect: dict,
    execution_status: str, disposition: str,
) -> LegalProvision:
    notes = (
        "Exact source transcription and disposition verified. Procedural legal "
        "effect, conditions, exceptions, sequencing, and discretion have not "
        "been encoded."
        if execution_status == "non_executable_pending_clause_review"
        else "Exact source transcription and source disposition verified."
    )
    return LegalProvision(
        id=id,
        subject={"article": "III", "section": span.section, "type": "source_atom"},
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
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    snapshot = args.snapshot or latest_snapshot(ROOT / "resources/municode")
    corpus = compile_municode_source_corpus(snapshot)
    ledger = build_article_iii_ledger(corpus)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(ledger.to_json() + "\n", encoding="utf-8")
    pending = sum(
        item.review["disposition"] == "pending_clause_review"
        for item in ledger.provisions
    )
    print(f"wrote {len(ledger.provisions)} Article III atoms; {pending} pending clause review")


if __name__ == "__main__":
    main()
