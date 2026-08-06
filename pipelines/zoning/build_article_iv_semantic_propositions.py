#!/usr/bin/env python3
"""Decompose Article IV source atoms into traceable legal propositions.

This is a deliberately conservative second layer. Sentence- and clause-level
spans are classified, but only a short reviewed allowlist of unambiguous
numeric rules receives a DSL projection. Administrative findings, open
standards, inherited list context, and external law remain queryable blockers.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import re
from pathlib import Path

from strongtowns_detroit.zoning.citations import extract_citations
from strongtowns_detroit.zoning.legal_ir import MunicodeSpan, ReviewedProvisionLedger
from strongtowns_detroit.zoning.municode_source_model import (
    compile_municode_source_corpus,
    latest_snapshot,
)


ROOT = Path(__file__).resolve().parents[2]
DOCUMENT = "ARTICLE_IV.municode.json"
SOURCE_LEDGER = ROOT / "data/zoning-ordinance/reviewed-provisions/article-iv.json"
DEFAULT_OUTPUT = ROOT / "data/zoning-ordinance/reviewed-provisions/article-iv-propositions.json"
DEFAULT_AMBIGUITIES = ROOT / "data/zoning-ordinance/reviewed-provisions/article-iv-ambiguities.json"
ABBREVIATIONS = ("No.", "Nos.", "MCL.", "U.S.", "e.g.", "i.e.", "et seq.")
MODAL_RE = re.compile(r"\b(shall not|may not|must not|shall|must|required to|may|will not|will)\b", re.I)
OPEN_STANDARD_RE = re.compile(
    r"\b(?:reasonable|reasonably|adequate|appropriate|necessary|detrimental|"
    r"harmon(?:y|ious)|intent|purpose|hardship|minimal|sufficient|good cause|"
    r"opinion|determination|deemed|feasible|practical difficulty)\b",
    re.I,
)
EXTERNAL_RE = re.compile(
    r"\b(?:MCL|Michigan .* Act|Charter|Chapter \d+|federal|state statutes?|"
    r"United States Constitution|Michigan Constitution)\b",
    re.I,
)
CONDITION_RE = re.compile(r"\b(?:if|unless|where|when|provided|except|upon|after|prior to)\b", re.I)


EXECUTABLE_PROJECTIONS: dict[int, tuple[str, dict]] = {
    151: (
        "The text states a closed maximum duration and express conformity conditions.",
        {"type":"numeric_limit","metric":"temporary_certificate_duration","operator":"<=","value":6,"unit":"months"},
    ),
    230: (
        "The first sentence states a closed one-year resubmission bar with an express exception.",
        {"type":"numeric_limit","metric":"denied_appeal_resubmission_wait","operator":">=","value":1,"unit":"year"},
    ),
    267: (
        "The listed administrative-adjustment category states a closed percentage ceiling.",
        {"type":"numeric_limit","metric":"numeric_standard_administrative_adjustment","operator":"<=","value":10,"unit":"percent"},
    ),
    271: (
        "The listed marijuana spacing-adjustment category states a closed percentage ceiling.",
        {"type":"numeric_limit","metric":"marijuana_spacing_reduction","operator":"<=","value":2,"unit":"percent"},
    ),
    317: (
        "The text states a closed minimum notice period while retaining referenced notice procedures as dependencies.",
        {"type":"numeric_limit","metric":"variance_hearing_notice","operator":">=","value":15,"unit":"days_before_hearing"},
    ),
    387: (
        "The application-information item states a closed three-year appraisal lookback.",
        {"type":"numeric_lookback","metric":"hardship_petition_appraisals","operator":"<=","value":3,"unit":"years_before_application"},
    ),
    389: (
        "The application-information item states a closed three-year assessment and tax lookback.",
        {"type":"numeric_lookback","metric":"hardship_petition_assessment_and_tax_history","operator":"=","value":3,"unit":"previous_years"},
    ),
    395: (
        "The application-information item states a closed three-year commissioned-study lookback.",
        {"type":"numeric_lookback","metric":"hardship_petition_feasibility_studies","operator":"<=","value":3,"unit":"years_before_application"},
    ),
    397: (
        "The application-information item states a closed three-year income and expense lookback.",
        {"type":"numeric_lookback","metric":"hardship_petition_income_expense_statements","operator":"=","value":3,"unit":"previous_years"},
    ),
    399: (
        "The application-information item states a closed three-year expenditure lookback.",
        {"type":"numeric_lookback","metric":"hardship_petition_property_expenditures","operator":"<=","value":3,"unit":"past_years"},
    ),
}


def _split_ranges(text: str) -> list[tuple[int, int, str]]:
    """Split only at defensible sentence or explicit compound boundaries."""
    boundaries = [0]
    for match in re.finditer(r"[.!?]\s+", text):
        end = match.start() + 1
        prefix = text[:end]
        if any(prefix.endswith(item) for item in ABBREVIATIONS):
            continue
        boundaries.append(end)
        boundaries.append(match.end())
    boundaries.append(len(text))
    raw = []
    for start, end in zip(boundaries[::2], boundaries[1::2]):
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if start < end:
            raw.append((start, end, "sentence_or_semicolon_boundary"))

    result: list[tuple[int, int, str]] = []
    queue = list(raw)
    while queue:
        start, end, method = queue.pop(0)
        segment = text[start:end]
        provided = re.search(r",\s+provided,\s+(?:further\s+)?that\s+", segment, re.I)
        coordinated = re.search(r"\s+(?:and|but)\s+(?=(?:may|shall)\b)", segment, re.I)
        match = provided or coordinated
        if match is None:
            result.append((start, end, method))
            continue
        if provided:
            first_end = start + match.start() + 1  # retain the comma
            second_start = start + match.start() + 2  # retain "provided"
            split_method = "explicit_proviso_boundary"
        else:
            first_end = start + match.start()
            second_start = start + match.start() + len(match.group(0)) - len(match.group(0).lstrip())
            split_method = "coordinated_modal_clause"
        queue.insert(0, (second_start, end, split_method))
        queue.insert(0, (start, first_end, split_method))
    return result


def _semantic_shape(text: str) -> tuple[str, str, list[str]]:
    modals = [match.group(1).lower() for match in MODAL_RE.finditer(text)]
    flags: list[str] = []
    if len(modals) > 1:
        flags.append("compound_modalities_remaining")
    if any(value in {"may", "may not"} for value in modals):
        flags.append("administrative_discretion")
    if OPEN_STANDARD_RE.search(text):
        flags.append("open_legal_standard")
    if EXTERNAL_RE.search(text):
        flags.append("external_legal_dependency")
    if CONDITION_RE.search(text):
        flags.append("factual_or_procedural_condition")
    lower = text.lower()
    if "make every effort" in lower or "to the extent possible" in lower or "as nearly as possible" in lower:
        flags.append("aspirational_timing")

    if any(value in {"shall not", "must not", "may not", "will not"} for value in modals):
        modality, effect_type = "prohibition", "prohibition"
    elif any(value in {"shall", "must", "required to", "will"} for value in modals):
        modality, effect_type = "mandatory", "requirement"
    elif "may" in modals:
        modality, effect_type = "discretionary", "authority"
    else:
        modality, effect_type = "declarative_or_inherited", "context_or_inherited_rule"
        flags.append("modality_inherited_or_unstated")
    return modality, effect_type, sorted(set(flags))


def _formalization_hints(
    text: str, modality: str, flags: list[str], dependencies: list[dict], projection: dict | None
) -> dict:
    """Record formal-model alignment without pretending unresolved semantics are solved."""
    if "administrative_discretion" in flags or "open_legal_standard" in flags:
        defeasibility = "defeasible_or_judgment_dependent_pending_review"
    elif "factual_or_procedural_condition" in flags:
        defeasibility = "explicit_conditions_present_pending_scope_encoding"
    else:
        defeasibility = "no_defeater_identified_in_this_span"
    priority = (
        "more_restrictive_rule_priority_requires_comparison"
        if "more restrictive" in text.lower()
        else "no_priority_relation_identified_in_this_span"
    )
    temporal_terms = re.findall(
        r"\b(?:\d+|one|two|three|six|ten|fifteen)\s+(?:days?|months?|years?)\b|"
        r"\b(?:prior to|after|within|until|effective date|date of application)\b",
        text,
        re.I,
    )
    spatial_terms = sorted({
        term for term in (
            "property", "site", "zoning lot", "district", "adjacent", "within", "setback",
            "spacing", "location", "building", "structure",
        ) if term in text.lower()
    })
    return {
        "legalRuleML": {
            "status": "alignment_recorded_not_serialized_as_legalruleml",
            "strength": modality,
            "defeasibility": defeasibility,
            "priority": priority,
            "dependencyCount": len(dependencies),
        },
        "catala": {
            "status": (
                "numeric_base_definition_projected_with_scope_dependencies"
                if projection else "base_definition_or_exception_structure_pending"
            ),
            "baseDefinition": projection,
            "exceptionsAndScopes": [
                flag for flag in flags
                if flag in {"factual_or_procedural_condition", "administrative_discretion", "open_legal_standard"}
            ],
        },
        "temporalApplicability": {
            "status": "explicit_terms_require_scope_review" if temporal_terms else "no_explicit_temporal_term_in_span",
            "terms": temporal_terms,
        },
        "spatialVocabulary": {
            "standard": "OGC Simple Features / GeoSPARQL",
            "status": "predicate_selection_pending" if spatial_terms else "not_applicable_on_text_review",
            "terms": spatial_terms,
            "predicates": [],
        },
    }


def build_propositions(corpus: dict, ledger: ReviewedProvisionLedger) -> dict:
    document = next(item for item in corpus["documents"] if item["document"] == DOCUMENT)
    blocks = {block["sourceIndex"]: block for block in document["blocks"]}
    pending = [item for item in ledger.provisions if item.review["disposition"] == "pending_clause_review"]
    pending_by_section: dict[str | None, list] = {}
    for item in pending:
        pending_by_section.setdefault(item.sources[0].section, []).append(item)

    propositions = []
    for parent in pending:
        parent_span = parent.sources[0]
        block = blocks[parent_span.source_index]
        text = block["text"]
        ranges = _split_ranges(text)
        for ordinal, (start, end, split_method) in enumerate(ranges, 1):
            quote = text[start:end]
            span = MunicodeSpan.cite(
                snapshot=parent_span.snapshot,
                document=DOCUMENT,
                node_id=parent_span.node_id,
                source_index=parent_span.source_index,
                section=parent_span.section,
                text=text,
                start=start,
                end=end,
            )
            modality, effect_type, flags = _semantic_shape(quote)
            dependencies: list[dict] = []
            for citation in extract_citations(quote, parent_span.section or ""):
                dependencies.append({
                    "type": "legal_cross_reference",
                    "target": citation.target,
                    "citationType": citation.citation_type.value,
                    "rawText": citation.raw_text,
                })
            section_items = pending_by_section[parent_span.section]
            position = section_items.index(parent)
            if position and parent_span.source_index >= 2:
                previous = section_items[position - 1]
                previous_quote = previous.sources[0].quote
                if previous_quote.endswith(":"):
                    dependencies.append({
                        "type": "inherited_list_context",
                        "sourceProvisionId": previous.id,
                    })
                    flags.append("modality_or_effect_inherited_from_list_intro")

            projection = None
            rationale = (
                "The parent Municode paragraph was split at explicit sentence, semicolon, "
                "or coordinated-modal boundaries; no unstated actor was supplied."
            )
            if parent_span.source_index in EXECUTABLE_PROJECTIONS:
                reviewed_rationale, candidate = EXECUTABLE_PROJECTIONS[parent_span.source_index]
                # Multi-sentence parents only project the proposition containing the
                # relevant numeric language.
                numeric_tokens = ("six months", "one year", "ten percent", "two percent", "15 days", "three years")
                if any(token in quote.lower() for token in numeric_tokens):
                    projection = candidate
                    execution_status = "partially_executable_numeric_projection"
                    rationale = reviewed_rationale
                else:
                    execution_status = "non_executable_context_fragment"
            elif "compound_modalities_remaining" in flags:
                execution_status = "pending_further_compound_decomposition"
            elif "administrative_discretion" in flags:
                execution_status = "pending_administrative_discretion"
            elif "open_legal_standard" in flags:
                execution_status = "pending_open_legal_standard"
            elif "modality_inherited_or_unstated" in flags:
                execution_status = "pending_inherited_or_unstated_effect"
            elif dependencies:
                execution_status = "structured_non_executable_with_dependencies"
            else:
                execution_status = "structured_non_executable_procedure"

            propositions.append({
                "id": f"{parent.id}:proposition:{ordinal}",
                "sourceProvisionId": parent.id,
                "source": asdict(span),
                "transformation": {
                    "method": split_method,
                    "rationale": rationale,
                    "parentStart": parent_span.start,
                    "parentEnd": parent_span.end,
                },
                "semantics": {
                    "modality": modality,
                    "effectType": effect_type,
                    "sourceText": quote,
                },
                "dependencies": dependencies,
                "judgmentFlags": sorted(set(flags)),
                "executionStatus": execution_status,
                "dslProjection": projection,
                "projectionScope": "numeric_component_only" if projection else None,
                "formalization": _formalization_hints(
                    quote, modality, flags, dependencies, projection
                ),
            })

    return {
        "schemaVersion": "detroit-article-iv-propositions-v1",
        "sourceLedger": {
            "path": str(SOURCE_LEDGER.relative_to(ROOT)),
            "sha256": hashlib.sha256(SOURCE_LEDGER.read_bytes()).hexdigest(),
        },
        "article": "IV",
        "propositions": propositions,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--ledger", type=Path, default=SOURCE_LEDGER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--ambiguities-output", type=Path, default=DEFAULT_AMBIGUITIES)
    args = parser.parse_args()
    snapshot = args.snapshot or latest_snapshot(ROOT / "resources/municode")
    corpus = compile_municode_source_corpus(snapshot)
    ledger = ReviewedProvisionLedger.load(args.ledger)
    result = build_propositions(corpus, ledger)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ambiguity_descriptions = {
        "compound_modalities_remaining": "More than one modal legal operation remains in a proposition span.",
        "administrative_discretion": "The source grants or withholds administrative discretion; no outcome is automatic.",
        "open_legal_standard": "Application depends on an evaluative legal standard such as reasonable, adequate, necessary, or hardship.",
        "external_legal_dependency": "The proposition depends on authority or standards outside this source span.",
        "factual_or_procedural_condition": "A factual trigger, exception, or procedural prerequisite must be established.",
        "modality_inherited_or_unstated": "The proposition is a list item or declaration whose legal modality is inherited or unstated.",
        "modality_or_effect_inherited_from_list_intro": "The proposition depends on a preceding list introduction for its legal effect.",
        "aspirational_timing": "Timing is qualified by effort or feasibility language and is not encoded as a hard deadline.",
    }
    groups = []
    for flag, description in ambiguity_descriptions.items():
        ids = [item["id"] for item in result["propositions"] if flag in item["judgmentFlags"]]
        groups.append({"flag": flag, "description": description, "count": len(ids), "propositionIds": ids})
    ambiguity_payload = {
        "schemaVersion": "detroit-article-iv-ambiguities-v1",
        "article": "IV",
        "sourcePropositions": str(args.output.relative_to(ROOT)),
        "groups": groups,
        "consequentialFindings": [
            {
                "id": "article-iv:50-4-121:boolean-criteria-hierarchy",
                "section": "50-4-121",
                "type": "compound_boolean_structure_pending",
                "description": "The source permits approval upon either a federal reasonable-accommodation finding or satisfaction of the full nested criteria list. The AND/OR hierarchy remains unprojected.",
                "sourceProvisionIds": ["detroit:article-iv:block:238", "detroit:article-iv:block:240", "detroit:article-iv:block:242"],
            },
            {
                "id": "article-iv:50-4-131:enumeration-count-conflict",
                "section": "50-4-131",
                "type": "source_internal_conflict",
                "description": "The introductory text says dimensional variances may be granted in seven instances, but the canonical source enumerates only five numbered instances.",
                "sourceProvisionIds": ["detroit:article-iv:block:320", "detroit:article-iv:block:322", "detroit:article-iv:block:324", "detroit:article-iv:block:326", "detroit:article-iv:block:328", "detroit:article-iv:block:334"],
            },
            {
                "id": "article-iv:50-4-132:reserved-article-reference",
                "section": "50-4-132",
                "type": "apparently_stale_internal_reference",
                "description": "The use-variance clause references quantified dimensional standards in Article VI, Divisions 2, 3, and 4, while canonical Article VI is reserved. No intended replacement is inferred.",
                "sourceProvisionIds": ["detroit:article-iv:block:339"],
            },
            {
                "id": "article-iv:qualified-time-periods",
                "section": "multiple",
                "type": "aspirational_not_hard_deadline",
                "description": "Ten-day, annual, and two 30-day periods are qualified by every-effort, as-nearly-as-possible, or to-the-extent-possible language and are not encoded as hard deadlines.",
                "sourceProvisionIds": ["detroit:article-iv:block:52", "detroit:article-iv:block:129", "detroit:article-iv:block:417", "detroit:article-iv:block:425"],
            },
            {
                "id": "article-iv:open-standards-and-board-discretion",
                "section": "multiple",
                "type": "legal_judgment_required",
                "description": "Practical difficulty, substantial justice, adequate mitigation, exceptional hardship, reasonable economic use, and appropriate relief require administrative or legal judgment and remain non-executable.",
                "sourceProvisionIds": ["detroit:article-iv:block:246", "detroit:article-iv:block:248", "detroit:article-iv:block:252", "detroit:article-iv:block:260", "detroit:article-iv:block:350", "detroit:article-iv:block:371", "detroit:article-iv:block:463"],
            },
        ],
    }
    args.ambiguities_output.parent.mkdir(parents=True, exist_ok=True)
    args.ambiguities_output.write_text(
        json.dumps(ambiguity_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    executable = sum(item["dslProjection"] is not None for item in result["propositions"])
    print(f"wrote {len(result['propositions'])} propositions; {executable} partial numeric projections")


if __name__ == "__main__":
    main()
