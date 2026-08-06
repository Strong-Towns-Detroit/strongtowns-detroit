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
LEDGER_PATH = ROOT / "data/zoning-ordinance/reviewed-provisions/article-v.json"
DOCUMENT = "ARTICLE_V.municode.json"


@pytest.fixture(scope="module")
def article_v_corpus():
    corpus = compile_municode_source_corpus(SNAPSHOT)
    article = next(item for item in corpus["documents"] if item["document"] == DOCUMENT)
    return {"canonicalSource": corpus["canonicalSource"], "documents": [article]}


@pytest.fixture(scope="module")
def ledger():
    return ReviewedProvisionLedger.load(LEDGER_PATH)


def test_article_v_is_a_flat_exact_span_ledger(ledger):
    assert ledger.schema_version == "detroit-legal-ir-v1"
    assert len(ledger.provisions) == 321
    assert all(item.review["status"] == "verified" for item in ledger.provisions)


def test_ledger_round_trips_without_losing_article_v_spans(ledger):
    restored = ReviewedProvisionLedger.from_json(ledger.to_json())
    assert restored == ledger


def test_every_article_v_span_verifies(article_v_corpus, ledger):
    verify_provisions(article_v_corpus, ledger.provisions)


def test_every_derived_article_v_block_has_a_disposition(article_v_corpus, ledger):
    blocks = article_v_corpus["documents"][0]["blocks"]
    cited = {source.source_index for item in ledger.provisions for source in item.sources}
    assert len(blocks) == 217
    assert cited == {block["sourceIndex"] for block in blocks}
    assert all(item.review.get("disposition") for item in ledger.provisions)


def test_all_penalty_table_cells_remain_non_executable_pending_review(ledger):
    cells = [item for item in ledger.provisions if item.effect["type"] == "penalty_table_cell"]
    assert len(cells) == 108
    assert all(item.sources[0].row is not None for item in cells)
    assert all(
        item.review["executionStatus"] == "non_executable_pending_penalty_table_review"
        and "compound_table" in item.review["flags"]
        for item in cells
    )


def test_compound_discretionary_and_external_provisions_are_flagged_pending(ledger):
    pending = [item for item in ledger.provisions if item.review["disposition"] == "pending_compound_review"]
    assert pending
    assert all(item.review["executionStatus"].startswith("non_executable_pending_") for item in pending)
    assert all(item.review["notes"] for item in pending)
    flags = {flag for item in pending for flag in item.review["flags"]}
    assert {
        "compound_enforcement_semantics",
        "discretion_or_open_standard",
        "external_legal_dependency",
        "compound_table",
    }.issubset(flags)


def test_reserved_ranges_are_explicitly_nonoperative(ledger):
    reserved = [item for item in ledger.provisions if item.effect["type"] == "reserved"]
    assert len(reserved) == 4
    assert all(item.review["disposition"] == "accounted_nonoperative" for item in reserved)


def test_every_article_v_span_fails_independently_when_occluded(article_v_corpus, ledger):
    for provision in ledger.provisions:
        for span in provision.sources:
            occluded = occlude_span(article_v_corpus, span)
            with pytest.raises(ProvenanceError, match="changed or was occluded"):
                verify_provision(occluded, provision)
