import json

from audit_legal_ir_coverage import main
from strongtowns_detroit.zoning.legal_ir import LegalProvision, MunicodeSpan
from strongtowns_detroit.zoning.legal_ir_coverage import aggregate_coverage


SNAPSHOT = "test-snapshot"
DOCUMENT = "ARTICLE_TEST.municode.json"


def corpus():
    return {
        "canonicalSource": {"snapshot": SNAPSHOT},
        "documents": [{
            "document": DOCUMENT,
            "blocks": [{
                "type": "paragraph", "sourceIndex": 0, "municodeNodeId": "n1",
                "section": "50-1-1", "text": "Minimum area is 5,000 feet.  ",
            }, {
                "type": "paragraph", "sourceIndex": 1, "municodeNodeId": "n2",
                "section": "50-1-2", "text": "Maximum height is 35 feet.",
            }],
        }],
    }


def provision(source_index, text, start, end, provision_id, effect="minimum"):
    span = MunicodeSpan.cite(
        snapshot=SNAPSHOT, document=DOCUMENT, node_id=f"n{source_index + 1}",
        source_index=source_index, section=f"50-1-{source_index + 1}",
        text=text, start=start, end=end,
    )
    return LegalProvision(
        id=provision_id, subject={"district": ["R1"]},
        effect={"type": effect}, sources=(span,),
        review={"status": "verified", "disposition": "operative", "executionStatus": "executable"},
    )


def write_ledger(directory, provisions, status="in_progress"):
    directory.mkdir()
    payload = {
        "schemaVersion": "detroit-legal-ir-v1", "document": DOCUMENT,
        "coverageStatus": status,
        "provisions": [item.to_dict() for item in provisions],
    }
    (directory / "article-test.json").write_text(json.dumps(payload), encoding="utf-8")


def test_reports_block_and_character_coverage_counts(tmp_path):
    text = corpus()["documents"][0]["blocks"][0]["text"]
    first = provision(0, text, 0, 20, "p1")
    second = provision(0, text, 16, 27, "p2", "measurement")
    ledgers = tmp_path / "ledgers"
    write_ledger(ledgers, [first, second])

    report = aggregate_coverage(corpus(), ledgers)
    block = report["blocks"][0]
    atom = block["atoms"][0]
    assert block["disposition"] == "overlapping"
    assert atom["citedRanges"] == [[0, 27]]
    assert atom["overlappingRanges"] == [[16, 20]]
    assert atom["gaps"] == [{"start": 27, "end": 29, "text": "  ", "kind": "whitespace"}]
    assert report["counts"]["effects"] == {"measurement": 1, "minimum": 1}
    assert report["counts"]["dispositions"] == {"operative": 2}
    assert report["counts"]["executionStatuses"] == {"executable": 2}
    assert report["counts"]["blocks"] == {"cited": 0, "uncited": 1, "overlapping": 1}


def test_complete_article_fails_for_substantive_character_gap(tmp_path):
    source = corpus()
    text = source["documents"][0]["blocks"][0]["text"]
    partial = provision(0, text, text.index("5,000"), text.index("feet") + 4, "token-only")
    ledgers = tmp_path / "ledgers"
    write_ledger(ledgers, [partial], status="complete")

    report = aggregate_coverage(source, ledgers)
    assert not report["ok"]
    assert any(item["sourceIndex"] == 0 for item in report["completeArticleFailures"])
    assert any(item["sourceIndex"] == 1 for item in report["completeArticleFailures"])


def test_complete_article_accepts_only_whitespace_gaps_and_cli_returns_success(tmp_path):
    source = corpus()
    blocks = source["documents"][0]["blocks"]
    provisions = [
        provision(0, blocks[0]["text"], 0, len(blocks[0]["text"].rstrip()), "whole-1"),
        provision(1, blocks[1]["text"], 0, len(blocks[1]["text"]), "whole-2", "maximum"),
    ]
    ledgers = tmp_path / "ledgers"
    write_ledger(ledgers, provisions, status="complete")
    corpus_path = tmp_path / "corpus.json"
    output = tmp_path / "coverage.json"
    corpus_path.write_text(json.dumps(source), encoding="utf-8")

    assert main(["--corpus", str(corpus_path), "--ledgers", str(ledgers), "--output", str(output)]) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["ok"]
    assert report["completeArticleFailures"] == []
