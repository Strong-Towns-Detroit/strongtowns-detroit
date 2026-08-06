"""Article III semantic decomposition and narrowly gated DSL projection."""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from .legal_ir import (
    LegalProvision,
    MunicodeSpan,
    ProjectionError,
    project_provision,
)


# These four source blocks state complete, numeric minimum-notice rules.  No
# other Article III clause is promoted merely because it contains a number.
NOTICE_DEADLINES = {
    79: (15, "buildings_safety_engineering_and_environmental_department"),
    81: (15, "board_of_zoning_appeals"),
    83: (15, "city_planning_commission"),
    85: (5, "city_council"),
}

REFERENCE_RE = re.compile(
    r"(?:Sections?\s+50-\d+-\d+|MCL\s+\d+\.\d+(?:\(\d+\))?|"
    r"Section\s+\d+-\d+(?:\(\d+\))?\s+of\s+the\s+Charter)", re.I
)
BOUNDARY_RE = re.compile(r"(?<=[.!?;])\s+(?=[A-Z\"'(])")


def atomic_ranges(text: str) -> Iterable[tuple[int, int]]:
    """Yield deterministic, trimmed sentence/semicolon proposition ranges."""
    cursor = 0
    for boundary in BOUNDARY_RE.finditer(text):
        yield from _trimmed(text, cursor, boundary.start())
        cursor = boundary.end()
    yield from _trimmed(text, cursor, len(text))


def _trimmed(text: str, start: int, end: int) -> Iterable[tuple[int, int]]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    if start < end:
        yield start, end


def dependencies(text: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(match.group(0) for match in REFERENCE_RE.finditer(text)))


def non_execution_reasons(text: str) -> tuple[str, ...]:
    lower = text.lower()
    reasons = []
    if re.search(r"\b(may|deem(?:ed)?|reasonable|appropriate|satisfactory)\b", lower):
        reasons.append("official_discretion_or_judgment")
    if re.search(r"\b(if|where|unless|except|subject to|provided)\b", lower):
        reasons.append("context_or_exception_requires_modeling")
    if REFERENCE_RE.search(text) or "in accordance with" in lower or "pursuant to" in lower:
        reasons.append("external_or_cross_referenced_rule_dependency")
    if not re.search(r"\b(shall|must|may not|no |is required|are required)\b", lower):
        reasons.append("no_complete_mandatory_operator")
    if not reasons:
        reasons.append("procedure_not_yet_supported_by_executable_dsl")
    return tuple(reasons)


def decompose_pending_provision(
    parent: LegalProvision,
    block_text: str,
    supporting_sources: tuple[tuple[str, MunicodeSpan], ...] = (),
) -> list[LegalProvision]:
    source = parent.sources[0]
    propositions = []
    for ordinal, (start, end) in enumerate(atomic_ranges(source.quote), 1):
        absolute_start = source.start + start
        absolute_end = source.start + end
        span = MunicodeSpan.cite(
            snapshot=source.snapshot, document=source.document, node_id=source.node_id,
            source_index=source.source_index, section=source.section, text=block_text,
            start=absolute_start, end=absolute_end,
        )
        text = span.quote
        if source.source_index in NOTICE_DEADLINES and ordinal == 1:
            days, forum = NOTICE_DEADLINES[source.source_index]
            effect: Mapping[str, Any] = {
                "type": "minimum_notice_period",
                "actor": "agency_responsible_for_giving_notice",
                "event": "public_hearing",
                "forum": forum,
                "operator": ">=",
                "value": days,
                "unit": "days",
                "scope": {"procedure": "published_public_hearing_notice"},
                "exceptions": [],
                "legalRuleModel": {
                    "statementType": "prescriptive",
                    "strength": "strict",
                    "defeasible": False,
                    "priority": None,
                    "temporalRelation": "before_event",
                },
            }
            execution_status = "executable"
            reasons: tuple[str, ...] = ()
            rationale = (
                "The deadline line and its supporting introduction together state actor, event, "
                "forum, minimum period, value, and unit."
            )
        else:
            effect = {"type": "procedural_proposition", "text": text}
            execution_status = "non_executable"
            reasons = non_execution_reasons(text)
            rationale = "Preserved as an atomic proposition; executable semantics are not fully modeled."
        deps = dependencies(text)
        support_ids = tuple(item[0] for item in supporting_sources) if execution_status == "executable" else ()
        sources = (span,) + tuple(item[1] for item in supporting_sources) if execution_status == "executable" else (span,)
        legal_model = effect.get("legalRuleModel", {
            "statementType": "prescriptive" if re.search(r"\b(shall|must|may not|no )\b", text, re.I) else "unclassified",
            "strength": "unassessed",
            "defeasible": None,
            "priority": None,
            "temporalRelation": "not_encoded",
        })
        propositions.append(LegalProvision(
            id=f"{parent.id}:proposition:{ordinal}",
            subject={
                "article": "III", "section": source.section,
                "type": "procedural_proposition", "parentSourceId": parent.id,
            },
            effect=effect,
            sources=sources,
            cross_references=deps,
            review={
                "status": "verified", "method": "deterministic_atomic_decomposition",
                "parentSourceId": parent.id, "executionStatus": execution_status,
                "nonExecutionReasons": list(reasons), "rationale": rationale,
                "dependencies": list(deps) + list(support_ids),
                "supportingSourceIds": list(support_ids),
                "interpretation": "literal_source_bound",
                "legalRuleModel": legal_model,
                "validity": {"basis": "canonical_snapshot", "effectiveInterval": "not_encoded"},
            },
        ))
    return propositions


def project_article_iii_proposition(corpus: Mapping[str, Any], proposition: LegalProvision) -> dict:
    """Project only the reviewed whitelist into a small executable DSL record."""
    if proposition.review.get("executionStatus") != "executable":
        reasons = ", ".join(proposition.review.get("nonExecutionReasons", ()))
        raise ProjectionError(f"{proposition.id} is non-executable: {reasons}")

    def projector(item: LegalProvision) -> dict:
        effect = item.effect
        if effect.get("type") != "minimum_notice_period":
            raise ProjectionError(f"unsupported Article III effect {effect.get('type')}")
        return {
            "id": item.id,
            "kind": "procedural_deadline",
            "scope": effect["scope"],
            "baseDefinition": {
                "when": {"hearingForum": effect["forum"], "event": effect["event"]},
                "consequence": {
                    "metric": "notice_period", "operator": effect["operator"],
                    "value": effect["value"], "unit": effect["unit"],
                },
            },
            "exceptions": effect["exceptions"],
            "legalRuleModel": effect["legalRuleModel"],
            "actor": effect["actor"],
            "sourceIds": [item.review["parentSourceId"], *item.review["supportingSourceIds"]],
        }

    return project_provision(corpus, proposition, projector)
