"""Declarative legal IR with exact, verifiable Municode provenance.

This module deliberately does not infer law.  It represents a reviewer's
encoding and proves that the encoding remains attached to an exact source
span in a compiled Municode corpus.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, TypeVar


class ProvenanceError(ValueError):
    """A provision cannot be traced to its declared source span."""


class ProjectionError(ValueError):
    """A provision is not eligible for executable projection."""


def span_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MunicodeSpan:
    """Half-open character range in one derived Municode source block.

    ``source_index`` is the stable block order within the document.  Node ID
    prevents an index collision after accidental reordering.  ``quote`` and
    ``sha256`` make drift or occlusion observable rather than silently binding
    the rule to whatever later occupies the range.
    """

    snapshot: str
    document: str
    node_id: int | str
    source_index: int
    start: int
    end: int
    quote: str
    sha256: str
    section: str | None = None
    row: int | None = None
    column: int | None = None

    def __post_init__(self) -> None:
        if (self.row is None) != (self.column is None):
            raise ValueError("table provenance requires both row and column")
        if self.row is not None and (self.row < 0 or self.column < 0):
            raise ValueError("table coordinates cannot be negative")

    @classmethod
    def cite(
        cls,
        *,
        snapshot: str,
        document: str,
        node_id: int | str,
        source_index: int,
        text: str,
        start: int,
        end: int,
        section: str | None = None,
    ) -> "MunicodeSpan":
        quote = text[start:end]
        if not quote or start < 0 or end > len(text) or start >= end:
            raise ValueError("source span must be a non-empty range within the block")
        return cls(
            snapshot=snapshot,
            document=document,
            node_id=node_id,
            source_index=source_index,
            start=start,
            end=end,
            quote=quote,
            sha256=span_digest(quote),
            section=section,
        )

    @classmethod
    def cite_table_cell(
        cls,
        *,
        snapshot: str,
        document: str,
        node_id: int | str,
        source_index: int,
        cell_text: str,
        row: int,
        column: int,
        start: int = 0,
        end: int | None = None,
        section: str | None = None,
    ) -> "MunicodeSpan":
        """Cite characters within one cell, never a flattened table string."""
        end = len(cell_text) if end is None else end
        quote = cell_text[start:end]
        if not quote or start < 0 or end > len(cell_text) or start >= end:
            raise ValueError("source span must be a non-empty range within the cell")
        return cls(
            snapshot=snapshot,
            document=document,
            node_id=node_id,
            source_index=source_index,
            start=start,
            end=end,
            quote=quote,
            sha256=span_digest(quote),
            section=section,
            row=row,
            column=column,
        )


@dataclass(frozen=True)
class LegalProvision:
    """A reviewed provision before projection into an executable rule engine."""

    id: str
    subject: Mapping[str, Any]
    effect: Mapping[str, Any]
    sources: tuple[MunicodeSpan, ...]
    conditions: tuple[Mapping[str, Any], ...] = ()
    exceptions: tuple[Mapping[str, Any], ...] = ()
    cross_references: tuple[str, ...] = ()
    review: Mapping[str, Any] = field(
        default_factory=lambda: {"status": "unreviewed"}
    )

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("provision id is required")
        if not self.sources:
            raise ValueError("at least one exact source span is required")
        if "type" not in self.effect:
            raise ValueError("effect.type is required")
        if "status" not in self.review:
            raise ValueError("review.status is required")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "LegalProvision":
        return cls(
            id=str(value["id"]),
            subject=value["subject"],
            effect=value["effect"],
            sources=tuple(MunicodeSpan(**source) for source in value["sources"]),
            conditions=tuple(value.get("conditions", ())),
            exceptions=tuple(value.get("exceptions", ())),
            cross_references=tuple(value.get("cross_references", ())),
            review=value.get("review", {"status": "unreviewed"}),
        )


@dataclass(frozen=True)
class ReviewedProvisionLedger:
    """Portable, declarative collection of independently reviewed provisions."""

    provisions: tuple[LegalProvision, ...]
    schema_version: str = "detroit-legal-ir-v1"

    def __post_init__(self) -> None:
        ids = [provision.id for provision in self.provisions]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate provision id in reviewed ledger")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "provisions": [provision.to_dict() for provision in self.provisions],
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ReviewedProvisionLedger":
        return cls(
            schema_version=str(value["schemaVersion"]),
            provisions=tuple(
                LegalProvision.from_dict(item) for item in value.get("provisions", ())
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "ReviewedProvisionLedger":
        return cls.from_dict(json.loads(payload))

    @classmethod
    def load(cls, path: Path) -> "ReviewedProvisionLedger":
        return cls.from_json(Path(path).read_text(encoding="utf-8"))


def _span_text(block: Mapping[str, Any], span: MunicodeSpan) -> str:
    if block.get("type") == "paragraph":
        if span.row is not None:
            raise ProvenanceError("paragraph span cannot have table coordinates")
        return str(block.get("text", ""))
    if block.get("type") == "table":
        if span.row is None or span.column is None:
            raise ProvenanceError("table span requires explicit row and column")
        try:
            return str(block["rows"][span.row][span.column])
        except (IndexError, KeyError, TypeError):
            raise ProvenanceError(
                f"missing table cell [{span.row},{span.column}] for "
                f"{span.document}:{span.source_index}"
            ) from None
    raise ProvenanceError(f"unsupported source block type {block.get('type')!r}")


def find_block(corpus: Mapping[str, Any], span: MunicodeSpan) -> Mapping[str, Any]:
    actual_snapshot = corpus.get("canonicalSource", {}).get("snapshot")
    if actual_snapshot != span.snapshot:
        raise ProvenanceError(
            f"{span.document}:{span.source_index}: snapshot mismatch "
            f"({actual_snapshot!r} != {span.snapshot!r})"
        )
    document = next(
        (item for item in corpus.get("documents", []) if item.get("document") == span.document),
        None,
    )
    if document is None:
        raise ProvenanceError(f"missing source document {span.document}")
    block = next(
        (item for item in document.get("blocks", []) if item.get("sourceIndex") == span.source_index),
        None,
    )
    if block is None:
        raise ProvenanceError(f"missing source block {span.document}:{span.source_index}")
    if block.get("municodeNodeId") != span.node_id:
        raise ProvenanceError(f"node mismatch for {span.document}:{span.source_index}")
    if span.section is not None and block.get("section") != span.section:
        raise ProvenanceError(f"section mismatch for {span.document}:{span.source_index}")
    return block


def verify_span(corpus: Mapping[str, Any], span: MunicodeSpan) -> None:
    text = _span_text(find_block(corpus, span), span)
    actual = text[span.start:span.end]
    if actual != span.quote or span_digest(actual) != span.sha256:
        raise ProvenanceError(
            f"source span changed or was occluded: {span.document}:"
            f"{span.source_index}[{span.start}:{span.end}]"
        )


def verify_provision(corpus: Mapping[str, Any], provision: LegalProvision) -> None:
    for span in provision.sources:
        verify_span(corpus, span)


def verify_provisions(
    corpus: Mapping[str, Any], provisions: Iterable[LegalProvision]
) -> None:
    for provision in provisions:
        verify_provision(corpus, provision)


Projection = TypeVar("Projection")


def project_provision(
    corpus: Mapping[str, Any],
    provision: LegalProvision,
    projector: Callable[[LegalProvision], Projection],
) -> Projection:
    """Run a projection only after review status and every span are verified."""
    if provision.review.get("status") != "verified":
        raise ProjectionError(f"provision {provision.id} has not been verified")
    verify_provision(corpus, provision)
    return projector(provision)
