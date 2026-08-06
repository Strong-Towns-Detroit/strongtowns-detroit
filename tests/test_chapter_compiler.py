from pathlib import Path

from strongtowns_detroit.zoning.chapter_compiler import compile_chapter_package
from strongtowns_detroit.zoning.detroit_code import build_detroit_code
from strongtowns_detroit.zoning.detroit_permissions import add_structural_permissions
from strongtowns_detroit.zoning.detroit_lexicon import add_structural_lexicon
from strongtowns_detroit.zoning.detroit_dimensions import add_structural_dimensions
from strongtowns_detroit.zoning.detroit_text_candidates import add_text_candidates
from strongtowns_detroit.zoning.detroit_formulas import add_side_setback_formulas
from strongtowns_detroit.zoning.source_model import compile_source_corpus

ROOT = Path(__file__).resolve().parents[1]


def package():
    source = compile_source_corpus(ROOT / "resources")
    builder = build_detroit_code()
    add_structural_permissions(builder, source)
    add_structural_lexicon(builder, source)
    add_structural_dimensions(builder, source)
    add_side_setback_formulas(builder, source)
    add_text_candidates(builder, source)
    executable = builder.compile()
    return source, executable, compile_chapter_package(source, executable)


def test_every_source_block_is_accounted_for_once():
    source, _, chapter = package()
    source_count = sum(len(document["blocks"]) for document in source["documents"])
    represented = sum(
        len(section["provisions"]) for section in chapter["sections"]
    ) + len(chapter["unsectionedBlocks"])
    assert represented == source_count == chapter["coverage"]["sourceBlocks"]


def test_every_numbered_section_has_review_status_and_provisions():
    _, _, chapter = package()
    assert len(chapter["sections"]) == 1801
    assert all(section["provisions"] for section in chapter["sections"])
    assert all(section["review"]["status"] for section in chapter["sections"])


def test_all_reviewed_rules_are_linked_back_to_source_sections():
    _, executable, chapter = package()
    assert chapter["coverage"]["executableRules"] == len(executable["rules"])
    assert chapter["coverage"]["verifiedExecutableRules"] == 66
    assert chapter["coverage"]["structuralDimensionRules"] == 730
    assert chapter["coverage"]["reviewedRulesWithoutSourceSection"] == []
    assert chapter["coverage"]["structuralPermissions"] == 7565
    assert chapter["coverage"]["structuralPermissionsWithoutSourceSection"] == []
    assert chapter["coverage"]["structuralDefinitions"] == 467
    assert chapter["coverage"]["structuralDefinitionsWithoutSourceSection"] == []
    assert chapter["coverage"]["structuralUseAssignments"] == 478
    assert chapter["coverage"]["machineClassifiedProvisions"] > 3000
    assert chapter["coverage"]["machineClassifiedProvisionsWithoutSourceSection"] == []
    assert chapter["coverage"]["formulas"] == 2
    assert chapter["coverage"]["formulasWithoutSourceSection"] == []
    assert chapter["coverage"]["computedRules"] == 80
    assert chapter["coverage"]["computedRulesWithoutSourceSection"] == []


def test_context_prevents_map_tables_becoming_dimensional_rules():
    _, _, chapter = package()
    article_17_classes = {
        cls
        for section in chapter["sections"] if section["article"] == 17
        for provision in section["provisions"] for cls in provision["classes"]
    }
    assert "map" in article_17_classes
    assert "dimensional_or_intensity_table" not in article_17_classes
