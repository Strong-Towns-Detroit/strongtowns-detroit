#!/usr/bin/env python3
"""Create a lossless, versioned snapshot of codified Detroit Chapter 50.

Raw Municode response bytes are retained without JSON reserialization. A
manifest records request parameters, response hashes, product/job metadata,
and all externally referenced assets found in the article HTML. This snapshot
is the canonical upstream source; DOCX and zoning DSL artifacts are derived.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

API = "https://api.municode.com"
LIBRARY = "https://library.municode.com"


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")


class Snapshot:
    def __init__(self, output: Path):
        self.output = output
        self.raw = output / "raw"
        self.assets = output / "assets"
        self.raw.mkdir(parents=True, exist_ok=True)
        self.assets.mkdir(parents=True, exist_ok=True)
        self.records: list[dict[str, Any]] = []
        self.client = httpx.Client(
            timeout=120.0,
            follow_redirects=True,
            headers={"Accept": "application/json", "User-Agent": "strongtowns-detroit-zoning-audit/1"},
        )

    def close(self) -> None:
        self.client.close()

    def get_json(self, name: str, path: str, **params: Any) -> Any:
        url = f"{API}{path}"
        response = self.client.get(url, params=params)
        response.raise_for_status()
        payload = response.content
        target = self.raw / f"{name}.json"
        target.write_bytes(payload)
        self.records.append({
            "name": name,
            "kind": "municode_api_response",
            "requestUrl": str(response.request.url),
            "status": response.status_code,
            "contentType": response.headers.get("content-type"),
            "etag": response.headers.get("etag"),
            "lastModified": response.headers.get("last-modified"),
            "bytes": len(payload),
            "sha256": digest(payload),
            "path": str(target.relative_to(self.output)),
        })
        return response.json()

    def get_asset(self, url: str) -> None:
        response = self.client.get(url)
        response.raise_for_status()
        payload = response.content
        parsed = urlparse(str(response.url))
        filename = safe_name(Path(parsed.path).name or digest(url.encode())[:16])
        target = self.assets / filename
        if target.exists() and target.read_bytes() != payload:
            target = self.assets / f"{target.stem}_{digest(payload)[:12]}{target.suffix}"
        target.write_bytes(payload)
        self.records.append({
            "name": f"asset:{url}",
            "kind": "referenced_asset",
            "requestUrl": url,
            "resolvedUrl": str(response.url),
            "status": response.status_code,
            "contentType": response.headers.get("content-type"),
            "etag": response.headers.get("etag"),
            "lastModified": response.headers.get("last-modified"),
            "bytes": len(payload),
            "sha256": digest(payload),
            "path": str(target.relative_to(self.output)),
        })


def html_asset_urls(payload: Any) -> set[str]:
    urls: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in {"Content", "TitleHtml"} and isinstance(value, str):
                # Hyperlink targets are part of the captured HTML, not binary
                # dependencies. Mirroring every href would crawl the library.
                for match in re.finditer(r"\bsrc=[\"']([^\"']+)[\"']", value, re.I):
                    candidate = match.group(1)
                    if candidate.startswith(("data:", "#", "javascript:")):
                        continue
                    urls.add(urljoin(LIBRARY, candidate))
            else:
                urls.update(html_asset_urls(value))
    elif isinstance(payload, list):
        for item in payload:
            urls.update(html_asset_urls(item))
    return urls


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=Path("resources/municode"))
    parser.add_argument("--snapshot-name", help="Defaults to product update date and job ID")
    args = parser.parse_args()

    # Resolve version metadata before choosing the immutable snapshot directory.
    with httpx.Client(timeout=120.0, headers={"Accept": "application/json"}) as client:
        city = client.get(f"{API}/Clients/name", params={"clientName": "Detroit", "stateAbbr": "MI"})
        city.raise_for_status()
        city_data = city.json()
        content = client.get(f"{API}/ClientContent/{city_data['ClientID']}")
        content.raise_for_status()
        product = next(x for x in content.json()["codes"] if "code" in x["productName"].lower())
        job_response = client.get(f"{API}/Jobs/latest/{product['productId']}")
        job_response.raise_for_status()
        job = job_response.json()
    update_date = product["latestUpdatedDate"].split("T", 1)[0]
    snapshot_name = args.snapshot_name or f"{update_date}_job-{job['Id']}"
    output = args.output_root / snapshot_name
    if (output / "manifest.json").exists():
        raise SystemExit(f"snapshot already exists: {output}")

    snap = Snapshot(output)
    try:
        city_data = snap.get_json("client", "/Clients/name", clientName="Detroit", stateAbbr="MI")
        client_content = snap.get_json("client-content", f"/ClientContent/{city_data['ClientID']}")
        product = next(x for x in client_content["codes"] if "code" in x["productName"].lower())
        job = snap.get_json("latest-job", f"/Jobs/latest/{product['productId']}")
        common = {"jobId": job["Id"], "productId": product["productId"]}
        root = snap.get_json("toc-root", "/codesToc/children", nodeId=product["productId"], **common)
        container = next(x for x in root if x["Id"] == "COCH50")
        container_children = snap.get_json(
            "toc-chapter-container", "/codesToc/children", nodeId=container["Id"], **common
        )
        chapter = next(x for x in container_children if "Chapter 50" in x["Heading"])
        articles = snap.get_json(
            "toc-chapter-50", "/codesToc/children", nodeId=chapter["Id"], **common
        )
        assets: set[str] = set()
        article_manifest = []
        for index, article in enumerate(articles, 1):
            payload = snap.get_json(
                f"article-{index:02d}-{safe_name(article['Id'])}",
                "/CodesContent",
                nodeId=article["Id"],
                **common,
            )
            assets.update(html_asset_urls(payload))
            article_manifest.append({
                "id": article["Id"],
                "heading": article["Heading"],
                "docOrderId": article["DocOrderId"],
                "docs": len(payload.get("Docs", [])),
            })
        asset_errors = []
        for url in sorted(assets):
            try:
                snap.get_asset(url)
            except httpx.HTTPError as error:
                asset_errors.append({"url": url, "error": str(error)})
        manifest = {
            "schemaVersion": "municode-chapter-snapshot-v1",
            "capturedAt": datetime.now(timezone.utc).isoformat(),
            "municipality": "Detroit",
            "chapter": "50",
            "canonicalScope": "Municode currently codified publication; OrdBank excluded",
            "clientId": city_data["ClientID"],
            "productId": product["productId"],
            "publicationId": product.get("publicationId"),
            "latestUpdatedDate": product.get("latestUpdatedDate"),
            "pendingOrdinanceCountReported": product.get("newOrdCount"),
            "jobId": job["Id"],
            "jobName": job.get("Name"),
            "chapterNodeId": chapter["Id"],
            "articles": article_manifest,
            "referencedAssetUrls": sorted(assets),
            "assetErrors": asset_errors,
            "files": snap.records,
        }
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        print(json.dumps({
            "snapshot": str(output),
            "articles": len(article_manifest),
            "articleDocs": sum(x["docs"] for x in article_manifest),
            "assets": len(assets),
            "assetErrors": len(asset_errors),
            "files": len(snap.records),
        }, indent=2))
    finally:
        snap.close()


if __name__ == "__main__":
    main()
