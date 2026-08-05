#!/usr/bin/env python3
"""Audit the local Detroit Chapter 50 DOCX corpus against Municode.

This audit deliberately separates two questions:

1. Does the local corpus contain every article and numbered section in the
   currently codified Municode Chapter 50 publication?
2. How closely does the normalized local text for each numbered section match
   Municode's HTML representation?

Pending OrdBank ordinances are not silently folded into the codified corpus.
They require a separate amendment audit because some may concern other chapters
or may already be reflected in the latest codification.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import httpx
from lxml import html

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from strongtowns_detroit.zoning.source_model import compile_source_corpus  # noqa: E402


API = "https://api.municode.com"
SECTION_RE = re.compile(r"\b(?:Sec\.?\s*)?(50-\d{1,2}-\d{1,4}(?:\.\d+)*)\b", re.I)
ARTICLE_RE = re.compile(r"\bARTICLE\s+(XVII|XVI|XV|XIV|XIII|XII|XI|IX|VIII|VII|VI|IV|III|II|X|V|I)\b")


def request(client: httpx.Client, path: str, **params: Any) -> Any:
    response = client.get(f"{API}{path}", params=params)
    response.raise_for_status()
    return response.json()


def normalize(value: str) -> str:
    value = value.replace("\u2018", "'").replace("\u2019", "'")
    value = value.replace("\u201c", '"').replace("\u201d", '"')
    value = value.replace("\u2013", "-").replace("\u2014", "-")
    value = value.replace("\u00a0", " ")
    return re.sub(r"\s+", " ", value).strip().lower()


def html_text(value: str) -> str:
    if not value:
        return ""
    return html.fromstring(f"<div>{value}</div>").text_content()


def local_sections(resources: Path) -> tuple[dict[str, str], dict[str, str], dict[str, Any]]:
    corpus = compile_source_corpus(resources)
    text: dict[str, list[str]] = defaultdict(list)
    titles: dict[str, str] = {}
    for document in corpus["documents"]:
        for block in document["blocks"]:
            section = block.get("section")
            if not section:
                continue
            if block["type"] == "paragraph":
                paragraph = block["text"]
                match = SECTION_RE.search(paragraph)
                if match and match.group(1).lower() == section.lower():
                    titles.setdefault(section, paragraph)
                text[section].append(paragraph)
            else:
                text[section].extend(cell for row in block["rows"] for cell in row if cell)
    return ({key: normalize(" ".join(value)) for key, value in text.items()}, titles, corpus)


def find_chapter_articles(client: httpx.Client, product_id: int, job_id: int) -> list[dict[str, Any]]:
    roots = request(
        client, "/codesToc/children", jobId=job_id, productId=product_id, nodeId=product_id
    )
    chapter_container = next(node for node in roots if node["Id"] == "COCH50")
    chapter = request(
        client,
        "/codesToc/children",
        jobId=job_id,
        productId=product_id,
        nodeId=chapter_container["Id"],
    )
    zoning = next(node for node in chapter if "Chapter 50" in node["Heading"])
    return request(
        client,
        "/codesToc/children",
        jobId=job_id,
        productId=product_id,
        nodeId=zoning["Id"],
    )


def municode_sections(
    client: httpx.Client, articles: list[dict[str, Any]], product_id: int, job_id: int
) -> tuple[dict[str, str], dict[str, str], list[dict[str, Any]]]:
    text: dict[str, str] = {}
    titles: dict[str, str] = {}
    article_summary = []
    for article in articles:
        payload = request(
            client,
            "/CodesContent",
            jobId=job_id,
            productId=product_id,
            nodeId=article["Id"],
        )
        docs = payload.get("Docs", [])
        section_count = 0
        for doc in docs:
            match = SECTION_RE.search(doc.get("Title", ""))
            if not match:
                continue
            section = match.group(1)
            section_count += 1
            titles[section] = html_text(doc.get("TitleHtml") or doc.get("Title", ""))
            text[section] = normalize(
                " ".join((html_text(doc.get("TitleHtml", "")), html_text(doc.get("Content", ""))))
            )
        article_summary.append(
            {
                "id": article["Id"],
                "heading": article["Heading"],
                "docOrderId": article["DocOrderId"],
                "numberedSections": section_count,
            }
        )
    return text, titles, article_summary


def similarity(local: str, remote: str) -> float:
    if not local and not remote:
        return 1.0
    return round(SequenceMatcher(None, local, remote, autojunk=False).ratio(), 6)


def section_sort_key(value: str) -> tuple[int, ...]:
    return tuple(int(piece) for piece in re.findall(r"\d+", value))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resources", type=Path, default=ROOT / "resources")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "artifacts/zoning/municode_corpus_audit.json"
    )
    args = parser.parse_args()

    local_text, local_titles, corpus = local_sections(args.resources)
    with httpx.Client(timeout=120.0, headers={"Accept": "application/json"}) as client:
        city = request(client, "/Clients/name", clientName="Detroit", stateAbbr="MI")
        content = request(client, f"/ClientContent/{city['ClientID']}")
        product = next(item for item in content["codes"] if "code" in item["productName"].lower())
        job = request(client, f"/Jobs/latest/{product['productId']}")
        articles = find_chapter_articles(client, product["productId"], job["Id"])
        remote_text, remote_titles, article_summary = municode_sections(
            client, articles, product["productId"], job["Id"]
        )

    local_ids = set(local_text)
    remote_ids = set(remote_text)
    remote_reserved_ids = {
        section
        for section, title in remote_titles.items()
        if "reserved" in normalize(title)
    }
    remote_substantive_ids = remote_ids - remote_reserved_ids
    shared = sorted(local_ids & remote_substantive_ids, key=section_sort_key)
    comparisons = [
        {
            "section": section,
            "similarity": similarity(local_text[section], remote_text[section]),
            "localChars": len(local_text[section]),
            "municodeChars": len(remote_text[section]),
            "localTitle": local_titles.get(section),
            "municodeTitle": remote_titles.get(section),
        }
        for section in shared
    ]
    mismatch = [row for row in comparisons if row["similarity"] < 0.98]
    local_reserved_ids = local_ids & remote_reserved_ids
    local_substantive_ids = local_ids - remote_reserved_ids
    missing_substantive = remote_substantive_ids - local_substantive_ids
    extra_local = local_substantive_ids - remote_substantive_ids
    report = {
        "schemaVersion": "municode-corpus-audit-v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "scope": "Currently codified Detroit Chapter 50 only; pending OrdBank ordinances excluded",
        "municode": {
            "clientId": city["ClientID"],
            "productId": product["productId"],
            "productName": product["productName"],
            "latestUpdatedDate": product.get("latestUpdatedDate"),
            "pendingOrdinanceCountReported": product.get("newOrdCount"),
            "jobId": job["Id"],
            "jobName": job.get("Name"),
        },
        "local": {
            "documents": len(corpus["documents"]),
            "numberedSections": len(local_ids),
            "archiveBytes": sum(doc["archiveBytes"] for doc in corpus["documents"]),
        },
        "articles": article_summary,
        "coverage": {
            "municodeArticles": len(articles),
            "municodeNumberedNodes": len(remote_ids),
            "municodeReservedRangeNodes": len(remote_reserved_ids),
            "municodeSubstantiveSections": len(remote_substantive_ids),
            "localReservedRangeNodesIndexedAsSections": [
                {"section": section, "title": remote_titles[section]}
                for section in sorted(local_reserved_ids, key=section_sort_key)
            ],
            "sharedNumberedSections": len(shared),
            "reservedRangeNodesNotIndexedAsSections": [
                {"section": section, "title": remote_titles[section]}
                for section in sorted(remote_reserved_ids - local_ids, key=section_sort_key)
            ],
            "missingSubstantiveSectionsLocally": sorted(
                missing_substantive, key=section_sort_key
            ),
            "extraLocalSections": sorted(extra_local, key=section_sort_key),
            "substantiveSectionIndexComplete": not missing_substantive and not extra_local,
        },
        "textComparison": {
            "method": "normalized Unicode punctuation/whitespace SequenceMatcher over section title and content",
            "exactOrNearExactAt98Pct": len(comparisons) - len(mismatch),
            "below98Pct": len(mismatch),
            "minimumSimilarity": min((row["similarity"] for row in comparisons), default=None),
            "meanSimilarity": round(
                sum(row["similarity"] for row in comparisons) / len(comparisons), 6
            ) if comparisons else None,
            "below98PctSections": mismatch,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "documents": report["local"]["documents"],
        "articles": report["coverage"]["municodeArticles"],
        "localSections": len(local_ids),
        "municodeNodes": len(remote_ids),
        "municodeReservedRangeNodes": len(remote_reserved_ids),
        "municodeSubstantiveSections": len(remote_substantive_ids),
        "missingSubstantiveLocally": len(missing_substantive),
        "extraLocally": len(extra_local),
        "below98Pct": len(mismatch),
    }, indent=2))


if __name__ == "__main__":
    main()
