"""Tests for the Municipal Zoning Ontology (MZO) schema and RDF builder."""

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS, XSD

from strongtowns_detroit.zoning.ontology import (
    MZO,
    ALL_CLASSES,
    ARTICLE,
    CHAPTER,
    CONCEPT_SCHEMES,
    CROSS_REFERENCE,
    DIMENSIONAL_STANDARD,
    DISTRICT_CATEGORY,
    DISTRICT_SCHEME,
    EXTERNAL_LAW,
    EXTERNAL_LAW_TYPE,
    LAND_USE,
    LAND_USE_CATEGORY,
    LAND_USE_SCHEME,
    MUNICIPAL_CODE,
    PERM_BY_RIGHT,
    PERM_CONDITIONAL,
    PERM_NOT_PERMITTED,
    PERMISSION_LEVEL,
    PERMISSION_LEVELS,
    PERMISSION_SCHEME,
    REL_CONSTRAINS,
    REL_DEFINES,
    REL_EXCEPTS,
    REL_REFERENCES,
    REL_REQUIRES,
    REL_UNKNOWN,
    RELATIONSHIP_TYPE,
    RELATIONSHIP_TYPES,
    SECTION,
    STANDARD_TYPE,
    TERM_DEFINITION,
    USE_PERMISSION,
    ZONING_DISTRICT,
    build_ontology,
)
from strongtowns_detroit.zoning.rdf_builder import (
    _permission_to_uri,
    _slugify,
    _find_context_sentence,
    classify_relationship,
    build_rdf_graph,
    export_graph,
)
from strongtowns_detroit.zoning.models import (
    Citation,
    CitationGraph,
    CitationType,
    DimensionalStandard,
    SectionNode,
    UsePermission,
    ZoningDefinition,
)


# ──────────────────────────────────────────────
# Ontology schema tests
# ──────────────────────────────────────────────

class TestOntologySchema:
    """Test that build_ontology() produces a valid T-Box."""

    @pytest.fixture
    def schema(self):
        return build_ontology()

    def test_all_classes_declared(self, schema):
        """Every class in ALL_CLASSES should be declared as owl:Class."""
        for cls in ALL_CLASSES:
            assert (cls, RDF.type, OWL.Class) in schema, f"{cls} not declared"

    def test_class_count(self, schema):
        classes = list(schema.subjects(RDF.type, OWL.Class))
        assert len(classes) == len(ALL_CLASSES)

    def test_key_classes_present(self, schema):
        """Spot-check critical classes."""
        for cls in [SECTION, ZONING_DISTRICT, USE_PERMISSION, CROSS_REFERENCE,
                    TERM_DEFINITION, DIMENSIONAL_STANDARD, EXTERNAL_LAW]:
            assert (cls, RDF.type, OWL.Class) in schema

    def test_land_use_is_skos_concept(self, schema):
        """LandUse and LandUseCategory should be subclasses of skos:Concept."""
        assert (LAND_USE, RDFS.subClassOf, SKOS.Concept) in schema
        assert (LAND_USE_CATEGORY, RDFS.subClassOf, SKOS.Concept) in schema

    def test_district_is_skos_concept(self, schema):
        assert (ZONING_DISTRICT, RDFS.subClassOf, SKOS.Concept) in schema


class TestConceptSchemes:
    """Test SKOS concept schemes."""

    @pytest.fixture
    def schema(self):
        return build_ontology()

    def test_all_schemes_declared(self, schema):
        for scheme, _label in CONCEPT_SCHEMES:
            assert (scheme, RDF.type, SKOS.ConceptScheme) in schema

    def test_scheme_count(self, schema):
        schemes = list(schema.subjects(RDF.type, SKOS.ConceptScheme))
        assert len(schemes) == 4


class TestPermissionLevels:
    """Test PermissionLevel named individuals."""

    @pytest.fixture
    def schema(self):
        return build_ontology()

    def test_all_permission_levels_declared(self, schema):
        for uri, _label in PERMISSION_LEVELS:
            assert (uri, RDF.type, PERMISSION_LEVEL) in schema

    def test_permission_level_count(self, schema):
        individuals = list(schema.subjects(RDF.type, PERMISSION_LEVEL))
        assert len(individuals) == 4

    def test_permission_level_labels(self, schema):
        for uri, label in PERMISSION_LEVELS:
            assert (uri, RDFS.label, Literal(label)) in schema


class TestRelationshipTypes:
    """Test RelationshipType named individuals."""

    @pytest.fixture
    def schema(self):
        return build_ontology()

    def test_all_relationship_types_declared(self, schema):
        for uri, _label, _desc in RELATIONSHIP_TYPES:
            assert (uri, RDF.type, RELATIONSHIP_TYPE) in schema

    def test_relationship_type_count(self, schema):
        individuals = list(schema.subjects(RDF.type, RELATIONSHIP_TYPE))
        assert len(individuals) == 11

    def test_relationship_types_have_comments(self, schema):
        for uri, _label, _desc in RELATIONSHIP_TYPES:
            comments = list(schema.objects(uri, RDFS.comment))
            assert len(comments) == 1


class TestProperties:
    """Test that properties have correct domain/range."""

    @pytest.fixture
    def schema(self):
        return build_ontology()

    def test_object_properties_exist(self, schema):
        obj_props = list(schema.subjects(RDF.type, OWL.ObjectProperty))
        assert len(obj_props) >= 10

    def test_datatype_properties_exist(self, schema):
        dt_props = list(schema.subjects(RDF.type, OWL.DatatypeProperty))
        assert len(dt_props) >= 5

    def test_section_number_domain_range(self, schema):
        assert (MZO.sectionNumber, RDFS.domain, SECTION) in schema
        assert (MZO.sectionNumber, RDFS.range, XSD.string) in schema

    def test_permits_use_domain_range(self, schema):
        assert (MZO.permitsUse, RDFS.domain, USE_PERMISSION) in schema
        assert (MZO.permitsUse, RDFS.range, LAND_USE) in schema

    def test_cross_reference_properties(self, schema):
        assert (MZO.fromSection, RDFS.domain, CROSS_REFERENCE) in schema
        assert (MZO.toSection, RDFS.domain, CROSS_REFERENCE) in schema
        assert (MZO.relationshipType, RDFS.domain, CROSS_REFERENCE) in schema
        assert (MZO.contextSentence, RDFS.domain, CROSS_REFERENCE) in schema


# ──────────────────────────────────────────────
# RDF builder helper tests
# ──────────────────────────────────────────────

class TestSlugify:
    def test_basic(self):
        assert _slugify("Single Family Dwelling") == "single_family_dwelling"

    def test_special_chars(self):
        assert _slugify("R1-A (Special)") == "r1_a_special"

    def test_strips_leading_trailing(self):
        assert _slugify("  hello  ") == "hello"


class TestPermissionMapping:
    def test_by_right(self):
        assert _permission_to_uri("R") == PERM_BY_RIGHT

    def test_conditional(self):
        assert _permission_to_uri("C") == PERM_CONDITIONAL

    def test_mixed_cr(self):
        from strongtowns_detroit.zoning.ontology import PERM_BY_RIGHT_WITH_CONDITIONS
        assert _permission_to_uri("C/R") == PERM_BY_RIGHT_WITH_CONDITIONS

    def test_dash_not_permitted(self):
        assert _permission_to_uri("—") == PERM_NOT_PERMITTED


class TestContextSentence:
    def test_finds_sentence(self):
        text = "First sentence. See Section 50-12-101 for details. Third sentence."
        result = _find_context_sentence(text, "Section 50-12-101")
        assert "See Section 50-12-101 for details" in result

    def test_no_match_returns_empty(self):
        assert _find_context_sentence("No citations here.", "Section 50-12-101") == ""


class TestRelationshipClassification:
    def test_defines(self):
        assert classify_relationship("as defined in Section 50-12-101") == REL_DEFINES

    def test_constrains(self):
        assert classify_relationship("subject to the requirements of") == REL_CONSTRAINS

    def test_requires(self):
        assert classify_relationship("shall comply with Section 50-12-101") == REL_REQUIRES

    def test_excepts(self):
        assert classify_relationship("except as provided in Section 50-12-101") == REL_EXCEPTS

    def test_references(self):
        assert classify_relationship("see Section 50-12-101") == REL_REFERENCES

    def test_unknown(self):
        assert classify_relationship("blah blah Section 50-12-101") == REL_UNKNOWN


# ──────────────────────────────────────────────
# RDF builder integration
# ──────────────────────────────────────────────

class TestBuildRdfGraph:
    """Test build_rdf_graph with synthetic data."""

    @pytest.fixture
    def sample_data(self):
        """Create a small synthetic dataset."""
        sections = [
            SectionNode(
                number="",
                title="Article XII",
                level=3,
                content=[
                    "Sec. 50-12-101. Use tables. The following table shows permitted uses.",
                    "See Section 50-12-102 for conditions.",
                    "Sec. 50-12-102. Conditions. Subject to the requirements of Section 50-12-101.",
                ],
                children=[],
            ),
        ]

        use_permissions = [
            UsePermission("Single-family dwelling", "R1", "R"),
            UsePermission("Single-family dwelling", "R2", "R"),
            UsePermission("Duplex", "R1", "C", conditions="Min lot 6000 sqft"),
            UsePermission("Duplex", "R2", "R"),
            UsePermission("Office", "B1", "R"),
        ]

        dimensional_standards = [
            DimensionalStandard("R1", "Minimum Lot Area", "5,000 sq ft"),
            DimensionalStandard("R2", "Minimum Lot Area", "3,000 sq ft"),
            DimensionalStandard("R1", "Maximum Height", "35 ft"),
        ]

        definitions = [
            ZoningDefinition("Dwelling", "A building designed for residential use."),
            ZoningDefinition("Setback", "The minimum distance from a lot line.", "50-16-101"),
        ]

        citation_graph = CitationGraph(
            nodes={
                "50-12-101": "Use tables",
                "50-12-102": "Conditions",
            },
            edges=[
                Citation("50-12-101", "50-12-102", CitationType.SECTION, "Section 50-12-102"),
                Citation("50-12-102", "50-12-101", CitationType.SECTION, "Section 50-12-101"),
            ],
        )

        use_categories = {
            "Household living": {
                "Single-family dwelling": {"by_right": ["R1", "R2"]},
                "Duplex": {"by_right": ["R2"], "conditional": ["R1"]},
            },
            "Commercial": {
                "Office": {"by_right": ["B1"]},
            },
        }

        return {
            "sections": sections,
            "use_permissions": use_permissions,
            "dimensional_standards": dimensional_standards,
            "definitions": definitions,
            "citation_graph": citation_graph,
            "use_categories": use_categories,
        }

    @pytest.fixture
    def graph(self, sample_data):
        return build_rdf_graph(
            citation_graph=sample_data["citation_graph"],
            sections=sample_data["sections"],
            use_permissions=sample_data["use_permissions"],
            dimensional_standards=sample_data["dimensional_standards"],
            definitions=sample_data["definitions"],
            use_categories=sample_data["use_categories"],
            municipality="testcity",
            chapter="99",
        )

    def test_graph_not_empty(self, graph):
        assert len(graph) > 0

    def test_has_ontology_classes(self, graph):
        """Graph includes the T-Box."""
        assert (SECTION, RDF.type, OWL.Class) in graph

    def test_sections_created(self, graph):
        sections = list(graph.subjects(RDF.type, MZO.Section))
        assert len(sections) >= 2

    def test_section_has_content(self, graph):
        from rdflib import Namespace
        ns = Namespace("http://municipalzoning.org/testcity/")
        sec = ns["section/50-12-101"]
        contents = list(graph.objects(sec, MZO.sectionContent))
        assert len(contents) == 1
        assert "Use tables" in str(contents[0])

    def test_districts_as_skos(self, graph):
        districts = list(graph.subjects(RDF.type, MZO.ZoningDistrict))
        assert len(districts) >= 2  # At least R1, R2

    def test_use_permissions_created(self, graph):
        perms = list(graph.subjects(RDF.type, MZO.UsePermission))
        assert len(perms) == 5

    def test_dimensional_standards_created(self, graph):
        dims = list(graph.subjects(RDF.type, MZO.DimensionalStandard))
        assert len(dims) == 3

    def test_definitions_created(self, graph):
        defs = list(graph.subjects(RDF.type, MZO.TermDefinition))
        assert len(defs) == 2

    def test_cross_references_created(self, graph):
        xrefs = list(graph.subjects(RDF.type, MZO.CrossReference))
        assert len(xrefs) == 2

    def test_bidirectional_detected(self, graph):
        """Bidirectional edges should be flagged."""
        xrefs = list(graph.subjects(RDF.type, MZO.CrossReference))
        bidir_count = 0
        for xref in xrefs:
            for _, _, val in graph.triples((xref, MZO.isBidirectional, None)):
                if val.toPython() is True:
                    bidir_count += 1
        assert bidir_count == 2  # Both directions flagged

    def test_skos_hierarchy(self, graph):
        """Use categories should link to specific uses via broader/narrower."""
        from rdflib import Namespace
        ns = Namespace("http://municipalzoning.org/testcity/")
        cat_uri = ns["use_category/household_living"]
        narrower = list(graph.objects(cat_uri, SKOS.narrower))
        assert len(narrower) >= 2  # Single-family and Duplex

    def test_article_created(self, graph):
        articles = list(graph.subjects(RDF.type, MZO.Article))
        assert len(articles) >= 1

    def test_chapter_created(self, graph):
        chapters = list(graph.subjects(RDF.type, MZO.Chapter))
        assert len(chapters) == 1


class TestExportGraph:
    """Test graph serialization."""

    def test_export_turtle(self, tmp_path):
        g = build_ontology()
        out = tmp_path / "test.ttl"
        export_graph(g, out)
        assert out.exists()
        assert out.stat().st_size > 0

        # Round-trip: parse the file back
        g2 = Graph()
        g2.parse(str(out))
        assert len(g2) == len(g)
