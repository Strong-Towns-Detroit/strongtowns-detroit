from pathlib import Path

from strongtowns_detroit.zoning.source_model import compile_source_corpus


def test_full_corpus_preserves_documents_sections_and_tables():
    corpus = compile_source_corpus(Path("resources"))
    assert len(corpus["documents"]) == 18
    assert "50-13-1" in corpus["sectionIndex"]
    assert "50-16-382" in corpus["sectionIndex"]
    assert sum(
        block["type"] == "table"
        for document in corpus["documents"]
        for block in document["blocks"]
    ) == 224


def test_article_xiii_tables_keep_active_section_provenance():
    corpus = compile_source_corpus(Path("resources"))
    article = next(
        item for item in corpus["documents"]
        if item["document"].startswith("ARTICLE_XIII")
    )
    tables = [block for block in article["blocks"] if block["type"] == "table"]
    assert tables[0]["section"] == "50-13-2"
    assert tables[1]["section"] == "50-13-3"
