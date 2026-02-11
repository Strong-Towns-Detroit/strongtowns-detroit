"""Tests for zoning citation extraction and graph construction."""

import pytest

from strongtowns_detroit.zoning.citations import (
    _expand_section_range,
    extract_content_sections,
    extract_citations,
    build_citation_graph,
)
from strongtowns_detroit.zoning.models import (
    Citation,
    CitationGraph,
    CitationType,
    SectionNode,
)


# ──────────────────────────────────────────────
# extract_citations — Internal section references
# ──────────────────────────────────────────────

class TestExtractSectionRefs:
    """Test extraction of Section 50-XX-YYY references."""

    def test_explicit_section_ref(self):
        cits = extract_citations("See Section 50-12-101 for details.")
        assert len(cits) == 1
        assert cits[0].target == "50-12-101"
        assert cits[0].citation_type == CitationType.SECTION

    def test_abbreviated_sec_ref(self):
        cits = extract_citations("Sec. 50-13-205 applies here.")
        assert len(cits) == 1
        assert cits[0].target == "50-13-205"

    def test_multiple_sections(self):
        text = "Section 50-12-101 and Section 50-12-102 both apply."
        cits = extract_citations(text)
        targets = {c.target for c in cits}
        assert "50-12-101" in targets
        assert "50-12-102" in targets

    def test_bare_section_number(self):
        cits = extract_citations("requirements of 50-14-301 apply")
        assert len(cits) == 1
        assert cits[0].target == "50-14-301"

    def test_bare_number_not_extracted_when_covered_by_explicit(self):
        """'Section 50-12-101' should produce ONE citation, not two."""
        cits = extract_citations("Section 50-12-101")
        assert len(cits) == 1

    def test_source_section_attached(self):
        cits = extract_citations("See Section 50-12-101", source_section="50-14-301")
        assert cits[0].source_section == "50-14-301"


class TestExtractSectionRanges:
    """Test extraction of 'Sections X through Y' ranges."""

    def test_simple_range(self):
        text = "Sections 50-12-101 through 50-12-103 apply."
        cits = extract_citations(text)
        targets = [c.target for c in cits]
        assert "50-12-101" in targets
        assert "50-12-102" in targets
        assert "50-12-103" in targets

    def test_range_does_not_double_count(self):
        """A range should not also produce individual section matches."""
        text = "Sections 50-12-101 through 50-12-102 apply."
        cits = extract_citations(text)
        # Should be exactly 2 (the expanded range), not 4
        section_cits = [c for c in cits if c.citation_type == CitationType.SECTION]
        assert len(section_cits) == 2


class TestExpandSectionRange:
    """Test the section range expansion helper."""

    def test_same_prefix(self):
        result = _expand_section_range("50-12-101", "50-12-105")
        assert len(result) == 5
        assert result[0] == "50-12-101"
        assert result[-1] == "50-12-105"

    def test_different_article(self):
        result = _expand_section_range("50-12-101", "50-13-105")
        assert result == ["50-12-101", "50-13-105"]

    def test_reversed_range(self):
        result = _expand_section_range("50-12-105", "50-12-101")
        assert result == ["50-12-105", "50-12-101"]

    def test_excessive_range_capped(self):
        result = _expand_section_range("50-12-1", "50-12-200")
        # More than 100 — returns just endpoints
        assert result == ["50-12-1", "50-12-200"]


# ──────────────────────────────────────────────
# extract_citations — Article / Division / Subdivision
# ──────────────────────────────────────────────

class TestExtractHierarchicalRefs:
    """Test extraction of article, division, subdivision references."""

    def test_article_reference(self):
        cits = extract_citations("pursuant to Article XII")
        assert len(cits) >= 1
        art_cits = [c for c in cits if c.citation_type == CitationType.ARTICLE]
        assert len(art_cits) == 1
        assert art_cits[0].target == "article:XII"

    def test_division_reference(self):
        cits = extract_citations("Division 3 of this article")
        div_cits = [c for c in cits if c.citation_type == CitationType.DIVISION]
        assert len(div_cits) == 1
        assert div_cits[0].target == "div:3"

    def test_subdivision_reference(self):
        cits = extract_citations("Subdivision A requirements")
        sub_cits = [c for c in cits if c.citation_type == CitationType.SUBDIVISION]
        assert len(sub_cits) == 1
        assert sub_cits[0].target == "subdiv:A"

    def test_self_reference_article(self):
        cits = extract_citations("elsewhere in this article")
        self_cits = [c for c in cits if c.citation_type == CitationType.SELF_REF]
        assert len(self_cits) == 1
        assert self_cits[0].target == "self:article"

    def test_self_reference_section(self):
        cits = extract_citations("as used in this section")
        self_cits = [c for c in cits if c.citation_type == CitationType.SELF_REF]
        assert len(self_cits) == 1
        assert self_cits[0].target == "self:section"


# ──────────────────────────────────────────────
# extract_citations — Figure and Table references
# ──────────────────────────────────────────────

class TestExtractFigureTableRefs:

    def test_figure_reference(self):
        cits = extract_citations("(See Figure 50-12-101)")
        fig_cits = [c for c in cits if c.citation_type == CitationType.FIGURE]
        assert len(fig_cits) == 1
        assert fig_cits[0].target == "fig:50-12-101"

    def test_table_reference(self):
        cits = extract_citations("Table 50-13-200 shows the standards")
        tbl_cits = [c for c in cits if c.citation_type == CitationType.TABLE_REF]
        assert len(tbl_cits) == 1
        assert tbl_cits[0].target == "tbl:50-13-200"


# ──────────────────────────────────────────────
# extract_citations — External references
# ──────────────────────────────────────────────

class TestExtractExternalRefs:
    """Test extraction of MCL, USC, CFR, P.A., and Chapter references."""

    def test_mcl_reference(self):
        cits = extract_citations("as defined in MCL 125.3101")
        mcl_cits = [c for c in cits if c.citation_type == CitationType.MCL]
        assert len(mcl_cits) == 1
        assert mcl_cits[0].target == "mcl:125.3101"

    def test_mcl_with_letter_suffix(self):
        cits = extract_citations("MCL 324.3104a et seq.")
        mcl_cits = [c for c in cits if c.citation_type == CitationType.MCL]
        assert len(mcl_cits) == 1
        assert "324.3104a" in mcl_cits[0].target

    def test_public_act(self):
        cits = extract_citations("P.A. 110 of 2006")
        pa_cits = [c for c in cits if c.citation_type == CitationType.PUBLIC_ACT]
        assert len(pa_cits) == 1
        assert pa_cits[0].target == "pa:110 of 2006"

    def test_usc_reference(self):
        cits = extract_citations("42 USC 11001 requirements")
        usc_cits = [c for c in cits if c.citation_type == CitationType.USC]
        assert len(usc_cits) == 1
        assert usc_cits[0].target == "usc:42-11001"

    def test_cfr_reference(self):
        cits = extract_citations("44 CFR 60.3 compliance")
        cfr_cits = [c for c in cits if c.citation_type == CitationType.CFR]
        assert len(cfr_cits) == 1
        assert cfr_cits[0].target == "cfr:44-60.3"

    def test_chapter_reference(self):
        cits = extract_citations("See Chapter 14 for building codes")
        ch_cits = [c for c in cits if c.citation_type == CitationType.CHAPTER]
        assert len(ch_cits) == 1
        assert ch_cits[0].target == "chapter:14"

    def test_chapter_50_excluded(self):
        """Chapter 50 is the zoning code itself — should not be an external ref."""
        cits = extract_citations("Chapter 50 of the Detroit Code")
        ch_cits = [c for c in cits if c.citation_type == CitationType.CHAPTER]
        assert len(ch_cits) == 0


# ──────────────────────────────────────────────
# extract_citations — Edge cases
# ──────────────────────────────────────────────

class TestExtractEdgeCases:

    def test_empty_string(self):
        assert extract_citations("") == []

    def test_no_citations(self):
        assert extract_citations("This is regular text with no legal references.") == []

    def test_mixed_internal_and_external(self):
        text = "Section 50-12-101 complies with MCL 125.3101 and 42 USC 11001."
        cits = extract_citations(text)
        types = {c.citation_type for c in cits}
        assert CitationType.SECTION in types
        assert CitationType.MCL in types
        assert CitationType.USC in types

    def test_concatenated_sections_parser_artifact(self):
        """Handle the known parser artifact: 'Section 50-13-236Section 50-13-237'."""
        text = "Section 50-13-236Section 50-13-237"
        cits = extract_citations(text)
        targets = {c.target for c in cits if c.citation_type == CitationType.SECTION}
        assert "50-13-236" in targets
        assert "50-13-237" in targets


# ──────────────────────────────────────────────
# build_citation_graph — Unit tests
# ──────────────────────────────────────────────

def _make_section(number: str, title: str, content: list[str],
                  level: int = 5, children: list[SectionNode] | None = None) -> SectionNode:
    """Helper to build a SectionNode for testing."""
    return SectionNode(
        number=number,
        title=title,
        level=level,
        content=content,
        children=children or [],
    )


class TestBuildCitationGraph:
    """Test graph construction from section trees."""

    def test_simple_two_section_graph(self):
        sections = [
            _make_section("50-12-101", "Sec A", ["See Section 50-12-102 for limits."]),
            _make_section("50-12-102", "Sec B", ["No external references here."]),
        ]
        graph = build_citation_graph(sections)

        assert "50-12-101" in graph.nodes
        assert "50-12-102" in graph.nodes
        assert len(graph.edges) == 1
        assert graph.edges[0].source_section == "50-12-101"
        assert graph.edges[0].target == "50-12-102"

    def test_external_reference_creates_terminal_node(self):
        sections = [
            _make_section("50-14-101", "Hazards", ["Comply with MCL 125.3101."]),
        ]
        graph = build_citation_graph(sections)

        assert "mcl:125.3101" in graph.nodes
        assert "mcl:125.3101" in graph.external_nodes
        assert len(graph.edges) == 1

    def test_self_reference_section_creates_no_edge(self):
        """'this section' referring to itself should not create an edge."""
        sections = [
            _make_section("50-12-101", "Sec A", ["As used in this section."]),
        ]
        graph = build_citation_graph(sections)
        # Self-edges are skipped
        assert len(graph.edges) == 0

    def test_self_reference_article_resolved(self):
        """'this article' should resolve to article-level and then expand."""
        # Section in article 12 referencing "this article"
        art = _make_section("50-12", "Article XII", [], level=3, children=[
            _make_section("50-12-101", "Sec A", ["elsewhere in this article"]),
            _make_section("50-12-102", "Sec B", []),
        ])
        graph = build_citation_graph([art], resolve_hierarchical=True)

        # "this article" from 50-12-101 should create edges to the article's sections
        edges_from_a = [e for e in graph.edges if e.source_section == "50-12-101"]
        targets = {e.target for e in edges_from_a}
        # Should include 50-12-102 (but not self)
        assert "50-12-102" in targets

    def test_article_reference_expanded(self):
        """'Article XII' should expand to edges to all leaf sections under Art XII."""
        art12 = _make_section("50-12", "Article XII", [], level=3, children=[
            _make_section("50-12-101", "Use Regs", []),
            _make_section("50-12-102", "More Uses", []),
        ])
        art14 = _make_section("50-14", "Article XIV", [], level=3, children=[
            _make_section("50-14-101", "Signs", ["See Article XII for use tables."]),
        ])
        graph = build_citation_graph([art12, art14], resolve_hierarchical=True)

        edges_from_14 = [e for e in graph.edges if e.source_section == "50-14-101"]
        targets = {e.target for e in edges_from_14}
        # Should have expanded to both leaf sections under article 12
        assert "50-12-101" in targets
        assert "50-12-102" in targets

    def test_article_reference_not_expanded_when_disabled(self):
        art12 = _make_section("50-12", "Article XII", [], level=3, children=[
            _make_section("50-12-101", "Use Regs", []),
        ])
        art14 = _make_section("50-14", "Article XIV", [], level=3, children=[
            _make_section("50-14-101", "Signs", ["See Article XII."]),
        ])
        graph = build_citation_graph([art12, art14], resolve_hierarchical=False)

        edges_from_14 = [e for e in graph.edges if e.source_section == "50-14-101"]
        assert len(edges_from_14) == 1
        assert edges_from_14[0].target == "article:XII"

    def test_nested_sections_all_become_nodes(self):
        """All sections in the tree should become graph nodes."""
        root = _make_section("50-12", "Article XII", [], level=3, children=[
            _make_section("50-12-1", "Div 1", [], level=4, children=[
                _make_section("50-12-101", "Sec A", []),
                _make_section("50-12-102", "Sec B", []),
            ]),
        ])
        graph = build_citation_graph([root])
        assert "50-12" in graph.nodes
        assert "50-12-1" in graph.nodes
        assert "50-12-101" in graph.nodes
        assert "50-12-102" in graph.nodes

    def test_internal_vs_external_nodes(self):
        sections = [
            _make_section("50-12-101", "Sec A", [
                "See MCL 125.3101 and Section 50-12-102."
            ]),
            _make_section("50-12-102", "Sec B", []),
        ]
        graph = build_citation_graph(sections)
        assert "50-12-101" in graph.internal_nodes
        assert "50-12-102" in graph.internal_nodes
        assert "mcl:125.3101" in graph.external_nodes

    def test_empty_sections_produce_no_edges(self):
        sections = [
            _make_section("50-12-101", "Sec A", []),
        ]
        graph = build_citation_graph(sections)
        assert len(graph.edges) == 0
        assert "50-12-101" in graph.nodes

    def test_section_without_number_skipped(self):
        """Sections with empty number should not produce edges."""
        sections = [
            _make_section("", "Unnamed", ["See Section 50-12-101."]),
            _make_section("50-12-101", "Target", []),
        ]
        graph = build_citation_graph(sections)
        # Only the unnamed section's content has a citation,
        # but it has no number so it's skipped as a source
        edge_sources = {e.source_section for e in graph.edges}
        assert "" not in edge_sources

    def test_content_sections_extracted_into_graph(self):
        """Numbered sections embedded in content should become graph nodes."""
        # Simulates real document structure: heading has no number,
        # but content paragraphs start with "Sec. 50-XX-YYY."
        sections = [
            _make_section("", "Subdivision A", [
                "Sec. 50-12-101. Use tables.",
                "See Section 50-12-102 for details.",
                "Sec. 50-12-102. Additional uses.",
                "This section has no outgoing citations.",
            ]),
        ]
        graph = build_citation_graph(sections)
        assert "50-12-101" in graph.nodes
        assert "50-12-102" in graph.nodes
        # 50-12-101 cites 50-12-102
        edges_from_101 = [e for e in graph.edges if e.source_section == "50-12-101"]
        assert any(e.target == "50-12-102" for e in edges_from_101)


# ──────────────────────────────────────────────
# extract_content_sections — Unit tests
# ──────────────────────────────────────────────

class TestExtractContentSections:
    """Test extraction of numbered sections from content paragraphs."""

    def test_single_section(self):
        node = _make_section("", "Subdiv A", [
            "Sec. 50-12-101. Use tables.",
            "Additional detail here.",
        ])
        sections = extract_content_sections(node)
        assert len(sections) == 1
        assert sections[0][0] == "50-12-101"
        assert "Use tables" in sections[0][1]
        assert "Additional detail" in sections[0][2]

    def test_multiple_sections(self):
        node = _make_section("", "Subdiv A", [
            "Sec. 50-12-101. First section.",
            "Detail for first.",
            "Sec. 50-12-102. Second section.",
            "Detail for second.",
        ])
        sections = extract_content_sections(node)
        assert len(sections) == 2
        assert sections[0][0] == "50-12-101"
        assert sections[1][0] == "50-12-102"
        # First section's content should include its detail
        assert "Detail for first" in sections[0][2]
        # But NOT the second section's content
        assert "Detail for second" not in sections[0][2]

    def test_no_section_markers(self):
        node = _make_section("", "Subdiv A", [
            "This is just regular content.",
            "No section markers here.",
        ])
        sections = extract_content_sections(node)
        assert len(sections) == 0

    def test_empty_content(self):
        node = _make_section("", "Subdiv A", [])
        sections = extract_content_sections(node)
        assert len(sections) == 0

    def test_text_before_first_section_excluded(self):
        """Paragraphs before the first Sec. marker are not included."""
        node = _make_section("", "Subdiv A", [
            "Introduction paragraph.",
            "Sec. 50-12-101. First actual section.",
        ])
        sections = extract_content_sections(node)
        assert len(sections) == 1
        assert "Introduction" not in sections[0][2]
