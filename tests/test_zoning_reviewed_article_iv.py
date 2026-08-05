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
LEDGER_PATH = ROOT / "data/zoning-ordinance/reviewed-provisions/article-iv.json"
DOCUMENT = "ARTICLE_IV.municode.json"


@pytest.fixture(scope="module")
def article_iv_corpus():
    corpus = compile_municode_source_corpus(SNAPSHOT)
    article = next(item for item in corpus["documents"] if item["document"] == DOCUMENT)
    return {"canonicalSource": corpus["canonicalSource"], "documents": [article]}


@pytest.fixture(scope="module")
def ledger():
    return ReviewedProvisionLedger.load(LEDGER_PATH)


def test_article_iv_is_a_flat_roundtrippable_exact_span_ledger(ledger):
    assert ledger.schema_version == "detroit-legal-ir-v1"
    assert len(ledger.provisions) == 741
    assert ReviewedProvisionLedger.from_json(ledger.to_json()) == ledger
    assert all(item.review["status"] == "verified" for item in ledger.provisions)


def test_every_article_iv_span_verifies(article_iv_corpus, ledger):
    verify_provisions(article_iv_corpus, ledger.provisions)


def test_every_article_iv_source_block_has_a_disposition(article_iv_corpus, ledger):
    blocks = article_iv_corpus["documents"][0]["blocks"]
    cited = {source.source_index for item in ledger.provisions for source in item.sources}

    assert len(blocks) == 483
    assert cited == {block["sourceIndex"] for block in blocks}
    assert all(item.review.get("disposition") for item in ledger.provisions)


def test_informational_tables_are_complete_and_non_executable(article_iv_corpus, ledger):
    tables = [block for block in article_iv_corpus["documents"][0]["blocks"] if block["type"] == "table"]
    expected = sum(bool(cell) for table in tables for row in table["rows"] for cell in row)
    cells = [item for item in ledger.provisions if item.effect["type"] == "informational_historical_table_cell"]

    assert expected == len(cells) == 260
    assert all(item.sources[0].row is not None for item in cells)
    assert all(item.review["executionStatus"] == "non_executable_informational_table" for item in cells)


def test_reserved_history_and_structure_are_separate_from_pending_semantics(ledger):
    reserved = [item for item in ledger.provisions if item.effect["type"] == "reserved"]
    history = [item for item in ledger.provisions if item.effect["type"] == "history"]
    pending = [item for item in ledger.provisions if item.review["disposition"] == "pending_clause_review"]

    assert len(reserved) == 11
    assert len(history) == 78
    assert len(pending) == 187
    assert all(item.review["executionStatus"] == "source_record_only" for item in reserved + history)
    assert all(item.review["executionStatus"] == "non_executable_pending_clause_review" for item in pending)


def test_compound_discretionary_and_ambiguous_text_remains_pending(ledger):
    expected_counts = {
        "compound_procedure_source": 12,
        "discretionary_procedure_source": 19,
        "mandatory_procedure_source": 66,
        "ambiguous_procedure_source": 90,
    }
    for effect_type, expected in expected_counts.items():
        items = [item for item in ledger.provisions if item.effect["type"] == effect_type]
        assert len(items) == expected
        assert all(
            item.review["disposition"] == "pending_clause_review"
            and item.review["notes"]
            for item in items
        )


def test_every_article_iv_span_fails_independently_when_occluded(article_iv_corpus, ledger):
    for provision in ledger.provisions:
        for span in provision.sources:
            occluded = occlude_span(article_iv_corpus, span)
            with pytest.raises(ProvenanceError, match="changed or was occluded"):
                verify_provision(occluded, provision)
