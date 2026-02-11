"""Tests for SPARQL query tools on the Municipal Zoning Knowledge Graph."""

import pytest
from rdflib import Graph

from strongtowns_detroit.zoning.models import (
    Citation,
    CitationGraph,
    CitationType,
    DimensionalStandard,
    SectionNode,
    UsePermission,
    ZoningDefinition,
)
from strongtowns_detroit.zoning.rdf_builder import build_rdf_graph
from strongtowns_detroit.zoning.kg_queries import (
    bfs_traverse,
    query_concept_hierarchy,
    query_cross_references,
    query_definition,
    query_dimensional_standards,
    query_related_concepts,
    query_sections_by_topic,
    query_use_permissions,
)


# ──────────────────────────────────────────────
# Shared synthetic dataset
# ──────────────────────────────────────────────

@pytest.fixture
def kg() -> Graph:
    """Build a small knowledge graph for testing queries.

    Contains:
    - 3 districts: R1, R2, B1
    - 5 uses: Single-family, Duplex, Townhouse, Office, Restaurant
    - 8 sections across 2 articles
    - 10 cross-references
    - 3 dimensional standards
    - 2 definitions
    """
    sections = [
        SectionNode(
            number="",
            title="Article XII",
            level=3,
            content=[
                "Sec. 50-12-101. Use regulations. This section establishes permitted uses.",
                "See Section 50-12-102 for residential conditions.",
                "Sec. 50-12-102. Residential conditions. Subject to the requirements of "
                "Section 50-12-101. As defined in Section 50-16-201.",
                "Sec. 50-12-103. Commercial uses. Office use shall comply with Section 50-13-201.",
                "Sec. 50-12-104. Special provisions. Except as provided in Section 50-12-101, "
                "the following apply.",
            ],
            children=[],
        ),
        SectionNode(
            number="",
            title="Article XIII",
            level=3,
            content=[
                "Sec. 50-13-201. Dimensional standards. See Section 50-12-101 for context.",
                "Sec. 50-13-202. Height limits. As determined by the Planning Commission "
                "pursuant to Section 50-13-201.",
                "Sec. 50-13-203. Setback requirements. In addition to Section 50-13-201.",
            ],
            children=[],
        ),
        SectionNode(
            number="",
            title="Article XVI",
            level=3,
            content=[
                "Sec. 50-16-201. Definitions. This section provides definitions.",
            ],
            children=[],
        ),
    ]

    use_permissions = [
        UsePermission("Single-family dwelling", "R1", "R"),
        UsePermission("Single-family dwelling", "R2", "R"),
        UsePermission("Duplex", "R1", "C", conditions="Min lot 6000 sqft"),
        UsePermission("Duplex", "R2", "R"),
        UsePermission("Townhouse", "R2", "C"),
        UsePermission("Office", "B1", "R"),
        UsePermission("Restaurant", "B1", "C"),
    ]

    dimensional_standards = [
        DimensionalStandard("R1", "Minimum Lot Area", "5,000 sq ft", "50-13-201"),
        DimensionalStandard("R2", "Minimum Lot Area", "3,000 sq ft", "50-13-201"),
        DimensionalStandard("R1", "Maximum Height", "35 ft", "50-13-202"),
    ]

    definitions = [
        ZoningDefinition("Dwelling", "A building designed for residential use.", "50-16-201"),
        ZoningDefinition("Setback", "The minimum distance from a lot line.", "50-16-201"),
    ]

    citation_graph = CitationGraph(
        nodes={
            "50-12-101": "Use regulations",
            "50-12-102": "Residential conditions",
            "50-12-103": "Commercial uses",
            "50-12-104": "Special provisions",
            "50-13-201": "Dimensional standards",
            "50-13-202": "Height limits",
            "50-13-203": "Setback requirements",
            "50-16-201": "Definitions",
        },
        edges=[
            Citation("50-12-101", "50-12-102", CitationType.SECTION, "Section 50-12-102"),
            Citation("50-12-102", "50-12-101", CitationType.SECTION, "Section 50-12-101"),
            Citation("50-12-102", "50-16-201", CitationType.SECTION, "Section 50-16-201"),
            Citation("50-12-103", "50-13-201", CitationType.SECTION, "Section 50-13-201"),
            Citation("50-12-104", "50-12-101", CitationType.SECTION, "Section 50-12-101"),
            Citation("50-13-201", "50-12-101", CitationType.SECTION, "Section 50-12-101"),
            Citation("50-13-202", "50-13-201", CitationType.SECTION, "Section 50-13-201"),
            Citation("50-13-203", "50-13-201", CitationType.SECTION, "Section 50-13-201"),
        ],
    )

    use_categories = {
        "Household living": {
            "Single-family dwelling": {"by_right": ["R1", "R2"]},
            "Duplex": {"by_right": ["R2"], "conditional": ["R1"]},
            "Townhouse": {"conditional": ["R2"]},
        },
        "Commercial": {
            "Office": {"by_right": ["B1"]},
            "Restaurant": {"conditional": ["B1"]},
        },
    }

    return build_rdf_graph(
        citation_graph=citation_graph,
        sections=sections,
        use_permissions=use_permissions,
        dimensional_standards=dimensional_standards,
        definitions=definitions,
        use_categories=use_categories,
        municipality="testcity",
        chapter="99",
    )


# ──────────────────────────────────────────────
# query_use_permissions
# ──────────────────────────────────────────────

class TestQueryUsePermissions:
    def test_filter_by_district(self, kg):
        results = query_use_permissions(kg, district="R1")
        assert len(results) >= 2
        assert all(r["district"] == "R1" for r in results)

    def test_filter_by_use(self, kg):
        results = query_use_permissions(kg, use="duplex")
        assert len(results) >= 2
        uses = {r["use"] for r in results}
        assert any("Duplex" in u for u in uses)

    def test_filter_by_permission(self, kg):
        results = query_use_permissions(kg, permission="conditional")
        assert len(results) >= 2
        assert all(r["permission"] == "conditional" for r in results)

    def test_conditions_returned(self, kg):
        results = query_use_permissions(kg, district="R1", use="duplex")
        assert len(results) >= 1
        cond_result = [r for r in results if r["conditions"]]
        assert len(cond_result) >= 1
        assert "6000" in cond_result[0]["conditions"]

    def test_no_filters_returns_all(self, kg):
        results = query_use_permissions(kg)
        assert len(results) == 7

    def test_no_match_returns_empty(self, kg):
        results = query_use_permissions(kg, district="X99")
        assert results == []


# ──────────────────────────────────────────────
# query_dimensional_standards
# ──────────────────────────────────────────────

class TestQueryDimensionalStandards:
    def test_filter_by_district(self, kg):
        results = query_dimensional_standards(kg, district="R1")
        assert len(results) >= 2
        assert all(r["district"] == "R1" for r in results)

    def test_filter_by_type(self, kg):
        results = query_dimensional_standards(kg, standard_type="lot area")
        assert len(results) >= 2

    def test_value_returned(self, kg):
        results = query_dimensional_standards(kg, district="R1", standard_type="lot area")
        assert len(results) >= 1
        assert "5,000" in results[0]["value"]

    def test_unit_extracted(self, kg):
        results = query_dimensional_standards(kg, district="R1", standard_type="lot area")
        assert len(results) >= 1
        assert results[0]["unit"] == "sq ft"

    def test_no_match_returns_empty(self, kg):
        results = query_dimensional_standards(kg, district="X99")
        assert results == []


# ──────────────────────────────────────────────
# query_definition
# ──────────────────────────────────────────────

class TestQueryDefinition:
    def test_find_definition(self, kg):
        result = query_definition(kg, "dwelling")
        assert result is not None
        assert "residential" in result.lower()

    def test_case_insensitive(self, kg):
        result = query_definition(kg, "SETBACK")
        assert result is not None
        assert "distance" in result.lower()

    def test_not_found_returns_none(self, kg):
        result = query_definition(kg, "nonexistent_term_xyz")
        assert result is None


# ──────────────────────────────────────────────
# query_cross_references
# ──────────────────────────────────────────────

class TestQueryCrossReferences:
    def test_outgoing_refs(self, kg):
        results = query_cross_references(kg, "50-12-101", direction="outgoing")
        assert len(results) >= 1
        assert all(r["from_section"] == "50-12-101" for r in results)
        targets = {r["to_section"] for r in results}
        assert "50-12-102" in targets

    def test_incoming_refs(self, kg):
        results = query_cross_references(kg, "50-12-101", direction="incoming")
        assert len(results) >= 2
        assert all(r["to_section"] == "50-12-101" for r in results)

    def test_both_directions(self, kg):
        results = query_cross_references(kg, "50-12-101", direction="both")
        directions = {r["direction"] for r in results}
        assert "outgoing" in directions
        assert "incoming" in directions

    def test_relationship_type_classified(self, kg):
        results = query_cross_references(kg, "50-12-102", direction="outgoing")
        rels = {r["relationship"] for r in results}
        # "Subject to the requirements" → constrains or requires
        # "As defined in" → defines
        assert len(rels) >= 1
        assert "unknown" not in rels or len(rels) > 1  # At least some classified

    def test_no_refs_returns_empty(self, kg):
        results = query_cross_references(kg, "99-99-999", direction="both")
        assert results == []


# ──────────────────────────────────────────────
# query_concept_hierarchy
# ──────────────────────────────────────────────

class TestQueryConceptHierarchy:
    def test_category_has_narrower(self, kg):
        from rdflib import Namespace
        ns = Namespace("http://municipalzoning.org/testcity/")
        cat_uri = ns["use_category/household_living"]
        result = query_concept_hierarchy(kg, cat_uri, depth=1)
        assert result["label"] == "Household living"
        assert len(result["narrower"]) >= 2

    def test_use_has_broader(self, kg):
        from rdflib import Namespace
        ns = Namespace("http://municipalzoning.org/testcity/")
        use_uri = ns["use/single_family_dwelling"]
        result = query_concept_hierarchy(kg, use_uri, depth=1)
        assert len(result["broader"]) >= 1
        assert any("Household" in b["label"] for b in result["broader"])

    def test_depth_zero_no_children(self, kg):
        from rdflib import Namespace
        ns = Namespace("http://municipalzoning.org/testcity/")
        cat_uri = ns["use_category/household_living"]
        result = query_concept_hierarchy(kg, cat_uri, depth=0)
        assert result["narrower"] == []


# ──────────────────────────────────────────────
# bfs_traverse
# ──────────────────────────────────────────────

class TestBfsTraverse:
    def test_start_section_in_layer_zero(self, kg):
        result = bfs_traverse(kg, "50-12-101", max_depth=1)
        assert result["start"] == "50-12-101"
        assert result["layers"][0]["sections"] == ["50-12-101"]

    def test_depth_one_finds_neighbors(self, kg):
        result = bfs_traverse(kg, "50-12-101", max_depth=1)
        assert len(result["layers"]) >= 2
        layer1_sections = result["layers"][1]["sections"]
        assert len(layer1_sections) >= 1

    def test_respects_max_depth(self, kg):
        result = bfs_traverse(kg, "50-12-101", max_depth=1)
        assert len(result["layers"]) <= 2

    def test_outgoing_only(self, kg):
        result = bfs_traverse(kg, "50-12-101", max_depth=1, direction="outgoing")
        if len(result["layers"]) > 1:
            edges = result["layers"][1]["edges"]
            assert all(e["from"] == "50-12-101" for e in edges)

    def test_no_duplicates_across_layers(self, kg):
        result = bfs_traverse(kg, "50-12-101", max_depth=3)
        all_sections = set()
        for layer in result["layers"]:
            for sec in layer["sections"]:
                assert sec not in all_sections, f"{sec} appears in multiple layers"
                all_sections.add(sec)


# ──────────────────────────────────────────────
# query_sections_by_topic
# ──────────────────────────────────────────────

class TestQuerySectionsByTopic:
    def test_find_sections(self, kg):
        results = query_sections_by_topic(kg, ["residential"])
        assert len(results) >= 1

    def test_and_logic(self, kg):
        results = query_sections_by_topic(kg, ["residential", "conditions"])
        # Only sections containing BOTH keywords
        assert len(results) >= 1
        for r in results:
            assert r["section_id"] is not None

    def test_no_keywords_returns_empty(self, kg):
        results = query_sections_by_topic(kg, [])
        assert results == []

    def test_no_match_returns_empty(self, kg):
        results = query_sections_by_topic(kg, ["xyznonexistent"])
        assert results == []


# ──────────────────────────────────────────────
# query_related_concepts
# ──────────────────────────────────────────────

class TestQueryRelatedConcepts:
    def test_finds_dimensional_standards(self, kg):
        results = query_related_concepts(kg, "50-13-201")
        types = {r["type"] for r in results}
        assert "DimensionalStandard" in types

    def test_finds_definitions(self, kg):
        results = query_related_concepts(kg, "50-16-201")
        types = {r["type"] for r in results}
        assert "TermDefinition" in types

    def test_section_with_no_concepts(self, kg):
        results = query_related_concepts(kg, "50-12-104")
        # May or may not have related concepts; should not error
        assert isinstance(results, list)
