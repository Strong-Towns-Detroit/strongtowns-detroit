import json
from pathlib import Path

import pytest

from strongtowns_detroit.zoning.article_v_semantics import build_article_v_semantic_trace
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
LEDGER = ROOT / "data/zoning-ordinance/reviewed-provisions/article-v.json"
TRACE = ROOT / "data/zoning-ordinance/reviewed-provisions/article-v-semantic-trace.json"


@pytest.fixture(scope="module")
def corpus():
    full = compile_municode_source_corpus(SNAPSHOT)
    article = next(item for item in full["documents"] if item["document"] == "ARTICLE_V.municode.json")
    return {"canonicalSource": full["canonicalSource"], "documents": [article]}


@pytest.fixture(scope="module")
def generated(corpus):
    return build_article_v_semantic_trace(corpus, ReviewedProvisionLedger.load(LEDGER))


def test_committed_trace_is_deterministic(generated):
    assert json.loads(TRACE.read_text(encoding="utf-8")) == generated


def test_every_pending_source_atom_has_a_trace_record(generated):
    assert generated["coverage"]["pendingSourceAtoms"] == 191
    assert generated["coverage"]["tracedSourceAtoms"] == 191
    assert len({item["sourceProvisionId"] for item in generated["records"]}) == 191
    assert "LegalRuleML" in generated["semanticArchitecture"]["sourceRuleTrace"]


def test_every_exact_proposition_verifies_and_fails_when_occluded(corpus, generated):
    for record in generated["records"]:
        for proposition in record["propositions"]:
            span = MunicodeSpan(**proposition["span"])
            verify_span(corpus, span)
            with pytest.raises(ProvenanceError, match="changed or was occluded"):
                verify_span(occlude_span(corpus, span), span)


def test_prose_decomposition_preserves_exact_ordered_text(corpus, generated):
    for record in generated["records"]:
        source = MunicodeSpan(**record["source"])
        if source.row is not None:
            continue
        propositions = record["propositions"]
        assert propositions
        starts = [item["span"]["start"] for item in propositions]
        assert starts == sorted(starts)
        assert all(item["text"] == item["span"]["quote"] for item in propositions)


def test_penalty_tables_compile_only_complete_dollar_rows(generated):
    schedules = [item for item in generated["dslProjections"] if item["type"] == "fine_schedule_lookup"]
    assert len(schedules) == 20
    assert all(set(item["values"]) == {"first", "second_repeat", "third_or_subsequent_repeat"} for item in schedules)
    assert all(len(item["sourceProvisionIds"]) == 4 for item in schedules)
    assert all(item["parameterization"]["validAtSnapshot"] == "2025-10-09_job-429936" for item in schedules)
    assert all(item["parameterization"]["effectiveDate"] is None for item in schedules)
    assert next(item for item in schedules if item["when"]["violation_category"] == "Unlawful change of use of building or land")["values"] == {
        "first": 2500.0, "second_repeat": 5000.0, "third_or_subsequent_repeat": 7500.0,
    }


def test_only_narrow_direct_computations_are_projected(generated):
    computed = [item for item in generated["dslProjections"] if item["type"] == "computed_standard"]
    assert len(computed) == 4
    multipliers = [
        item["expression"]["args"][1]
        for item in computed if item["metric"] == "payable_civil_fine"
    ]
    assert sorted(multipliers) == [0.9, 1.0, 1.1]
    assert any(item["metric"] == "separate_violation_count" for item in computed)


def test_every_unprojected_proposition_has_an_explicit_reason(generated):
    unprojected = [
        item for record in generated["records"] for item in record["propositions"]
        if item["status"] == "non_executable"
    ]
    assert unprojected
    assert all(item["dslProjection"] is None and item["nonExecutableReason"] for item in unprojected)
