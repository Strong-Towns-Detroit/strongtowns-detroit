#!/usr/bin/env python3
"""Build Article IV's exact-span source-disposition ledger.

Coverage here means every derived Municode source atom has an exact citation
and an explicit disposition. It does not mean that procedural legal semantics
have been projected into executable rules.
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
DOCUMENT = "ARTICLE_IV.municode.json"
DEFAULT_OUTPUT = ROOT / "data/zoning-ordinance/reviewed-provisions/article-iv.json"
HISTORY_RE = re.compile(r"^\((?:Code 1984|Ord\.)", re.I)
LABEL_RE = re.compile(r"^(?:\([a-z0-9]+\)|[a-z]\.|\d+\.)$", re.I)
RESERVED_RE = re.compile(r"reserved", re.I)
INFORMATIONAL_TABLES = {"50-4-3": "50-4-3", "50-4-4": "50-4-4"}


def build_article_iv_ledger(corpus: dict) -> ReviewedProvisionLedger:
    snapshot = corpus["canonicalSource"]["snapshot"]
    document = next(item for item in corpus["documents"] if item["document"] == DOCUMENT)
    provisions: list[LegalProvision] = []
    for block in document["blocks"]:
        if block["type"] == "paragraph":
            text = block["text"]
            effect, execution_status, disposition, notes = classify_paragraph(block)
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
                id=f"detroit:article-iv:block:{block['sourceIndex']}",
                span=span,
                effect=effect,
                execution_status=execution_status,
                disposition=disposition,
                notes=notes,
            ))
            continue

        table_name = INFORMATIONAL_TABLES[block["section"]]
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
                    id=(f"detroit:article-iv:block:{block['sourceIndex']}:"
                        f"row:{row_index}:column:{column_index}"),
                    span=span,
                    effect={
                        "type": "informational_historical_table_cell",
                        "table": table_name,
                        "row": row_index,
                        "column": column_index,
                        "role": "header" if row_index == 0 else "historical_reference_value",
                    },
                    execution_status="non_executable_informational_table",
                    disposition="accounted_contextual",
                    notes=(
                        "Exact informational table cell verified. The source labels this table "
                        "for informational purposes only; no current district or development-plan "
                        "legal effect is inferred."
                    ),
                ))
    return ReviewedProvisionLedger(tuple(provisions))


def classify_paragraph(block: dict) -> tuple[dict, str, str, str]:
    text = block["text"].strip()
    style = block.get("style")
    if RESERVED_RE.search(text) and len(text) < 100:
        return (
            {"type": "reserved", "role": "reserved_source_text"},
            "source_record_only",
            "accounted_nonoperative",
            "Exact reserved source text and disposition verified.",
        )
    if style == "MunicodeTitle":
        return (
            {"type": "source_structure", "role": "heading"},
            "source_record_only",
            "accounted_nonoperative",
            "Exact source heading and disposition verified.",
        )
    if HISTORY_RE.match(text):
        return (
            {"type": "history", "role": "codification_and_amendment_history"},
            "source_record_only",
            "accounted_nonoperative",
            "Exact codification history and disposition verified.",
        )
    if LABEL_RE.fullmatch(text):
        return (
            {"type": "source_structure", "role": "subdivision_label"},
            "source_record_only",
            "accounted_contextual",
            "Exact source subdivision label and disposition verified.",
        )
    if text.startswith("Table 50-4-") and "For Informational Purposes Only" in text:
        return (
            {"type": "source_structure", "role": "informational_table_caption"},
            "non_executable_informational_table",
            "accounted_contextual",
            "Exact table caption verified; its express informational-only limitation is preserved.",
        )

    lower = f" {text.lower()} "
    has_mandatory = " shall " in lower or " must " in lower
    has_discretionary = " may " in lower
    if has_mandatory and has_discretionary:
        effect_type = "compound_procedure_source"
        note = (
            "This exact source block combines mandatory and discretionary language. "
            "Conditions, exceptions, sequencing, and decisional authority remain pending clause review."
        )
    elif has_discretionary:
        effect_type = "discretionary_procedure_source"
        note = (
            "This exact source block contains discretionary language. It is not encoded as an "
            "automatic entitlement or outcome; clause-level review remains pending."
        )
    elif has_mandatory:
        effect_type = "mandatory_procedure_source"
        note = (
            "This exact source block contains mandatory language, but its subjects, conditions, "
            "exceptions, and sequencing remain pending clause review."
        )
    else:
        effect_type = "ambiguous_procedure_source"
        note = (
            "Exact procedural or contextual text verified. Its legal effect is not inferred from "
            "wording alone and remains pending clause review."
        )
    return (
        {"type": effect_type, "role": "unparsed_procedural_clause"},
        "non_executable_pending_clause_review",
        "pending_clause_review",
        note,
    )


def _provision(
    *, id: str, span: MunicodeSpan, effect: dict,
    execution_status: str, disposition: str, notes: str,
) -> LegalProvision:
    return LegalProvision(
        id=id,
        subject={"article": "IV", "section": span.section, "type": "source_atom"},
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
    ledger = build_article_iv_ledger(corpus)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(ledger.to_json() + "\n", encoding="utf-8")
    pending = sum(
        item.review["disposition"] == "pending_clause_review"
        for item in ledger.provisions
    )
    print(f"wrote {len(ledger.provisions)} Article IV atoms; {pending} pending clause review")


if __name__ == "__main__":
    main()
