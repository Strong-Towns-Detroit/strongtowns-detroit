"""Extract cross-references from zoning ordinance text and build a citation graph.

Detroit's zoning ordinance (Chapter 50) uses several citation formats:

Internal references (within the ordinance):
- ``Section 50-12-101`` / ``Sec. 50-12-101`` — specific section
- ``Sections 50-12-101 through 50-12-105`` — range of sections
- ``Section 50-12-101, 50-12-102`` — compound references
- ``Article XII`` — article-level reference
- ``Division 2`` / ``Subdivision A`` — structural references
- ``this article`` / ``this section`` — self-references
- ``Figure 50-12-101`` / ``Table 50-12-101`` — figure/table refs

External references:
- ``MCL 125.3101`` — Michigan Compiled Laws
- ``P.A. 110 of 2006`` — Michigan Public Acts
- ``42 USC 11001`` — US Code
- ``44 CFR 60.3`` — Code of Federal Regulations
- ``Chapter 14`` — other Detroit Code of Ordinances chapters
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from strongtowns_detroit.zoning.document import parse_document, walk_sections
from strongtowns_detroit.zoning.models import (
    Citation,
    CitationGraph,
    CitationType,
    SectionNode,
)


# ──────────────────────────────────────────────
# Regex patterns for citation extraction
# ──────────────────────────────────────────────

# Internal section references: "Section 50-12-101" or "Sec. 50-12-101"
_SECTION_RE = re.compile(
    r"(?:Section|Sec\.)\s+(50-\d{1,2}-\d{1,4})", re.IGNORECASE
)

# Range references: "Sections 50-12-101 through 50-12-105"
_SECTION_RANGE_RE = re.compile(
    r"(?:Sections?)\s+(50-\d{1,2}-\d{1,4})\s+through\s+(50-\d{1,2}-\d{1,4})",
    re.IGNORECASE,
)

# Bare section numbers (without "Section" prefix): "50-12-101"
# Must be preceded by word boundary but NOT by "Section " or "Sec. "
_BARE_SECTION_RE = re.compile(
    r"(?<![.\w])(50-\d{1,2}-\d{1,4})(?!\d)"
)

# Article references: "Article XII"
_ARTICLE_RE = re.compile(
    r"Article\s+([IVXLC]+)", re.IGNORECASE
)

# Division references: "Division 2" or "Division N"
_DIVISION_RE = re.compile(
    r"Division\s+(\d+)", re.IGNORECASE
)

# Subdivision references: "Subdivision A" or "Subdivision 1"
_SUBDIVISION_RE = re.compile(
    r"Subdivision\s+([A-Z\d]+)", re.IGNORECASE
)

# Self-references: "this article", "this section", etc.
_SELF_REF_RE = re.compile(
    r"this\s+(article|chapter|division|section|subdivision)", re.IGNORECASE
)

# Figure / Table references within the ordinance
_FIGURE_RE = re.compile(r"Figure\s+(50-\d{1,2}-\d{1,4})", re.IGNORECASE)
_TABLE_REF_RE = re.compile(r"Table\s+(50-\d{1,2}-\d{1,4})", re.IGNORECASE)

# Michigan Compiled Laws: "MCL 125.3101" or "MCL 125.3101a et seq."
_MCL_RE = re.compile(
    r"MCL\s+(\d+\.\d+[a-z]?(?:\s+et\s+seq\.?)?)", re.IGNORECASE
)

# Public Acts: "P.A. 110 of 2006" or "P.A. 110"
_PA_RE = re.compile(
    r"P\.A\.\s+(\d+(?:\s+of\s+\d{4})?)", re.IGNORECASE
)

# US Code: "42 USC 11001"
_USC_RE = re.compile(
    r"(\d+)\s+USC\s+(\d+)", re.IGNORECASE
)

# Code of Federal Regulations: "44 CFR 60.3"
_CFR_RE = re.compile(
    r"(\d+)\s+CFR\s+(\d+(?:\.\d+)?)", re.IGNORECASE
)

# Other Detroit Code chapters: "Chapter 14"
_CHAPTER_RE = re.compile(
    r"Chapter\s+(\d+)", re.IGNORECASE
)


# ──────────────────────────────────────────────
# Roman numeral utilities
# ──────────────────────────────────────────────

_ROMAN_TO_INT = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
    "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10,
    "XI": 11, "XII": 12, "XIII": 13, "XIV": 14, "XV": 15,
    "XVI": 16, "XVII": 17, "XVIII": 18, "XIX": 19, "XX": 20,
}

# Article number → section prefix mapping (Article XII → 50-12-xxx)
_ARTICLE_TO_PREFIX: dict[str, str] = {
    roman: f"50-{num}" for roman, num in _ROMAN_TO_INT.items()
}


# ──────────────────────────────────────────────
# Citation extraction
# ──────────────────────────────────────────────

def extract_citations(text: str, source_section: str = "") -> list[Citation]:
    """Extract all citations from a block of text.

    Returns a list of Citation objects with normalized target IDs.
    The *source_section* is the section number of the text's origin
    (e.g., "50-12-101").
    """
    citations: list[Citation] = []
    # Track positions already matched to avoid duplicates
    matched_spans: list[tuple[int, int]] = []

    def _overlaps(start: int, end: int) -> bool:
        return any(s <= start < e or s < end <= e for s, e in matched_spans)

    def _add(start: int, end: int, target: str, ctype: CitationType, raw: str) -> None:
        if not _overlaps(start, end):
            matched_spans.append((start, end))
            citations.append(Citation(
                source_section=source_section,
                target=target,
                citation_type=ctype,
                raw_text=raw,
            ))

    # 1. Section ranges (must match before individual sections)
    for m in _SECTION_RANGE_RE.finditer(text):
        start_sec, end_sec = m.group(1), m.group(2)
        # Expand range into individual section targets
        targets = _expand_section_range(start_sec, end_sec)
        # Claim the span once, then add all expanded targets
        matched_spans.append((m.start(), m.end()))
        for t in targets:
            citations.append(Citation(
                source_section=source_section,
                target=t,
                citation_type=CitationType.SECTION,
                raw_text=m.group(0),
            ))

    # 2. Explicit section references
    for m in _SECTION_RE.finditer(text):
        _add(m.start(), m.end(), m.group(1), CitationType.SECTION, m.group(0))

    # 3. Figure references
    for m in _FIGURE_RE.finditer(text):
        _add(m.start(), m.end(), f"fig:{m.group(1)}", CitationType.FIGURE, m.group(0))

    # 4. Table references
    for m in _TABLE_REF_RE.finditer(text):
        _add(m.start(), m.end(), f"tbl:{m.group(1)}", CitationType.TABLE_REF, m.group(0))

    # 5. Bare section numbers (after explicit matches to avoid duplication)
    for m in _BARE_SECTION_RE.finditer(text):
        _add(m.start(), m.end(), m.group(1), CitationType.SECTION, m.group(0))

    # 6. Article references
    for m in _ARTICLE_RE.finditer(text):
        roman = m.group(1).upper()
        target = f"article:{roman}"
        _add(m.start(), m.end(), target, CitationType.ARTICLE, m.group(0))

    # 7. Division references
    for m in _DIVISION_RE.finditer(text):
        _add(m.start(), m.end(), f"div:{m.group(1)}", CitationType.DIVISION, m.group(0))

    # 8. Subdivision references
    for m in _SUBDIVISION_RE.finditer(text):
        _add(m.start(), m.end(), f"subdiv:{m.group(1)}", CitationType.SUBDIVISION, m.group(0))

    # 9. Self-references
    for m in _SELF_REF_RE.finditer(text):
        ref_type = m.group(1).lower()
        _add(m.start(), m.end(), f"self:{ref_type}", CitationType.SELF_REF, m.group(0))

    # 10. MCL references
    for m in _MCL_RE.finditer(text):
        _add(m.start(), m.end(), f"mcl:{m.group(1).strip()}", CitationType.MCL, m.group(0))

    # 11. Public Act references
    for m in _PA_RE.finditer(text):
        _add(m.start(), m.end(), f"pa:{m.group(1).strip()}", CitationType.PUBLIC_ACT, m.group(0))

    # 12. USC references
    for m in _USC_RE.finditer(text):
        _add(m.start(), m.end(), f"usc:{m.group(1)}-{m.group(2)}", CitationType.USC, m.group(0))

    # 13. CFR references
    for m in _CFR_RE.finditer(text):
        _add(m.start(), m.end(), f"cfr:{m.group(1)}-{m.group(2)}", CitationType.CFR, m.group(0))

    # 14. Chapter references (exclude Chapter 50 — that's the zoning code itself)
    for m in _CHAPTER_RE.finditer(text):
        chap_num = m.group(1)
        if chap_num != "50":
            _add(m.start(), m.end(), f"chapter:{chap_num}", CitationType.CHAPTER, m.group(0))

    return citations


def _expand_section_range(start: str, end: str) -> list[str]:
    """Expand a section range like '50-12-101' through '50-12-105'.

    Only expands ranges that share the same article prefix and have
    sequential final numbers.  Returns individual section IDs.
    """
    parts_s = start.split("-")
    parts_e = end.split("-")

    if len(parts_s) != 3 or len(parts_e) != 3:
        return [start, end]

    # Same article prefix required
    if parts_s[0] != parts_e[0] or parts_s[1] != parts_e[1]:
        return [start, end]

    try:
        first = int(parts_s[2])
        last = int(parts_e[2])
    except ValueError:
        return [start, end]

    if last < first or (last - first) > 100:
        return [start, end]

    prefix = f"{parts_s[0]}-{parts_s[1]}"
    return [f"{prefix}-{n}" for n in range(first, last + 1)]


# ──────────────────────────────────────────────
# Graph construction
# ──────────────────────────────────────────────

def _section_text(node: SectionNode) -> str:
    """Concatenate all content paragraphs of a section into one text block."""
    return " ".join(node.content)


# Pattern to detect section-starting paragraphs like "Sec. 50-12-101. Title."
_SEC_START_RE = re.compile(r"^Sec\.?\s+(\d{2}-\d{1,2}-\d{1,4})\b")


def extract_content_sections(
    node: SectionNode,
) -> list[tuple[str, str, str]]:
    """Extract numbered sections from content paragraphs.

    The real ordinance embeds section numbers in content paragraphs
    (e.g., "Sec. 50-12-101. Use tables.") rather than in headings.
    A single SectionNode (subdivision/division) often contains many
    numbered sections.

    Returns a list of (section_number, section_title, content_text) tuples.
    Each tuple groups all paragraphs from one "Sec. XX-XX-XXX" marker
    to the next.
    """
    if not node.content:
        return []

    sections: list[tuple[str, str, str]] = []
    current_num = ""
    current_title = ""
    current_paras: list[str] = []

    for para in node.content:
        m = _SEC_START_RE.match(para)
        if m:
            # Save previous section
            if current_num:
                sections.append((current_num, current_title, " ".join(current_paras)))
            current_num = m.group(1)
            current_title = para
            current_paras = [para]
        else:
            current_paras.append(para)

    # Save last section
    if current_num:
        sections.append((current_num, current_title, " ".join(current_paras)))

    return sections


def _resolve_self_ref(source_section: str, self_type: str) -> str | None:
    """Resolve a 'this article/division/section' reference to a concrete ID.

    For 'this section', returns the source section number.
    For 'this article', returns the article prefix (e.g. '50-12').
    """
    if not source_section:
        return None
    parts = source_section.split("-")
    if self_type == "section" or self_type == "subdivision":
        return source_section
    if self_type == "article" or self_type == "chapter":
        if len(parts) >= 2:
            return f"article:{_int_to_roman(int(parts[1]))}" if parts[1].isdigit() else None
    if self_type == "division":
        return None  # Division can't be resolved without more context
    return None


def _int_to_roman(n: int) -> str:
    """Convert an integer (1-20) to a Roman numeral string."""
    for roman, val in _ROMAN_TO_INT.items():
        if val == n:
            return roman
    return str(n)


def build_citation_graph(
    sections: list[SectionNode],
    resolve_hierarchical: bool = True,
) -> CitationGraph:
    """Build a directed citation graph from parsed section trees.

    Walks all sections, extracts citations from their content, and
    builds a graph where:
    - Nodes are section numbers (lowest level) or external reference IDs
    - Edges are directed citations from source to target

    The real ordinance embeds section numbers in content paragraphs
    (e.g., "Sec. 50-12-101. Use tables.") within subdivision/division
    heading nodes.  This function extracts those numbered sections
    from content and uses them as the graph's internal nodes.

    If a SectionNode already has a section number in its heading
    (e.g., from unit-test fixtures), that is used directly.

    If *resolve_hierarchical* is True, article-level references are
    expanded to edges targeting all leaf sections under that article.
    Self-references are resolved to concrete section IDs where possible.
    """
    graph = CitationGraph()

    # First pass: extract all numbered sections
    # Each entry: (section_number, title, content_text)
    all_tree_nodes: list[SectionNode] = list(walk_sections(sections))
    numbered_sections: list[tuple[str, str, str]] = []
    article_sections: dict[str, list[str]] = {}  # article prefix → section numbers

    for node in all_tree_nodes:
        if node.number:
            # Node has a number from its heading (or from test fixtures)
            numbered_sections.append((
                node.number,
                node.title,
                _section_text(node),
            ))
        # Also extract sub-sections from content paragraphs
        content_secs = extract_content_sections(node)
        numbered_sections.extend(content_secs)

    # Register all section nodes
    for sec_num, title, _ in numbered_sections:
        if sec_num and sec_num not in graph.nodes:
            graph.nodes[sec_num] = title
            parts = sec_num.split("-")
            if len(parts) >= 2:
                art_prefix = f"{parts[0]}-{parts[1]}"
                article_sections.setdefault(art_prefix, []).append(sec_num)

    # Second pass: extract citations from each numbered section
    for sec_num, _title, text in numbered_sections:
        if not sec_num or not text:
            continue

        citations = extract_citations(text, source_section=sec_num)

        for cit in citations:
            target = cit.target

            # Handle self-references
            if cit.citation_type == CitationType.SELF_REF:
                self_type = target.replace("self:", "")
                resolved = _resolve_self_ref(sec_num, self_type)
                if resolved is None:
                    continue
                target = resolved
                if target.startswith("article:"):
                    cit = Citation(
                        source_section=cit.source_section,
                        target=target,
                        citation_type=CitationType.ARTICLE,
                        raw_text=cit.raw_text,
                    )

            # Handle hierarchical article references
            if cit.citation_type == CitationType.ARTICLE and resolve_hierarchical:
                roman = target.replace("article:", "")
                art_num = _ROMAN_TO_INT.get(roman)
                if art_num is not None:
                    art_prefix = f"50-{art_num}"
                    leaf_sections = article_sections.get(art_prefix, [])
                    if leaf_sections:
                        for leaf in leaf_sections:
                            if leaf == sec_num:
                                continue  # Skip self-edges
                            edge = Citation(
                                source_section=sec_num,
                                target=leaf,
                                citation_type=CitationType.SECTION,
                                raw_text=cit.raw_text,
                            )
                            graph.edges.append(edge)
                            if leaf not in graph.nodes:
                                graph.nodes[leaf] = leaf
                        continue

            # Add target node if not already known
            if target not in graph.nodes:
                graph.nodes[target] = cit.raw_text

            # Skip self-edges
            if target == sec_num:
                continue

            graph.edges.append(Citation(
                source_section=sec_num,
                target=target,
                citation_type=cit.citation_type,
                raw_text=cit.raw_text,
            ))

    return graph


def build_citation_graph_from_docx(
    docx_paths: list[Path],
    resolve_hierarchical: bool = True,
) -> CitationGraph:
    """Convenience function: parse .docx files and build the citation graph.

    Accepts a list of .docx file paths, parses each into section trees,
    and builds the combined citation graph.
    """
    all_sections: list[SectionNode] = []
    for path in docx_paths:
        all_sections.extend(parse_document(path))
    return build_citation_graph(all_sections, resolve_hierarchical=resolve_hierarchical)
