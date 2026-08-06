"""Test helpers for removing cited law from a derived source corpus."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .legal_ir import MunicodeSpan, ProvenanceError, find_block


def occlude_span(
    corpus: Mapping[str, Any], span: MunicodeSpan, marker: str = "\u2588"
) -> dict[str, Any]:
    """Return a deep-copied corpus with exactly one cited range masked.

    Keeping string length unchanged means other character citations retain
    their offsets, allowing rules to be occluded and tested one at a time.
    """
    result = deepcopy(corpus)
    block = find_block(result, span)
    if block.get("type") == "paragraph":
        if span.row is not None:
            raise ProvenanceError("paragraph span cannot have table coordinates")
        text = str(block.get("text", ""))
        block["text"] = text[:span.start] + marker * (span.end - span.start) + text[span.end:]
    elif block.get("type") == "table":
        if span.row is None or span.column is None:
            raise ProvenanceError("table span requires explicit row and column")
        try:
            text = str(block["rows"][span.row][span.column])
            block["rows"][span.row][span.column] = (
                text[:span.start] + marker * (span.end - span.start) + text[span.end:]
            )
        except (IndexError, KeyError, TypeError):
            raise ProvenanceError("cannot occlude missing table cell") from None
    else:
        raise ProvenanceError(f"unsupported source block type {block.get('type')!r}")
    return result
