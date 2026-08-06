"""Encode every source block in the DSL without claiming legal normalization."""

from __future__ import annotations

from strongtowns_detroit.zoning.chapter_compiler import classify_paragraph, classify_table
from strongtowns_detroit.zoning.citations import extract_citations
from strongtowns_detroit.zoning.codebook import OrdinanceBuilder, Source


def add_source_provisions(code: OrdinanceBuilder, source_corpus: dict) -> int:
    count = 0
    for document in source_corpus["documents"]:
        for block in document["blocks"]:
            section = block.get("section")
            article = int(section.split("-")[1]) if section else _document_article(document["document"])
            block_id = f"{document['document']}:{block['sourceIndex']}"
            if block["type"] == "paragraph":
                classes = tuple(classify_paragraph(block["text"], article or 0))
                citations = tuple(sorted({
                    item.target for item in extract_citations(block["text"], section or "")
                }))
                payload = {"text": block["text"], "style": block.get("style", "")}
            else:
                classes = (classify_table(article or 0, section or "", block["rows"]),)
                citations = ()
                payload = {"rows": block["rows"]}
            code.source_provision(
                id=block_id,
                kind=block["type"],
                classes=classes,
                payload=payload,
                source=Source(
                    document["document"], (section,) if section else (),
                    block["text"] if block["type"] == "paragraph" else "table",
                    "Source encoded; legal normalization and review remain pending.",
                ),
                cross_references=citations,
            )
            count += 1
    return count


def _document_article(name: str) -> int | None:
    roman = name.removeprefix("ARTICLE_").split(".", 1)[0]
    values = {
        "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6,
        "VII": 7, "VIII": 8, "IX": 9, "X": 10, "XI": 11,
        "XII": 12, "XIII": 13, "XIV": 14, "XV": 15,
        "XVI": 16, "XVII": 17,
    }
    return values.get(roman)
