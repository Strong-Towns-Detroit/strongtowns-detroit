import json
from pathlib import Path

import pytest

from strongtowns_detroit.zoning.municode_source_model import (
    _expand_table,
    compile_municode_source_corpus,
    latest_snapshot,
    verify_snapshot,
)
from lxml import html


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = ROOT / "resources/municode"
HAS_SNAPSHOT = any(SNAPSHOT_ROOT.glob("*/manifest.json"))


def test_expands_html_rowspan_and_colspan():
    table = html.fromstring(
        "<table><tr><td rowspan='2'>A</td><td colspan='2'>B</td></tr>"
        "<tr><td>C</td><td>D</td></tr></table>"
    )
    assert _expand_table(table) == [["A", "B", "B"], ["A", "C", "D"]]


@pytest.mark.skipif(not HAS_SNAPSHOT, reason="Municode snapshot not available")
def test_snapshot_manifest_integrity():
    snapshot = latest_snapshot(SNAPSHOT_ROOT)
    manifest = verify_snapshot(snapshot)
    assert len(manifest["articles"]) == 18
    assert not manifest["assetErrors"]


@pytest.mark.skipif(not HAS_SNAPSHOT, reason="Municode snapshot not available")
def test_compiles_complete_current_chapter():
    source = compile_municode_source_corpus(latest_snapshot(SNAPSHOT_ROOT))
    assert source["schemaVersion"] == "ordinance-source-v3-municode"
    assert len(source["documents"]) == 18
    assert len(source["nodeIndex"]) == 2224
    assert len(source["sectionIndex"]) == 1982
    assert "50-1-1" in source["sectionIndex"]
    assert "50-16-463" in source["sectionIndex"]  # reserved-range node
    assert source["canonicalSource"]["jobId"] == 429936


@pytest.mark.skipif(not HAS_SNAPSHOT, reason="Municode snapshot not available")
def test_retains_raw_node_html_and_provenance():
    source = compile_municode_source_corpus(latest_snapshot(SNAPSHOT_ROOT))
    article = source["documents"][1]
    node = next(item for item in article["sourceNodes"] if item["section"] == "50-2-91")
    assert "<table" in node["contentHtml"]
    table = next(
        block for block in article["blocks"]
        if block["section"] == "50-2-91" and block["type"] == "table"
    )
    assert table["municodeNodeId"] == node["municodeNodeId"]
    assert table["rows"][0] == ["Advisory Committee", "Chairperson", "Members"]
