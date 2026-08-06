"""Traceable semantic decomposition of Detroit zoning Article V.

The input is the exact-span Article V ledger. This module splits pending prose
into exact subspans and emits only narrow projections whose result follows from
the source once the required input classification is supplied.
"""

from __future__ import annotations

from dataclasses import asdict
import re
from typing import Any, Mapping

from .citations import extract_citations
from .legal_ir import (
    LegalProvision,
    MunicodeSpan,
    ReviewedProvisionLedger,
    find_block,
    span_digest,
)


CLAUSE_BOUNDARY_RE = re.compile(r";\s+|(?<=[.!?])\s+(?=[A-Z\"])")
COMPOUND_RE = re.compile(r"\b(?:and|or|unless|except|provided|where|whenever)\b", re.I)
DISCRETION_RE = re.compile(
    r"\b(?:may|reasonable|appropriate|deemed|determines?|satisfaction|"
    r"discretion|presumed|good cause|injurious|nuisance)\b",
    re.I,
)
EXTERNAL_RE = re.compile(
    r"\b(?:state law|Michigan|MCL|Charter|Chapter [0-9]|administrative rules|"
    r"court|bylaws?)\b",
    re.I,
)
MONEY_RE = re.compile(r"^\$([\d,]+(?:\.\d{2})?)$")


def build_article_v_semantic_trace(
    corpus: Mapping[str, Any], source_ledger: ReviewedProvisionLedger
) -> dict[str, Any]:
    pending = tuple(
        item for item in source_ledger.provisions
        if item.review.get("disposition") == "pending_compound_review"
    )
    records: list[dict[str, Any]] = []
    for provision in pending:
        source = provision.sources[0]
        block = find_block(corpus, source)
        if source.row is None:
            propositions = _prose_propositions(block, provision)
        else:
            propositions = [_table_cell_proposition(provision)]
        records.append({
            "sourceProvisionId": provision.id,
            "sourceDisposition": provision.review["disposition"],
            "source": asdict(source),
            "propositions": propositions,
        })
    projections = _penalty_schedule_projections(corpus, source_ledger)
    projections.extend(_direct_projections(records))
    return {
        "schemaVersion": "detroit-article-v-semantic-trace-v1",
        "semanticArchitecture": {
            "sourceRuleTrace": "LegalRuleML-style exact source association and dependency trace",
            "executableScope": "Catala-style scoped definitions and exceptions only where source-complete",
            "numericParameters": "OpenFisca-style versioned schedules at the pinned snapshot",
            "policy": "No priority, defeasibility, exception, or temporal rule is inferred from silence.",
        },
        "sourceLedger": "data/zoning-ordinance/reviewed-provisions/article-v.json",
        "sourceSnapshot": corpus["canonicalSource"]["snapshot"],
        "records": records,
        "dslProjections": sorted(projections, key=lambda item: item["id"]),
        "coverage": {
            "pendingSourceAtoms": len(pending),
            "tracedSourceAtoms": len(records),
            "exactPropositions": sum(len(item["propositions"]) for item in records),
            "executableProjections": len(projections),
            "nonExecutablePropositions": sum(
                proposition["status"] == "non_executable"
                for record in records for proposition in record["propositions"]
            ),
        },
    }


def _prose_propositions(block: Mapping[str, Any], provision: LegalProvision) -> list[dict]:
    text = str(block["text"])
    ranges = _clause_ranges(text)
    result = []
    for ordinal, (start, end) in enumerate(ranges, 1):
        quote = text[start:end]
        span = MunicodeSpan.cite(
            snapshot=provision.sources[0].snapshot,
            document=provision.sources[0].document,
            node_id=provision.sources[0].node_id,
            source_index=provision.sources[0].source_index,
            section=provision.sources[0].section,
            text=text,
            start=start,
            end=end,
        )
        proposition_type = _proposition_type(span.section, quote)
        dependencies = sorted({
            citation.target for citation in extract_citations(quote, span.section or "")
        })
        reason_flags = []
        if COMPOUND_RE.search(quote):
            reason_flags.append("compound_logical_relationship")
        if DISCRETION_RE.search(quote):
            reason_flags.append("discretion_or_open_standard")
        if EXTERNAL_RE.search(quote) or dependencies:
            reason_flags.append("external_or_cross_referenced_law")
        projection = _direct_projection(span, quote)
        result.append({
            "id": f"{provision.id}:proposition:{ordinal}",
            "text": quote,
            "type": proposition_type,
            "span": asdict(span),
            "transformationRationale": (
                "Exact sentence/semicolon-bounded source clause; no words were "
                "paraphrased or supplied."
            ),
            "dependencies": dependencies,
            "status": "supports_projection" if projection else "non_executable",
            "dslProjection": projection,
            "nonExecutableReason": None if projection else (
                reason_flags or ["semantic_actor_trigger_or_consequence_not_yet_normalized"]
            ),
        })
    return result


def _table_cell_proposition(provision: LegalProvision) -> dict:
    span = provision.sources[0]
    money = MONEY_RE.match(span.quote)
    is_header = span.row == 0
    return {
        "id": f"{provision.id}:proposition:1",
        "text": span.quote,
        "type": "penalty_amount" if money else "penalty_matrix_label",
        "span": asdict(span),
        "transformationRationale": "Exact rectangularized Municode table cell.",
        "dependencies": [span.section] if span.section else [],
        "status": "supports_projection" if money else "contextual",
        "dslProjection": (
            {"type": "fine_amount_operand", "value": float(money.group(1).replace(",", "")), "unit": "usd"}
            if money else None
        ),
        "nonExecutableReason": (
            None if money else
            ["table_header"] if is_header else
            ["row_or_group_label_requires_sibling_amount_cells"]
        ),
    }


def _clause_ranges(text: str) -> list[tuple[int, int]]:
    ranges = []
    cursor = 0
    for match in CLAUSE_BOUNDARY_RE.finditer(text):
        end = match.start() + (1 if text[match.start():].startswith(";") else 0)
        if text[cursor:end].strip():
            start = cursor + len(text[cursor:end]) - len(text[cursor:end].lstrip())
            trimmed_end = end - len(text[cursor:end]) + len(text[cursor:end].rstrip())
            ranges.append((start, trimmed_end))
        cursor = match.end()
    if text[cursor:].strip():
        start = cursor + len(text[cursor:]) - len(text[cursor:].lstrip())
        ranges.append((start, len(text.rstrip())))
    return ranges


def _proposition_type(section: str | None, text: str) -> str:
    number = int(section.rsplit("-", 1)[1]) if section else 0
    if 21 <= number <= 35:
        return "violation_or_penalty_rule"
    if 51 <= number <= 60:
        return "remedy_or_enforcement_power"
    if 71 <= number <= 75:
        return "revocation_or_abandonment_procedure"
    return "enforcement_authority"


def _direct_projection(span: MunicodeSpan, quote: str) -> dict | None:
    if span.section == "50-5-25" and quote.startswith("Each day that a violation remains"):
        return {
            "type": "computed_standard",
            "metric": "separate_violation_count",
            "expression": {"var": "days_violation_remains_uncorrected_after_city_notice"},
            "operator": "==",
            "inputAssumption": "Count begins only after City notice and while uncorrected.",
        }
    multipliers = {
        "A civil fine that is paid before the appearance date shall be reduced by ten percent;": 0.9,
        "A civil fine that is paid after the appearance date shall be increased by ten percent;": 1.1,
        "A civil fine that is paid on the appearance date shall be neither reduced nor increased.": 1.0,
    }
    if span.section == "50-5-33" and quote in multipliers:
        timing = "before" if "before" in quote else "after" if "after" in quote else "on"
        return {
            "type": "computed_standard",
            "metric": "payable_civil_fine",
            "expression": {"op": "multiply", "args": [
                {"var": "base_civil_fine"}, multipliers[quote],
            ]},
            "when": {"payment_timing_relative_to_appearance_date": timing},
            "unit": "usd",
        }
    return None


def _penalty_schedule_projections(
    corpus: Mapping[str, Any], source_ledger: ReviewedProvisionLedger
) -> list[dict]:
    document = next(item for item in corpus["documents"] if item["document"] == "ARTICLE_V.municode.json")
    by_coordinate = {
        (source.source_index, source.row, source.column): provision
        for provision in source_ledger.provisions
        for source in provision.sources if source.row is not None
    }
    projections = []
    tiers = ("first", "second_repeat", "third_or_subsequent_repeat")
    for block in document["blocks"]:
        if block["type"] != "table":
            continue
        for row_index, row in enumerate(block["rows"][1:], 1):
            amounts = [MONEY_RE.match(value) for value in row[1:4]]
            if not all(amounts):
                continue
            source_ids = [
                by_coordinate[(block["sourceIndex"], row_index, column)].id
                for column in range(4)
            ]
            projections.append({
                "id": f"detroit:{block['section']}:penalty-row:{row_index}",
                "type": "fine_schedule_lookup",
                "effect": "civil_fine_amount",
                "when": {"violation_category": row[0]},
                "values": {
                    tier: float(match.group(1).replace(",", ""))
                    for tier, match in zip(tiers, amounts)
                },
                "unit": "usd",
                "parameterization": {
                    "style": "dated_parameter_schedule",
                    "validAtSnapshot": corpus["canonicalSource"]["snapshot"],
                    "effectiveDate": None,
                    "note": "The snapshot proves current codified text, not the first effective date of every row.",
                },
                "sourceProvisionIds": source_ids,
                "dependencies": [
                    "50-5-27",
                    "External determination that the conduct belongs to the named violation category.",
                    "External determination of repeat-offense tier.",
                ],
                "transformationRationale": (
                    "Direct row-wise transcription of the violation label and the three "
                    "dollar cells; the lookup does not classify conduct or offense history."
                ),
            })
    return projections


def _direct_projections(records: list[dict]) -> list[dict]:
    result = []
    for record in records:
        for proposition in record["propositions"]:
            projection = proposition.get("dslProjection")
            if projection and projection.get("type") == "computed_standard":
                result.append({
                    "id": proposition["id"] + ":projection",
                    **projection,
                    "sourceProvisionIds": [record["sourceProvisionId"]],
                    "sourcePropositionIds": [proposition["id"]],
                    "transformationRationale": proposition["transformationRationale"],
                })
    return result
