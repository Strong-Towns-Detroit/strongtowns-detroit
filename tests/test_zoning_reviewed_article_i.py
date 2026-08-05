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
LEDGER_PATH = ROOT / "data/zoning-ordinance/reviewed-provisions/article-i.json"
DOCUMENT = "ARTICLE_I.municode.json"


@pytest.fixture(scope="module")
def article_i_corpus():
    corpus = compile_municode_source_corpus(SNAPSHOT)
    article = next(item for item in corpus["documents"] if item["document"] == DOCUMENT)
    return {
        "canonicalSource": corpus["canonicalSource"],
        "documents": [article],
    }


@pytest.fixture(scope="module")
def ledger():
    return ReviewedProvisionLedger.load(LEDGER_PATH)


def test_article_i_is_a_valid_flat_reviewed_provision_ledger(ledger):
    assert ledger.schema_version == "detroit-legal-ir-v1"
    assert len(ledger.provisions) == 113
    assert all(provision.review["status"] == "verified" for provision in ledger.provisions)


def test_every_article_i_span_verifies_against_canonical_municode(article_i_corpus, ledger):
    verify_provisions(article_i_corpus, ledger.provisions)


def test_every_derived_article_i_source_block_is_accounted_for(article_i_corpus, ledger):
    blocks = article_i_corpus["documents"][0]["blocks"]
    cited = {
        source.source_index
        for provision in ledger.provisions
        for source in provision.sources
    }

    assert len(blocks) == 101
    assert cited == {block["sourceIndex"] for block in blocks}


def test_article_i_classifies_purpose_history_authority_and_reserved_material(ledger):
    effects = [provision.effect for provision in ledger.provisions]

    assert sum(effect["type"] == "purpose" for effect in effects) == 17
    assert sum(effect["type"] == "history" for effect in effects) == 15
    assert sum(effect["type"] == "authority" for effect in effects) == 1
    assert any(
        effect["type"] == "reserved"
        and effect["range"] == {"from": "50-1-16", "through": "50-1-40"}
        for effect in effects
    )


def test_each_article_i_provision_fails_when_its_exact_span_is_occluded(
    article_i_corpus, ledger
):
    for provision in ledger.provisions:
        occluded = occlude_span(article_i_corpus, provision.sources[0])
        with pytest.raises(ProvenanceError, match="changed or was occluded"):
            verify_provision(occluded, provision)


def test_article_i_keeps_interpretation_questions_non_executable(ledger):
    by_id = {provision.id: provision for provision in ledger.provisions}

    applicability = by_id["detroit:50-1-3:citywide-applicability"]
    assert applicability.review["executionStatus"] == "requires_external_exemption_determination"
    assert applicability.review["notes"]

    government_conflict = by_id["detroit:50-1-8:government-conflict"]
    assert government_conflict.review["executionStatus"] == "requires_legal_comparison"
    assert government_conflict.review["notes"]
