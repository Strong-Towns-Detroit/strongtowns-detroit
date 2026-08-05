"""Reviewed rules from explicit Article XI overlay lists."""

from __future__ import annotations

import re

from strongtowns_detroit.zoning.codebook import OrdinanceBuilder, Source

ITEM_RE = re.compile(r"^\((\d+)\)\s*(.*)$")


def add_gateway_overlay_prohibitions(code: OrdinanceBuilder, source_corpus: dict) -> int:
    """Compile unqualified prohibited uses in §50-11-364(a) and (b)."""
    document = next(
        item for item in source_corpus["documents"]
        if item["document"].startswith("ARTICLE_XI.")
    )
    mode: str | None = None
    pending_item: str | None = None
    pending_subsection: str | None = None
    count = 0
    for block in document["blocks"]:
        if block.get("section") != "50-11-364" or block["type"] != "paragraph":
            continue
        text = block["text"]
        if text in {"(a)", "(b)", "(c)", "(d)"}:
            pending_subsection = text[1]
            pending_item = None
            if pending_subsection in {"c", "d"}:
                mode = None
            continue
        if text.startswith("(a)The following uses are prohibited") or (
            pending_subsection == "a" and text.startswith("The following uses are prohibited")
        ):
            mode, pending_subsection = "b2_b4", None
            continue
        if text.startswith("(b)The following uses are prohibited") or (
            pending_subsection == "b" and text.startswith("The following uses are prohibited")
        ):
            mode, pending_subsection = "all_districts", None
            continue
        if text.startswith("(c)") or text.startswith("(d)"):
            mode = None
            continue
        match = ITEM_RE.match(text)
        if match and mode is not None:
            item_number, label = match.groups()
            if not label:
                pending_item = item_number
                continue
        elif pending_item is not None and mode is not None:
            item_number, label = pending_item, text
            pending_item = None
        else:
            continue
        label = label.strip().rstrip(".")
        # These two items contain their own corridor exception/limitation and
        # cannot be represented as unconditional B2/B4 prohibitions.
        if mode == "b2_b4" and item_number in {"16", "27"}:
            continue
        use_id = _slug(label)
        code.use(use_id, label, "ordinance_use")
        districts = ("B2", "B4") if mode == "b2_b4" else ("*",)
        for district in districts:
            code.permission(
                id=f"{document['document']}:{block['sourceIndex']}:{district}",
                use=use_id,
                district=district,
                permission="not_allowed",
                conditions=("overlay:a",),
                source=Source(
                    document["document"], ("50-11-364",), text,
                    "Applies within a Gateway Radial Thoroughfare Overlay Area.",
                ),
                review_status="verified",
            )
            count += 1
    return count


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_") or "unnamed_use"
