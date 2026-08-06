from pathlib import Path

import pytest

from strongtowns_detroit.zoning.legal_ir import (
    ProvenanceError,
    ReviewedProvisionLedger,
    verify_provision,
    verify_provisions,
)
from strongtowns_detroit.zoning.municode_source_model import compile_municode_source_corpus
from strongtowns_detroit.zoning.occlusion import occlude_span


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "resources/municode/2025-10-09_job-429936"
LEDGER_PATH = ROOT / "data/zoning-ordinance/reviewed-provisions/article-ii.json"
DOCUMENT = "ARTICLE_II.municode.json"


@pytest.fixture(scope="module")
def article_ii_corpus():
    corpus = compile_municode_source_corpus(SNAPSHOT)
    article = next(item for item in corpus["documents"] if item["document"] == DOCUMENT)
    return {"canonicalSource": corpus["canonicalSource"], "documents": [article]}


@pytest.fixture(scope="module")
def ledger():
    return ReviewedProvisionLedger.load(LEDGER_PATH)


def test_article_ii_is_a_valid_flat_reviewed_provision_ledger(ledger):
    assert ledger.schema_version == "detroit-legal-ir-v1"
    assert len(ledger.provisions) == 927
    assert all(provision.review["status"] == "verified" for provision in ledger.provisions)


def test_every_article_ii_span_verifies_against_canonical_municode(article_ii_corpus, ledger):
    verify_provisions(article_ii_corpus, ledger.provisions)


def test_every_article_ii_source_block_and_table_cell_is_accounted_for(article_ii_corpus, ledger):
    blocks = article_ii_corpus["documents"][0]["blocks"]
    cited_blocks = {source.source_index for provision in ledger.provisions for source in provision.sources}

    assert len(blocks) == 907
    assert cited_blocks == {block["sourceIndex"] for block in blocks}

    table = next(block for block in blocks if block["type"] == "table")
    expected_cells = {
        (row, column)
        for row, values in enumerate(table["rows"])
        for column, value in enumerate(values)
        if value
    }
    cited_cells = {
        (source.row, source.column)
        for provision in ledger.provisions
        for source in provision.sources
        if source.source_index == table["sourceIndex"]
    }
    assert cited_cells == expected_cells


def test_article_ii_separates_nonoperative_and_unresolved_material(ledger):
    effect_types = [provision.effect["type"] for provision in ledger.provisions]

    assert effect_types.count("history") == 75
    assert effect_types.count("reserved") == 15
    assert effect_types.count("cross_reference_note") == 2
    assert effect_types.count("discretionary_authority") == 15
    assert effect_types.count("prohibition") == 2
    assert effect_types.count("definition") == 2
    assert all(
        provision.review["executionStatus"] == "administrative_discretion_required"
        and provision.review.get("notes")
        for provision in ledger.provisions
        if provision.effect["type"] == "discretionary_authority"
    )


def test_each_article_ii_provision_fails_when_its_exact_span_is_occluded(article_ii_corpus, ledger):
    for provision in ledger.provisions:
        occluded = occlude_span(article_ii_corpus, provision.sources[0])
        with pytest.raises(ProvenanceError, match="changed or was occluded"):
            verify_provision(occluded, provision)


def test_article_ii_does_not_project_substantive_blocks_as_parcel_answers(ledger):
    permitted = {"source_record_only", "interpretive_context_only"}
    substantive = [
        provision for provision in ledger.provisions
        if provision.review["executionStatus"] not in permitted
    ]

    assert substantive
    assert all(
        provision.review["executionStatus"] != "executable"
        for provision in substantive
    )
