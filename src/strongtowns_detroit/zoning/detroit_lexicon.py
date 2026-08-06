"""Generate structurally verified definitions and use assignments."""

from __future__ import annotations

from strongtowns_detroit.zoning.candidates import compile_candidates
from strongtowns_detroit.zoning.codebook import OrdinanceBuilder, Source


def add_structural_lexicon(code: OrdinanceBuilder, source_corpus: dict) -> dict[str, int]:
    candidates = compile_candidates(source_corpus)
    definitions = 0
    assignments = 0
    for item in candidates["definitions"]:
        if item["reviewReadiness"] != "ready_for_cell_review":
            continue
        provenance = item["source"]
        code.definition(
            id=item["id"],
            term=item["term"],
            meaning=item["meaning"],
            source=Source(
                provenance["document"], (provenance["section"],), item["meaning"],
                "Structurally transcribed from the Article XVI definition table.",
            ),
            review_status="structurally_verified",
        )
        definitions += 1
    for item in candidates["useAssignments"]:
        provenance = item["source"]
        code.assign_use(
            id=item["id"],
            specific_use=item["specificUse"],
            use_category=item["useCategory"],
            source=Source(
                provenance["document"], (), item["useCategory"],
                "Structurally transcribed from Appendix A; Appendix A has no numbered section.",
            ),
            review_status="structurally_verified",
        )
        assignments += 1
    return {"definitions": definitions, "useAssignments": assignments}
