import json
from pathlib import Path

import pytest

from build_reviewed_article_vi import build_article_vi_ledger
from strongtowns_detroit.zoning.legal_ir import (
    ProvenanceError,
    ReviewedProvisionLedger,
    verify_provision,
    verify_provisions,
)
from strongtowns_detroit.zoning.legal_ir_coverage import aggregate_coverage
from strongtowns_detroit.zoning.municode_source_model import compile_municode_source_corpus
from strongtowns_detroit.zoning.occlusion import occlude_span


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "resources/municode/2025-10-09_job-429936"
LEDGER_PATH = ROOT / "data/zoning-ordinance/reviewed-provisions/article-vi.json"
DOCUMENT = "ARTICLE_VI.municode.json"


@pytest.fixture(scope="module")
def article_vi_corpus():
    corpus = compile_municode_source_corpus(SNAPSHOT)
    article = next(item for item in corpus["documents"] if item["document"] == DOCUMENT)
    return {"canonicalSource": corpus["canonicalSource"], "documents": [article]}


@pytest.fixture(scope="module")
def ledger():
    return ReviewedProvisionLedger.load(LEDGER_PATH)


def test_article_vi_ledger_is_deterministic_and_round_trips(article_vi_corpus, ledger):
    rebuilt = build_article_vi_ledger(article_vi_corpus)
    assert rebuilt == ledger
    assert ReviewedProvisionLedger.from_json(ledger.to_json()) == ledger
    assert len(ledger.provisions) == 3


def test_every_article_vi_source_atom_is_exact_and_independently_occludable(article_vi_corpus, ledger):
    verify_provisions(article_vi_corpus, ledger.provisions)
    assert {p.sources[0].source_index for p in ledger.provisions} == {0, 1, 2}
    for provision in ledger.provisions:
        occluded = occlude_span(article_vi_corpus, provision.sources[0])
        with pytest.raises(ProvenanceError, match="changed or was occluded"):
            verify_provision(occluded, provision)


def test_reserved_article_is_accounted_but_not_claimed_executable(ledger):
    reserved = [p for p in ledger.provisions if p.effect["type"] == "reserved"]
    assert len(reserved) == 2
    assert all(p.review["disposition"] == "accounted_nonoperative" for p in reserved)
    assert all(p.review["executionStatus"] == "source_record_only" for p in ledger.provisions)
    history = next(p for p in ledger.provisions if p.effect["type"] == "history")
    assert history.review["disposition"] == "accounted_contextual"
    assert "not executable" in history.review["notes"]


def test_article_vi_has_complete_character_coverage(article_vi_corpus, ledger, tmp_path):
    directory = tmp_path / "ledgers"
    directory.mkdir()
    payload = ledger.to_dict()
    payload.update({"document": DOCUMENT, "coverageStatus": "complete"})
    (directory / "article-vi.json").write_text(json.dumps(payload), encoding="utf-8")
    report = aggregate_coverage(article_vi_corpus, directory)
    assert report["ok"]
    assert report["completeArticleFailures"] == []
    assert report["counts"]["provisions"] == 3
    assert report["counts"]["blocks"] == {"cited": 3, "uncited": 0, "overlapping": 0}
    assert report["counts"]["gaps"] == {"substantive": 0, "whitespace": 0}
