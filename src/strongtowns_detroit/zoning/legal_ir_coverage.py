"""Coverage accounting for reviewed legal IR against a Municode corpus."""

from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .legal_ir import LegalProvision, ProvenanceError, verify_provision


def _ranges(intervals: Iterable[tuple[int, int]]) -> tuple[list[list[int]], list[list[int]]]:
    """Return interval union and portions covered more than once."""
    events: dict[int, int] = defaultdict(int)
    for start, end in intervals:
        events[start] += 1
        events[end] -= 1
    union: list[list[int]] = []
    overlap: list[list[int]] = []
    depth = 0
    previous: int | None = None
    for position in sorted(events):
        if previous is not None and position > previous:
            target = union if depth >= 1 else None
            if target is not None:
                if target and target[-1][1] == previous:
                    target[-1][1] = position
                else:
                    target.append([previous, position])
            if depth >= 2:
                if overlap and overlap[-1][1] == previous:
                    overlap[-1][1] = position
                else:
                    overlap.append([previous, position])
        depth += events[position]
        previous = position
    return union, overlap


def _gaps(text: str, union: list[list[int]]) -> list[dict[str, Any]]:
    gaps = []
    cursor = 0
    for start, end in union:
        if start > cursor:
            value = text[cursor:start]
            gaps.append({
                "start": cursor, "end": start, "text": value,
                "kind": "whitespace" if not value.strip() else "substantive",
            })
        cursor = max(cursor, end)
    if cursor < len(text):
        value = text[cursor:]
        gaps.append({
            "start": cursor, "end": len(text), "text": value,
            "kind": "whitespace" if not value.strip() else "substantive",
        })
    return gaps


def _atoms(block: Mapping[str, Any]) -> Iterable[tuple[int | None, int | None, str]]:
    if block.get("type") == "paragraph":
        yield None, None, str(block.get("text", ""))
    elif block.get("type") == "table":
        for row_index, row in enumerate(block.get("rows", [])):
            for column_index, cell in enumerate(row):
                yield row_index, column_index, str(cell)


def load_ledgers(directory: Path) -> list[tuple[Path, dict[str, Any], list[LegalProvision]]]:
    loaded = []
    for path in sorted(Path(directory).glob("article-*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        provisions = [LegalProvision.from_dict(item) for item in raw.get("provisions", [])]
        loaded.append((path, raw, provisions))
    return loaded


def aggregate_coverage(
    corpus: Mapping[str, Any], ledger_directory: Path
) -> dict[str, Any]:
    """Compare all article ledgers with canonical blocks and character atoms."""
    ledgers = load_ledgers(ledger_directory)
    provisions = [item for _, _, group in ledgers for item in group]
    citations: dict[tuple[str, int, int | None, int | None], list[tuple[int, int, str]]] = defaultdict(list)
    provenance_errors = []
    for provision in provisions:
        try:
            verify_provision(corpus, provision)
        except ProvenanceError as error:
            provenance_errors.append({"provisionId": provision.id, "error": str(error)})
        for span in provision.sources:
            citations[(span.document, span.source_index, span.row, span.column)].append(
                (span.start, span.end, provision.id)
            )

    complete_documents: set[str] = set()
    ledger_reports = []
    for path, raw, group in ledgers:
        documents = sorted(
            {span.document for p in group for span in p.sources}
            | ({str(raw["document"])} if raw.get("document") else set())
        )
        declared = raw.get("coverageStatus") == "complete" or raw.get("articleStatus") == "complete"
        if declared:
            complete_documents.update(documents)
        ledger_reports.append({
            "ledger": path.name,
            "documents": documents,
            "coverageStatus": "complete" if declared else raw.get("coverageStatus", "in_progress"),
            "provisionCount": len(group),
        })

    block_reports = []
    cited_blocks = uncited_blocks = overlapping_blocks = 0
    substantive_gap_count = whitespace_gap_count = 0
    complete_failures = []
    for document in corpus.get("documents", []):
        name = document["document"]
        for block in document.get("blocks", []):
            source_index = block["sourceIndex"]
            block_citations = [
                value for key, values in citations.items()
                if key[0] == name and key[1] == source_index for value in values
            ]
            provision_ids = sorted({value[2] for value in block_citations})
            if not block_citations:
                disposition = "uncited"
                uncited_blocks += 1
            elif len(provision_ids) > 1:
                disposition = "overlapping"
                overlapping_blocks += 1
            else:
                disposition = "cited"
                cited_blocks += 1
            atom_reports = []
            for row, column, text in _atoms(block):
                intervals = [
                    (start, end) for start, end, _ in
                    citations.get((name, source_index, row, column), [])
                ]
                union, overlap = _ranges(intervals)
                gaps = _gaps(text, union)
                substantive_gap_count += sum(gap["kind"] == "substantive" for gap in gaps)
                whitespace_gap_count += sum(gap["kind"] == "whitespace" for gap in gaps)
                atom_reports.append({
                    "row": row, "column": column, "length": len(text),
                    "citedRanges": union, "overlappingRanges": overlap, "gaps": gaps,
                })
                if name in complete_documents:
                    for gap in gaps:
                        if gap["kind"] == "substantive":
                            complete_failures.append({
                                "document": name, "sourceIndex": source_index,
                                "row": row, "column": column,
                                "start": gap["start"], "end": gap["end"],
                                "text": gap["text"],
                            })
            block_reports.append({
                "document": name, "sourceIndex": source_index,
                "municodeNodeId": block.get("municodeNodeId"),
                "section": block.get("section"), "type": block.get("type"),
                "disposition": disposition, "provisionIds": provision_ids,
                "atoms": atom_reports,
            })

    def counts(values: Iterable[str]) -> dict[str, int]:
        return dict(sorted(Counter(values).items()))

    return {
        "schemaVersion": "detroit-legal-ir-coverage-v1",
        "canonicalSnapshot": corpus.get("canonicalSource", {}).get("snapshot"),
        "ledgers": ledger_reports,
        "counts": {
            "provisions": len(provisions),
            "effects": counts(str(p.effect.get("type", "unspecified")) for p in provisions),
            "dispositions": counts(str(p.review.get("disposition", "unspecified")) for p in provisions),
            "executionStatuses": counts(str(p.review.get("executionStatus", "unspecified")) for p in provisions),
            "blocks": {"cited": cited_blocks, "uncited": uncited_blocks, "overlapping": overlapping_blocks},
            "gaps": {"substantive": substantive_gap_count, "whitespace": whitespace_gap_count},
        },
        "blocks": block_reports,
        "provenanceErrors": provenance_errors,
        "completeArticleFailures": complete_failures,
        "ok": not provenance_errors and not complete_failures,
    }
