import pytest

from strongtowns_detroit.zoning.legal_ir import (
    LegalProvision,
    MunicodeSpan,
    ProvenanceError,
    ReviewedProvisionLedger,
    project_provision,
    verify_provision,
)
from strongtowns_detroit.zoning.occlusion import occlude_span


TEXT = "In the R1 district, minimum lot area is 5,000 square feet."


@pytest.fixture
def corpus():
    return {
        "canonicalSource": {"snapshot": "2025-10-09_job-429936"},
        "documents": [{
            "document": "ARTICLE_XIII.municode.json",
            "blocks": [{
                "type": "paragraph",
                "sourceIndex": 42,
                "municodeNodeId": 98765,
                "section": "50-13-2",
                "text": TEXT,
            }, {
                "type": "table",
                "sourceIndex": 43,
                "municodeNodeId": 98765,
                "section": "50-13-2",
                "rows": [["District", "Minimum lot area"], ["R1", "5,000 sq. ft."]],
            }],
        }],
    }


@pytest.fixture
def provision():
    start = TEXT.index("5,000 square feet")
    source = MunicodeSpan.cite(
        snapshot="2025-10-09_job-429936",
        document="ARTICLE_XIII.municode.json",
        node_id=98765,
        source_index=42,
        section="50-13-2",
        text=TEXT,
        start=start,
        end=start + len("5,000 square feet"),
    )
    return LegalProvision(
        id="detroit:50-13-2:r1-minimum-lot-area",
        subject={"district": ["R1"], "use": ["one_family_dwelling"]},
        effect={
            "type": "minimum",
            "metric": "lot_area",
            "value": 5000,
            "unit": "square_feet",
        },
        conditions=(),
        exceptions=(),
        cross_references=("50-12-10",),
        sources=(source,),
        review={"status": "verified", "method": "human_review"},
    )


def test_reviewed_rule_is_bound_to_exact_municode_span(corpus, provision):
    verify_provision(corpus, provision)
    encoded = provision.to_dict()
    assert encoded["sources"][0]["quote"] == "5,000 square feet"
    assert encoded["sources"][0]["sha256"]
    assert encoded["conditions"] == ()
    assert encoded["exceptions"] == ()


def test_rule_fails_when_its_cited_source_span_is_occluded(corpus, provision):
    occluded = occlude_span(corpus, provision.sources[0])
    with pytest.raises(ProvenanceError, match="changed or was occluded"):
        verify_provision(occluded, provision)


def test_rule_fails_if_same_text_is_attached_to_wrong_node(corpus, provision):
    corpus["documents"][0]["blocks"][0]["municodeNodeId"] = 111
    with pytest.raises(ProvenanceError, match="node mismatch"):
        verify_provision(corpus, provision)


def test_reviewed_ledger_round_trips_without_losing_provenance(provision):
    ledger = ReviewedProvisionLedger((provision,))
    restored = ReviewedProvisionLedger.from_json(ledger.to_json())
    assert restored == ledger
    assert restored.provisions[0].sources[0].node_id == 98765


def test_occlusion_blocks_only_the_dependent_projection(corpus, provision):
    unrelated_text = "In the R1 district"
    unrelated_source = MunicodeSpan.cite(
        snapshot="2025-10-09_job-429936",
        document="ARTICLE_XIII.municode.json",
        node_id=98765,
        source_index=42,
        section="50-13-2",
        text=TEXT,
        start=0,
        end=len(unrelated_text),
    )
    unrelated = LegalProvision(
        id="detroit:50-13-2:r1-applicability",
        subject={"district": ["R1"]},
        effect={"type": "applies"},
        sources=(unrelated_source,),
        review={"status": "verified"},
    )
    projected = []

    def projector(item):
        projected.append(item.id)
        return {"id": item.id, "effect": dict(item.effect)}

    occluded = occlude_span(corpus, provision.sources[0])
    with pytest.raises(ProvenanceError, match="occluded"):
        project_provision(occluded, provision, projector)
    result = project_provision(occluded, unrelated, projector)

    assert projected == [unrelated.id]  # failed rule never reached the projector
    assert result["id"] == unrelated.id


def test_table_cell_span_uses_coordinates_and_is_occludable(corpus):
    source = MunicodeSpan.cite_table_cell(
        snapshot="2025-10-09_job-429936",
        document="ARTICLE_XIII.municode.json",
        node_id=98765,
        source_index=43,
        section="50-13-2",
        cell_text="5,000 sq. ft.",
        row=1,
        column=1,
    )
    provision = LegalProvision(
        id="detroit:50-13-2:r1-table-lot-area",
        subject={"district": ["R1"]},
        effect={"type": "minimum", "metric": "lot_area", "value": 5000},
        sources=(source,),
        review={"status": "verified"},
    )
    assert source.row == 1 and source.column == 1
    verify_provision(corpus, provision)

    occluded = occlude_span(corpus, source)
    assert occluded["documents"][0]["blocks"][1]["rows"][1][0] == "R1"
    with pytest.raises(ProvenanceError, match="occluded"):
        project_provision(occluded, provision, lambda item: item.effect)
