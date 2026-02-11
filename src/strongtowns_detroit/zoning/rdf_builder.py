"""Convert parsed zoning ordinance data into an RDF knowledge graph.

Builds the A-Box (instance data) layered on top of the MZO ontology.
All URIs are scoped by municipality to support multi-city graphs.

The builder consumes the same data structures produced by
``parse_ordinance()`` and ``build_citation_graph()`` and emits RDF
triples suitable for SPARQL querying.
"""

from __future__ import annotations

import re
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS, XSD

from strongtowns_detroit.zoning.document import walk_sections
from strongtowns_detroit.zoning.models import (
    Citation,
    CitationGraph,
    CitationType,
    DimensionalStandard,
    SectionNode,
    UsePermission,
    ZoningDefinition,
)
from strongtowns_detroit.zoning.ontology import (
    MZO,
    DISTRICT_SCHEME,
    LAND_USE_SCHEME,
    PERMISSION_SCHEME,
    DIMENSIONAL_SCHEME,
    PERM_BY_RIGHT,
    PERM_CONDITIONAL,
    PERM_BY_RIGHT_WITH_CONDITIONS,
    PERM_NOT_PERMITTED,
    REL_DEFINES,
    REL_CONSTRAINS,
    REL_REQUIRES,
    REL_EXCEPTS,
    REL_REFERENCES,
    REL_AUTHORIZES,
    REL_DELEGATES,
    REL_SUPPLEMENTS,
    REL_INCORPORATES,
    REL_SUPERSEDES,
    REL_UNKNOWN,
    EXT_STATE_COMPILED,
    EXT_FEDERAL_CODE,
    EXT_FEDERAL_REGULATION,
    EXT_PUBLIC_ACT,
    build_ontology,
)

# ──────────────────────────────────────────────
# URI helpers
# ──────────────────────────────────────────────

BASE = "http://municipalzoning.org/"


def _muni_ns(municipality: str) -> Namespace:
    """Namespace for a specific municipality's instance data."""
    return Namespace(f"{BASE}{municipality}/")


def _slugify(text: str) -> str:
    """Convert text to a URI-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower().strip())
    return slug.strip("_")


def _section_uri(ns: Namespace, sec_num: str) -> URIRef:
    return ns[f"section/{sec_num}"]


def _district_uri(ns: Namespace, district: str) -> URIRef:
    return ns[f"district/{_slugify(district)}"]


def _use_uri(ns: Namespace, use_name: str) -> URIRef:
    return ns[f"use/{_slugify(use_name)}"]


def _category_uri(ns: Namespace, category: str) -> URIRef:
    return ns[f"category/{_slugify(category)}"]


def _article_uri(ns: Namespace, article_num: str) -> URIRef:
    return ns[f"article/{article_num}"]


# ──────────────────────────────────────────────
# Permission level mapping
# ──────────────────────────────────────────────

def _permission_to_uri(permission: str) -> URIRef:
    """Map a permission string from UsePermission.permission to a PermissionLevel URI."""
    p = permission.strip().upper()
    if p == "R":
        return PERM_BY_RIGHT
    if p == "C":
        return PERM_CONDITIONAL
    if p in ("C/R", "R/C"):
        return PERM_BY_RIGHT_WITH_CONDITIONS
    return PERM_NOT_PERMITTED


# ──────────────────────────────────────────────
# Relationship classification
# ──────────────────────────────────────────────

# Priority-ordered patterns for classifying citation context
_RELATIONSHIP_PATTERNS: list[tuple[re.Pattern, URIRef]] = [
    (re.compile(r"as\s+defined\s+in|meaning\s+given\s+in|definition\s+in", re.I),
     REL_DEFINES),
    (re.compile(r"notwithstanding.*to\s+the\s+contrary", re.I),
     REL_SUPERSEDES),
    (re.compile(r"except\s+as\s+provided\s+in|notwithstanding", re.I),
     REL_EXCEPTS),
    (re.compile(r"subject\s+to|limited\s+by|restricted\s+by", re.I),
     REL_CONSTRAINS),
    (re.compile(r"shall\s+comply\s+with|in\s+accordance\s+with|must\s+conform\s+to", re.I),
     REL_REQUIRES),
    (re.compile(r"as\s+permitted\s+by|authorized\s+by|allowed\s+under", re.I),
     REL_AUTHORIZES),
    (re.compile(r"as\s+determined\s+by|at\s+the\s+discretion\s+of|approved\s+by", re.I),
     REL_DELEGATES),
    (re.compile(r"in\s+addition\s+to|supplemented?\s+by", re.I),
     REL_SUPPLEMENTS),
    (re.compile(r"incorporated?\s+by\s+reference", re.I),
     REL_INCORPORATES),
    (re.compile(r"see\b|refer\s+to|as\s+described\s+in|pursuant\s+to|set\s+forth\s+in", re.I),
     REL_REFERENCES),
]


def classify_relationship(context: str) -> URIRef:
    """Classify citation context into a RelationshipType."""
    for pattern, rel_type in _RELATIONSHIP_PATTERNS:
        if pattern.search(context):
            return rel_type
    return REL_UNKNOWN


# ──────────────────────────────────────────────
# Sentence extraction
# ──────────────────────────────────────────────

# Sentence boundary: period/semicolon/colon followed by whitespace or end
_SENTENCE_RE = re.compile(r"[.;:]\s+|$")


def _find_context_sentence(full_text: str, raw_citation: str) -> str:
    """Find the sentence containing a citation in section text.

    Returns the sentence or a 200-char window around the match.
    """
    idx = full_text.find(raw_citation)
    if idx < 0:
        return ""

    # Walk backward to find sentence start
    start = max(0, idx)
    while start > 0 and full_text[start - 1] not in ".;:\n":
        start -= 1
    # Walk forward to find sentence end
    m = _SENTENCE_RE.search(full_text, idx + len(raw_citation))
    end = m.start() + 1 if m and m.start() > idx else min(len(full_text), idx + 200)

    return full_text[start:end].strip()


# ──────────────────────────────────────────────
# District category mapping
# ──────────────────────────────────────────────

# Static district-category mapping (generalizable for Detroit; other
# cities will supply their own).
_DISTRICT_CATEGORIES = {
    "residential": ["R1", "R2", "R3", "R4", "R5", "R6"],
    "special_district": ["SD1", "SD2", "SD4", "SD5"],
    "business": ["B1", "B2", "B3", "B4", "B5", "B6"],
    "industrial": ["M1", "M2", "M3", "M4", "M5"],
    "special_purpose": [
        "PCA", "PC", "PD", "TM", "W1",
        "PR1", "PR2",
    ],
    "parks_recreation": ["PR1", "PR2"],
}


def _get_district_category(district: str) -> str:
    """Return the category name for a district code."""
    for cat, districts in _DISTRICT_CATEGORIES.items():
        if district.upper() in [d.upper() for d in districts]:
            return cat
    return "other"


# ──────────────────────────────────────────────
# Section number pattern
# ──────────────────────────────────────────────

_SEC_START_RE = re.compile(r"^Sec\.?\s+(\d{2}-\d{1,2}-\d{1,4})\b")


def _extract_content_sections(node: SectionNode) -> list[tuple[str, str, str]]:
    """Extract numbered sections from content paragraphs.

    Returns (section_number, title, content_text) tuples.
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
            if current_num:
                sections.append((current_num, current_title, " ".join(current_paras)))
            current_num = m.group(1)
            current_title = para
            current_paras = [para]
        else:
            current_paras.append(para)

    if current_num:
        sections.append((current_num, current_title, " ".join(current_paras)))

    return sections


# ──────────────────────────────────────────────
# External law type mapping
# ──────────────────────────────────────────────

def _external_law_type(target: str) -> URIRef | None:
    """Map a citation target to an ExternalLawType URI."""
    if target.startswith("mcl:"):
        return EXT_STATE_COMPILED
    if target.startswith("usc:"):
        return EXT_FEDERAL_CODE
    if target.startswith("cfr:"):
        return EXT_FEDERAL_REGULATION
    if target.startswith("pa:"):
        return EXT_PUBLIC_ACT
    return None


# ──────────────────────────────────────────────
# Sub-builders
# ──────────────────────────────────────────────

def _add_document_structure(
    g: Graph,
    sections: list[SectionNode],
    ns: Namespace,
    municipality: str,
    chapter: str,
) -> None:
    """Convert SectionNode trees into RDF document structure triples."""
    # Municipal code and chapter
    code_uri = ns["code"]
    chapter_uri = ns[f"chapter/{chapter}"]

    g.add((code_uri, RDF.type, MZO.MunicipalCode))
    g.add((code_uri, DCTERMS.title, Literal(f"{municipality.title()} Code of Ordinances")))

    g.add((chapter_uri, RDF.type, MZO.Chapter))
    g.add((chapter_uri, DCTERMS.identifier, Literal(chapter)))
    g.add((chapter_uri, DCTERMS.title, Literal(f"Chapter {chapter} — Zoning")))
    g.add((code_uri, MZO.hasChapter, chapter_uri))

    # Build section text index for later use (returned via side effect on graph)
    for node in walk_sections(sections):
        level = node.level

        if level == 3:  # Article
            art_num = node.number or _slugify(node.title)
            art_uri = _article_uri(ns, art_num)
            g.add((art_uri, RDF.type, MZO.Article))
            g.add((art_uri, DCTERMS.title, Literal(node.title)))
            if node.number:
                g.add((art_uri, DCTERMS.identifier, Literal(node.number)))
            g.add((chapter_uri, MZO.hasArticle, art_uri))

        elif level == 4:  # Division
            div_slug = _slugify(f"{node.number}_{node.title}" if node.number else node.title)
            div_uri = ns[f"division/{div_slug}"]
            g.add((div_uri, RDF.type, MZO.Division))
            g.add((div_uri, DCTERMS.title, Literal(node.title)))

        elif level == 5:  # Subdivision
            subdiv_slug = _slugify(
                f"{node.number}_{node.title}" if node.number else node.title
            )
            subdiv_uri = ns[f"subdivision/{subdiv_slug}"]
            g.add((subdiv_uri, RDF.type, MZO.Subdivision))
            g.add((subdiv_uri, DCTERMS.title, Literal(node.title)))

        # Extract numbered sections from content paragraphs
        content_secs = _extract_content_sections(node)
        for sec_num, title, text in content_secs:
            sec_uri = _section_uri(ns, sec_num)
            g.add((sec_uri, RDF.type, MZO.Section))
            g.add((sec_uri, MZO.sectionNumber, Literal(sec_num)))
            g.add((sec_uri, DCTERMS.title, Literal(title)))
            if text:
                g.add((sec_uri, MZO.sectionContent, Literal(text)))

            # Link to article via prefix
            parts = sec_num.split("-")
            if len(parts) >= 2:
                art_prefix = f"{parts[0]}-{parts[1]}"
                art_uri = _article_uri(ns, art_prefix)
                g.add((sec_uri, MZO.inArticle, art_uri))
                g.add((art_uri, MZO.hasSection, sec_uri))

        # Also handle nodes with direct section numbers (from test fixtures)
        if node.number and re.match(r"^\d{2}-\d{1,2}-\d{1,4}$", node.number):
            sec_uri = _section_uri(ns, node.number)
            if (sec_uri, RDF.type, MZO.Section) not in g:
                g.add((sec_uri, RDF.type, MZO.Section))
                g.add((sec_uri, MZO.sectionNumber, Literal(node.number)))
                g.add((sec_uri, DCTERMS.title, Literal(node.title)))
                text = " ".join(node.content)
                if text:
                    g.add((sec_uri, MZO.sectionContent, Literal(text)))
                parts = node.number.split("-")
                if len(parts) >= 2:
                    art_prefix = f"{parts[0]}-{parts[1]}"
                    art_uri = _article_uri(ns, art_prefix)
                    g.add((sec_uri, MZO.inArticle, art_uri))
                    g.add((art_uri, MZO.hasSection, sec_uri))


def _add_districts(
    g: Graph,
    use_categories: dict | None,
    ns: Namespace,
) -> None:
    """Add SKOS concepts for zoning districts."""
    seen_districts: set[str] = set()

    # Collect districts from use_categories if available
    if use_categories:
        for _cat_name, uses in use_categories.items():
            for _use_name, perm_data in uses.items():
                for districts in perm_data.values():
                    if isinstance(districts, list):
                        seen_districts.update(districts)

    # Add static-known districts
    for cat_districts in _DISTRICT_CATEGORIES.values():
        seen_districts.update(cat_districts)

    # Create district category concepts
    cat_uris: dict[str, URIRef] = {}
    for cat_name in _DISTRICT_CATEGORIES:
        cat_uri = _category_uri(ns, cat_name)
        cat_uris[cat_name] = cat_uri
        g.add((cat_uri, RDF.type, MZO.DistrictCategory))
        g.add((cat_uri, RDF.type, SKOS.Concept))
        g.add((cat_uri, SKOS.prefLabel, Literal(cat_name.replace("_", " ").title())))
        g.add((cat_uri, SKOS.inScheme, DISTRICT_SCHEME))

    # Create district concepts
    for district in sorted(seen_districts):
        d_uri = _district_uri(ns, district)
        g.add((d_uri, RDF.type, MZO.ZoningDistrict))
        g.add((d_uri, RDF.type, SKOS.Concept))
        g.add((d_uri, SKOS.notation, Literal(district)))
        g.add((d_uri, SKOS.prefLabel, Literal(district)))
        g.add((d_uri, SKOS.inScheme, DISTRICT_SCHEME))

        # Link to category
        cat_name = _get_district_category(district)
        if cat_name in cat_uris:
            g.add((d_uri, MZO.inCategory, cat_uris[cat_name]))
            g.add((d_uri, SKOS.broader, cat_uris[cat_name]))
            g.add((cat_uris[cat_name], SKOS.narrower, d_uri))


def _add_use_permissions(
    g: Graph,
    use_permissions: list[UsePermission],
    use_categories: dict | None,
    ns: Namespace,
) -> None:
    """Convert UsePermission records into RDF triples with SKOS hierarchy."""
    # Build category lookup from use_categories JSON
    use_to_category: dict[str, str] = {}
    if use_categories:
        for cat_name, uses in use_categories.items():
            for use_name in uses:
                use_to_category[use_name.lower()] = cat_name

    # Create SKOS category concepts
    seen_categories: set[str] = set()
    for cat_name in (use_to_category.values() if use_to_category else []):
        if cat_name not in seen_categories:
            seen_categories.add(cat_name)
            cat_uri = ns[f"use_category/{_slugify(cat_name)}"]
            g.add((cat_uri, RDF.type, MZO.LandUseCategory))
            g.add((cat_uri, RDF.type, SKOS.Concept))
            g.add((cat_uri, SKOS.prefLabel, Literal(cat_name)))
            g.add((cat_uri, SKOS.inScheme, LAND_USE_SCHEME))

    # Create use permission triples
    seen_uses: set[str] = set()
    for i, perm in enumerate(use_permissions):
        # Create land use concept (once per unique use)
        use_key = perm.use_name.lower()
        use_uri = _use_uri(ns, perm.use_name)
        if use_key not in seen_uses:
            seen_uses.add(use_key)
            g.add((use_uri, RDF.type, MZO.LandUse))
            g.add((use_uri, RDF.type, SKOS.Concept))
            g.add((use_uri, SKOS.prefLabel, Literal(perm.use_name)))
            g.add((use_uri, SKOS.inScheme, LAND_USE_SCHEME))

            # Link to category
            if use_key in use_to_category:
                cat_uri = ns[f"use_category/{_slugify(use_to_category[use_key])}"]
                g.add((use_uri, SKOS.broader, cat_uri))
                g.add((cat_uri, SKOS.narrower, use_uri))

        # Create reified UsePermission node
        perm_uri = ns[f"permission/{_slugify(perm.use_name)}_{_slugify(perm.district)}_{i}"]
        g.add((perm_uri, RDF.type, MZO.UsePermission))
        g.add((perm_uri, MZO.permitsUse, use_uri))
        g.add((perm_uri, MZO.inDistrict, _district_uri(ns, perm.district)))
        g.add((perm_uri, MZO.permissionLevel, _permission_to_uri(perm.permission)))

        if perm.conditions:
            g.add((perm_uri, MZO.conditions, Literal(perm.conditions)))


def _add_dimensional_standards(
    g: Graph,
    dimensional_standards: list[DimensionalStandard],
    ns: Namespace,
) -> None:
    """Convert DimensionalStandard records into RDF triples."""
    seen_types: set[str] = set()

    for i, dim in enumerate(dimensional_standards):
        # Create StandardType concept (once per unique name)
        type_slug = _slugify(dim.standard_name)
        type_uri = ns[f"standard_type/{type_slug}"]
        if type_slug not in seen_types:
            seen_types.add(type_slug)
            g.add((type_uri, RDF.type, MZO.StandardType))
            g.add((type_uri, SKOS.prefLabel, Literal(dim.standard_name)))
            g.add((type_uri, SKOS.inScheme, DIMENSIONAL_SCHEME))

        # Create DimensionalStandard instance
        dim_uri = ns[f"dimensional/{_slugify(dim.district)}_{type_slug}_{i}"]
        g.add((dim_uri, RDF.type, MZO.DimensionalStandard))
        g.add((dim_uri, MZO.appliesTo, _district_uri(ns, dim.district)))
        g.add((dim_uri, MZO.standardType, type_uri))
        g.add((dim_uri, MZO.standardValue, Literal(dim.value)))

        # Try to extract unit from value
        unit = _extract_unit(dim.value)
        if unit:
            g.add((dim_uri, MZO.standardUnit, Literal(unit)))

        # Link to defining section if available
        if dim.section_ref:
            sec_uri = _section_uri(ns, dim.section_ref)
            g.add((dim_uri, MZO.definedInSection, sec_uri))


def _extract_unit(value: str) -> str:
    """Try to extract a unit from a dimensional standard value string."""
    v = value.lower().strip()
    if "sq ft" in v or "square feet" in v:
        return "sq ft"
    if "ft" in v or "feet" in v:
        return "ft"
    if "stories" in v or "story" in v:
        return "stories"
    if "%" in v:
        return "%"
    if "acres" in v or "acre" in v:
        return "acres"
    return ""


def _add_definitions(
    g: Graph,
    definitions: list[ZoningDefinition],
    ns: Namespace,
) -> None:
    """Convert ZoningDefinition records into RDF triples."""
    for i, defn in enumerate(definitions):
        defn_uri = ns[f"definition/{_slugify(defn.term)}_{i}"]
        g.add((defn_uri, RDF.type, MZO.TermDefinition))
        g.add((defn_uri, MZO["term"], Literal(defn.term)))
        g.add((defn_uri, MZO.definitionText, Literal(defn.definition)))
        g.add((defn_uri, SKOS.definition, Literal(defn.definition)))

        if defn.section_ref:
            sec_uri = _section_uri(ns, defn.section_ref)
            g.add((defn_uri, MZO.definedInSection, sec_uri))


def _add_cross_references(
    g: Graph,
    citation_graph: CitationGraph,
    sections: list[SectionNode],
    ns: Namespace,
) -> None:
    """Convert citation edges into reified CrossReference triples."""
    # Build section text index for context extraction
    section_texts: dict[str, str] = {}
    for node in walk_sections(sections):
        # From content paragraph sections
        content_secs = _extract_content_sections(node)
        for sec_num, _title, text in content_secs:
            section_texts[sec_num] = text
        # From direct section numbers
        if node.number and node.content:
            section_texts.setdefault(node.number, " ".join(node.content))

    # Detect bidirectional pairs
    edge_pairs: set[tuple[str, str]] = set()
    for edge in citation_graph.edges:
        edge_pairs.add((edge.source_section, edge.target))
    bidirectional: set[tuple[str, str]] = set()
    for src, tgt in edge_pairs:
        if (tgt, src) in edge_pairs:
            pair = tuple(sorted([src, tgt]))
            bidirectional.add(pair)

    # Create CrossReference triples
    for i, edge in enumerate(citation_graph.edges):
        ref_uri = ns[f"xref/{i}"]
        g.add((ref_uri, RDF.type, MZO.CrossReference))
        g.add((ref_uri, MZO.rawCitationText, Literal(edge.raw_text)))

        # Source section
        src_uri = _section_uri(ns, edge.source_section)
        g.add((ref_uri, MZO.fromSection, src_uri))
        # Ensure source section exists as a node
        if (src_uri, RDF.type, MZO.Section) not in g:
            g.add((src_uri, RDF.type, MZO.Section))
            g.add((src_uri, MZO.sectionNumber, Literal(edge.source_section)))

        # Target — may be a section or external law
        ext_type = _external_law_type(edge.target)
        if ext_type:
            tgt_uri = ns[f"external/{_slugify(edge.target)}"]
            g.add((tgt_uri, RDF.type, MZO.ExternalLaw))
            g.add((tgt_uri, MZO.externalLawType, ext_type))
            g.add((tgt_uri, RDFS.label, Literal(edge.target)))
            g.add((ref_uri, MZO.toSection, tgt_uri))
        else:
            tgt_uri = _section_uri(ns, edge.target)
            g.add((ref_uri, MZO.toSection, tgt_uri))
            if (tgt_uri, RDF.type, MZO.Section) not in g:
                g.add((tgt_uri, RDF.type, MZO.Section))
                g.add((tgt_uri, MZO.sectionNumber, Literal(edge.target)))

        # Context sentence and relationship classification
        full_text = section_texts.get(edge.source_section, "")
        if full_text and edge.raw_text:
            context = _find_context_sentence(full_text, edge.raw_text)
            if context:
                g.add((ref_uri, MZO.contextSentence, Literal(context)))
                rel_type = classify_relationship(context)
                g.add((ref_uri, MZO.relationshipType, rel_type))
            else:
                g.add((ref_uri, MZO.relationshipType, REL_UNKNOWN))
        else:
            g.add((ref_uri, MZO.relationshipType, REL_UNKNOWN))

        # Bidirectional flag
        pair = tuple(sorted([edge.source_section, edge.target]))
        if pair in bidirectional:
            g.add((ref_uri, MZO.isBidirectional, Literal(True)))


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────

def build_rdf_graph(
    citation_graph: CitationGraph,
    sections: list[SectionNode],
    use_permissions: list[UsePermission],
    dimensional_standards: list[DimensionalStandard],
    definitions: list[ZoningDefinition],
    use_categories: dict | None = None,
    municipality: str = "detroit",
    chapter: str = "50",
) -> Graph:
    """Build complete RDF knowledge graph from parsed ordinance data.

    Layers instance data (A-Box) on top of the MZO ontology (T-Box).
    All URIs are scoped under ``http://municipalzoning.org/{municipality}/``.
    """
    g = build_ontology()
    ns = _muni_ns(municipality)
    g.bind(municipality, ns)

    _add_document_structure(g, sections, ns, municipality, chapter)
    _add_districts(g, use_categories, ns)
    _add_use_permissions(g, use_permissions, use_categories, ns)
    _add_dimensional_standards(g, dimensional_standards, ns)
    _add_definitions(g, definitions, ns)
    _add_cross_references(g, citation_graph, sections, ns)

    return g


def export_graph(graph: Graph, path: Path, fmt: str = "turtle") -> None:
    """Serialize the RDF graph to a file.

    Supported formats: ``turtle`` (.ttl), ``json-ld`` (.jsonld),
    ``nt`` (.nt), ``xml`` (.rdf).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    graph.serialize(destination=str(path), format=fmt)
