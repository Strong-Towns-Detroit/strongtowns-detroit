from strongtowns_detroit.zoning.legal_ir import (
    LegalProvision,
    MunicodeSpan,
    ReviewedProvisionLedger,
)
from strongtowns_detroit.zoning.source_span_review import article_atoms, render_review_page


def fixture():
    text = "This chapter applies throughout Detroit."
    cell = "Minimum 5,000 square feet"
    corpus = {
        "canonicalSource": {"snapshot": "snapshot"},
        "documents": [{
            "document": "ARTICLE_I.municode.json",
            "blocks": [
                {"type": "paragraph", "text": "Sec. 50-1-1. Scope.", "sourceIndex": 0,
                 "municodeNodeId": 10, "section": "50-1-1"},
                {"type": "paragraph", "text": text, "sourceIndex": 1,
                 "municodeNodeId": 10, "section": "50-1-1"},
                {"type": "table", "rows": [["Rule", cell]], "sourceIndex": 2,
                 "municodeNodeId": 11, "section": "50-1-2"},
            ],
        }],
    }
    phrase = "throughout Detroit"
    paragraph_span = MunicodeSpan.cite(
        snapshot="snapshot", document="ARTICLE_I.municode.json", node_id=10,
        source_index=1, section="50-1-1", text=text,
        start=text.index(phrase), end=text.index(phrase) + len(phrase),
    )
    table_quote = "5,000"
    table_span = MunicodeSpan.cite_table_cell(
        snapshot="snapshot", document="ARTICLE_I.municode.json", node_id=11,
        source_index=2, section="50-1-2", cell_text=cell, row=0, column=1,
        start=cell.index(table_quote), end=cell.index(table_quote) + len(table_quote),
    )
    ledger = ReviewedProvisionLedger((
        LegalProvision(
            id="scope", subject={"place": "Detroit"}, effect={"type": "applies"},
            sources=(paragraph_span,), review={"status": "verified", "disposition": "operative"},
        ),
        LegalProvision(
            id="minimum", subject={"district": "R1"},
            effect={"type": "minimum", "value": 5000}, sources=(table_span,),
            review={"status": "unreviewed", "disposition": "candidate"},
        ),
    ))
    return corpus, ledger


def test_atoms_follow_source_order_and_have_stable_keys():
    _, ledger = fixture()
    atoms = article_atoms(ledger)
    assert [atom.provision.id for atom in atoms] == ["scope", "minimum"]
    assert atoms[0].key == "scope#source-1"


def test_page_highlights_exact_paragraph_span_and_surrounding_node_context():
    corpus, ledger = fixture()
    page = render_review_page(corpus, ledger, selected="scope")
    assert "Sec. 50-1-1. Scope." in page
    assert "This chapter applies &lt;mark&gt;" not in page
    assert "applies <mark>throughout Detroit</mark>." in page
    assert "operative" in page
    assert "Previous" in page and "Next" in page


def test_page_highlights_only_selected_characters_in_table_cell():
    corpus, ledger = fixture()
    page = render_review_page(corpus, ledger, selected="minimum")
    assert "Minimum <mark>5,000</mark> square feet" in page
    assert 'class="selected-cell"' in page
    assert "candidate" in page


def test_page_embeds_deterministic_navigation_and_selection():
    corpus, ledger = fixture()
    page = render_review_page(corpus, ledger, selected=1)
    assert page.count('class="atom active"') == 1
    assert 'id="atom-minimum-source-1"' in page
    assert "ArrowLeft" in page and "ArrowRight" in page
