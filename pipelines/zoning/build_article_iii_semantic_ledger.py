#!/usr/bin/env python3
"""Build atomic semantics for Article III's pending procedural sources."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from strongtowns_detroit.zoning.article_iii_semantics import decompose_pending_provision
from strongtowns_detroit.zoning.legal_ir import ReviewedProvisionLedger
from strongtowns_detroit.zoning.municode_source_model import (
    compile_municode_source_corpus,
    latest_snapshot,
)


ROOT = Path(__file__).resolve().parents[2]
DOCUMENT = "ARTICLE_III.municode.json"
PARENT_LEDGER = ROOT / "data/zoning-ordinance/reviewed-provisions/article-iii.json"
DEFAULT_OUTPUT = ROOT / "data/zoning-ordinance/reviewed-propositions/article-iii.json"
DEFAULT_DECISIONS = ROOT / "data/zoning-ordinance/reviewed-propositions/article-iii-decisions.json"


def build_article_iii_semantic_ledger(corpus: dict, parents: ReviewedProvisionLedger) -> ReviewedProvisionLedger:
    document = next(item for item in corpus["documents"] if item["document"] == DOCUMENT)
    block_text = {block["sourceIndex"]: block["text"] for block in document["blocks"] if block["type"] == "paragraph"}
    propositions = []
    parent_by_index = {p.sources[0].source_index: p for p in parents.provisions}
    for parent in parents.provisions:
        if parent.review.get("disposition") != "pending_clause_review":
            continue
        source = parent.sources[0]
        supporting = ()
        if source.source_index in {79, 81, 83, 85}:
            introduction = parent_by_index[77]
            supporting = ((introduction.id, introduction.sources[0]),)
        propositions.extend(decompose_pending_provision(
            parent, block_text[source.source_index], supporting_sources=supporting,
        ))
    return ReviewedProvisionLedger(tuple(propositions), schema_version="detroit-legal-propositions-v1")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--parent-ledger", type=Path, default=PARENT_LEDGER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)
    args = parser.parse_args()
    snapshot = args.snapshot or latest_snapshot(ROOT / "resources/municode")
    corpus = compile_municode_source_corpus(snapshot)
    ledger = build_article_iii_semantic_ledger(corpus, ReviewedProvisionLedger.load(args.parent_ledger))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(ledger.to_json() + "\n", encoding="utf-8")
    executable_items = [p for p in ledger.provisions if p.review["executionStatus"] == "executable"]
    decisions = {
        "schemaVersion": "detroit-article-iii-semantic-decisions-v1",
        "policy": {
            "default": "non_executable",
            "executableCriterion": (
                "The deadline line and its verified introductory source together state actor, "
                "event, forum, comparison, numeric value, and unit; the effect is supported by "
                "the procedural-deadline DSL."
            ),
            "excludedCategories": [
                "official_discretion_or_judgment",
                "context_or_exception_requires_modeling",
                "external_or_cross_referenced_rule_dependency",
                "no_complete_mandatory_operator",
                "procedure_not_yet_supported_by_executable_dsl",
            ],
        },
        "materialDecisions": [{
            "sourceSection": "50-3-10",
            "decision": "project_explicit_minimum_public_hearing_notice_periods",
            "propositionIds": [p.id for p in executable_items],
            "rationale": executable_items[0].review["rationale"] if executable_items else "",
            "architecture": {
                "sourceRuleRelationship": "LegalRuleML-inspired source/interpretation/rule trace",
                "executableShape": "Catala-inspired scope/base-definition/exceptions",
                "serialization": "project JSON; no XML migration",
            },
        }],
    }
    args.decisions.parent.mkdir(parents=True, exist_ok=True)
    args.decisions.write_text(json.dumps(decisions, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    executable = sum(p.review["executionStatus"] == "executable" for p in ledger.provisions)
    print(f"wrote {len(ledger.provisions)} propositions; {executable} executable")


if __name__ == "__main__":
    main()
