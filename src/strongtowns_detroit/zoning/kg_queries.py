"""SPARQL query tools for the Municipal Zoning Knowledge Graph.

Pre-built queries that an AI agent can call to answer zoning questions.
Each function takes an rdflib ``Graph`` and returns structured Python
objects (lists of dicts, strings, or nested dicts).

All queries use the MZO ontology namespace and are municipality-agnostic —
they work on any graph built by ``rdf_builder.build_rdf_graph()``.
"""

from __future__ import annotations

from collections import defaultdict

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS, SKOS

from strongtowns_detroit.zoning.ontology import MZO


# ──────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────

def _execute_sparql(g: Graph, query: str, bindings: dict | None = None) -> list[dict]:
    """Execute a SPARQL SELECT and return a list of dicts.

    Each dict maps variable name → value (as Python string or URIRef).
    """
    results = g.query(query, initBindings=bindings or {})
    rows = []
    for row in results:
        d = {}
        for var in results.vars:
            val = getattr(row, str(var), None)
            d[str(var)] = str(val) if val is not None else None
        rows.append(d)
    return rows


def _uri_fragment(uri: str) -> str:
    """Extract the fragment or last path segment from a URI."""
    if "#" in uri:
        return uri.split("#")[-1]
    return uri.rstrip("/").split("/")[-1]


# ──────────────────────────────────────────────
# Query functions
# ──────────────────────────────────────────────

def query_use_permissions(
    g: Graph,
    district: str | None = None,
    use: str | None = None,
    permission: str | None = None,
) -> list[dict]:
    """Query use permissions — what uses are allowed in a district.

    Filter by district code, use name (substring match), and/or
    permission level (``by_right``, ``conditional``, etc.).

    Returns list of dicts with keys: use, district, permission, conditions.
    """
    filters = []
    bindings: dict = {}

    if district:
        filters.append("FILTER(STR(?dist_label) = ?dist_filter)")
        bindings[Literal("dist_filter")] = Literal(district)

    if use:
        filters.append("FILTER(CONTAINS(LCASE(STR(?use_label)), LCASE(?use_filter)))")
        bindings[Literal("use_filter")] = Literal(use)

    if permission:
        filters.append("FILTER(CONTAINS(LCASE(STR(?perm_uri)), LCASE(?perm_filter)))")
        bindings[Literal("perm_filter")] = Literal(permission)

    # Use initBindings for safe parameterization
    query = f"""
    PREFIX mzo: <http://municipalzoning.org/ontology#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

    SELECT ?use_label ?dist_label ?perm_uri ?conditions
    WHERE {{
        ?p a mzo:UsePermission ;
           mzo:permitsUse ?use ;
           mzo:inDistrict ?dist ;
           mzo:permissionLevel ?perm_uri .
        ?use skos:prefLabel ?use_label .
        ?dist skos:prefLabel ?dist_label .
        OPTIONAL {{ ?p mzo:conditions ?conditions }}
        {chr(10).join(filters)}
    }}
    ORDER BY ?use_label ?dist_label
    """

    # Build initBindings with Variable keys
    from rdflib import Variable
    init = {}
    if district:
        init[Variable("dist_filter")] = Literal(district)
    if use:
        init[Variable("use_filter")] = Literal(use)
    if permission:
        init[Variable("perm_filter")] = Literal(permission)

    rows = _execute_sparql(g, query, init)

    return [
        {
            "use": r["use_label"],
            "district": r["dist_label"],
            "permission": _uri_fragment(r["perm_uri"]),
            "conditions": r.get("conditions") or "",
        }
        for r in rows
    ]


def query_dimensional_standards(
    g: Graph,
    district: str | None = None,
    standard_type: str | None = None,
) -> list[dict]:
    """Query dimensional standards for a district or standard type.

    Returns list of dicts with keys: district, standard, value, unit.
    """
    filters = []
    init: dict = {}

    if district:
        filters.append("FILTER(STR(?dist_label) = ?dist_filter)")
        from rdflib import Variable
        init[Variable("dist_filter")] = Literal(district)

    if standard_type:
        filters.append(
            "FILTER(CONTAINS(LCASE(STR(?type_label)), LCASE(?type_filter)))"
        )
        from rdflib import Variable
        init[Variable("type_filter")] = Literal(standard_type)

    query = f"""
    PREFIX mzo: <http://municipalzoning.org/ontology#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

    SELECT ?dist_label ?type_label ?value ?unit
    WHERE {{
        ?d a mzo:DimensionalStandard ;
           mzo:appliesTo ?dist ;
           mzo:standardType ?stype ;
           mzo:standardValue ?value .
        ?dist skos:prefLabel ?dist_label .
        ?stype skos:prefLabel ?type_label .
        OPTIONAL {{ ?d mzo:standardUnit ?unit }}
        {chr(10).join(filters)}
    }}
    ORDER BY ?dist_label ?type_label
    """

    rows = _execute_sparql(g, query, init)

    return [
        {
            "district": r["dist_label"],
            "standard": r["type_label"],
            "value": r["value"],
            "unit": r.get("unit") or "",
        }
        for r in rows
    ]


def query_definition(g: Graph, term: str) -> str | None:
    """Look up a zoning term definition.

    Uses case-insensitive substring match. Returns the definition text
    or None if not found.
    """
    from rdflib import Variable

    query = """
    PREFIX mzo: <http://municipalzoning.org/ontology#>

    SELECT ?def_text
    WHERE {
        ?d a mzo:TermDefinition ;
           mzo:term ?term ;
           mzo:definitionText ?def_text .
        FILTER(CONTAINS(LCASE(STR(?term)), LCASE(?search)))
    }
    LIMIT 1
    """

    rows = _execute_sparql(g, query, {Variable("search"): Literal(term)})
    if rows:
        return rows[0]["def_text"]
    return None


def query_cross_references(
    g: Graph,
    section_id: str,
    direction: str = "both",
) -> list[dict]:
    """Query cross-references for a section.

    *direction*: ``"outgoing"`` (cites), ``"incoming"`` (cited by),
    or ``"both"``.

    Returns list of dicts with keys: from_section, to_section,
    relationship, context, raw_text, bidirectional.
    """
    results: list[dict] = []

    if direction in ("outgoing", "both"):
        query = """
        PREFIX mzo: <http://municipalzoning.org/ontology#>

        SELECT ?to_sec ?rel ?context ?raw ?bidir
        WHERE {
            ?xref a mzo:CrossReference ;
                  mzo:fromSection ?from ;
                  mzo:toSection ?to ;
                  mzo:relationshipType ?rel .
            ?from mzo:sectionNumber ?from_num .
            FILTER(STR(?from_num) = ?sec_id)
            ?to mzo:sectionNumber ?to_sec .
            OPTIONAL { ?xref mzo:contextSentence ?context }
            OPTIONAL { ?xref mzo:rawCitationText ?raw }
            OPTIONAL { ?xref mzo:isBidirectional ?bidir }
        }
        """
        from rdflib import Variable
        rows = _execute_sparql(g, query, {Variable("sec_id"): Literal(section_id)})
        for r in rows:
            results.append({
                "from_section": section_id,
                "to_section": r["to_sec"],
                "relationship": _uri_fragment(r["rel"]),
                "context": r.get("context") or "",
                "raw_text": r.get("raw") or "",
                "bidirectional": r.get("bidir") == "true",
                "direction": "outgoing",
            })

    if direction in ("incoming", "both"):
        query = """
        PREFIX mzo: <http://municipalzoning.org/ontology#>

        SELECT ?from_sec ?rel ?context ?raw ?bidir
        WHERE {
            ?xref a mzo:CrossReference ;
                  mzo:fromSection ?from ;
                  mzo:toSection ?to ;
                  mzo:relationshipType ?rel .
            ?to mzo:sectionNumber ?to_num .
            FILTER(STR(?to_num) = ?sec_id)
            ?from mzo:sectionNumber ?from_sec .
            OPTIONAL { ?xref mzo:contextSentence ?context }
            OPTIONAL { ?xref mzo:rawCitationText ?raw }
            OPTIONAL { ?xref mzo:isBidirectional ?bidir }
        }
        """
        from rdflib import Variable
        rows = _execute_sparql(g, query, {Variable("sec_id"): Literal(section_id)})
        for r in rows:
            results.append({
                "from_section": r["from_sec"],
                "to_section": section_id,
                "relationship": _uri_fragment(r["rel"]),
                "context": r.get("context") or "",
                "raw_text": r.get("raw") or "",
                "bidirectional": r.get("bidir") == "true",
                "direction": "incoming",
            })

    return results


def query_concept_hierarchy(
    g: Graph,
    concept_uri: str | URIRef,
    depth: int = 2,
) -> dict:
    """Navigate the SKOS broader/narrower hierarchy.

    Returns a nested dict::

        {
            "uri": "...",
            "label": "...",
            "broader": [...],
            "narrower": [{...recursive...}],
        }

    Descends up to *depth* levels for narrower concepts.
    """
    if isinstance(concept_uri, str):
        concept_uri = URIRef(concept_uri)

    label = _get_label(g, concept_uri)

    result: dict = {
        "uri": str(concept_uri),
        "label": label,
        "broader": [],
        "narrower": [],
    }

    # Broader (one level up only)
    for _, _, broader in g.triples((concept_uri, SKOS.broader, None)):
        result["broader"].append({
            "uri": str(broader),
            "label": _get_label(g, broader),
        })

    # Narrower (recursive to depth)
    if depth > 0:
        for _, _, narrower in g.triples((concept_uri, SKOS.narrower, None)):
            child = query_concept_hierarchy(g, narrower, depth - 1)
            result["narrower"].append(child)

    return result


def _get_label(g: Graph, uri: URIRef) -> str:
    """Get the best label for a URI (skos:prefLabel > rdfs:label > fragment)."""
    for _, _, label in g.triples((uri, SKOS.prefLabel, None)):
        return str(label)
    for _, _, label in g.triples((uri, RDFS.label, None)):
        return str(label)
    return _uri_fragment(str(uri))


def bfs_traverse(
    g: Graph,
    start_section: str,
    max_depth: int = 3,
    direction: str = "both",
) -> dict:
    """BFS traversal from a section, returning annotated layers.

    Returns::

        {
            "start": "50-12-101",
            "layers": [
                {  # depth 0
                    "sections": ["50-12-101"],
                    "edges": []
                },
                {  # depth 1
                    "sections": ["50-12-102", "50-12-103"],
                    "edges": [
                        {"from": "50-12-101", "to": "50-12-102", "relationship": "requires"},
                        ...
                    ]
                },
                ...
            ]
        }
    """
    visited: set[str] = {start_section}
    layers: list[dict] = [{"sections": [start_section], "edges": []}]

    current_frontier = {start_section}

    for _depth in range(max_depth):
        next_frontier: set[str] = set()
        layer_edges: list[dict] = []

        for sec_id in current_frontier:
            refs = query_cross_references(g, sec_id, direction=direction)
            for ref in refs:
                neighbor = (
                    ref["to_section"] if ref["direction"] == "outgoing"
                    else ref["from_section"]
                )
                if neighbor not in visited:
                    visited.add(neighbor)
                    next_frontier.add(neighbor)
                layer_edges.append({
                    "from": ref["from_section"],
                    "to": ref["to_section"],
                    "relationship": ref["relationship"],
                })

        if not next_frontier:
            break

        layers.append({
            "sections": sorted(next_frontier),
            "edges": layer_edges,
        })
        current_frontier = next_frontier

    return {"start": start_section, "layers": layers}


def query_sections_by_topic(
    g: Graph,
    topic_keywords: list[str],
) -> list[dict]:
    """Find sections whose content mentions given keywords.

    Uses case-insensitive substring matching against ``mzo:sectionContent``.
    All keywords must match (AND logic).

    Returns list of dicts with keys: section_id, title, snippet.
    """
    if not topic_keywords:
        return []

    # Build FILTER clause for AND matching
    kw_filters = []
    bindings: dict = {}
    from rdflib import Variable

    for i, kw in enumerate(topic_keywords):
        var_name = f"kw{i}"
        kw_filters.append(
            f"FILTER(CONTAINS(LCASE(STR(?content)), LCASE(?{var_name})))"
        )
        bindings[Variable(var_name)] = Literal(kw)

    query = f"""
    PREFIX mzo: <http://municipalzoning.org/ontology#>
    PREFIX dcterms: <http://purl.org/dc/terms/>

    SELECT ?sec_num ?title ?content
    WHERE {{
        ?s a mzo:Section ;
           mzo:sectionNumber ?sec_num ;
           mzo:sectionContent ?content .
        OPTIONAL {{ ?s dcterms:title ?title }}
        {chr(10).join(kw_filters)}
    }}
    ORDER BY ?sec_num
    """

    rows = _execute_sparql(g, query, bindings)

    results = []
    for r in rows:
        content = r.get("content", "")
        # Create snippet around first keyword match
        snippet = _make_snippet(content, topic_keywords[0]) if content else ""
        results.append({
            "section_id": r["sec_num"],
            "title": r.get("title") or "",
            "snippet": snippet,
        })

    return results


def _make_snippet(text: str, keyword: str, window: int = 100) -> str:
    """Extract a snippet around the first occurrence of keyword."""
    idx = text.lower().find(keyword.lower())
    if idx < 0:
        return text[:200] + "..." if len(text) > 200 else text
    start = max(0, idx - window)
    end = min(len(text), idx + len(keyword) + window)
    snippet = text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet


def query_related_concepts(
    g: Graph,
    section_id: str,
) -> list[dict]:
    """Find concepts (uses, districts, standards) related to a section.

    Looks for any UsePermission, DimensionalStandard, or TermDefinition
    linked to the section, plus cross-references.

    Returns list of dicts with keys: type, label, uri.
    """
    from rdflib import Variable

    results: list[dict] = []

    # UsePermissions that reference this section (via conditions text)
    # DimensionalStandards defined in this section
    query = """
    PREFIX mzo: <http://municipalzoning.org/ontology#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

    SELECT ?type ?label ?uri
    WHERE {
        {
            ?uri a mzo:DimensionalStandard ;
                 mzo:definedInSection ?sec ;
                 mzo:standardType ?stype .
            ?sec mzo:sectionNumber ?sec_num .
            ?stype skos:prefLabel ?label .
            FILTER(STR(?sec_num) = ?search)
            BIND("DimensionalStandard" AS ?type)
        }
        UNION
        {
            ?uri a mzo:TermDefinition ;
                 mzo:definedInSection ?sec ;
                 mzo:term ?label .
            ?sec mzo:sectionNumber ?sec_num .
            FILTER(STR(?sec_num) = ?search)
            BIND("TermDefinition" AS ?type)
        }
    }
    """

    rows = _execute_sparql(g, query, {Variable("search"): Literal(section_id)})
    for r in rows:
        results.append({
            "type": r["type"],
            "label": r["label"],
            "uri": r["uri"],
        })

    return results
