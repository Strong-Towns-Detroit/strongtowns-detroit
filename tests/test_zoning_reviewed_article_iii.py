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
LEDGER_PATH = ROOT / "data/zoning-ordinance/reviewed-provisions/article-iii.json"
DOCUMENT = "ARTICLE_III.municode.json"


@pytest.fixture(scope="module")
def article_iii_corpus():
    corpus = compile_municode_source_corpus(SNAPSHOT)
    article = next(item for item in corpus["documents"] if item["document"] == DOCUMENT)
    return {"canonicalSource": corpus["canonicalSource"], "documents": [article]}


@pytest.fixture(scope="module")
def ledger():
    return ReviewedProvisionLedger.load(LEDGER_PATH)


def test_article_iii_is_a_flat_exact_span_ledger(ledger):
    assert ledger.schema_version == "detroit-legal-ir-v1"
    assert len(ledger.provisions) == 1517
    assert all(item.review["status"] == "verified" for item in ledger.provisions)


def test_every_article_iii_span_verifies(article_iii_corpus, ledger):
    verify_provisions(article_iii_corpus, ledger.provisions)


def test_every_derived_source_block_has_a_disposition(article_iii_corpus, ledger):
    blocks = article_iii_corpus["documents"][0]["blocks"]
    cited = {source.source_index for item in ledger.provisions for source in item.sources}
    assert len(blocks) == 1431
    assert cited == {block["sourceIndex"] for block in blocks}
    assert all(item.review.get("disposition") for item in ledger.provisions)


def test_summary_table_cells_are_exact_and_explicitly_non_executable(ledger):
    table_cells = [
        item for item in ledger.provisions
        if item.effect["type"] == "procedure_summary_table_cell"
    ]
    assert len(table_cells) == 87
    assert all(item.sources[0].row is not None for item in table_cells)
    assert all(item.review["executionStatus"] == "non_executable_summary" for item in table_cells)


def test_ambiguous_procedures_are_not_claimed_as_executable(ledger):
    pending = [
        item for item in ledger.provisions
        if item.review["disposition"] == "pending_clause_review"
    ]
    assert pending
    assert all(
        item.effect["type"] == "procedure_source"
        and item.review["executionStatus"] == "non_executable_pending_clause_review"
        and item.review["notes"]
        for item in pending
    )


def test_reserved_ranges_are_explicitly_accounted_as_nonoperative(ledger):
    reserved = [item for item in ledger.provisions if item.effect["type"] == "reserved"]
    assert len(reserved) == 26
    assert all(
        item.review["disposition"] == "accounted_nonoperative"
        and item.review["executionStatus"] == "source_record_only"
        for item in reserved
    )


def test_every_article_iii_span_fails_independently_when_occluded(article_iii_corpus, ledger):
    for provision in ledger.provisions:
        for span in provision.sources:
            occluded = occlude_span(article_iii_corpus, span)
            with pytest.raises(ProvenanceError, match="changed or was occluded"):
                verify_provision(occluded, provision)
