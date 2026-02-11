"""Municipal Zoning Ontology (MZO) — OWL/SKOS schema definition.

Defines the T-Box (terminology) for representing any US municipality's
zoning ordinance as an RDF knowledge graph.  The ``mzo:`` namespace is
generalizable: the same classes and properties work for Detroit, Chicago,
or any city.

Vocabularies used:
- OWL / RDFS — class definitions, property domains/ranges
- SKOS — concept hierarchies (districts, land uses)
- Dublin Core Terms — document metadata
"""

from __future__ import annotations

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS, XSD

# ──────────────────────────────────────────────
# Namespace
# ──────────────────────────────────────────────

MZO = Namespace("http://municipalzoning.org/ontology#")


# ──────────────────────────────────────────────
# OWL classes
# ──────────────────────────────────────────────

# Document structure
MUNICIPAL_CODE = MZO.MunicipalCode
CHAPTER = MZO.Chapter
ARTICLE = MZO.Article
DIVISION = MZO.Division
SUBDIVISION = MZO.Subdivision
SECTION = MZO.Section

# Zoning regulation
ZONING_DISTRICT = MZO.ZoningDistrict
DISTRICT_CATEGORY = MZO.DistrictCategory
LAND_USE = MZO.LandUse
LAND_USE_CATEGORY = MZO.LandUseCategory
USE_PERMISSION = MZO.UsePermission
PERMISSION_LEVEL = MZO.PermissionLevel

# Dimensional
DIMENSIONAL_STANDARD = MZO.DimensionalStandard
STANDARD_TYPE = MZO.StandardType

# Definitions
TERM_DEFINITION = MZO.TermDefinition

# Cross-references
CROSS_REFERENCE = MZO.CrossReference
RELATIONSHIP_TYPE = MZO.RelationshipType

# External law
EXTERNAL_LAW = MZO.ExternalLaw
EXTERNAL_LAW_TYPE = MZO.ExternalLawType

ALL_CLASSES = [
    MUNICIPAL_CODE, CHAPTER, ARTICLE, DIVISION, SUBDIVISION, SECTION,
    ZONING_DISTRICT, DISTRICT_CATEGORY, LAND_USE, LAND_USE_CATEGORY,
    USE_PERMISSION, PERMISSION_LEVEL,
    DIMENSIONAL_STANDARD, STANDARD_TYPE,
    TERM_DEFINITION,
    CROSS_REFERENCE, RELATIONSHIP_TYPE,
    EXTERNAL_LAW, EXTERNAL_LAW_TYPE,
]


# ──────────────────────────────────────────────
# PermissionLevel named individuals
# ──────────────────────────────────────────────

PERM_BY_RIGHT = MZO.by_right
PERM_CONDITIONAL = MZO.conditional
PERM_BY_RIGHT_WITH_CONDITIONS = MZO.by_right_with_conditions
PERM_NOT_PERMITTED = MZO.not_permitted

PERMISSION_LEVELS = [
    (PERM_BY_RIGHT, "By Right"),
    (PERM_CONDITIONAL, "Conditional"),
    (PERM_BY_RIGHT_WITH_CONDITIONS, "By Right with Conditions"),
    (PERM_NOT_PERMITTED, "Not Permitted"),
]


# ──────────────────────────────────────────────
# RelationshipType named individuals
# ──────────────────────────────────────────────

REL_DEFINES = MZO.defines
REL_CONSTRAINS = MZO.constrains
REL_REQUIRES = MZO.requires
REL_EXCEPTS = MZO.excepts
REL_REFERENCES = MZO.references
REL_AUTHORIZES = MZO.authorizes
REL_DELEGATES = MZO.delegates
REL_SUPPLEMENTS = MZO.supplements
REL_INCORPORATES = MZO.incorporates
REL_SUPERSEDES = MZO.supersedes
REL_UNKNOWN = MZO.unknown

RELATIONSHIP_TYPES = [
    (REL_DEFINES, "Defines", "as defined in, meaning given in"),
    (REL_CONSTRAINS, "Constrains", "subject to, limited by"),
    (REL_REQUIRES, "Requires", "shall comply with, in accordance with"),
    (REL_EXCEPTS, "Excepts", "except as provided in, notwithstanding"),
    (REL_REFERENCES, "References", "see, refer to, as described in, pursuant to"),
    (REL_AUTHORIZES, "Authorizes", "as permitted by, authorized by"),
    (REL_DELEGATES, "Delegates", "as determined by, at the discretion of"),
    (REL_SUPPLEMENTS, "Supplements", "in addition to, supplemented by"),
    (REL_INCORPORATES, "Incorporates", "incorporated by reference"),
    (REL_SUPERSEDES, "Supersedes", "notwithstanding ... to the contrary"),
    (REL_UNKNOWN, "Unknown", "no pattern matched"),
]


# ──────────────────────────────────────────────
# ExternalLawType named individuals
# ──────────────────────────────────────────────

EXT_STATE_COMPILED = MZO.state_compiled
EXT_FEDERAL_CODE = MZO.federal_code
EXT_FEDERAL_REGULATION = MZO.federal_regulation
EXT_PUBLIC_ACT = MZO.public_act

EXTERNAL_LAW_TYPES = [
    (EXT_STATE_COMPILED, "State Compiled Laws", "e.g. Michigan Compiled Laws"),
    (EXT_FEDERAL_CODE, "Federal Code", "e.g. US Code"),
    (EXT_FEDERAL_REGULATION, "Federal Regulation", "e.g. Code of Federal Regulations"),
    (EXT_PUBLIC_ACT, "Public Act", "e.g. P.A. 110 of 2006"),
]


# ──────────────────────────────────────────────
# SKOS Concept Schemes
# ──────────────────────────────────────────────

DISTRICT_SCHEME = MZO.DistrictScheme
LAND_USE_SCHEME = MZO.LandUseScheme
PERMISSION_SCHEME = MZO.PermissionScheme
DIMENSIONAL_SCHEME = MZO.DimensionalScheme

CONCEPT_SCHEMES = [
    (DISTRICT_SCHEME, "Zoning Districts"),
    (LAND_USE_SCHEME, "Land Uses"),
    (PERMISSION_SCHEME, "Permission Levels"),
    (DIMENSIONAL_SCHEME, "Dimensional Standards"),
]


# ──────────────────────────────────────────────
# Property definitions
# ──────────────────────────────────────────────

def _add_object_property(g: Graph, prop: URIRef, domain: URIRef, range_: URIRef,
                         label: str) -> None:
    """Add an OWL ObjectProperty with domain, range, and label."""
    g.add((prop, RDF.type, OWL.ObjectProperty))
    g.add((prop, RDFS.domain, domain))
    g.add((prop, RDFS.range, range_))
    g.add((prop, RDFS.label, Literal(label)))


def _add_datatype_property(g: Graph, prop: URIRef, domain: URIRef, range_: URIRef,
                           label: str) -> None:
    """Add an OWL DatatypeProperty with domain, range, and label."""
    g.add((prop, RDF.type, OWL.DatatypeProperty))
    g.add((prop, RDFS.domain, domain))
    g.add((prop, RDFS.range, range_))
    g.add((prop, RDFS.label, Literal(label)))


def build_ontology() -> Graph:
    """Return the MZO T-Box (schema only, no instance data).

    The returned graph contains OWL class declarations, property
    definitions with domains/ranges, SKOS concept scheme stubs,
    and named individuals for enumerated types (PermissionLevel,
    RelationshipType, ExternalLawType).
    """
    g = Graph()
    g.bind("mzo", MZO)
    g.bind("skos", SKOS)
    g.bind("dcterms", DCTERMS)
    g.bind("owl", OWL)

    # ── Classes ──
    for cls in ALL_CLASSES:
        g.add((cls, RDF.type, OWL.Class))
        g.add((cls, RDFS.label, Literal(cls.fragment)))

    # LandUse and LandUseCategory are also SKOS Concepts
    g.add((LAND_USE, RDFS.subClassOf, SKOS.Concept))
    g.add((LAND_USE_CATEGORY, RDFS.subClassOf, SKOS.Concept))
    g.add((ZONING_DISTRICT, RDFS.subClassOf, SKOS.Concept))
    g.add((DISTRICT_CATEGORY, RDFS.subClassOf, SKOS.Concept))

    # ── SKOS Concept Schemes ──
    for scheme, label in CONCEPT_SCHEMES:
        g.add((scheme, RDF.type, SKOS.ConceptScheme))
        g.add((scheme, RDFS.label, Literal(label)))

    # ── PermissionLevel individuals ──
    for uri, label in PERMISSION_LEVELS:
        g.add((uri, RDF.type, PERMISSION_LEVEL))
        g.add((uri, RDFS.label, Literal(label)))

    # ── RelationshipType individuals ──
    for uri, label, description in RELATIONSHIP_TYPES:
        g.add((uri, RDF.type, RELATIONSHIP_TYPE))
        g.add((uri, RDFS.label, Literal(label)))
        g.add((uri, RDFS.comment, Literal(description)))

    # ── ExternalLawType individuals ──
    for uri, label, description in EXTERNAL_LAW_TYPES:
        g.add((uri, RDF.type, EXTERNAL_LAW_TYPE))
        g.add((uri, RDFS.label, Literal(label)))
        g.add((uri, RDFS.comment, Literal(description)))

    # ── Document structure properties ──
    _add_object_property(g, MZO.hasChapter, MUNICIPAL_CODE, CHAPTER, "has chapter")
    _add_object_property(g, MZO.hasArticle, CHAPTER, ARTICLE, "has article")
    _add_object_property(g, MZO.hasDivision, ARTICLE, DIVISION, "has division")
    _add_object_property(g, MZO.hasSubdivision, DIVISION, SUBDIVISION, "has subdivision")
    _add_object_property(g, MZO.hasSection, ARTICLE, SECTION, "has section")
    _add_object_property(g, MZO.inArticle, SECTION, ARTICLE, "in article")

    _add_datatype_property(g, MZO.sectionNumber, SECTION, XSD.string, "section number")
    _add_datatype_property(g, MZO.sectionContent, SECTION, XSD.string, "section content")

    # ── Zoning properties ──
    _add_object_property(g, MZO.inCategory, ZONING_DISTRICT, DISTRICT_CATEGORY, "in category")
    _add_object_property(g, MZO.permitsUse, USE_PERMISSION, LAND_USE, "permits use")
    _add_object_property(g, MZO.inDistrict, USE_PERMISSION, ZONING_DISTRICT, "in district")
    _add_object_property(g, MZO.permissionLevel, USE_PERMISSION, PERMISSION_LEVEL,
                         "permission level")
    _add_datatype_property(g, MZO.conditions, USE_PERMISSION, XSD.string, "conditions")

    # ── Dimensional properties ──
    _add_object_property(g, MZO.appliesTo, DIMENSIONAL_STANDARD, ZONING_DISTRICT,
                         "applies to district")
    _add_object_property(g, MZO.standardType, DIMENSIONAL_STANDARD, STANDARD_TYPE,
                         "standard type")
    _add_datatype_property(g, MZO.standardValue, DIMENSIONAL_STANDARD, XSD.string,
                           "standard value")
    _add_datatype_property(g, MZO.standardUnit, DIMENSIONAL_STANDARD, XSD.string,
                           "standard unit")

    # ── Definition properties ──
    _add_datatype_property(g, MZO["term"], TERM_DEFINITION, XSD.string, "term")
    _add_datatype_property(g, MZO.definitionText, TERM_DEFINITION, XSD.string,
                           "definition text")
    _add_object_property(g, MZO.definedInSection, TERM_DEFINITION, SECTION,
                         "defined in section")

    # ── Cross-reference properties ──
    _add_object_property(g, MZO.fromSection, CROSS_REFERENCE, SECTION, "from section")
    _add_object_property(g, MZO.toSection, CROSS_REFERENCE, SECTION, "to section")
    _add_object_property(g, MZO.relationshipType, CROSS_REFERENCE, RELATIONSHIP_TYPE,
                         "relationship type")
    _add_datatype_property(g, MZO.contextSentence, CROSS_REFERENCE, XSD.string,
                           "context sentence")
    _add_datatype_property(g, MZO.rawCitationText, CROSS_REFERENCE, XSD.string,
                           "raw citation text")
    _add_datatype_property(g, MZO.isBidirectional, CROSS_REFERENCE, XSD.boolean,
                           "is bidirectional")

    # ── External law properties ──
    _add_object_property(g, MZO.externalLawType, EXTERNAL_LAW, EXTERNAL_LAW_TYPE,
                         "external law type")

    return g
