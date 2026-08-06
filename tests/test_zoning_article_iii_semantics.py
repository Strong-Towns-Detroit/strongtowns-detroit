from collections import defaultdict
from pathlib import Path

import pytest

from build_article_iii_semantic_ledger import build_article_iii_semantic_ledger
from strongtowns_detroit.zoning.article_iii_semantics import project_article_iii_proposition
from strongtowns_detroit.zoning.legal_ir import (
    ProjectionError,
    ProvenanceError,
    ReviewedProvisionLedger,
    verify_provision,
    verify_provisions,
)
from strongtowns_detroit.zoning.municode_source_model import compile_municode_source_corpus
from strongtowns_detroit.zoning.occlusion import occlude_span


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "resources/municode/2025-10-09_job-429936"
SOURCE_LEDGER = ROOT / "data/zoning-ordinance/reviewed-provisions/article-iii.json"
SEMANTIC_LEDGER = ROOT / "data/zoning-ordinance/reviewed-propositions/article-iii.json"
DOCUMENT = "ARTICLE_III.municode.json"


@pytest.fixture(scope="module")
def corpus():
    complete = compile_municode_source_corpus(SNAPSHOT)
    article = next(item for item in complete["documents"] if item["document"] == DOCUMENT)
    return {"canonicalSource": complete["canonicalSource"], "documents": [article]}


@pytest.fixture(scope="module")
def parents():
    return ReviewedProvisionLedger.load(SOURCE_LEDGER)


@pytest.fixture(scope="module")
def ledger():
    return ReviewedProvisionLedger.load(SEMANTIC_LEDGER)


def test_all_586_pending_sources_are_deterministically_decomposed(corpus, parents, ledger):
    assert ledger.schema_version == "detroit-legal-propositions-v1"
    assert len(ledger.provisions) == 886
    assert len({p.review["parentSourceId"] for p in ledger.provisions}) == 586
    assert build_article_iii_semantic_ledger(corpus, parents) == ledger
    assert ReviewedProvisionLedger.from_json(ledger.to_json()) == ledger


def test_every_atomic_span_verifies_and_accounts_for_parent_non_whitespace(corpus, parents, ledger):
    verify_provisions(corpus, ledger.provisions)
    by_parent = defaultdict(list)
    for proposition in ledger.provisions:
        by_parent[proposition.review["parentSourceId"]].append(proposition.sources[0])
    pending = [p for p in parents.provisions if p.review.get("disposition") == "pending_clause_review"]
    for parent in pending:
        source = parent.sources[0]
        covered = [False] * len(source.quote)
        for span in by_parent[parent.id]:
            for offset in range(span.start - source.start, span.end - source.start):
                covered[offset] = True
        assert all(flag or character.isspace() for flag, character in zip(covered, source.quote))


def test_every_proposition_has_deterministic_trace_and_occlusion_failure(corpus, ledger):
    blocks = {b["sourceIndex"]: b for b in corpus["documents"][0]["blocks"]}
    for proposition in ledger.provisions:
        span = proposition.sources[0]
        atom_corpus = {
            "canonicalSource": corpus["canonicalSource"],
            "documents": [{"document": DOCUMENT, "blocks": [blocks[span.source_index]]}],
        }
        for supporting_span in proposition.sources:
            support_block = blocks[supporting_span.source_index]
            support_corpus = {
                "canonicalSource": corpus["canonicalSource"],
                "documents": [{"document": DOCUMENT, "blocks": [blocks[span.source_index], support_block]}],
            }
            # Avoid duplicating the same dict when the primary span is the support.
            support_corpus["documents"][0]["blocks"] = list({b["sourceIndex"]: b for b in support_corpus["documents"][0]["blocks"]}.values())
            occluded = occlude_span(support_corpus, supporting_span)
            with pytest.raises(ProvenanceError, match="changed or was occluded"):
                verify_provision(occluded, proposition)
        assert proposition.review["parentSourceId"] in proposition.id
        assert "rationale" in proposition.review
        assert proposition.review["dependencies"][:len(proposition.cross_references)] == list(proposition.cross_references)
        assert proposition.review["interpretation"] == "literal_source_bound"
        assert proposition.review["legalRuleModel"]


def test_only_four_unambiguous_notice_deadlines_project(corpus, ledger):
    executable = [p for p in ledger.provisions if p.review["executionStatus"] == "executable"]
    assert [p.effect["value"] for p in executable] == [15, 15, 15, 5]
    projected = [project_article_iii_proposition(corpus, p) for p in executable]
    assert all(item["kind"] == "procedural_deadline" for item in projected)
    assert {item["baseDefinition"]["consequence"]["operator"] for item in projected} == {">="}
    assert all(item["exceptions"] == [] for item in projected)
    assert all(len(item["sourceIds"]) == 2 for item in projected)
    occluded = occlude_span(corpus, executable[0].sources[0])
    with pytest.raises(ProvenanceError):
        project_article_iii_proposition(occluded, executable[0])


def test_non_executable_propositions_have_machine_readable_reasons(corpus, ledger):
    pending = [p for p in ledger.provisions if p.review["executionStatus"] == "non_executable"]
    assert len(pending) == 882
    assert all(p.review["nonExecutionReasons"] for p in pending)
    with pytest.raises(ProjectionError, match="non-executable"):
        project_article_iii_proposition(corpus, pending[0])
