"""Integration tests against real Detroit Zoning Ordinance .docx files.

These tests parse the actual documents in resources/ and verify the output
against known facts about Detroit's zoning code.  They serve as regression
tests to catch parser breakage when the code is refactored.

The tests are skipped if the resources directory is missing (e.g. in CI
without the data files).
"""

import json
from collections import Counter
from pathlib import Path

import pytest

RESOURCES = Path(__file__).resolve().parent.parent / "resources"
PIPELINES = Path(__file__).resolve().parent.parent / "pipelines"

# Skip all tests in this module if the resources directory is missing
pytestmark = pytest.mark.skipif(
    not (RESOURCES / "ARTICLE_XII.___USE_REGULATIONS.docx").exists(),
    reason="resources/*.docx files not available",
)

# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

ARTICLE_XII = RESOURCES / "ARTICLE_XII.___USE_REGULATIONS.docx"
ARTICLE_XIII = RESOURCES / "ARTICLE_XIII.___INTENSITY_AND_DIMENSIONAL_STANDARDS.docx"
ARTICLE_XVI = RESOURCES / "ARTICLE_XVI.___RULES_OF_CONSTRUCTION_AND_DEFINITIONS.docx"
APPENDIX_A = RESOURCES / "APPENDIX_A.___ASSIGNMENT_OF_SPECIFIC_USE_TYPES_TO_GENERAL_USE_CATEGORIES.docx"


@pytest.fixture(scope="module")
def lot_size_restrictions():
    """Load ground-truth lot size restrictions from the parcel pipeline."""
    path = PIPELINES / "parcel-data" / "zoning_districts_to_lot_size_restrictions.json"
    if not path.exists():
        pytest.skip("lot size restrictions JSON not available")
    with open(path) as f:
        return json.load(f)


# ──────────────────────────────────────────────
# Table Classifier
# ──────────────────────────────────────────────

class TestClassifyRealTables:
    """Verify that classify_table() correctly identifies table types
    in the actual ordinance documents."""

    def test_article_xii_has_use_matrices(self):
        from strongtowns_detroit.zoning.table_parser import extract_tables_xml, classify_table

        tables = extract_tables_xml(ARTICLE_XII)
        use_matrices = [g for g in tables if classify_table(g) == "use_matrix"]
        # Article XII has 41 use-permission matrices
        assert len(use_matrices) >= 40

    def test_article_xiii_has_dimensional_tables(self):
        from strongtowns_detroit.zoning.table_parser import extract_tables_xml, classify_table

        tables = extract_tables_xml(ARTICLE_XIII)
        dim_tables = [g for g in tables if classify_table(g) == "dimensional"]
        # Article XIII has ~32 dimensional tables
        assert len(dim_tables) >= 29

    def test_article_xvi_all_lookup(self):
        from strongtowns_detroit.zoning.table_parser import extract_tables_xml, classify_table

        tables = extract_tables_xml(ARTICLE_XVI)
        lookup_tables = [g for g in tables if classify_table(g) == "lookup"]
        assert len(lookup_tables) == len(tables)
        assert len(lookup_tables) >= 50

    def test_appendix_a_all_lookup(self):
        from strongtowns_detroit.zoning.table_parser import extract_tables_xml, classify_table

        tables = extract_tables_xml(APPENDIX_A)
        lookup_tables = [g for g in tables if classify_table(g) == "lookup"]
        assert len(lookup_tables) == len(tables)
        assert len(lookup_tables) >= 20


# ──────────────────────────────────────────────
# Article XII — Use Permissions
# ──────────────────────────────────────────────

class TestArticleXIIUsePermissions:
    """Verify use-permission parsing against known facts."""

    @pytest.fixture(scope="class")
    def use_records(self):
        from strongtowns_detroit.zoning.use_tables import extract_all_use_permissions
        return extract_all_use_permissions(ARTICLE_XII)

    def test_record_count(self, use_records):
        # 41 tables × ~7 data rows × 29 districts ≈ thousands of records
        assert len(use_records) > 5000

    def test_expected_districts(self, use_records):
        districts = sorted(set(r.district for r in use_records))
        # Must include all residential and business districts
        for expected in ["R1", "R2", "R3", "R4", "R5", "R6",
                         "B1", "B2", "B3", "B4", "B5", "B6"]:
            assert expected in districts, f"Missing district {expected}"

    def test_29_districts(self, use_records):
        districts = set(r.district for r in use_records)
        assert len(districts) == 29

    def test_single_family_by_right_in_r1(self, use_records):
        """Single-family detached dwelling should be R (by-right) in R1."""
        matches = [r for r in use_records
                   if "single-family" in r.use_name.lower()
                   and "detached" in r.use_name.lower()
                   and r.district == "R1"]
        assert len(matches) == 1
        assert matches[0].permission == "R"

    def test_single_family_not_permitted_in_b1(self, use_records):
        """Single-family detached dwelling should not be by-right in B1."""
        matches = [r for r in use_records
                   if "single-family" in r.use_name.lower()
                   and "detached" in r.use_name.lower()
                   and r.district == "B1"]
        assert len(matches) == 1
        assert matches[0].permission != "R"

    def test_adult_foster_care_conditional_in_r3(self, use_records):
        """Adult foster care facility should be conditional (C) in R3."""
        matches = [r for r in use_records
                   if "adult foster care" in r.use_name.lower()
                   and r.district == "R3"]
        assert len(matches) >= 1
        assert matches[0].permission == "C"

    def test_no_empty_use_names(self, use_records):
        """Every record should have a non-empty use name."""
        empty = [r for r in use_records if not r.use_name.strip()]
        assert len(empty) == 0

    def test_valid_permission_codes(self, use_records):
        """Permission codes should be R, C, C/R, R/C, L, or —."""
        valid = {"R", "C", "C/R", "R/C", "L", "—"}
        invalid = [r for r in use_records if r.permission not in valid]
        # Allow a small number of edge cases (footnote markers, etc.)
        assert len(invalid) < len(use_records) * 0.05, (
            f"Too many invalid permissions: {len(invalid)} of {len(use_records)}. "
            f"Examples: {[r.permission for r in invalid[:5]]}"
        )

    def test_unique_uses_count(self, use_records):
        """Should have 200+ unique specific land use names."""
        uses = set(r.use_name for r in use_records)
        assert len(uses) >= 200


# ──────────────────────────────────────────────
# Article XIII — Dimensional Standards
# ──────────────────────────────────────────────

class TestArticleXIIIDimensionalStandards:
    """Verify dimensional-standards parsing against known lot size data."""

    @pytest.fixture(scope="class")
    def dim_records(self):
        from strongtowns_detroit.zoning.dimensional import extract_all_dimensional_standards
        return extract_all_dimensional_standards(ARTICLE_XIII)

    def test_record_count(self, dim_records):
        # 32 tables × ~10 data rows × ~8 standards ≈ hundreds of records
        assert len(dim_records) > 500

    def test_standard_names_include_lot_area(self, dim_records):
        names = set(r.standard_name for r in dim_records)
        area_names = [n for n in names if "area" in n.lower()]
        assert len(area_names) >= 1, f"No lot-area standard found. Names: {names}"

    def test_standard_names_include_setbacks(self, dim_records):
        names = set(r.standard_name for r in dim_records)
        setback_names = [n for n in names if "setback" in n.lower()]
        assert len(setback_names) >= 1

    def test_single_family_lot_area_5000(self, dim_records):
        """R1 single-family dwellings should have 5,000 sq ft minimum lot area."""
        area_records = [r for r in dim_records
                        if "single-family" in r.district.lower()
                        and "area" in r.standard_name.lower()]
        # At least one table should report 5,000
        values = [r.value for r in area_records]
        assert any("5,000" in v or "5000" in v for v in values), (
            f"Expected 5,000 sqft for single-family. Got: {values[:5]}"
        )

    def test_lot_width_values_present(self, dim_records):
        """Should have width standards."""
        width_records = [r for r in dim_records if "width" in r.standard_name.lower()]
        assert len(width_records) > 0

    def test_cross_reference_lot_sizes(self, dim_records, lot_size_restrictions):
        """Cross-reference parsed lot areas with ground-truth JSON.

        The ground-truth says R1-R6 all have 5,000 sqft minimums.  We verify
        that the parser finds 5,000 in lot-area records for single-family
        uses (which appear in the R1-R6 district tables).
        """
        area_records = [r for r in dim_records
                        if "area" in r.standard_name.lower()
                        and "single-family" in r.district.lower()]
        found_values = {r.value.replace(",", "").strip() for r in area_records}
        # 5000 should appear (from R1 through R6 district tables)
        assert "5000" in found_values or "5,000" in found_values, (
            f"Expected 5000 in lot area values. Found: {found_values}"
        )


# ──────────────────────────────────────────────
# Article XVI — Definitions
# ──────────────────────────────────────────────

class TestArticleXVIDefinitions:
    """Verify definition parsing against known zoning terms."""

    @pytest.fixture(scope="class")
    def definitions(self):
        from strongtowns_detroit.zoning.definitions import extract_all_definitions
        return extract_all_definitions(ARTICLE_XVI)

    def test_definition_count(self, definitions):
        """Article XVI should have 400+ definitions."""
        assert len(definitions) >= 400

    def test_known_terms_present(self, definitions):
        """Common zoning terms should appear."""
        terms = {d.term.lower() for d in definitions}
        for expected in ["lot", "setback", "dwelling"]:
            matches = [t for t in terms if expected in t]
            assert len(matches) >= 1, f"Expected term containing '{expected}' not found"

    def test_no_empty_terms(self, definitions):
        empty = [d for d in definitions if not d.term.strip()]
        assert len(empty) == 0

    def test_most_have_definitions(self, definitions):
        """Most entries should have non-empty definition text."""
        with_def = [d for d in definitions if d.definition.strip()]
        assert len(with_def) >= len(definitions) * 0.9


# ──────────────────────────────────────────────
# Appendix A — Use Category Assignments
# ──────────────────────────────────────────────

class TestAppendixADefinitions:
    """Verify Appendix A use-category assignment parsing."""

    @pytest.fixture(scope="class")
    def definitions(self):
        from strongtowns_detroit.zoning.definitions import extract_all_definitions
        return extract_all_definitions(APPENDIX_A)

    def test_definition_count(self, definitions):
        """Appendix A should have substantial number of entries."""
        assert len(definitions) >= 100

    def test_use_categories_present(self, definitions):
        """Should contain common use category assignments."""
        all_text = " ".join(d.definition.lower() for d in definitions)
        assert "manufacturing" in all_text or "retail" in all_text


# ──────────────────────────────────────────────
# Document Structure
# ──────────────────────────────────────────────

class TestDocumentStructure:
    """Verify section hierarchy parsing against known article structures."""

    def test_article_xii_structure(self):
        from strongtowns_detroit.zoning.document import parse_document, walk_sections

        sections = parse_document(ARTICLE_XII)
        all_nodes = list(walk_sections(sections))

        # Should have a meaningful number of sections
        assert len(all_nodes) >= 10

        # Top level should be Article XII
        assert len(sections) >= 1
        assert "XII" in sections[0].title or "USE" in sections[0].title.upper()

    def test_article_xiii_structure(self):
        from strongtowns_detroit.zoning.document import parse_document, walk_sections

        sections = parse_document(ARTICLE_XIII)
        all_nodes = list(walk_sections(sections))

        assert len(all_nodes) >= 5
        assert "XIII" in sections[0].title or "DIMENSIONAL" in sections[0].title.upper()

    def test_article_xii_tables_attached(self):
        """Tables should be attached to section nodes."""
        from strongtowns_detroit.zoning.document import parse_document, walk_sections

        sections = parse_document(ARTICLE_XII)
        tables_found = sum(len(s.tables) for s in walk_sections(sections))
        # Article XII has 49 tables
        assert tables_found >= 40

    def test_article_xvi_sections_with_content(self):
        from strongtowns_detroit.zoning.document import parse_document, walk_sections

        sections = parse_document(ARTICLE_XVI)
        with_content = [s for s in walk_sections(sections) if s.content]
        assert len(with_content) >= 1


# ──────────────────────────────────────────────
# Full Orchestrator
# ──────────────────────────────────────────────

class TestOrchestrator:
    """Integration test for the full parse_ordinance() pipeline."""

    def test_parse_all_articles(self):
        from strongtowns_detroit.zoning.ordinance import parse_ordinance

        data = parse_ordinance(RESOURCES)

        assert len(data["sections"]) > 0, "No sections parsed"
        assert len(data["use_permissions"]) > 5000, "Too few use permissions"
        assert len(data["dimensional_standards"]) > 500, "Too few dimensional standards"
        assert len(data["definitions"]) > 400, "Too few definitions"

    def test_export_round_trip(self, tmp_path):
        """Export to JSON and verify it's valid."""
        from strongtowns_detroit.zoning.ordinance import parse_ordinance, export_to_json
        import json

        data = parse_ordinance(RESOURCES)
        export_to_json(data, tmp_path)

        # Verify all files are valid JSON
        for name in ["use_permissions.json", "dimensional_standards.json",
                      "definitions.json", "sections.json"]:
            path = tmp_path / name
            assert path.exists(), f"Missing {name}"
            with open(path) as f:
                loaded = json.load(f)
            assert isinstance(loaded, list)
            assert len(loaded) > 0, f"Empty {name}"


# ──────────────────────────────────────────────
# Citation Extraction
# ──────────────────────────────────────────────

class TestCitationExtraction:
    """Verify citation extraction from real ordinance text."""

    @pytest.fixture(scope="class")
    def article_xii_sections(self):
        from strongtowns_detroit.zoning.document import parse_document
        return parse_document(ARTICLE_XII)

    @pytest.fixture(scope="class")
    def article_xiv_sections(self):
        from strongtowns_detroit.zoning.document import parse_document
        return parse_document(
            RESOURCES / "ARTICLE_XIV.___DEVELOPMENT_STANDARDS.docx"
        )

    def test_article_xii_has_section_citations(self, article_xii_sections):
        """Article XII should contain many internal section cross-references."""
        from strongtowns_detroit.zoning.citations import extract_citations
        from strongtowns_detroit.zoning.document import walk_sections
        from strongtowns_detroit.zoning.models import CitationType

        all_cits = []
        for node in walk_sections(article_xii_sections):
            text = " ".join(node.content)
            all_cits.extend(extract_citations(text, source_section=node.number))

        section_cits = [c for c in all_cits if c.citation_type == CitationType.SECTION]
        # Article XII has hundreds of Section 50-XX-YYY references
        assert len(section_cits) > 100, (
            f"Expected 100+ section citations, found {len(section_cits)}"
        )

    def test_article_xii_has_article_references(self, article_xii_sections):
        """Article XII references other articles (e.g., Article XIII, XIV)."""
        from strongtowns_detroit.zoning.citations import extract_citations
        from strongtowns_detroit.zoning.document import walk_sections
        from strongtowns_detroit.zoning.models import CitationType

        all_cits = []
        for node in walk_sections(article_xii_sections):
            text = " ".join(node.content)
            all_cits.extend(extract_citations(text, source_section=node.number))

        article_cits = [c for c in all_cits if c.citation_type == CitationType.ARTICLE]
        assert len(article_cits) > 10, (
            f"Expected 10+ article references, found {len(article_cits)}"
        )

    def test_article_xiv_has_mcl_references(self, article_xiv_sections):
        """Article XIV (Development Standards) should cite Michigan Compiled Laws."""
        from strongtowns_detroit.zoning.citations import extract_citations
        from strongtowns_detroit.zoning.document import walk_sections
        from strongtowns_detroit.zoning.models import CitationType

        all_cits = []
        for node in walk_sections(article_xiv_sections):
            text = " ".join(node.content)
            all_cits.extend(extract_citations(text, source_section=node.number))

        mcl_cits = [c for c in all_cits if c.citation_type == CitationType.MCL]
        assert len(mcl_cits) >= 5, (
            f"Expected 5+ MCL citations in Art XIV, found {len(mcl_cits)}"
        )

    def test_citation_types_present(self, article_xii_sections):
        """Verify that multiple citation types are extracted from real text."""
        from strongtowns_detroit.zoning.citations import extract_citations
        from strongtowns_detroit.zoning.document import walk_sections
        from strongtowns_detroit.zoning.models import CitationType

        type_counts: Counter = Counter()
        for node in walk_sections(article_xii_sections):
            text = " ".join(node.content)
            for cit in extract_citations(text, source_section=node.number):
                type_counts[cit.citation_type] += 1

        # Article XII should have at least section refs and article refs
        assert CitationType.SECTION in type_counts
        assert CitationType.ARTICLE in type_counts


# ──────────────────────────────────────────────
# Citation Graph
# ──────────────────────────────────────────────

class TestCitationGraph:
    """Verify citation graph construction from real documents."""

    @pytest.fixture(scope="class")
    def full_graph(self):
        """Build a citation graph from all available articles."""
        from strongtowns_detroit.zoning.citations import build_citation_graph_from_docx
        docx_files = sorted(RESOURCES.glob("*.docx"))
        return build_citation_graph_from_docx(docx_files, resolve_hierarchical=False)

    @pytest.fixture(scope="class")
    def resolved_graph(self):
        """Build a citation graph with hierarchical resolution enabled."""
        from strongtowns_detroit.zoning.citations import build_citation_graph_from_docx
        docx_files = sorted(RESOURCES.glob("*.docx"))
        return build_citation_graph_from_docx(docx_files, resolve_hierarchical=True)

    def test_graph_has_nodes(self, full_graph):
        """Graph should have hundreds of section nodes."""
        assert len(full_graph.nodes) > 100

    def test_graph_has_edges(self, full_graph):
        """Graph should have hundreds of citation edges."""
        assert len(full_graph.edges) > 500

    def test_graph_has_internal_and_external_nodes(self, full_graph):
        """Graph should contain both internal section nodes and external refs."""
        assert len(full_graph.internal_nodes) > 50
        assert len(full_graph.external_nodes) > 5

    def test_external_nodes_include_mcl(self, full_graph):
        """External nodes should include MCL references."""
        mcl_nodes = [n for n in full_graph.external_nodes if n.startswith("mcl:")]
        assert len(mcl_nodes) >= 1

    def test_most_cited_section_is_reasonable(self, full_graph):
        """The most-cited section should be a well-known cross-reference target."""
        from strongtowns_detroit.zoning.models import CitationType

        target_counts: Counter = Counter()
        for edge in full_graph.edges:
            if edge.citation_type == CitationType.SECTION:
                target_counts[edge.target] += 1

        if target_counts:
            most_cited, count = target_counts.most_common(1)[0]
            # The most-cited section should have substantial citations
            assert count >= 10, (
                f"Most-cited section {most_cited} has only {count} citations"
            )
            # It should look like a valid section number
            assert most_cited.startswith("50-")

    def test_resolved_graph_has_more_edges(self, full_graph, resolved_graph):
        """Hierarchical resolution should expand article refs into more edges."""
        # The resolved graph should have at least as many edges
        assert len(resolved_graph.edges) >= len(full_graph.edges)

    def test_cross_article_citations_exist(self, full_graph):
        """Sections in one article should cite sections in other articles."""
        cross_article = []
        for edge in full_graph.edges:
            src_parts = edge.source_section.split("-")
            tgt_parts = edge.target.split("-")
            if (len(src_parts) >= 2 and len(tgt_parts) >= 2
                    and src_parts[1] != tgt_parts[1]
                    and tgt_parts[0] == "50"):
                cross_article.append(edge)
        assert len(cross_article) > 50, (
            f"Expected 50+ cross-article citations, found {len(cross_article)}"
        )
