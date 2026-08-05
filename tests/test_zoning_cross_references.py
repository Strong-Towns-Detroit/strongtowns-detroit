from pathlib import Path

from strongtowns_detroit.zoning.citations import extract_citations
from strongtowns_detroit.zoning.cross_references import compile_cross_references
from strongtowns_detroit.zoning.source_model import compile_source_corpus

ROOT = Path(__file__).resolve().parents[1]


def graph():
    return compile_cross_references(compile_source_corpus(ROOT / "resources"))


def test_decimal_section_identity_and_citation_are_preserved():
    source = compile_source_corpus(ROOT / "resources")
    assert "50-12-131.1" in source["sectionIndex"]
    assert "50-12-295.1" in source["sectionIndex"]
    citation = extract_citations("See Section 50-12-295.1.")[0]
    assert citation.target == "50-12-295.1"


def test_reserved_range_targets_are_not_reported_missing():
    package = graph()
    edges = [edge for edge in package["edges"] if edge["target"] == "50-1-16"]
    assert edges
    assert {edge["resolution"] for edge in edges} == {"resolved_reserved_section"}


def test_apparent_source_errors_remain_visible():
    package = graph()
    assert "50-13-492" in package["coverage"]["missingInternalTargets"]
    assert "50-12-139" not in package["coverage"]["missingInternalTargets"]
