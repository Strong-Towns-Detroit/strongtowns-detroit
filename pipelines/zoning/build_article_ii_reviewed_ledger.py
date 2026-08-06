"""Build the conservative, exact-span Article II reviewed provision ledger.

Article II is organized as Municode paragraphs: headings, list markers, list
items, history notes, and operative prose.  This builder gives every derived
source block an explicit disposition.  Its classifications intentionally stop
short of projecting administrative discretion or compound prose into parcel
rules.
"""

from __future__ import annotations

import re
from pathlib import Path

from strongtowns_detroit.zoning.citations import extract_citations
from strongtowns_detroit.zoning.legal_ir import LegalProvision, MunicodeSpan, ReviewedProvisionLedger
from strongtowns_detroit.zoning.municode_source_model import compile_municode_source_corpus


ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = "2025-10-09_job-429936"
DOCUMENT = "ARTICLE_II.municode.json"
OUTPUT = ROOT / "data/zoning-ordinance/reviewed-provisions/article-ii.json"
MARKER_RE = re.compile(r"(?:\([A-Za-z0-9]+\)|[a-z0-9]+\.)")


def _classification(text: str, *, title: str) -> tuple[str, str, list[str]]:
    """Return broad legal role, execution status, and conservative notes."""
    lower = text.lower()
    if text.startswith(("(Code ", "(Ord. ", "Editor's note—")):
        return "history", "source_record_only", []
    if text.startswith(("Cross reference—", "State Law reference—")):
        return "cross_reference_note", "source_record_only", []
    if MARKER_RE.fullmatch(text):
        return "source_structure", "source_record_only", []
    if text.startswith("NOTE:"):
        return "source_note", "interpretive_context_only", []
    if text.startswith("Table "):
        return "table_caption", "source_record_only", []
    if "purpose" in title.lower() and not any(word in lower for word in (" shall ", " must ", " may ")):
        return "purpose_or_scope", "interpretive_context_only", []
    if re.search(r'\b(?:the )?term ["\u201c].+?["\u201d] means\b', lower):
        return "definition", "legal_definition_requires_projection", []
    prohibition = " shall not " in f" {lower} " or " may not " in f" {lower} " or " must not " in f" {lower} "
    mandatory = " shall " in f" {lower} " or " must " in f" {lower} "
    discretionary = " may " in f" {lower} "
    if prohibition:
        return "prohibition", "semantic_encoding_required", [
            "The prohibition is preserved as prose; its conditions and exceptions have not yet been projected."
        ]
    if mandatory and discretionary:
        return "compound_mandatory_and_discretionary_rule", "semantic_encoding_required", [
            "The source block combines mandatory and discretionary language and must be decomposed before execution."
        ]
    if mandatory:
        return "mandatory_rule", "semantic_encoding_required", []
    if discretionary:
        return "discretionary_authority", "administrative_discretion_required", [
            "The text grants discretion; no automatic approval or entitlement is inferred."
        ]
    if re.search(r"\b(?:is|are) hereby (?:created|established)\b", lower):
        return "body_establishment", "nonparcel_administrative_rule", []
    if re.search(r"\b(?:has|have) (?:the )?(?:power|authority|jurisdiction)\b", lower):
        return "assigned_authority", "semantic_encoding_required", []
    if re.search(r"\b(?:consist|consists|composed)\b", lower):
        return "membership_or_composition", "semantic_encoding_required", []
    if text.startswith("To ") or re.search(r"\. To \w", text):
        return "administrative_power_or_duty", "semantic_encoding_required", []
    if "criteria" in title.lower() or "duties and functions" in title.lower():
        return "criterion_or_review_factor", "semantic_encoding_required", [
            "This list item is preserved without inferring its weight, mandatory character, or decisional effect."
        ]
    title_lower = title.lower()
    if any(term in title_lower for term in (
        "membership", "personnel", "officers", "director", "creation", "establishment",
        "advisory group structure",
    )):
        return "governance_or_membership_text", "semantic_encoding_required", [
            "The governance or membership text is preserved without inferring appointment, voting, or tenure effects not stated in this span."
        ]
    if any(term in title_lower for term in (
        "meetings", "meeting,", "records", "procedures", "reports", "date of decision",
        "transmittal of decision", "simultaneous review",
    )):
        return "procedure_or_recordkeeping_text", "semantic_encoding_required", []
    if "application fee" in title_lower:
        return "fee_rule_text", "semantic_encoding_required", []
    if any(term in title_lower for term in (
        "powers and duties", "subject to review", "processing antenna", "contaminated propert",
    )):
        return "administrative_review_text", "semantic_encoding_required", [
            "The administrative text is preserved without inferring an approval standard or outcome."
        ]
    if any(term in title_lower for term in (
        "appeals", "variances", "hardship relief", "revocation", "limitations on power",
        "nonconformities", "minor deviations", "modification of neighborhood",
    )):
        return "adjudication_text", "semantic_encoding_required", [
            "The adjudicative text is preserved without converting discretion or required findings into an automatic result."
        ]
    return "substantive_text_unresolved", "manual_semantic_review_required", [
        "Exact text is accounted for, but its legal effect has not been inferred from wording alone."
    ]


def _title_classification(text: str) -> tuple[str, str]:
    if text.endswith("- Reserved."):
        return "reserved", "reserved_range"
    if text.startswith(("ARTICLE ", "DIVISION ", "Subdivision ")):
        return "source_structure", "organizational_heading"
    return "source_structure", "section_heading"


def main() -> None:
    corpus = compile_municode_source_corpus(ROOT / "resources/municode" / SNAPSHOT)
    document = next(item for item in corpus["documents"] if item["document"] == DOCUMENT)
    titles = {node["municodeNodeId"]: node["title"] for node in document["sourceNodes"]}
    provisions: list[LegalProvision] = []

    for block in document["blocks"]:
        node_id = block["municodeNodeId"]
        section = block.get("section")
        title = titles[node_id]
        if block["type"] == "table":
            for row, values in enumerate(block["rows"]):
                for column, cell_text in enumerate(values):
                    if not cell_text:
                        continue
                    span = MunicodeSpan.cite_table_cell(
                        snapshot=SNAPSHOT,
                        document=DOCUMENT,
                        node_id=node_id,
                        source_index=block["sourceIndex"],
                        cell_text=cell_text,
                        row=row,
                        column=column,
                        section=section,
                    )
                    provisions.append(LegalProvision(
                        id=f"detroit:article-ii:block-{block['sourceIndex']}:cell-{row}-{column}",
                        subject={"type": "advisory_committee_structure", "sectionTitle": title},
                        effect={"type": "table_cell", "role": "header" if row == 0 else "committee_structure_value"},
                        sources=(span,),
                        review={
                            "status": "verified",
                            "method": "conservative_source_block_review",
                            "executionStatus": "semantic_encoding_required",
                            "reviewedOn": "2026-07-31",
                        },
                    ))
            continue

        text = block["text"]
        if block.get("style") == "MunicodeTitle":
            classification, role = _title_classification(text)
            execution_status = "source_record_only"
            notes: list[str] = []
        else:
            classification, execution_status, notes = _classification(text, title=title)
            role = "source_paragraph"
        span = MunicodeSpan.cite(
            snapshot=SNAPSHOT,
            document=DOCUMENT,
            node_id=node_id,
            source_index=block["sourceIndex"],
            text=text,
            start=0,
            end=len(text),
            section=section,
        )
        references = tuple(
            citation.target for citation in extract_citations(text, section or "")
        )
        provisions.append(LegalProvision(
            id=f"detroit:article-ii:block-{block['sourceIndex']}",
            subject={"type": classification, "sectionTitle": title},
            effect={"type": classification, "role": role},
            sources=(span,),
            cross_references=references,
            review={
                "status": "verified",
                "method": "conservative_source_block_review",
                "executionStatus": execution_status,
                "reviewedOn": "2026-07-31",
                **({"notes": notes} if notes else {}),
            },
        ))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(ReviewedProvisionLedger(tuple(provisions)).to_json() + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
