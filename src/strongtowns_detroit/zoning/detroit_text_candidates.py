"""Promote source paragraphs to typed, non-executable review candidates."""

from __future__ import annotations

from collections import Counter

from strongtowns_detroit.zoning.chapter_compiler import classify_paragraph
from strongtowns_detroit.zoning.citations import extract_citations
from strongtowns_detroit.zoning.codebook import OrdinanceBuilder, Source

TYPED_EFFECTS = {
    "definition",
    "enforcement",
    "exception",
    "map",
    "nonconformity",
    "procedure",
    "prohibition",
    "purpose",
    "requirement",
}


def add_text_candidates(code: OrdinanceBuilder, source_corpus: dict) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for document in source_corpus["documents"]:
        for block in document["blocks"]:
            if block["type"] != "paragraph" or not block.get("section"):
                continue
            section = block["section"]
            article = int(section.split("-")[1])
            effects = TYPED_EFFECTS.intersection(classify_paragraph(block["text"], article))
            if not effects:
                continue
            references = tuple(sorted({
                item.target for item in extract_citations(block["text"], section)
            }))
            for effect in sorted(effects):
                code.provision(
                    id=f"{document['document']}:{block['sourceIndex']}:{effect}",
                    effect=effect,
                    text=block["text"],
                    source=Source(
                        document["document"], (section,), block["text"],
                        "Machine-classified legal effect; applicability and effect require review.",
                    ),
                    cross_references=references,
                    review_status="machine_classified",
                )
                counts[effect] += 1
    return dict(sorted(counts.items()))
