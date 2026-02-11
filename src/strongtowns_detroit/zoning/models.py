"""Data models for structured zoning ordinance data."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


@dataclass
class UsePermission:
    """One cell from a Type A use-permission matrix.

    Represents whether a specific land use is allowed in a specific
    zoning district, and under what conditions.
    """

    use_name: str       # e.g. "One-family dwelling"
    district: str       # e.g. "R1"
    permission: str     # "R", "C", "C/R", "—", etc.
    conditions: str = ""  # footnote text if any


@dataclass
class DimensionalStandard:
    """One row from a Type B dimensional-standards table.

    Values are kept as strings because units vary (sq ft, ft, %, stories).
    """

    district: str
    standard_name: str    # e.g. "Minimum Lot Area"
    value: str            # e.g. "5,000 sq ft"
    section_ref: str = ""


@dataclass
class ZoningDefinition:
    """One entry from a Type C definition/lookup table."""

    term: str
    definition: str
    section_ref: str = ""


@dataclass
class SectionNode:
    """A node in the document's section hierarchy.

    Represents a heading (Article, Division, or Section) with its
    content paragraphs and any tables found under it.
    """

    number: str                              # e.g. "50-12-101"
    title: str
    level: int                               # heading depth (3=Article, 4=Division, 5=Section)
    content: list[str] = field(default_factory=list)
    children: list[SectionNode] = field(default_factory=list)
    tables: list[list[list[str]]] = field(default_factory=list)


class CitationType(Enum):
    """Classification of a citation target."""

    SECTION = "section"          # Section 50-XX-YYY (specific section)
    ARTICLE = "article"          # Article XII (article-level)
    DIVISION = "division"        # Division 2 (division-level)
    SUBDIVISION = "subdivision"  # Subdivision X
    FIGURE = "figure"            # Figure 50-XX-YYY
    TABLE_REF = "table_ref"      # Table 50-XX-YYY
    MCL = "mcl"                  # Michigan Compiled Laws
    USC = "usc"                  # US Code
    CFR = "cfr"                  # Code of Federal Regulations
    PUBLIC_ACT = "public_act"    # P.A. NNN of YYYY
    CHAPTER = "chapter"          # Chapter NN (Detroit Code of Ordinances)
    SELF_REF = "self_ref"        # "this article", "this section", etc.


@dataclass
class Citation:
    """A single citation extracted from ordinance text.

    Represents a directed reference from a source section to a target.
    """

    source_section: str      # Section number where the citation appears
    target: str              # Normalized target identifier
    citation_type: CitationType
    raw_text: str            # Original matched text


@dataclass
class CitationGraph:
    """A directed graph of cross-references within the zoning ordinance.

    Nodes represent sections (at the lowest subsection level) or external
    reference targets (MCL, USC, etc.).  Edges represent citations from
    one section to another.
    """

    nodes: dict[str, str] = field(default_factory=dict)
    # node_id -> label (section title or external ref description)

    edges: list[Citation] = field(default_factory=list)
    # directed edges (source → target)

    @property
    def internal_nodes(self) -> set[str]:
        """Return node IDs that are internal sections (50-XX-YYY format)."""
        return {n for n in self.nodes if _is_internal_id(n)}

    @property
    def external_nodes(self) -> set[str]:
        """Return node IDs that are external references (terminal nodes)."""
        return {n for n in self.nodes if not _is_internal_id(n)}


def _is_internal_id(node_id: str) -> bool:
    """Check if a node ID looks like an internal section number."""
    import re
    return bool(re.match(r"^\d{2}-\d{1,2}-\d{1,4}$", node_id))
