#!/usr/bin/env python3
"""Build Article V's exact-span source-disposition ledger.

Article V governs violations, penalties, remedies, and revocation. This pass
accounts for every source block without projecting those compound and often
discretionary provisions into executable semantics.
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
DOCUMENT = "ARTICLE_V.municode.json"
DEFAULT_OUTPUT = ROOT / "data/zoning-ordinance/reviewed-provisions/article-v.json"
HISTORY_RE = re.compile(r"^\((?:Code 1984|Ord\.)", re.I)
LABEL_RE = re.compile(r"^(?:\([a-z0-9]+\)|[a-z]\.|\d+\.)$", re.I)
RESERVED_RE = re.compile(r"reserved", re.I)
DISCRETION_RE = re.compile(
    r"\b(?:may|reasonable|appropriate|deemed|determines?|satisfaction|"
    r"discretion|presumed|good cause|injurious|nuisance)\b",
    re.I,
)
EXTERNAL_RE = re.compile(
    r"\b(?:state law|Michigan|MCL|Charter|Chapter [0-9]|other provisions|"
    r"administrative rules|court|bylaws?)\b",
    re.I,
)


def build_article_v_ledger(corpus: dict) -> ReviewedProvisionLedger:
    snapshot = corpus["canonicalSource"]["snapshot"]
    document = next(item for item in corpus["documents"] if item["document"] == DOCUMENT)
    provisions: list[LegalProvision] = []
    for block in document["blocks"]:
        if block["type"] == "paragraph":
            text = block["text"]
            effect, execution_status, disposition, flags = classify_paragraph(block)
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
                id=f"detroit:article-v:block:{block['sourceIndex']}",
                span=span,
                effect=effect,
                execution_status=execution_status,
                disposition=disposition,
                flags=flags,
            ))
            continue
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
                    id=(f"detroit:article-v:block:{block['sourceIndex']}:"
                        f"row:{row_index}:column:{column_index}"),
                    span=span,
                    effect={
                        "type": "penalty_table_cell",
                        "row": row_index,
                        "column": column_index,
                        "role": "unparsed_penalty_matrix_cell",
                    },
                    execution_status="non_executable_pending_penalty_table_review",
                    disposition="pending_compound_review",
                    flags=("compound_table", "repeat_offense_semantics"),
                ))
    return ReviewedProvisionLedger(tuple(provisions))


def classify_paragraph(block: dict) -> tuple[dict, str, str, tuple[str, ...]]:
    text = block["text"].strip()
    if RESERVED_RE.search(text) and len(text) < 100:
        return (
            {"type": "reserved", "role": "reserved_source_text"},
            "source_record_only", "accounted_nonoperative", (),
        )
    if block.get("style") == "MunicodeTitle":
        return (
            {"type": "source_structure", "role": "heading"},
            "source_record_only", "accounted_nonoperative", (),
        )
    if HISTORY_RE.match(text):
        return (
            {"type": "history", "role": "codification_and_amendment_history"},
            "source_record_only", "accounted_nonoperative", (),
        )
    if LABEL_RE.fullmatch(text):
        return (
            {"type": "source_structure", "role": "subdivision_label"},
            "source_record_only", "accounted_contextual", (),
        )
    flags = ["compound_enforcement_semantics"]
    if DISCRETION_RE.search(text):
        flags.append("discretion_or_open_standard")
    if EXTERNAL_RE.search(text):
        flags.append("external_legal_dependency")
    execution_status = (
        "non_executable_pending_discretionary_review"
        if "discretion_or_open_standard" in flags
        else "non_executable_pending_external_dependency_review"
        if "external_legal_dependency" in flags
        else "non_executable_pending_compound_rule_review"
    )
    return (
        {"type": "enforcement_source", "role": "unparsed_enforcement_clause"},
        execution_status,
        "pending_compound_review",
        tuple(flags),
    )


def _provision(
    *, id: str, span: MunicodeSpan, effect: dict, execution_status: str,
    disposition: str, flags: tuple[str, ...],
) -> LegalProvision:
    pending = disposition == "pending_compound_review"
    return LegalProvision(
        id=id,
        subject={"article": "V", "section": span.section, "type": "source_atom"},
        effect=effect,
        sources=(span,),
        review={
            "status": "verified",
            "method": "complete_source_block_disposition",
            "reviewedOn": "2026-07-31",
            "disposition": disposition,
            "executionStatus": execution_status,
            "flags": list(flags),
            "notes": (
                "Exact source transcription and disposition verified. Enforcement "
                "elements, actors, triggers, alternatives, discretion, external law, "
                "and consequences remain unencoded."
                if pending else
                "Exact source transcription and source disposition verified."
            ),
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    snapshot = args.snapshot or latest_snapshot(ROOT / "resources/municode")
    corpus = compile_municode_source_corpus(snapshot)
    ledger = build_article_v_ledger(corpus)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(ledger.to_json() + "\n", encoding="utf-8")
    pending = sum(
        item.review["disposition"] == "pending_compound_review"
        for item in ledger.provisions
    )
    print(f"wrote {len(ledger.provisions)} Article V atoms; {pending} pending compound review")


if __name__ == "__main__":
    main()
