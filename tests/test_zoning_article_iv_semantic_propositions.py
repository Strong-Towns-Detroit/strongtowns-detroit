import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from strongtowns_detroit.zoning.legal_ir import (
    MunicodeSpan,
    ProvenanceError,
    ReviewedProvisionLedger,
    verify_span,
)
from strongtowns_detroit.zoning.municode_source_model import compile_municode_source_corpus
from strongtowns_detroit.zoning.occlusion import occlude_span


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "resources/municode/2025-10-09_job-429936"
LEDGER_PATH = ROOT / "data/zoning-ordinance/reviewed-provisions/article-iv.json"
PROPOSITIONS_PATH = ROOT / "data/zoning-ordinance/reviewed-provisions/article-iv-propositions.json"
AMBIGUITIES_PATH = ROOT / "data/zoning-ordinance/reviewed-provisions/article-iv-ambiguities.json"
BUILDER_PATH = ROOT / "pipelines/zoning/build_article_iv_semantic_propositions.py"
DOCUMENT = "ARTICLE_IV.municode.json"


@pytest.fixture(scope="module")
def corpus():
    compiled = compile_municode_source_corpus(SNAPSHOT)
    article = next(item for item in compiled["documents"] if item["document"] == DOCUMENT)
    return {"canonicalSource": compiled["canonicalSource"], "documents": [article]}


@pytest.fixture(scope="module")
def ledger():
    return ReviewedProvisionLedger.load(LEDGER_PATH)


@pytest.fixture(scope="module")
def payload():
    return json.loads(PROPOSITIONS_PATH.read_text(encoding="utf-8"))


def _builder_module():
    spec = importlib.util.spec_from_file_location("article_iv_semantics", BUILDER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_semantic_builder_is_deterministic_and_pinned_to_source_ledger(corpus, ledger, payload):
    rebuilt = _builder_module().build_propositions(corpus, ledger)

    assert rebuilt == payload
    assert payload["schemaVersion"] == "detroit-article-iv-propositions-v1"
    assert payload["sourceLedger"]["sha256"] == hashlib.sha256(LEDGER_PATH.read_bytes()).hexdigest()


def test_every_pending_source_atom_has_one_or_more_propositions(ledger, payload):
    pending_ids = {
        item.id for item in ledger.provisions
        if item.review["disposition"] == "pending_clause_review"
    }
    represented = {item["sourceProvisionId"] for item in payload["propositions"]}

    assert len(pending_ids) == 187
    assert represented == pending_ids
    assert len(payload["propositions"]) == 278


def test_every_proposition_has_an_exact_verified_child_span(corpus, payload):
    for item in payload["propositions"]:
        span = MunicodeSpan(**item["source"])
        verify_span(corpus, span)
        assert item["semantics"]["sourceText"] == span.quote
        assert item["transformation"]["parentStart"] <= span.start < span.end
        assert span.end <= item["transformation"]["parentEnd"]


def test_child_spans_cover_every_nonwhitespace_character_of_each_parent(ledger, payload):
    parents = {item.id: item for item in ledger.provisions}
    by_parent: dict[str, list[MunicodeSpan]] = {}
    for item in payload["propositions"]:
        by_parent.setdefault(item["sourceProvisionId"], []).append(MunicodeSpan(**item["source"]))

    for parent_id, spans in by_parent.items():
        parent = parents[parent_id].sources[0]
        covered = set()
        for span in spans:
            covered.update(range(span.start, span.end))
        for offset, character in enumerate(parent.quote, parent.start):
            if not character.isspace():
                assert offset in covered, (parent_id, offset, character)


def test_each_proposition_is_individually_occlusion_sensitive(corpus, payload):
    for item in payload["propositions"]:
        span = MunicodeSpan(**item["source"])
        occluded = occlude_span(corpus, span)
        with pytest.raises(ProvenanceError, match="changed or was occluded"):
            verify_span(occluded, span)


def test_only_reviewed_numeric_components_receive_dsl_projections(payload):
    projected = [item for item in payload["propositions"] if item["dslProjection"]]
    unprojected = [item for item in payload["propositions"] if not item["dslProjection"]]

    assert len(projected) == 10
    assert all(item["executionStatus"] == "partially_executable_numeric_projection" for item in projected)
    assert all(item["projectionScope"] == "numeric_component_only" for item in projected)
    assert all(item["dslProjection"]["type"] in {"numeric_limit", "numeric_lookback"} for item in projected)
    assert all(item["projectionScope"] is None for item in unprojected)
    assert all(item["executionStatus"] != "executable" for item in unprojected)


def test_formalization_metadata_preserves_priority_defeasibility_time_and_space(payload):
    for item in payload["propositions"]:
        formalization = item["formalization"]
        assert set(formalization) == {
            "legalRuleML", "catala", "temporalApplicability", "spatialVocabulary"
        }
        assert formalization["legalRuleML"]["defeasibility"]
        assert formalization["legalRuleML"]["priority"]
        assert formalization["temporalApplicability"]["status"]
        assert formalization["spatialVocabulary"]["standard"] == "OGC Simple Features / GeoSPARQL"
        assert formalization["spatialVocabulary"]["predicates"] == []


def test_consequential_ambiguities_are_separate_and_machine_queryable(payload):
    ambiguities = json.loads(AMBIGUITIES_PATH.read_text(encoding="utf-8"))
    by_flag = {group["flag"]: group for group in ambiguities["groups"]}

    assert ambiguities["schemaVersion"] == "detroit-article-iv-ambiguities-v1"
    assert by_flag["administrative_discretion"]["count"] == 36
    assert by_flag["open_legal_standard"]["count"] == 58
    assert by_flag["compound_modalities_remaining"]["count"] == 17
    assert by_flag["external_legal_dependency"]["count"] == 23
    proposition_ids = {item["id"] for item in payload["propositions"]}
    assert all(
        proposition_id in proposition_ids
        for group in ambiguities["groups"]
        for proposition_id in group["propositionIds"]
    )
    findings = {item["type"]: item for item in ambiguities["consequentialFindings"]}
    assert "source_internal_conflict" in findings
    assert "apparently_stale_internal_reference" in findings
    assert "compound_boolean_structure_pending" in findings
    assert "aspirational_not_hard_deadline" in findings
    assert "legal_judgment_required" in findings
